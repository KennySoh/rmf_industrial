#!/bin/bash

# Get script directory and derive paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROS_INDUSTRIAL_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_DIR="$SCRIPT_DIR/../compose_files/rmf2_broker"
LOGDIR="$ROS_INDUSTRIAL_DIR/logs/vda5050/$(date '+%Y-%m-%d_%H-%M-%S')"

# Usage: ./rmf2_res_vda5050_control.sh [start|stop]

mkdir -p "$LOGDIR"

usage() {
    echo "Usage: $0 [start|stop]"
    exit 1
}

if [ $# -ne 1 ]; then
    usage
fi

COMMAND=$1

if [[ "$COMMAND" != "start" && "$COMMAND" != "stop" ]]; then
    usage
fi

if [ ! -d "$COMPOSE_DIR" ]; then
    echo "Error: Directory '$COMPOSE_DIR' does not exist."
    exit 1
fi

if [ "$COMMAND" == "start" ]; then
    docker compose -f "$COMPOSE_DIR/vda5050_fiware.yml" up -d
    echo "VDA5050 started. Logs: docker logs vda5050_fiware"
elif [ "$COMMAND" == "stop" ]; then
    docker compose -f "$COMPOSE_DIR/vda5050_fiware.yml" down
fi
