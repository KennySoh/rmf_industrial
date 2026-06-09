#!/usr/bin/env python3
"""watch.py — tail VDA5050 MQTT topics.

  ./watch.py                       # ALL VDA5050 topics  (uagv/#)
  ./watch.py order [serial] [mfr]  # orders the MASTER publishes
  ./watch.py state [serial] [mfr]  # states the AGV publishes
  ./watch.py <serial> [mfr]        # everything for one AGV
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib


def main(argv):
    arg = argv[1] if len(argv) > 1 else "all"
    if arg == "all":
        topic = "uagv/#"
    elif arg in ("order", "state"):
        serial = argv[2] if len(argv) > 2 else "+"
        mfr = argv[3] if len(argv) > 3 else lib.MANUFACTURER
        topic = f"uagv/v2/{mfr}/{serial}/{arg}"
    else:  # arg = serial
        mfr = argv[2] if len(argv) > 2 else lib.MANUFACTURER
        topic = f"uagv/v2/{mfr}/{arg}/#"

    with lib.MQTTHelper() as mqtt:
        mqtt.watch(topic)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
