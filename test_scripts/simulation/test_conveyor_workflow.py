#!/usr/bin/env python3
"""
Test conveyor workflow — single run, step by step with MQTT monitoring.

Sequence:
  1. AMR goes to rack pickup point, lifts rack
  2. AMR goes to manipulator station
  3. Depalletize (load cargo onto rack)
  4. AMR goes to conveyor
  5. Conveyor dropoff (despawn cargo from rack)

Usage:
  python3 test_conveyor_workflow.py
  python3 test_conveyor_workflow.py --amr 1 --rack-wp P327 --manip ManipulatorRobot1 --manip-wp P501 --conveyor Conveyor_1 --conveyor-wp P619 --depal-count 5
"""

import paho.mqtt.client as mqtt
import json
import uuid
import time
import threading
import argparse
import sys
from datetime import datetime

MQTT_HOST = "localhost"
MQTT_PORT = 1883
MAP_ID = "urn:ngsi-ld:Map:warehouse_os_setup"

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
    idx = int(marker.replace("P", ""))
    row = idx // MARKERS_PER_ROW
    col = idx % MARKERS_PER_ROW
    ue_x = MARKER_ORIGIN_X + col * MARKER_STEP
    ue_y = MARKER_ORIGIN_Y + row * MARKER_STEP
    return round(ue_x / 100.0, 2), round(ue_y / 100.0, 2)


class MQTTHelper:
    def __init__(self, host, port):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.host = host
        self.port = port
        self.statuses = {}
        self.lock = threading.Lock()

    def connect(self):
        self.client.on_connect = lambda c, u, f, rc, p=None: log("MQTT", f"Connected to {self.host}:{self.port}")
        self.client.on_message = self._on_message
        self.client.connect(self.host, self.port, 60)
        self.client.loop_start()
        time.sleep(1)

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            asset_id = payload.get("asset_id", "")
            status = payload.get("status", "")
            with self.lock:
                self.statuses[asset_id] = {"status": status, "time": time.time(), "payload": payload}
            log("MQTT", f"{asset_id} -> {status}")
        except Exception:
            pass

    def subscribe(self, asset_id):
        self.client.subscribe(f"asset/{asset_id}/task_status")

    def send_task(self, asset_id, task_command, task_type):
        topic = f"asset/{asset_id}/task_request"
        task_id = str(uuid.uuid4())
        payload = {"id": task_id, "task_command": task_command, "task_type": task_type, "asset_id": asset_id, "task_params": {}}
        self.client.publish(topic, json.dumps(payload))
        log("TASK", f"Sent {task_command} to {asset_id}", color=Y)
        return task_id

    def send_vda_order(self, serial, goal):
        x, y = marker_to_vda(goal)
        topic = f"uagv/v2/Manufacturer/{serial}/order"
        order = {
            "headerId": int(time.time()) % 10000,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "version": "2.0.0",
            "manufacturer": "Manufacturer",
            "serialNumber": str(serial),
            "orderId": f"workflow-{uuid.uuid4()}",
            "orderUpdateId": 1,
            "nodes": [{"nodeId": goal, "sequenceId": 0, "released": True,
                        "nodePosition": {"x": x, "y": y, "allowedDeviationXY": 0.5,
                                         "allowedDeviationTheta": 0.5, "mapId": MAP_ID},
                        "actions": []}],
            "edges": [],
        }
        self.client.publish(topic, json.dumps(order))
        log("VDA", f"AMR {serial} -> {goal} (x={x}, y={y})", color=B)

    def wait_for_complete(self, asset_id, timeout=120):
        start = time.time()
        with self.lock:
            self.statuses.pop(asset_id, None)
        while time.time() - start < timeout:
            with self.lock:
                s = self.statuses.get(asset_id)
                if s and s["time"] > start:
                    if s["status"].upper() == "COMPLETED":
                        log("DONE", f"{asset_id} COMPLETED", color=G)
                        return True
                    if s["status"].upper() == "FAILED":
                        log("FAIL", f"{asset_id} FAILED", color=R)
                        return False
            time.sleep(1)
        log("FAIL", f"{asset_id} timeout after {timeout}s", color=R)
        return False

    def wait_for_arrival(self, serial, goal, timeout=300):
        state_topic = f"uagv/v2/Manufacturer/{serial}/state"
        arrived = threading.Event()

        def on_state(client, userdata, msg):
            try:
                state = json.loads(msg.payload.decode())
                last_node = state.get("lastNodeId", "")
                driving = state.get("driving", True)
                if last_node == goal and not driving:
                    arrived.set()
            except Exception:
                pass

        self.client.subscribe(state_topic)
        self.client.message_callback_add(state_topic, on_state)
        log("WAIT", f"Waiting for AMR {serial} to reach {goal}...")

        try:
            while not arrived.is_set() and timeout > 0:
                elapsed = int(300 - timeout)
                print(f"\r  AMR {serial}: waiting... ({elapsed}s)", end="", flush=True)
                arrived.wait(timeout=2)
                timeout -= 2
        finally:
            self.client.message_callback_remove(state_topic)
            self.client.unsubscribe(state_topic)
            print()

        if arrived.is_set():
            log("DONE", f"AMR {serial} arrived at {goal}!", color=G)
            return True
        log("FAIL", f"AMR {serial} timeout reaching {goal}", color=R)
        return False

    def wait_for_input(self, prompt):
        input(f"{Y}[WAIT ]{NC} {prompt} Press ENTER to continue...")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--amr", default="1", help="AMR serial number (default: 1)")
    p.add_argument("--rack-wp", default="P327", help="Rack pickup waypoint")
    p.add_argument("--manip", default="ManipulatorRobot1", help="Manipulator asset ID")
    p.add_argument("--manip-wp", default="P501", help="Manipulator waypoint")
    p.add_argument("--conveyor", default="Conveyor1", help="Conveyor asset ID")
    p.add_argument("--conveyor-wp", default="P619", help="Conveyor waypoint")
    p.add_argument("--depal-count", type=int, default=1, help="Number of depalletize cycles")
    args = p.parse_args()

    print(f"{G}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║              Conveyor Workflow Test                      ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{NC}")
    print(f"  AMR:       Manufacturer_{args.amr}")
    print(f"  Rack:      {args.rack_wp}")
    print(f"  Manip:     {args.manip} at {args.manip_wp}")
    print(f"  Conveyor:  {args.conveyor} at {args.conveyor_wp}")
    print(f"  Depal:     {args.depal_count}x")
    print()

    h = MQTTHelper(MQTT_HOST, MQTT_PORT)
    h.connect()
    h.subscribe(args.amr)
    h.subscribe(args.manip)
    h.subscribe(args.conveyor)

    try:
        # Step 1: AMR to rack pickup point
        log("STEP", f"1: AMR {args.amr} to rack at {args.rack_wp}", color=M)
        h.send_vda_order(args.amr, args.rack_wp)
        if not h.wait_for_arrival(args.amr, args.rack_wp):
            return 1

        # Step 2: Lift rack
        log("STEP", "2: Lift rack", color=M)
        h.send_task(args.amr, "liftrack", "liftrack")
        if not h.wait_for_complete(args.amr, timeout=30):
            return 1

        # Step 3: AMR to manipulator station
        log("STEP", f"3: AMR to {args.manip} at {args.manip_wp}", color=M)
        h.send_vda_order(args.amr, args.manip_wp)
        if not h.wait_for_arrival(args.amr, args.manip_wp):
            return 1

        # Step 4: Depalletize
        for i in range(args.depal_count):
            log("STEP", f"4.{i+1}: Depalletize {i+1}/{args.depal_count}", color=M)
            h.send_task(args.manip, "depalletize", "depalletize")
            if not h.wait_for_complete(args.manip, timeout=60):
                return 1

        # Step 5: AMR to conveyor
        log("STEP", f"5: AMR to {args.conveyor} at {args.conveyor_wp}", color=M)
        h.send_vda_order(args.amr, args.conveyor_wp)
        if not h.wait_for_arrival(args.amr, args.conveyor_wp):
            return 1

        # Step 6: Conveyor dropoff (despawn cargo from rack)
        for i in range(args.depal_count):
            log("STEP", f"6.{i+1}: Conveyor dropoff {i+1}/{args.depal_count}", color=M)
            h.send_task(args.conveyor, "dropoff", "dropoff")
            if not h.wait_for_complete(args.conveyor, timeout=30):
                log("WARN", "Conveyor dropoff didn't report complete, continuing...", color=Y)
            time.sleep(1)

        print()
        log("DONE", "=== WORKFLOW COMPLETE ===", color=G)
        return 0

    except KeyboardInterrupt:
        print(f"\n{Y}Interrupted.{NC}")
        return 0
    finally:
        h.disconnect()


if __name__ == "__main__":
    sys.exit(main())
