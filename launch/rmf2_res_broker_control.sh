#!/bin/bash

# Get script directory and derive paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROS_INDUSTRIAL_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_DIR="$ROS_INDUSTRIAL_DIR/compose_files/rmf2_broker"
COMPOSE_FILE="$COMPOSE_DIR/iocs_compose.yaml"

# Build contexts in iocs_compose.yaml are relative to rmf2_broker_repo
PROJECT_DIR="$(dirname "$ROS_INDUSTRIAL_DIR")/rmf2_broker_repo"

# Usage: ./rmf2_res_broker_control.sh [start|stop]

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

# Check if compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Error: Compose file '$COMPOSE_FILE' does not exist."
    exit 1
fi

# Check if project directory exists (needed for build contexts)
if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: rmf2_broker_repo directory '$PROJECT_DIR' does not exist."
    exit 1
fi

# Execute Docker Compose command
if [ "$COMMAND" == "start" ]; then
    docker compose -f "$COMPOSE_FILE" --project-directory "$PROJECT_DIR" up -d &
elif [ "$COMMAND" == "stop" ]; then
    docker compose -f "$COMPOSE_FILE" --project-directory "$PROJECT_DIR" down
fi
