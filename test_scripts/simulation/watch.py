#!/usr/bin/env python3
"""watch.py — tail simulation MQTT topics (devices, AGVs, or everything).

  ./watch.py                      # ALL topics  (discovery)
  ./watch.py asset [id]           # asset/<id>/#         (id omitted = all devices)
  ./watch.py vda [serial]         # uagv/v2/Manufacturer/<serial>/#
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib


def main(argv):
    mode = argv[1] if len(argv) > 1 else "all"
    if mode == "asset":
        topic = f"asset/{argv[2] if len(argv) > 2 else '+'}/#"
    elif mode == "vda":
        topic = f"uagv/v2/{lib.MANUFACTURER}/{argv[2] if len(argv) > 2 else '+'}/#"
    else:
        topic = "#"

    with lib.MQTTHelper() as h:
        h.watch(topic)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
