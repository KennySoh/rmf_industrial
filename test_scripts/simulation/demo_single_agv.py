#!/usr/bin/env python3
"""demo_single_agv.py — conveyor workflow, event-driven.

Drives one AGV through the pick -> manipulate -> conveyor cycle. Every step waits
on the live MQTT feed for the robot to report it's done (see MQTTHelper):
  send_agv     -> block until VDA5050 /state lastNodeId==<Pcode> && not driving
  send_device  -> block until asset/<id>/task_status == COMPLETED

  ./demo_single_agv.py [serial]      (default serial: 10)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib


def main(argv):
    agv_serial = argv[1] if len(argv) > 1 else "10"

    with lib.MQTTHelper() as mqtt:
        mqtt.send_agv(agv_serial, "P123")                  # AMR to rack pickup point
        mqtt.send_device(agv_serial, "liftrack")           # lift rack at current coord
        mqtt.send_agv(agv_serial, "P501")                  # AMR to manipulator station
        mqtt.send_device("ManipulatorRobot1", "depalletize")  # load cargo onto rack
        mqtt.send_agv(agv_serial, "P619")                  # AMR to conveyor
        mqtt.send_device("Conveyor1", "dropoff", fatal=False)  # dropoff (non-fatal)
        mqtt.send_agv(agv_serial, "P68")                  # AMR to conveyor
        mqtt.send_device(agv_serial, "droprack", fatal=False)  # dropoff (non-fatal)
        mqtt.send_agv(agv_serial, "P142")                  # AMR to conveyor

    lib.log("DONE", "=== demo complete ===", color=lib.G)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
