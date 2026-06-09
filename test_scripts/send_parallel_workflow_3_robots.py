#!/usr/bin/env python3
"""
Send a parallel 3-robot MAPF workflow to the Rust Task Orchestrator via AMQP.

This script creates a crossflow diagram with:
- fork_clone: splits into 3 parallel branches
- 3x MapfReplaceNode: one per robot
- 3x buffer: wait points
- join: waits for all robots to complete

Usage:
    python3 send_parallel_workflow_3_robots.py
    python3 send_parallel_workflow_3_robots.py --robots MiR_00014,MiR_00015,MiR_00016
    python3 send_parallel_workflow_3_robots.py --goals P300,P301,P302
"""

import pika
import json
import uuid
import argparse
from datetime import datetime


def create_parallel_workflow(robots: list, goals: list) -> dict:
    """
    Create a crossflow diagram for parallel robot movement.

    Args:
        robots: List of robot IDs (e.g., ["MiR_00014", "MiR_00015", "MiR_00016"])
        goals: List of goal waypoints (e.g., ["P300", "P301", "P302"])

    Returns:
        Complete Schedule message for AMQP
    """
    if len(robots) != len(goals):
        raise ValueError("Number of robots must match number of goals")

    workflow_id = str(uuid.uuid4())[:8]

    # Generate unique IDs for each operation
    fork_id = str(uuid.uuid4())
    join_id = str(uuid.uuid4())

    robot_nodes = []
    buffer_nodes = []

    for i, (robot, goal) in enumerate(zip(robots, goals)):
        robot_nodes.append({
            "id": str(uuid.uuid4()),
            "robot": robot,
            "goal": goal,
            "task_id": str(uuid.uuid4())
        })
        buffer_nodes.append(str(uuid.uuid4()))

    # Build the ops dictionary
    ops = {}

    # Fork node - splits into parallel branches
    ops[fork_id] = {
        "type": "fork_clone",
        "next": [node["id"] for node in robot_nodes]
    }

    # Robot movement nodes
    for i, (node, buffer_id) in enumerate(zip(robot_nodes, buffer_nodes)):
        ops[node["id"]] = {
            "type": "node",
            "builder": "MapfReplaceNode",
            "next": buffer_id,
            "display_text": f"{node['robot']} -> {node['goal']}",
            "config": {
                "asset_name": node["robot"],
                "coordinates": node["goal"],
                "task_type": "amr_mapf",
                "task_id": node["task_id"]
            }
        }

    # Buffer nodes (wait points for join)
    for buffer_id in buffer_nodes:
        ops[buffer_id] = {
            "type": "buffer"
        }

    # Join node - waits for all buffers
    ops[join_id] = {
        "type": "join",
        "buffers": buffer_nodes,
        "next": {"builtin": "terminate"}
    }

    # Build the diagram
    diagram = {
        "version": "0.1.0",
        "start": fork_id,
        "ops": ops
    }

    # Build the Schedule message
    schedule = {
        "id": f"urn:ngsi-ld:Schedule:parallel-{workflow_id}",
        "type": "Schedule",
        "payload": diagram
    }

    return schedule, robot_nodes


def send_workflow(schedule: dict, amqp_host='localhost', amqp_port=5672):
    """Send the workflow to the Task Orchestrator via AMQP."""

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=amqp_host, port=amqp_port)
    )
    channel = connection.channel()

    # Declare exchange (fanout to broadcast to all consumers)
    channel.exchange_declare(
        exchange='@RECEIVE@',
        exchange_type='fanout',
        durable=True
    )

    # Publish message
    channel.basic_publish(
        exchange='@RECEIVE@',
        routing_key='',
        body=json.dumps(schedule),
        properties=pika.BasicProperties(
            content_type='application/json',
            delivery_mode=2  # persistent
        )
    )

    connection.close()


def main():
    parser = argparse.ArgumentParser(
        description="Send parallel 3-robot MAPF workflow to Rust Task Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default: 3 Manufacturer robots using named goals
  python3 send_parallel_workflow_3_robots.py

  # Custom robots and goals
  python3 send_parallel_workflow_3_robots.py \\
      --robots Manufacturer_5,Manufacturer_6,Manufacturer_7 \\
      --goals Manufacturer_5_goal,Manufacturer_6_goal,Manufacturer_7_goal

  # Dry-run to see JSON without sending
  python3 send_parallel_workflow_3_robots.py --dry-run

Valid robots:
  Manufacturer_2 - Manufacturer_25

Named coordinates (from location_coord_map_os_res.json):
  Manufacturer_X_home  - robot home position
  Manufacturer_X_goal  - robot goal position
"""
    )

    parser.add_argument(
        '--robots',
        default='Manufacturer_2,Manufacturer_3,Manufacturer_4',
        help='Comma-separated robot IDs (default: Manufacturer_2,Manufacturer_3,Manufacturer_4)'
    )
    parser.add_argument(
        '--goals',
        default='Manufacturer_2_goal,Manufacturer_3_goal,Manufacturer_4_goal',
        help='Comma-separated goal names (default: Manufacturer_2_goal,Manufacturer_3_goal,Manufacturer_4_goal)'
    )
    parser.add_argument(
        '--amqp-host',
        default='localhost',
        help='AMQP broker host (default: localhost)'
    )
    parser.add_argument(
        '--amqp-port',
        type=int,
        default=5672,
        help='AMQP broker port (default: 5672)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print workflow JSON without sending'
    )

    args = parser.parse_args()

    robots = [r.strip() for r in args.robots.split(',')]
    goals = [g.strip() for g in args.goals.split(',')]

    if len(robots) != len(goals):
        print(f"Error: Number of robots ({len(robots)}) must match number of goals ({len(goals)})")
        return 1

    print(f"\n=== Parallel MAPF Workflow ({len(robots)} robots) ===\n")

    # Create workflow
    schedule, robot_nodes = create_parallel_workflow(robots, goals)

    print(f"Schedule ID: {schedule['id']}")
    print(f"Timestamp:   {datetime.now().isoformat()}")
    print()
    print("Robot Tasks:")
    for node in robot_nodes:
        print(f"  {node['robot']:20} -> {node['goal']:10} (task: {node['task_id'][:8]}...)")
    print()

    if args.dry_run:
        print("Workflow JSON (dry-run):")
        print(json.dumps(schedule, indent=2))
        return 0

    # Send workflow
    try:
        send_workflow(schedule, args.amqp_host, args.amqp_port)
        print(f"Workflow sent to AMQP broker at {args.amqp_host}:{args.amqp_port}")
        print()
        print("=== Next Steps ===")
        print("1. Check Rust Task Orchestrator logs:")
        print("   tail -f ~/ros_industrial_ws/docker_modules/rmf2_task_orchestrator/rust_orchestrator.log")
        print()
        print("2. Check active workflows:")
        print("   curl -s http://localhost:2727/workflow/get_workflows | jq")
        print()
        print("3. Check ADG executor (receives TaskRequest from orchestrator):")
        print("   docker logs adg_executor --tail 30")
        return 0

    except pika.exceptions.AMQPConnectionError as e:
        print(f"Error: Failed to connect to AMQP broker at {args.amqp_host}:{args.amqp_port}")
        print(f"  {e}")
        print()
        print("Make sure RabbitMQ is running:")
        print("  docker ps | grep rabbitmq")
        return 1


if __name__ == "__main__":
    exit(main())
