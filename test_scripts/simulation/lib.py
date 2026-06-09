#!/usr/bin/env python3
"""lib.py — shared MQTT helper for the simulation scripts.

Modelled on test_conveyor_workflow.py: a single persistent paho-mqtt client,
subscribed up front, with a background thread buffering every status message —
so one-shot completion messages are never missed. All the other scripts build
on the `MQTTHelper` class here.

Broker is the local MQTT broker at localhost:1883 (the UE5 sim's broker).
Not run directly — imported by send_agv.py, send_device.py, demo_single_agv.py,
demo_single_agv_reset.py and watch.py.
"""

import json
import threading
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

MQTT_HOST = "localhost"
MQTT_PORT = 1883
MAP_ID = "urn:ngsi-ld:Map:warehouse_os_setup"
MANUFACTURER = "Manufacturer"

# Marker grid -> VDA5050 metres (map frame). A waypoint "P<idx>" maps to an
# (x, y) on a regular grid; raw x,y in the same frame can be sent directly.
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


def marker_to_vda(marker):
    """'P619' -> (x, y) in map-frame metres."""
    idx = int(str(marker).replace("P", ""))
    row = idx // MARKERS_PER_ROW
    col = idx % MARKERS_PER_ROW
    x = MARKER_ORIGIN_X + col * MARKER_STEP
    y = MARKER_ORIGIN_Y + row * MARKER_STEP
    return round(x / 100.0, 2), round(y / 100.0, 2)


class MQTTHelper:
    """Persistent connection to the sim broker.

    Use as a context manager:

        with MQTTHelper() as h:
            h.send_agv("10", "P123")        # drive AGV, block until arrival
            h.send_device("10", "liftrack") # send task, block until COMPLETED
    """

    def __init__(self, host=MQTT_HOST, port=MQTT_PORT):
        self.host = host
        self.port = port
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = lambda c, u, f, rc, p=None: log(
            "MQTT", f"Connected to {self.host}:{self.port}")
        self.client.on_message = self._on_message
        self.statuses = {}
        self.lock = threading.Lock()

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

    # --- status buffering --------------------------------------------------
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            asset_id = payload.get("asset_id", "")
            status = payload.get("status", "")
            with self.lock:
                self.statuses[asset_id] = {"status": status, "time": time.time()}
            log("MQTT", f"{asset_id} -> {status}")
        except Exception:
            pass

    def subscribe(self, asset_id):
        """Listen for an asset's task_status (call before sending its task)."""
        self.client.subscribe(f"asset/{asset_id}/task_status")

    # --- low-level publish (no wait) --------------------------------------
    def send_order(self, serial, node_id, x, y, theta=0.0):
        """Publish a VDA5050 order moving <serial> to (x, y) named <node_id>."""
        topic = f"uagv/v2/{MANUFACTURER}/{serial}/order"
        order = {
            "headerId": int(time.time()) % 10000,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "version": "2.0.0",
            "manufacturer": MANUFACTURER,
            "serialNumber": str(serial),
            "orderId": f"order-{uuid.uuid4()}",
            "orderUpdateId": 1,
            "nodes": [{
                "nodeId": node_id, "sequenceId": 0, "released": True,
                "nodePosition": {"x": x, "y": y, "theta": theta,
                                 "allowedDeviationXY": 0.5,
                                 "allowedDeviationTheta": 0.5, "mapId": MAP_ID},
                "actions": [],
            }],
            "edges": [],
        }
        self.client.publish(topic, json.dumps(order)).wait_for_publish(timeout=5)
        log("VDA", f"AMR {serial} -> {node_id} (x={x}, y={y})", color=B)

    def send_task(self, asset_id, task_type, task_command=None):
        """Publish a TaskRequest to a device (task_command defaults to task_type)."""
        topic = f"asset/{asset_id}/task_request"
        payload = {
            "id": str(uuid.uuid4()),
            "task_type": task_type,
            "task_command": task_command or task_type,
            "asset_id": asset_id,
            "task_params": {},
        }
        self.client.publish(topic, json.dumps(payload)).wait_for_publish(timeout=5)
        log("TASK", f"Sent {task_type} to {asset_id}", color=Y)

    # --- high-level steps (publish + wait) --------------------------------
    def send_agv(self, serial, goal, theta=0.0, timeout=300):
        """Drive <serial> to waypoint <goal> (Pcode); block until it arrives."""
        x, y = marker_to_vda(goal)
        self.send_order(serial, goal, x, y, theta)
        return self.wait_for_arrival(serial, goal, timeout)

    def send_device(self, asset_id, task_type, timeout=120, fatal=True):
        """Send a task to <asset_id>; block until COMPLETED."""
        self.subscribe(asset_id)
        self.send_task(asset_id, task_type)
        ok = self.wait_for_complete(asset_id, timeout)
        if not ok and fatal:
            raise SystemExit(1)
        return ok

    # --- waiting -----------------------------------------------------------
    def wait_for_complete(self, asset_id, timeout=120):
        """Block until asset/<id>/task_status reports COMPLETED (or FAILED)."""
        start = time.time()
        with self.lock:
            self.statuses.pop(asset_id, None)
        while time.time() - start < timeout:
            with self.lock:
                s = self.statuses.get(asset_id)
            if s and s["time"] > start:
                up = str(s["status"]).upper()
                if up == "COMPLETED":
                    log("DONE", f"{asset_id} COMPLETED", color=G)
                    return True
                if up == "FAILED":
                    log("FAIL", f"{asset_id} FAILED", color=R)
                    return False
            time.sleep(1)
        log("FAIL", f"{asset_id} timeout after {timeout}s", color=R)
        return False

    def wait_for_arrival(self, serial, goal, timeout=300):
        """Block until the AGV's /state reports lastNodeId==goal and not driving."""
        state_topic = f"uagv/v2/{MANUFACTURER}/{serial}/state"
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


if __name__ == "__main__":
    raise SystemExit("lib.py is a helper module — import it, don't run it.")
