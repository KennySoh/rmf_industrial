#!/usr/bin/env python3
"""send_device.py — publish a TaskRequest to a UE5 device.

  ./send_device.py <asset_id> <task_type>
  task_type: depalletize | dropoff | liftrack | droprack
  (ManipulatorRobot1/2 -> depalletize | Conveyor1..3 -> dropoff | <serial> -> liftrack/droprack)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib


def main(argv):
    if len(argv) < 3:
        print(f"Usage: {argv[0]} <asset_id> <task_type>\n"
              "  task_type: depalletize | dropoff | liftrack | droprack",
              file=sys.stderr)
        return 2

    asset_id, task_type = argv[1], argv[2]
    with lib.MQTTHelper() as h:
        h.send_task(asset_id, task_type)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
