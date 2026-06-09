#!/usr/bin/env python3
"""send_mapf_task.py — submit a task at the TOP of the MAPF pipeline.

POST to the movement_request_server (`/mapf/send_task`). It pushes the task onto
the Redis `mapf_tasks` queue; the adg_executor dequeues it, calls the MAPF
solver, builds the action-dependency graph, and drives the robot by emitting
CommandMessage entities to Scorpio — which reach the master exactly like
./send_command_scorpio.py does, but planned by MAPF instead of hand-fed.

This talks to MAPF (one layer ABOVE the vda5050 master). Use it to exercise the
full solver -> executor -> master -> sim pipeline. See architecture.md.

  ./send_mapf_task.py <robot_id> <start> <goal> [task_id]
  ./send_mapf_task.py Manufacturer_10 P123 P619
  ./send_mapf_task.py Manufacturer_10 P123 P619 mytask1

  MRS_URL=http://localhost:8009 overrides the server URL.
  Poll status:  curl "$MRS_URL/mapf/monitor_task?task_id=<task_id>"
"""

import json
import os
import sys
import time

import requests

MRS_URL = os.environ.get("MRS_URL", "http://localhost:8009")


def main(argv):
    if len(argv) < 4:
        print(f"Usage: {argv[0]} <robot_id> <start> <goal> [task_id]\n"
              f"  e.g. {argv[0]} Manufacturer_10 P123 P619", file=sys.stderr)
        return 2

    robot_id, start, goal = argv[1], argv[2].upper(), argv[3].upper()
    task_id = argv[4] if len(argv) > 4 else f"task_{int(time.time())}"
    body = {"tasks": [{
        "task_id": task_id,
        "robot_id": robot_id,
        "start_location": start,
        "goal_location": goal,
    }]}

    url = f"{MRS_URL}/mapf/send_task"
    print(f"-> POST {url}")
    print(json.dumps(body, indent=2))
    r = requests.post(url, json=body, timeout=30)
    print(f"{r.status_code} {r.text}")
    print(f"Poll: curl \"{MRS_URL}/mapf/monitor_task?task_id={task_id}\"")
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
