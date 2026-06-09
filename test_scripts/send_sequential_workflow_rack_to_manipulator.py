#!/usr/bin/env python3
"""
Send a sequential workflow for robot(s): rack pickup -> manipulator depalletize.

This script creates a crossflow diagram with sequential operations:
1. Robot moves to rack position (MAPF: amr_mapf via MapfReplaceNode)
2. Robot lifts rack (TransferNode via MQTT, task_type: liftrack)
3. Robot moves to manipulator (MAPF: amr_mapf via MapfReplaceNode)
4. Robot depalletizes at manipulator (TransferNode via MQTT, task_type: depalletize)
5. (Optional) Robot drops rack (TransferNode via MQTT, task_type: droprack)

For multiple robots, each robot executes the sequence in parallel.

Usage:
    # Single robot: full sequence
    python3 send_sequential_workflow_rack_to_manipulator.py

    # Custom robot and waypoints
    python3 send_sequential_workflow_rack_to_manipulator.py \
        --robots Manufacturer_5 \
        --racks P63 \
        --manipulators P501 \
        --stations MANIP1

    # Skip depalletize (just move rack to manipulator area)
    python3 send_sequential_workflow_rack_to_manipulator.py --no-depalletize

    # Include droprack at end
    python3 send_sequential_workflow_rack_to_manipulator.py --droprack

    # Multiple robots in parallel
    python3 send_sequential_workflow_rack_to_manipulator.py \
        --robots Manufacturer_2,Manufacturer_3,Manufacturer_4 \
        --racks P63,P61,P59 \
        --manipulators P433,P431,P433 \
        --stations MANIP1,MANIP1,MANIP1

Waypoint Reference (from RACK_AMR_WAYPOINT_ASSIGNMENTS.txt):
    Racks (row 1):  P63 (Rack), P61 (Rack2), P59 (Rack3), P57 (Rack4), P55 (Rack5)
    Racks (row 2):  P131 (Rack6), P129 (Rack7), P127 (Rack8), P125 (Rack9), P123 (Rack10)
    Manipulator 1:  P501 (station), P433/P431 (holding points)
    Manipulator 2:  P492 (station), P424/P422 (holding points)

Node Builders Used:
    MapfReplaceNode - MAPF movement (amr_mapf)
    TransferNode    - MQTT transfer for liftrack, droprack, depalletize
"""

import pika
import json
import uuid
import argparse
from datetime import datetime

# Mapping from rack waypoint to rack name (from RACK_AMR_WAYPOINT_ASSIGNMENTS.txt)
RACK_WAYPOINT_TO_NAME = {
    "P63": "Rack", "P61": "Rack2", "P59": "Rack3", "P57": "Rack4", "P55": "Rack5",
    "P131": "Rack6", "P129": "Rack7", "P127": "Rack8", "P125": "Rack9", "P123": "Rack10",
    "P199": "Rack11", "P197": "Rack12", "P195": "Rack13", "P193": "Rack14", "P191": "Rack15",
    "P267": "Rack16", "P265": "Rack17", "P263": "Rack18", "P261": "Rack19", "P259": "Rack20",
    "P335": "Rack21", "P333": "Rack22", "P331": "Rack23", "P329": "Rack24", "P327": "Rack25",
}

def get_rack_name(waypoint: str) -> str:
    """Get rack name from waypoint, or use waypoint as fallback."""
    return RACK_WAYPOINT_TO_NAME.get(waypoint, waypoint)


def create_sequential_workflow(robots: list, racks: list, manipulators: list, stations: list,
                               include_depalletize: bool = True, include_droprack: bool = False) -> dict:
    """
    Create a crossflow diagram for sequential robot operations.
    """
    if len(robots) != len(racks) or len(robots) != len(manipulators) or len(robots) != len(stations):
        raise ValueError("Number of robots, racks, manipulators, and stations must match")

    workflow_id = str(uuid.uuid4())[:8]

    if len(robots) == 1:
        return create_single_robot_workflow(robots[0], racks[0], manipulators[0], stations[0],
                                           workflow_id, include_depalletize, include_droprack)
    else:
        return create_multi_robot_workflow(robots, racks, manipulators, stations, workflow_id,
                                          include_depalletize, include_droprack)


def create_single_robot_workflow(robot: str, rack: str, manipulator: str, station: str,
                                  workflow_id: str, include_depalletize: bool = True,
                                  include_droprack: bool = False) -> tuple:
    """Create a sequential workflow for one robot."""

    ops = {}
    robot_nodes = []
    nodes = []

    # Step 1: Move to rack (MAPF)
    move_rack_id = str(uuid.uuid4())
    move_rack_buffer = str(uuid.uuid4())
    move_rack_task = str(uuid.uuid4())
    nodes.append({
        "node_id": move_rack_id,
        "buffer_id": move_rack_buffer,
        "task_id": move_rack_task,
        "step": "move_to_rack",
        "display": f"{robot} -> {rack}",
        "builder": "MapfReplaceNode",
        "config": {
            "asset_name": robot,
            "coordinates": rack,
            "task_type": "amr_mapf",
            "task_id": move_rack_task
        }
    })
    robot_nodes.append({"robot": robot, "step": "move_to_rack", "goal": rack, "task_id": move_rack_task, "task_type": "amr_mapf"})

    # Step 2: Lift rack (TransferNode via MQTT)
    liftrack_id = str(uuid.uuid4())
    liftrack_buffer = str(uuid.uuid4())
    liftrack_task = str(uuid.uuid4())
    nodes.append({
        "node_id": liftrack_id,
        "buffer_id": liftrack_buffer,
        "task_id": liftrack_task,
        "step": "liftrack",
        "display": f"{robot} liftrack",
        "builder": "TransferNode",
        "config": {
            "asset_name": robot,
            "station_name": robot,
            "task_id": liftrack_task,
            "task_type": "liftrack",
            "coordinates": rack
        }
    })
    robot_nodes.append({"robot": robot, "step": "liftrack", "goal": rack, "task_id": liftrack_task, "task_type": "liftrack"})

    # Step 3: Move to manipulator (MAPF)
    move_manip_id = str(uuid.uuid4())
    move_manip_buffer = str(uuid.uuid4())
    move_manip_task = str(uuid.uuid4())
    nodes.append({
        "node_id": move_manip_id,
        "buffer_id": move_manip_buffer,
        "task_id": move_manip_task,
        "step": "move_to_manip",
        "display": f"{robot} -> {manipulator}",
        "builder": "MapfReplaceNode",
        "config": {
            "asset_name": robot,
            "coordinates": manipulator,
            "task_type": "amr_mapf",
            "task_id": move_manip_task
        }
    })
    robot_nodes.append({"robot": robot, "step": "move_to_manip", "goal": manipulator, "task_id": move_manip_task, "task_type": "amr_mapf"})

    # Step 4: Depalletize (TransferNode via MQTT)
    if include_depalletize:
        depal_id = str(uuid.uuid4())
        depal_buffer = str(uuid.uuid4())
        depal_task = str(uuid.uuid4())
        nodes.append({
            "node_id": depal_id,
            "buffer_id": depal_buffer,
            "task_id": depal_task,
            "step": "depalletize",
            "display": f"{robot} depalletize @ {station}",
            "builder": "TransferNode",
            "config": {
                "asset_name": robot,
                "station_name": station,
                "task_id": depal_task,
                "task_type": "depalletize",
                "coordinates": manipulator
            }
        })
        robot_nodes.append({"robot": robot, "step": "depalletize", "goal": station, "task_id": depal_task, "task_type": "depalletize"})

    # Step 5: Drop rack (TransferNode via MQTT)
    if include_droprack:
        drop_id = str(uuid.uuid4())
        drop_buffer = str(uuid.uuid4())
        drop_task = str(uuid.uuid4())
        nodes.append({
            "node_id": drop_id,
            "buffer_id": drop_buffer,
            "task_id": drop_task,
            "step": "droprack",
            "display": f"{robot} droprack",
            "builder": "TransferNode",
            "config": {
                "asset_name": robot,
                "station_name": robot,
                "task_id": drop_task,
                "task_type": "droprack",
                "coordinates": manipulator
            }
        })
        robot_nodes.append({"robot": robot, "step": "droprack", "goal": manipulator, "task_id": drop_task, "task_type": "droprack"})

    # Build the ops chain
    for i, node in enumerate(nodes):
        ops[node["node_id"]] = {
            "type": "node",
            "builder": node["builder"],
            "next": node["buffer_id"],
            "display_text": node["display"],
            "config": node["config"]
        }

        ops[node["buffer_id"]] = {
            "type": "buffer"
        }

        # Add join to chain to next node (except for last)
        if i < len(nodes) - 1:
            join_id = str(uuid.uuid4())
            ops[join_id] = {
                "type": "join",
                "buffers": [node["buffer_id"]],
                "next": nodes[i + 1]["node_id"]
            }

    # Final join to terminate
    final_join_id = str(uuid.uuid4())
    ops[final_join_id] = {
        "type": "join",
        "buffers": [nodes[-1]["buffer_id"]],
        "next": {"builtin": "terminate"}
    }

    diagram = {
        "version": "0.1.0",
        "start": nodes[0]["node_id"],
        "ops": ops
    }

    schedule = {
        "id": f"urn:ngsi-ld:Schedule:seq-rack-manip-{workflow_id}",
        "type": "Schedule",
        "payload": diagram
    }

    return schedule, robot_nodes


def create_robot_branch(robot: str, rack: str, manipulator: str, station: str,
                        include_depalletize: bool, include_droprack: bool) -> tuple:
    """Create a sequential branch for one robot."""

    ops = {}
    robot_nodes = []
    nodes = []

    # Step 1: Move to rack (MAPF)
    move_rack_id = str(uuid.uuid4())
    move_rack_buffer = str(uuid.uuid4())
    move_rack_task = str(uuid.uuid4())
    nodes.append({
        "node_id": move_rack_id,
        "buffer_id": move_rack_buffer,
        "task_id": move_rack_task,
        "step": "move_to_rack",
        "display": f"{robot} -> {rack}",
        "builder": "MapfReplaceNode",
        "config": {
            "asset_name": robot,
            "coordinates": rack,
            "task_type": "amr_mapf",
            "task_id": move_rack_task
        }
    })
    robot_nodes.append({"robot": robot, "step": "move_to_rack", "goal": rack, "task_id": move_rack_task, "task_type": "amr_mapf"})

    # Step 2: Lift rack (TransferNode via MQTT)
    liftrack_id = str(uuid.uuid4())
    liftrack_buffer = str(uuid.uuid4())
    liftrack_task = str(uuid.uuid4())
    nodes.append({
        "node_id": liftrack_id,
        "buffer_id": liftrack_buffer,
        "task_id": liftrack_task,
        "step": "liftrack",
        "display": f"{robot} liftrack",
        "builder": "TransferNode",
        "config": {
            "asset_name": robot,
            "station_name": robot,
            "task_id": liftrack_task,
            "task_type": "liftrack",
            "coordinates": rack
        }
    })
    robot_nodes.append({"robot": robot, "step": "liftrack", "goal": rack, "task_id": liftrack_task, "task_type": "liftrack"})

    # Step 3: Move to manipulator (MAPF)
    move_manip_id = str(uuid.uuid4())
    move_manip_buffer = str(uuid.uuid4())
    move_manip_task = str(uuid.uuid4())
    nodes.append({
        "node_id": move_manip_id,
        "buffer_id": move_manip_buffer,
        "task_id": move_manip_task,
        "step": "move_to_manip",
        "display": f"{robot} -> {manipulator}",
        "builder": "MapfReplaceNode",
        "config": {
            "asset_name": robot,
            "coordinates": manipulator,
            "task_type": "amr_mapf",
            "task_id": move_manip_task
        }
    })
    robot_nodes.append({"robot": robot, "step": "move_to_manip", "goal": manipulator, "task_id": move_manip_task, "task_type": "amr_mapf"})

    # Step 4: Depalletize (TransferNode)
    if include_depalletize:
        depal_id = str(uuid.uuid4())
        depal_buffer = str(uuid.uuid4())
        depal_task = str(uuid.uuid4())
        nodes.append({
            "node_id": depal_id,
            "buffer_id": depal_buffer,
            "task_id": depal_task,
            "step": "depalletize",
            "display": f"{robot} depalletize @ {station}",
            "builder": "TransferNode",
            "config": {
                "asset_name": robot,
                "station_name": station,
                "task_id": depal_task,
                "task_type": "depalletize",
                "coordinates": manipulator
            }
        })
        robot_nodes.append({"robot": robot, "step": "depalletize", "goal": station, "task_id": depal_task, "task_type": "depalletize"})

    # Step 5: Drop rack (TransferNode via MQTT)
    if include_droprack:
        drop_id = str(uuid.uuid4())
        drop_buffer = str(uuid.uuid4())
        drop_task = str(uuid.uuid4())
        nodes.append({
            "node_id": drop_id,
            "buffer_id": drop_buffer,
            "task_id": drop_task,
            "step": "droprack",
            "display": f"{robot} droprack",
            "builder": "TransferNode",
            "config": {
                "asset_name": robot,
                "station_name": robot,
                "task_id": drop_task,
                "task_type": "droprack",
                "coordinates": manipulator
            }
        })
        robot_nodes.append({"robot": robot, "step": "droprack", "goal": manipulator, "task_id": drop_task, "task_type": "droprack"})

    # Build the ops chain
    for i, node in enumerate(nodes):
        ops[node["node_id"]] = {
            "type": "node",
            "builder": node["builder"],
            "next": node["buffer_id"],
            "display_text": node["display"],
            "config": node["config"]
        }

        ops[node["buffer_id"]] = {
            "type": "buffer"
        }

        if i < len(nodes) - 1:
            join_id = str(uuid.uuid4())
            ops[join_id] = {
                "type": "join",
                "buffers": [node["buffer_id"]],
                "next": nodes[i + 1]["node_id"]
            }

    start_node_id = nodes[0]["node_id"]
    end_buffer_id = nodes[-1]["buffer_id"]

    return ops, start_node_id, end_buffer_id, robot_nodes


def create_multi_robot_workflow(robots: list, racks: list, manipulators: list, stations: list,
                                workflow_id: str, include_depalletize: bool = True,
                                include_droprack: bool = False) -> tuple:
    """Create a parallel workflow where each branch is a sequential operation sequence."""

    fork_id = str(uuid.uuid4())
    final_join_id = str(uuid.uuid4())

    all_ops = {}
    branch_starts = []
    branch_ends = []
    all_robot_nodes = []

    for robot, rack, manipulator, station in zip(robots, racks, manipulators, stations):
        branch_ops, start_id, end_id, robot_nodes = create_robot_branch(
            robot, rack, manipulator, station, include_depalletize, include_droprack
        )
        all_ops.update(branch_ops)
        branch_starts.append(start_id)
        branch_ends.append(end_id)
        all_robot_nodes.extend(robot_nodes)

    all_ops[fork_id] = {
        "type": "fork_clone",
        "next": branch_starts
    }

    all_ops[final_join_id] = {
        "type": "join",
        "buffers": branch_ends,
        "next": {"builtin": "terminate"}
    }

    diagram = {
        "version": "0.1.0",
        "start": fork_id,
        "ops": all_ops
    }

    schedule = {
        "id": f"urn:ngsi-ld:Schedule:seq-rack-manip-{workflow_id}",
        "type": "Schedule",
        "payload": diagram
    }

    return schedule, all_robot_nodes


def send_workflow(schedule: dict, amqp_host='localhost', amqp_port=5672):
    """Send the workflow to the Task Orchestrator via AMQP."""

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=amqp_host, port=amqp_port)
    )
    channel = connection.channel()

    channel.exchange_declare(
        exchange='@RECEIVE@',
        exchange_type='fanout',
        durable=True
    )

    channel.basic_publish(
        exchange='@RECEIVE@',
        routing_key='',
        body=json.dumps(schedule),
        properties=pika.BasicProperties(
            content_type='application/json',
            delivery_mode=2
        )
    )

    connection.close()


def main():
    parser = argparse.ArgumentParser(
        description="Send sequential workflow: rack -> liftrack -> manipulator -> depalletize",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single robot - full sequence
  python3 send_sequential_workflow_rack_to_manipulator.py

  # Custom robot and waypoints
  python3 send_sequential_workflow_rack_to_manipulator.py \\
      --robots Manufacturer_5 --racks P63 --manipulators P501 --stations MANIP1

  # Skip depalletize step
  python3 send_sequential_workflow_rack_to_manipulator.py --no-depalletize

  # Include droprack at end
  python3 send_sequential_workflow_rack_to_manipulator.py --droprack

  # 3 robots in parallel
  python3 send_sequential_workflow_rack_to_manipulator.py \\
      --robots Manufacturer_2,Manufacturer_3,Manufacturer_4 \\
      --racks P63,P61,P59 \\
      --manipulators P433,P431,P433 \\
      --stations MANIP1,MANIP1,MANIP1

  # Dry-run to see JSON
  python3 send_sequential_workflow_rack_to_manipulator.py --dry-run

Node Builders:
  MapfReplaceNode - MAPF movement (amr_mapf)
  TransferNode    - MQTT transfer for liftrack, droprack, depalletize

Waypoint Reference:
  Racks Row 1:   P63 (Rack), P61 (Rack2), P59 (Rack3), P57 (Rack4), P55 (Rack5)
  Manipulator 1: P501 (station), P433/P431 (holding)
  Manipulator 2: P492 (station), P424/P422 (holding)

Valid robots: Manufacturer_2 - Manufacturer_25
Valid stations: MANIP1, MANIP2
"""
    )

    parser.add_argument('--robots', default='Manufacturer_2',
        help='Comma-separated robot IDs (default: Manufacturer_2)')
    parser.add_argument('--racks', default='P63',
        help='Comma-separated rack waypoints (default: P63)')
    parser.add_argument('--manipulators', default='P433',
        help='Comma-separated manipulator waypoints (default: P433)')
    parser.add_argument('--stations', default='MANIP1',
        help='Comma-separated station names for depalletize (default: MANIP1)')
    parser.add_argument('--no-depalletize', action='store_true',
        help='Skip the depalletize step')
    parser.add_argument('--droprack', action='store_true',
        help='Include droprack step at the end')
    parser.add_argument('--amqp-host', default='localhost',
        help='AMQP broker host (default: localhost)')
    parser.add_argument('--amqp-port', type=int, default=5672,
        help='AMQP broker port (default: 5672)')
    parser.add_argument('--dry-run', action='store_true',
        help='Print workflow JSON without sending')

    args = parser.parse_args()

    robots = [r.strip() for r in args.robots.split(',')]
    racks = [r.strip() for r in args.racks.split(',')]
    manipulators = [m.strip() for m in args.manipulators.split(',')]
    stations = [s.strip() for s in args.stations.split(',')]

    # Expand stations if only one provided for multiple robots
    if len(stations) == 1 and len(robots) > 1:
        stations = stations * len(robots)

    include_depalletize = not args.no_depalletize
    include_droprack = args.droprack

    if len(robots) != len(racks) or len(robots) != len(manipulators) or len(robots) != len(stations):
        print(f"Error: Counts must match - robots:{len(robots)}, racks:{len(racks)}, manipulators:{len(manipulators)}, stations:{len(stations)}")
        return 1

    print(f"\n=== Sequential Workflow: Rack -> Manipulator ({len(robots)} robot(s)) ===\n")

    schedule, robot_nodes = create_sequential_workflow(
        robots, racks, manipulators, stations,
        include_depalletize=include_depalletize,
        include_droprack=include_droprack
    )

    print(f"Schedule ID: {schedule['id']}")
    print(f"Timestamp:   {datetime.now().isoformat()}")
    print(f"Depalletize: {'Yes' if include_depalletize else 'No'}")
    print(f"Droprack:    {'Yes' if include_droprack else 'No'}")
    print()
    print("Operation Sequence:")

    current_robot = None
    for node in robot_nodes:
        if node['robot'] != current_robot:
            if current_robot is not None:
                print()
            current_robot = node['robot']
            print(f"  {node['robot']}:")
        task_type = node.get('task_type', 'unknown')
        print(f"    {node['step']:14} -> {node['goal']:10} [{task_type}] (task: {node['task_id'][:8]}...)")
    print()

    if args.dry_run:
        print("Workflow JSON (dry-run):")
        print(json.dumps(schedule, indent=2))
        return 0

    try:
        send_workflow(schedule, args.amqp_host, args.amqp_port)
        print(f"Workflow sent to AMQP broker at {args.amqp_host}:{args.amqp_port}")
        print()
        print("=== Next Steps ===")
        print("1. Check Rust Task Orchestrator logs:")
        print("   tail -f ~/IHI_PHASE2_FINAL_DEMO/docker_modules/rmf2_task_orchestrator/rust_orchestrator.log")
        print()
        print("2. Check active workflows:")
        print("   curl -s http://localhost:2727/workflow/get_workflows | jq")
        print()
        print("3. Check ADG executor:")
        print("   docker logs adg_executor --tail 30")
        return 0

    except pika.exceptions.AMQPConnectionError as e:
        print(f"Error: Failed to connect to AMQP broker at {args.amqp_host}:{args.amqp_port}")
        print(f"  {e}")
        return 1


if __name__ == "__main__":
    exit(main())
