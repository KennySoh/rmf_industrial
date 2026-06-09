#!/usr/bin/env python3
"""send_command_scorpio.py — drive the master the SAME WAY THE MAPF EXECUTOR DOES.

POST/PATCH a `CommandMessage` NGSI-LD entity to Scorpio. Scorpio's subscription
(created by the master) then notifies the master over the `command_updates` MQTT
topic; the master converts it against its map and publishes a VDA5050 order.

This is the REAL command path (HTTP -> Scorpio -> MQTT -> master). For the
shortcut that fakes Scorpio's notification straight onto `command_updates`
(no Scorpio needed), use ./send_command.py instead. See architecture.md.

  ./send_command_scorpio.py <serial> [nodeId ...]      # default waypoints: P0 P1 P2 P3
  ./send_command_scorpio.py 10 P123 P501 P619          # route through these map nodes

Requirements (else the master logs an error and emits nothing):
  - Scorpio reachable (default http://localhost:9090; override with SCORPIO_URL=)
  - the AGV <mfr>/<serial> already DISCOVERED by the master (it has sent state)
  - every nodeId in the master's map, with an edge between each consecutive pair
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib


def main(argv):
    if len(argv) < 2:
        print(f"Usage: {argv[0]} <serial> [nodeId ...]\n"
              f"  e.g. {argv[0]} 10 P123 P501 P619", file=sys.stderr)
        return 2

    serial = argv[1]
    nodes = [n.upper() for n in argv[2:]] or ["P0", "P1", "P2", "P3"]
    scorpio = lib.Scorpio(url=os.environ.get("SCORPIO_URL", lib.SCORPIO_URL))
    r = scorpio.send_command(serial, nodes)
    lib.log("HINT", f"The master should publish an order: ./watch.py order {serial}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
