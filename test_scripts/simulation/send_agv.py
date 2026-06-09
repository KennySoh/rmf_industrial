#!/usr/bin/env python3
"""send_agv.py — send a VDA5050 order to an AGV, by waypoint OR raw coords.

  ./send_agv.py <serial> <Pcode>   [theta]   # x,y from the marker grid (map frame)
  ./send_agv.py <serial> <x> <y>   [theta]   # raw x,y in the map frame (metres)
  e.g.  ./send_agv.py 10 P0   ==   ./send_agv.py 10 -30.8 -49.3
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib


def main(argv):
    if len(argv) < 3:
        print(f"Usage: {argv[0]} <serial> <Pcode> [theta]\n"
              f"       {argv[0]} <serial> <x> <y> [theta]", file=sys.stderr)
        return 2

    serial = argv[1]
    with lib.MQTTHelper() as h:
        if re.match(r"^[Pp][0-9]+$", argv[2]):
            node = argv[2].upper()
            theta = float(argv[3]) if len(argv) > 3 else 0.0
            h.send_order(serial, node, *lib.marker_to_vda(node), theta)
        else:
            if len(argv) < 4:
                print(f"Usage: {argv[0]} <serial> <x> <y> [theta]", file=sys.stderr)
                return 2
            x, y = float(argv[2]), float(argv[3])
            theta = float(argv[4]) if len(argv) > 4 else 0.0
            h.send_order(serial, "Node_1", x, y, theta)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
