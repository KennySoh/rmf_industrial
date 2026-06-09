#!/usr/bin/env python3
"""send_order.py — ACT AS THE MASTER: publish a VDA5050 order straight to an AGV.

  Topic: uagv/v2/<mfr>/<serial>/order

You play the master: publish an order (one or more waypoints) directly to the
AGV/sim, bypassing FIWARE/Scorpio. Read the AGV's replies with
  ./watch.py state <serial>

  ./send_order.py <serial> <Pcode> [Pcode ...]   # x,y from the marker grid
  ./send_order.py 10 P123 P501 P619              # a 3-waypoint route
  ./send_order.py 10 P123                         # single-node order (no edges)

Multi-waypoint orders get connecting edges and VDA5050 sequence IDs, exactly
like a real master emits.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib


def main(argv):
    if len(argv) < 3:
        print(f"Usage: {argv[0]} <serial> <Pcode> [Pcode ...]\n"
              f"  e.g. {argv[0]} 10 P123 P501 P619", file=sys.stderr)
        return 2

    serial, pcodes = argv[1], [p.upper() for p in argv[2:]]
    with lib.MQTTHelper() as mqtt:
        mqtt.send_order(serial, pcodes)
        lib.log("HINT", f"Read the AGV's response: ./watch.py state {serial}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
