#!/bin/bash
#
# Control script for Unified MAPF Container
# Replaces: mapf_solver, adg_executor, mapf_mrs, movement_request_server,
#           fiware_map_server, load_maps
#
# Usage: ./rmf2_unified_mapf_control.sh [start|stop|status|logs|build]
#

# Get script directory and derive paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROS_INDUSTRIAL_DIR="$(dirname "$SCRIPT_DIR")"
UNIFIED_MAPF_FOLDER="$ROS_INDUSTRIAL_DIR/compose_files/mapf_unified"
LOGDIR="$ROS_INDUSTRIAL_DIR/logs/unified_mapf/$(date '+%Y-%m-%d_%H-%M-%S')"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    echo "Usage: $0 [start|stop|status|logs|build]"
    echo ""
    echo "Commands:"
    echo "  start   - Start unified MAPF container"
    echo "  stop    - Stop unified MAPF container"
    echo "  status  - Show container status"
    echo "  logs    - Tail container logs"
    echo "  build   - Build the unified image"
    exit 1
}

check_image_exists() {
    if ! docker images | grep -q "mapf_unified"; then
        echo -e "${YELLOW}[WARN]${NC} mapf_unified image not found. Building..."
        build_image
    fi
}

build_image() {
    echo -e "${GREEN}[INFO]${NC} Building unified MAPF image..."
    cd "$UNIFIED_MAPF_FOLDER"
    docker build -t mapf_unified:latest .
    echo -e "${GREEN}[OK]${NC} Build complete"
}

start_container() {
    echo -e "${GREEN}[INFO]${NC} Starting Unified MAPF Container..."

    # Check if already running
    if docker ps --format '{{.Names}}' | grep -q "mapf_unified"; then
        echo -e "${YELLOW}[WARN]${NC} mapf_unified is already running"
        return 0
    fi

    # Stop old separate containers if running
    echo -e "${GREEN}[INFO]${NC} Stopping any old separate MAPF containers..."
    for container in mapf_solver adg_executor mapf_mrs movement_request_server fiware_map load_map; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            docker rm -f $container >/dev/null 2>&1 || true
        fi
    done

    # Check if image exists
    check_image_exists

    # Create logs directory
    mkdir -p "$LOGDIR"
    mkdir -p "$UNIFIED_MAPF_FOLDER/logs"

    # Start with docker compose
    cd "$UNIFIED_MAPF_FOLDER"
    docker compose up -d 2>&1 | tee -a "$LOGDIR/startup.log"

    # Wait for services to be ready
    echo -e "${GREEN}[INFO]${NC} Waiting for services to initialize..."
    sleep 10

    # Check if running
    if docker ps --format '{{.Names}}' | grep -q "mapf_unified"; then
        echo -e "${GREEN}[OK]${NC} Unified MAPF container started successfully"
        echo ""
        echo "Services running inside container:"
        docker exec mapf_unified supervisorctl status 2>/dev/null || echo "  (supervisord still starting...)"
        echo ""
        echo "Ports exposed:"
        echo "  - 7073  (fiware_map_server)"
        echo "  - 8888  (mapf_solver)"
        echo "  - 6333  (adg_executor state server)"
        echo "  - 1932  (adg_executor MQTT)"
        echo "  - 1933  (mapf_mrs MQTT)"
        echo "  - 8009  (movement_request_server)"
    else
        echo -e "${RED}[ERROR]${NC} Failed to start unified MAPF container"
        echo "Check logs: docker logs mapf_unified"
        return 1
    fi
}

stop_container() {
    echo -e "${GREEN}[INFO]${NC} Stopping Unified MAPF Container..."

    cd "$UNIFIED_MAPF_FOLDER"
    docker compose down 2>/dev/null || true

    # Also stop any remaining related containers
    for container in mapf_unified fiware_map load_map; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            docker rm -f $container >/dev/null 2>&1 || true
        fi
    done

    echo -e "${GREEN}[OK]${NC} Unified MAPF container stopped"
}

show_status() {
    echo -e "${GREEN}=== Unified MAPF Container Status ===${NC}"
    echo ""

    if docker ps --format '{{.Names}}' | grep -q "mapf_unified"; then
        echo -e "Container: ${GREEN}RUNNING${NC}"
        echo ""
        echo "Internal services:"
        docker exec mapf_unified supervisorctl status 2>/dev/null || echo "  Unable to query supervisord"
        echo ""
        echo "Port bindings:"
        docker port mapf_unified 2>/dev/null || echo "  No ports mapped"
    else
        echo -e "Container: ${RED}STOPPED${NC}"
    fi

    echo ""
    echo "Related containers:"
    for container in mapf_unified fiware_map load_map mapf_solver adg_executor mapf_mrs movement_request_server; do
        if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            echo -e "  ${GREEN}[RUNNING]${NC} $container"
        elif docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            echo -e "  ${YELLOW}[STOPPED]${NC} $container"
        fi
    done
}

show_logs() {
    if docker ps --format '{{.Names}}' | grep -q "mapf_unified"; then
        echo -e "${GREEN}[INFO]${NC} Tailing unified MAPF logs (Ctrl+C to exit)..."
        docker exec mapf_unified tail -f /var/log/supervisor/*.log
    else
        echo -e "${RED}[ERROR]${NC} Container not running"
        exit 1
    fi
}

# Main
if [ $# -lt 1 ]; then
    usage
fi

COMMAND=$1

case "$COMMAND" in
    start)
        start_container
        ;;
    stop)
        stop_container
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    build)
        build_image
        ;;
    *)
        usage
        ;;
esac
