#!/usr/bin/env python3
"""
Test script for MAPF Replace Destination functionality.

Sends a replace_destination command to change a robot's goal mid-execution.
"""

import redis
import json
import sys
import argparse
from datetime import datetime


def send_replace_destination(robot_id: str, goal_location: str, redis_host='localhost', redis_port=6379):
    """
    Send a replace destination command to the MAPF system via Redis.

    Args:
        robot_id: The robot to redirect (e.g., "Manufacturer_24", "MiR_00014")
        goal_location: The new destination waypoint (e.g., "P370", "P523")
        redis_host: Redis server hostname (default: localhost)
        redis_port: Redis server port (default: 6379)

    Returns:
        bool: True if successfully queued, False otherwise
    """
    try:
        # Connect to Redis
        r = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=False)
        r.ping()  # Test connection

        # Create TaskRequest message in NGSI-LD format
        # TaskRequest.from_json() expects nested {"value": ...} format
        import uuid
        task_uuid = str(uuid.uuid4())
        task_id = f"urn:ngsi-ld:Task:urn:{task_uuid}:TaskRequest"

        # taskParams value should be a dict (NOT JSON string)
        # The executor iterates and expects json_params to be a dict
        task_params_item = {
            "robot_id": robot_id,
            "goal_location": goal_location
        }

        task_request = {
            "id": task_id,
            "taskType": {"value": "ReplaceDestination"},
            "taskCommand": {"value": "START"},
            "taskParams": {"value": [task_params_item]},  # Array of dicts
            "taskExpectedStart": {"value": datetime.now().isoformat()},
            "taskExpectedEnd": {"value": datetime.now().isoformat()},
            "taskExpectedDuration": {"value": "PT1H"}
        }

        # Push TaskRequest object directly (NOT wrapped in array)
        queue_name = "mapf_replace_destinations"
        r.lpush(queue_name, json.dumps(task_request))

        print(f"✓ Replace destination sent successfully!")
        print(f"  Robot:       {robot_id}")
        print(f"  New Goal:    {goal_location}")
        print(f"  Task ID:     {task_id}")
        print(f"  Queue:       {queue_name}")
        print(f"  Redis:       {redis_host}:{redis_port}")

        return True

    except redis.ConnectionError as e:
        print(f"✗ Failed to connect to Redis at {redis_host}:{redis_port}")
        print(f"  Error: {e}")
        print(f"  Make sure Redis is running: docker ps | grep redis")
        return False

    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Send replace_destination command to MAPF system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Redirect Manufacturer_24 to P165
  python3 test_replace_destination.py Manufacturer_24 P165

  # Redirect MiR_00014 to its home position P523
  python3 test_replace_destination.py MiR_00014 P523

  # Use custom Redis host
  python3 test_replace_destination.py Manufacturer_24 P370 --redis-host localhost --redis-port 6379

Valid waypoints for the active map (BUILDING_NAME=warehouse_os_setup_v2):
  Vertices are named P0-P713; a goal must be a navigable node (one on a lane).
  Known-good examples (the destinations test_scripts/mapf/send_test_tasks.sh uses):
    P165, P167, P171, P173, P175, P177, P231, P233, P235, P239,
    P241, P243, P245, P297, P299, P301, P303, P307, P309, P311,
    P363, P365, P367, P369
  Full vertex list: mapf_unified_repo/src/mapf/mapf_service/mapf_service/maps/warehouse_os_setup_v2.yaml


Valid robots (examples):
  Manufacturer_2 through Manufacturer_25
  MiR_0001 through MiR_00024
"""
    )

    parser.add_argument('robot_id', help='Robot ID (e.g., Manufacturer_24)')
    parser.add_argument('goal_location', help='New goal waypoint (e.g., P370)')
    parser.add_argument('--redis-host', default='localhost', help='Redis host (default: localhost)')
    parser.add_argument('--redis-port', type=int, default=6379, help='Redis port (default: 6379)')

    args = parser.parse_args()

    print(f"\n=== MAPF Replace Destination Test ===\n")

    success = send_replace_destination(
        robot_id=args.robot_id,
        goal_location=args.goal_location,
        redis_host=args.redis_host,
        redis_port=args.redis_port
    )

    if success:
        print(f"\n=== Next Steps ===")
        print(f"1. Check ADG executor logs for confirmation:")
        print(f"   docker exec mapf_unified tail -f -n10 /var/log/supervisor/adg_executor.log")
        print(f"2. Monitor robot position in UE5 simulation")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
