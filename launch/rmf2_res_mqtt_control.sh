#!/bin/bash

# Get script directory and derive paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/../compose_files/rmf2_broker"

# Usage: ./rmf2_res_mqtt_control.sh [start|stop]

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
    docker compose -f "$COMPOSE_DIR/compose.yml" up -d
elif [ "$COMMAND" == "stop" ]; then
    docker compose -f "$COMPOSE_DIR/compose.yml" down
fi
