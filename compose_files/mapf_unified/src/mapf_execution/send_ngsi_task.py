#!/usr/bin/env python3
"""
Script to send NGSI-LD task messages to Redis queues for adg_executor.

This script helps you send properly formatted NGSI-LD TaskRequest messages
to the Redis queues that adg_executor monitors.

Usage examples:
    # Send single robot task
    python3 send_ngsi_task.py --robot_id MiR_0005 --goal_location P65

    # Send task to specific queue
    python3 send_ngsi_task.py --robot_id MiR_0001 --goal_location P100 --queue mapf_replace_destinations

    # Send conflicting tasks (two robots to same location)
    python3 send_ngsi_task.py --conflict --goal_location P100
"""

import argparse
import json
import redis
import uuid
from datetime import datetime
from typing import List, Dict


def create_ngsi_ld_task(task_id: str, robot_id: str, goal_location: str, start_location: str = None) -> Dict:
    """
    Create an NGSI-LD formatted task message.

    Args:
        task_id: Unique task identifier (will be wrapped in URN format)
        robot_id: Robot identifier (e.g., "MiR_0001")
        goal_location: Goal location node (e.g., "P100")
        start_location: Optional start location (if not provided, robot uses current position)

    Returns:
        Dictionary containing NGSI-LD formatted task
    """
    task_params = {
        "goal_location": goal_location,
        "robot_id": robot_id
    }

    if start_location:
        task_params["start_location"] = start_location

    task_message = {
        "type": "Task",
        "id": f"urn:ngsi-ld:Task:urn:{task_id}:TaskRequest",
        "taskType": {
            "type": "Property",
            "value": "amr_mapf"
        },
        "taskCommand": {
            "type": "Property",
            "value": "RESUME"
        },
        "taskParams": {
            "type": "Property",
            "value": [task_params]
        },
        "taskExpectedStart": {
            "type": "Property",
            "value": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z"
        },
        "taskExpectedEnd": {
            "type": "Property",
            "value": ""
        },
        "taskExpectedDuration": {
            "type": "Property",
            "value": ""
        }
    }

    return task_message


def send_task_to_redis(
    redis_client,
    queue_name: str,
    task_message: Dict
) -> bool:
    """
    Send a task message to a Redis queue.

    Args:
        redis_client: Redis connection
        queue_name: Name of the queue to push to
        task_message: NGSI-LD formatted task dictionary

    Returns:
        True if successful, False otherwise
    """
    try:
        task_json = json.dumps(task_message)
        redis_client.lpush(queue_name, task_json)
        print(f"✓ Task sent to queue '{queue_name}'")
        print(f"  Task ID: {task_message['id']}")
        print(f"  Robot: {task_message['taskParams']['value'][0]['robot_id']}")
        print(f"  Goal: {task_message['taskParams']['value'][0]['goal_location']}")
        return True
    except Exception as e:
        print(f"✗ Failed to send task: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Send NGSI-LD task messages to adg_executor via Redis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Send single task for MiR_0005 to go to P65
  %(prog)s --robot_id MiR_0005 --goal_location P65

  # Send task with specific start location
  %(prog)s --robot_id MiR_0001 --start_location P70 --goal_location P100

  # Send conflicting tasks (two robots to same location) to test empty plan handling
  %(prog)s --conflict --goal_location P100

  # Send to specific queue
  %(prog)s --robot_id MiR_0003 --goal_location P70 --queue mapf_tasks
        """
    )

    parser.add_argument(
        "--robot_id",
        help="Robot ID (e.g., MiR_0001). Not used with --conflict"
    )
    parser.add_argument(
        "--start_location",
        help="Start location node (optional, robot uses current position if not specified)"
    )
    parser.add_argument(
        "--goal_location",
        required=True,
        help="Goal location node (e.g., P100)"
    )
    parser.add_argument(
        "--queue",
        default="mapf_replace_destinations",
        choices=["mapf_tasks", "mapf_replace_destinations"],
        help="Redis queue to send to (default: mapf_replace_destinations)"
    )
    parser.add_argument(
        "--conflict",
        action="store_true",
        help="Send two robots to same destination (for testing empty plan scenario)"
    )
    parser.add_argument(
        "--redis_host",
        default="localhost",
        help="Redis host (default: localhost)"
    )
    parser.add_argument(
        "--redis_port",
        type=int,
        default=6379,
        help="Redis port (default: 6379)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.conflict and not args.robot_id:
        parser.error("--robot_id is required unless using --conflict")

    # Connect to Redis
    try:
        r = redis.Redis(host=args.redis_host, port=args.redis_port, db=0)
        r.ping()
        print(f"✓ Connected to Redis at {args.redis_host}:{args.redis_port}")
    except Exception as e:
        print(f"✗ Failed to connect to Redis: {e}")
        return 1

    print(f"\nSending to queue: {args.queue}")
    print("=" * 60)

    # Create and send task(s)
    if args.conflict:
        # Send two robots to same location to test conflict/empty plan handling
        print("Creating conflicting tasks (two robots to same location)...")

        task_id1 = str(uuid.uuid4())
        task_id2 = str(uuid.uuid4())

        task1 = create_ngsi_ld_task(
            task_id=task_id1,
            robot_id="MiR_0001",
            goal_location=args.goal_location,
            start_location=args.start_location or "P70"
        )

        task2 = create_ngsi_ld_task(
            task_id=task_id2,
            robot_id="MiR_0002",
            goal_location=args.goal_location,
            start_location=args.start_location or "P539"
        )

        success1 = send_task_to_redis(r, args.queue, task1)
        print()
        success2 = send_task_to_redis(r, args.queue, task2)

        if success1 and success2:
            print("\n" + "=" * 60)
            print("✓ Both conflicting tasks sent successfully!")
            print("  Monitor adg_executor logs to see if solver returns empty plan")
            print("=" * 60)
    else:
        # Send single task
        task_id = str(uuid.uuid4())

        task = create_ngsi_ld_task(
            task_id=task_id,
            robot_id=args.robot_id,
            goal_location=args.goal_location,
            start_location=args.start_location
        )

        success = send_task_to_redis(r, args.queue, task)

        if success:
            print("\n" + "=" * 60)
            print("✓ Task sent successfully!")
            print("  Monitor adg_executor logs to see task execution")
            print("=" * 60)

    # Show how to monitor logs
    print("\nTo monitor adg_executor logs:")
    print(f"  docker logs adg_executor --follow")
    print("\nTo check queue length:")
    print(f"  docker exec rmf2_broker-redis-1 redis-cli LLEN {args.queue}")

    return 0


if __name__ == "__main__":
    exit(main())
