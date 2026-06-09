#!/usr/bin/env python3
"""demo_single_agv_reset.py — reset sequence, event-driven.

Picks the rack back up and parks it at P123, waiting on the live MQTT feed at
every step (see MQTTHelper) instead of fixed sleeps.

  ./demo_single_agv_reset.py [agv_serial]      (default agv_serial: 10)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib


def main(argv):
    agv_serial = argv[1] if len(argv) > 1 else "10"

    with lib.MQTTHelper() as mqtt:
        mqtt.send_agv(agv_serial, "P68")         # AMR to rack location
        mqtt.send_device(agv_serial, "liftrack")  # lift rack at current coord
        mqtt.send_agv(agv_serial, "P123")        # carry rack to park point
        mqtt.send_device(agv_serial, "droprack")  # drop rack at current coord
        mqtt.send_agv(agv_serial, "P142")        # AMR clears out

    lib.log("DONE", "=== reset complete ===", color=lib.G)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
