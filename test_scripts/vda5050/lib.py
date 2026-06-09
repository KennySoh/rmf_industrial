#!/usr/bin/env python3
"""lib.py — shared MQTT helper for the VDA5050 master test scripts.

Same style as ../simulation/lib.py: a single persistent paho-mqtt client over
the local broker (localhost:1883), with helpers to

  * publish a VDA5050 order straight to an AGV   (send_order — play the master)
  * fake a Scorpio CommandMessage to the master  (send_command — trigger the master)
  * wait on the AGV's /state feed                (wait_for_arrival)
  * tail topics                                  (watch)

Not run directly — imported by send_order.py, send_command.py, watch.py and the
demo_*.py scripts.
"""

import json
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

MQTT_HOST = "localhost"
MQTT_PORT = 1883
MAP_ID = "urn:ngsi-ld:Map:warehouse_os_setup"   # matches ../simulation/lib.py
MANUFACTURER = "Manufacturer"
NS = "ngsi-ld:default-context/"                 # NGSI-LD term prefix for CommandMessage

# Scorpio context broker (the REAL path the MAPF executor uses to reach the master).
SCORPIO_URL = "http://localhost:9090"           # container maps 9090:9090 to host
# Same @context Link the master + MAPF executor use; it does NOT define the
# command/waypoint terms, so Scorpio expands them to the default context — which
# is why the master reads them back as "ngsi-ld:default-context/<term>".
LD_LINK = ('https://smart-data-models.github.io/dataModel.AutonomousMobileRobot/'
           'StateMessage/examples/example-normalized.jsonld; '
           'rel="https://www.w3.org/ns/json-ld#context"; type="application/ld+json"')

# Marker grid -> VDA5050 metres (map frame); a waypoint "P<idx>" maps to (x, y).
# Same grid as ../simulation/lib.py (identical to ../simulation/ref/map.yaml).
MARKER_ORIGIN_X = -3080.0
MARKER_ORIGIN_Y = -4930.0
MARKER_STEP = 175.0
MARKERS_PER_ROW = 34

# Colors
R = "\033[0;31m"
G = "\033[0;32m"
Y = "\033[1;33m"
B = "\033[0;34m"
M = "\033[0;35m"
C = "\033[0;36m"
NC = "\033[0m"


def log(tag, msg, color=C):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{ts}][{tag:5s}]{NC} {msg}")


def now_iso():
    """Master parses '...T..:..:...000Z' — fractional seconds required."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def marker_to_vda(marker):
    """'P619' -> (x, y) in map-frame metres."""
    idx = int(str(marker).replace("P", ""))
    row = idx // MARKERS_PER_ROW
    col = idx % MARKERS_PER_ROW
    x = MARKER_ORIGIN_X + col * MARKER_STEP
    y = MARKER_ORIGIN_Y + row * MARKER_STEP
    return round(x / 100.0, 2), round(y / 100.0, 2)


class MQTTHelper:
    """Persistent connection to the broker.

    Use as a context manager:

        with MQTTHelper() as mqtt:
            mqtt.send_command("10", ["P123"])     # trigger the master
            mqtt.wait_for_arrival("10", "P123")   # watch the AGV drive there
    """

    def __init__(self, host=MQTT_HOST, port=MQTT_PORT, mfr=MANUFACTURER):
        self.host = host
        self.port = port
        self.mfr = mfr
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = lambda c, u, f, rc, p=None: log(
            "MQTT", f"Connected to {self.host}:{self.port}")

    # --- lifecycle ---------------------------------------------------------
    def connect(self):
        self.client.connect(self.host, self.port, 60)
        self.client.loop_start()
        time.sleep(1)
        return self

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.disconnect()
        return False

    # --- the master's OUTPUT: a VDA5050 order straight to the AGV -----------
    def send_order(self, serial, pcodes, theta=0.0, order_id=None, update_id=0,
                   zone_set_id="zone_A"):
        """Publish a VDA5050 order (one node per Pcode, with connecting edges).

        Multi-waypoint orders get VDA5050 sequence IDs (nodes 0,2,4,…;
        edges 1,3,5,…), exactly like a real master emits."""
        order_id = order_id or f"order_{int(time.time())}"
        nodes, edges, prev = [], [], None
        for seq, p in enumerate(pcodes):
            seq *= 2
            x, y = marker_to_vda(p)
            log("VDA", f"{p} -> x={x} y={y}  (seq {seq})", color=B)
            nodes.append({
                "nodeId": p, "sequenceId": seq, "released": True,
                "nodePosition": {"x": x, "y": y, "theta": theta, "mapId": MAP_ID},
                "actions": [],
            })
            if prev is not None:
                edges.append({
                    "edgeId": f"{prev}-{p}", "sequenceId": seq - 1, "released": True,
                    "startNodeId": prev, "endNodeId": p, "actions": [],
                })
            prev = p

        payload = {
            "headerId": 1,
            "timestamp": now_iso(),
            "version": "2.0.0",
            "manufacturer": self.mfr,
            "serialNumber": str(serial),
            "orderId": order_id,
            "orderUpdateId": update_id,
            "zoneSetId": zone_set_id,
            "nodes": nodes,
            "edges": edges,
        }
        topic = f"uagv/v2/{self.mfr}/{serial}/order"
        self.client.publish(topic, json.dumps(payload)).wait_for_publish(timeout=5)
        log("ORDER", f"-> {topic}  (orderId={order_id}, {len(pcodes)} node(s): {' '.join(pcodes)})",
            color=Y)

    # --- the master's INPUT: a faked Scorpio CommandMessage ----------------
    def send_command(self, serial, nodes, command="move_to", command_id=None,
                     update_id=0, topic="command_updates"):
        """Publish the NGSI-LD notification envelope the master converts to an order.

        The master looks each nodeId up in its own map for x,y — the positions
        here are placeholders, but the keys must exist."""
        command_id = command_id or f"cmd_{int(time.time())}"
        waypoints = [{
            "nodeId": n,
            f"{NS}point2D": {f"{NS}x": 0.0, f"{NS}y": 0.0},
            f"{NS}orientation2D": {f"{NS}theta": 0.0},
            "released": True,
            "sequenceId": i,
        } for i, n in enumerate(nodes)]

        payload = {"body": {"data": [{
            "id": f"urn:ngsi-ld:Robot:{self.mfr}:{serial}",
            "type": "CommandMessage",
            "commandId": {"value": command_id},
            "commandUpdateId": {"value": update_id},
            f"{NS}commandTime": {"value": now_iso()},
            f"{NS}command": {"value": command},
            f"{NS}waypoints": {"value": waypoints},
        }]}}
        self.client.publish(topic, json.dumps(payload)).wait_for_publish(timeout=5)
        log("CMD", f"-> {topic}  (commandId={command_id}, AGV={self.mfr}/{serial}, nodes: {' '.join(nodes)})",
            color=Y)

    # --- read the AGV's replies -------------------------------------------
    def wait_for_arrival(self, serial, goal, timeout=120):
        """Block until the AGV's /state reports lastNodeId==goal and not driving."""
        state_topic = f"uagv/v2/{self.mfr}/{serial}/state"
        arrived = threading.Event()

        def on_state(client, userdata, msg):
            try:
                state = json.loads(msg.payload.decode())
                if state.get("lastNodeId", "") == goal and not state.get("driving", True):
                    arrived.set()
            except Exception:
                pass

        self.client.subscribe(state_topic)
        self.client.message_callback_add(state_topic, on_state)
        log("WAIT", f"Waiting for AMR {serial} to reach {goal}...")
        try:
            remaining = timeout
            while not arrived.is_set() and remaining > 0:
                print(f"\r  AMR {serial}: waiting... ({timeout - remaining}s)",
                      end="", flush=True)
                arrived.wait(timeout=2)
                remaining -= 2
        finally:
            self.client.message_callback_remove(state_topic)
            self.client.unsubscribe(state_topic)
            print()

        if arrived.is_set():
            log("DONE", f"AMR {serial} arrived at {goal}!", color=G)
            return True
        log("FAIL", f"AMR {serial} timeout reaching {goal}", color=R)
        return False

    # --- passive listening -------------------------------------------------
    def watch(self, topic):
        """Print every message on <topic> until Ctrl-C."""
        self.client.on_message = lambda c, u, msg: print(
            f"{C}{msg.topic}{NC} {msg.payload.decode(errors='replace')}")
        self.client.subscribe(topic)
        log("WATCH", f"{topic}   (Ctrl-C to stop)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


class Scorpio:
    """Minimal NGSI-LD client for the Scorpio context broker.

    Mirrors vda5050_fiware's ScorpioAPI.send_entity_message: POST to create an
    entity, PATCH .../attrs to update it. Posting/patching a `CommandMessage`
    entity is EXACTLY how the MAPF executor drives the master — Scorpio then
    notifies the master over the `command_updates` MQTT topic.
    """

    def __init__(self, url=SCORPIO_URL, mfr=MANUFACTURER):
        self.url = url.rstrip("/")
        self.mfr = mfr

    def _entity_exists(self, entity_id):
        import requests
        r = requests.get(f"{self.url}/ngsi-ld/v1/entities/{entity_id}",
                         headers={"Accept": "application/ld+json",
                                  "Content-Type": "application/json"}, timeout=30)
        return r.status_code != 404

    def send_command(self, serial, nodes, command="move_to", command_id=None,
                     update_id=0):
        """Create/patch urn:ngsi-ld:CommandMessage:<mfr>:<serial> in Scorpio.

        nodes: list of map nodeIds. The master looks each up in its own map for
        x,y, so the positions here are placeholders."""
        import requests
        command_id = command_id or f"cmd_{int(time.time())}"
        entity_id = f"urn:ngsi-ld:CommandMessage:{self.mfr}:{serial}"
        waypoints = [{
            "nodeId": n,
            "point2D": {"x": 0.0, "y": 0.0},
            "orientation2D": {"theta": 0.0},
            "released": "true",          # to_json stores released as a JSON string
            "sequenceId": i,
        } for i, n in enumerate(nodes)]
        body = {
            "id": entity_id,
            "type": "CommandMessage",
            "commandTime": {"type": "Property", "value": now_iso()},
            "command": {"type": "Property", "value": command},
            "commandId": {"type": "Property", "value": command_id},
            "commandUpdateId": {"type": "Property", "value": update_id},
            "waypoints": {"type": "Property", "value": waypoints},
        }
        headers = {"Content-Type": "application/json", "Link": LD_LINK}
        if self._entity_exists(entity_id):
            ep = f"{self.url}/ngsi-ld/v1/entities/{entity_id}/attrs"
            r = requests.patch(ep, data=json.dumps(body), headers=headers, timeout=30)
        else:
            ep = f"{self.url}/ngsi-ld/v1/entities/"
            r = requests.post(ep, data=json.dumps(body), headers=headers, timeout=30)
        log("SCORPIO", f"{r.request.method} {entity_id} -> {r.status_code}  "
            f"(commandId={command_id}, nodes: {' '.join(nodes)})",
            color=G if r.ok else R)
        return r


if __name__ == "__main__":
    raise SystemExit("lib.py is a helper module — import it, don't run it.")
