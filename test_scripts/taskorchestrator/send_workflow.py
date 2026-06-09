#!/usr/bin/env python3
"""Send the two rack-workflow diagrams to the Task Orchestrator over AMQP.

The TO consumes from the fanout exchange `@RECEIVE@` (see config.toml /
amqp/src/amqp.rs). It only acts on messages whose `type` == "Schedule",
and it parses the diagram out of the `payload` field.

Just run it (no arguments needed):
    python3 send_workflow.py [--host HOST] [--port PORT]

Both diagrams are published as independent Schedule workflows.
"""
import argparse
import json
import os
import sys

import pika

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXCHANGE = "@RECEIVE@"  # fanout exchange the TO consumer binds to

# Diagrams to send, with the workflow task id used for each.
WORKFLOWS = [
    ("rack_workflow_1.json", "urn:ngsild:Task:rack_wf1"),
    ("rack_workflow_2.json", "urn:ngsild:Task:rack_wf2"),
]


def send(channel, diagram_file: str, task_id: str) -> None:
    path = os.path.join(SCRIPT_DIR, diagram_file)
    with open(path) as f:
        diagram = json.load(f)

    # WorkflowExecuteMessage envelope. The TO reads the diagram from `payload`.
    message = {"id": task_id, "type": "Schedule", "payload": diagram}
    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key="",  # ignored by fanout
        body=json.dumps(message).encode(),
        properties=pika.BasicProperties(content_type="application/json"),
    )
    print(f"Sent '{task_id}' ({diagram_file}, {len(diagram['ops'])} ops)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("AMQP_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AMQP_PORT", "5672")))
    args = parser.parse_args()

    conn = pika.BlockingConnection(pika.ConnectionParameters(host=args.host, port=args.port))
    channel = conn.channel()
    # Match the consumer-side declaration (fanout, durable) so this works
    # whether or not the TO has started yet.
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="fanout", durable=True)

    for diagram_file, task_id in WORKFLOWS:
        send(channel, diagram_file, task_id)

    conn.close()
    print(f"Done -> exchange '{EXCHANGE}' at {args.host}:{args.port}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
