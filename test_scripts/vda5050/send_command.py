#!/usr/bin/env python3
"""send_command.py — fake a Scorpio CommandMessage so the MASTER emits an order.

  Topic: command_updates   (the master's FIWARE/Scorpio command channel)

The master does NOT subscribe to the `order` topic — it PUBLISHES there. It emits
an order when its Scorpio bridge receives a CommandMessage on `command_updates`.
We hand-craft that envelope here; the master looks each nodeId up in its map,
converts it to an order, and publishes it to uagv/v2/<mfr>/<serial>/order —
watch it with  ./watch.py order <serial>.

  ./send_command.py <serial> [nodeId ...]      # default waypoints: P0 P1 P2 P3
  ./send_command.py 10 P123 P501 P619          # route through these map nodes

Requirements (else the master logs an error and emits nothing):
  - the AGV <mfr>/<serial> must already be DISCOVERED (send a state first)
  - every nodeId must exist in the master's loaded map, with an edge between
    each consecutive pair
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib


def main(argv):
    if len(argv) < 2:
        print(f"Usage: {argv[0]} <serial> [nodeId ...]\n"
              f"  e.g. {argv[0]} 10 P0 P1 P2 P3", file=sys.stderr)
        return 2

    serial = argv[1]
    nodes = [n.upper() for n in argv[2:]] or ["P0", "P1", "P2", "P3"]
    with lib.MQTTHelper() as mqtt:
        mqtt.send_command(serial, nodes)
        lib.log("HINT", f"The master should publish an order: ./watch.py order {serial}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
