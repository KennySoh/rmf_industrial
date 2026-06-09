#!/bin/bash
#
# IHI Phase 2 Final Demo - Environment Cleanup Script
# This script stops all services in reverse order of startup
#
# Usage:
#   ./stop_environment.sh           # Stop everything
#   ./stop_environment.sh --step N  # Stop from step N onwards
#   ./stop_environment.sh --only N  # Stop only step N
#   ./stop_environment.sh --list    # List all steps
#   ./stop_environment.sh --force   # Force kill everything
#

set -e

# Get script directory and derive paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROS_INDUSTRIAL_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_DIR="$ROS_INDUSTRIAL_DIR/compose_files/rmf2_broker"
INTERFACE_PORT=8083

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "\n${RED}=== STEP $1: $2 ===${NC}"; }

# Check if a port is in use
port_in_use() {
    lsof -i :$1 >/dev/null 2>&1
}

# Check if interface is available for API calls
interface_available() {
    curl -s -o /dev/null -w "%{http_code}" "http://localhost:$INTERFACE_PORT/iocs_heartbeat" 2>/dev/null | grep -qE "200|503"
}

# Step functions (reverse order of startup)
step1_stop_devices() {
    log_step 1 "Stopping Devices (VDA5050)"

    if interface_available; then
        log_info "Calling POST /device_offboard..."
        curl -s -X POST "http://localhost:$INTERFACE_PORT/device_offboard" || true
        echo ""
    else
        log_warn "Dashboard interface not available, stopping directly..."
        "$SCRIPT_DIR/rmf2_res_vda5050_control.sh" stop 2>/dev/null || true
    fi

    # Wait for containers to stop
    sleep 2
    log_success "Devices stopped"
}

step2_stop_services() {
    log_step 2 "Stopping Services (MAPF, TTE, RTS, Task Orchestrator)"

    # Stop Task Orchestrator container
    if docker ps --format '{{.Names}}' | grep -q "task_orchestrator"; then
        log_info "Stopping Task Orchestrator container..."
        docker stop task_orchestrator 2>/dev/null || true
        docker rm task_orchestrator 2>/dev/null || true
    fi

    # Check if unified MAPF container is running
    if docker ps --format '{{.Names}}' | grep -q "mapf_unified"; then
        log_info "Stopping unified MAPF container..."
        "$SCRIPT_DIR/rmf2_unified_mapf_control.sh" stop 2>/dev/null || true
    fi

    if interface_available; then
        log_info "Calling POST /service_offboard..."
        curl -s -X POST "http://localhost:$INTERFACE_PORT/service_offboard" || true
        echo ""
    else
        log_warn "Dashboard interface not available, stopping directly..."
        # Stop individual MAPF containers
        for container in mapf_solver adg_executor mapf_mrs movement_request_server fiware_map; do
            docker rm -f "$container" 2>/dev/null || true
        done
    fi

    # Also kill any remaining scheduler processes
    pkill -f "rmf2_scheduler_server" 2>/dev/null || true
    pkill -f "rmf2_task_estimator_server" 2>/dev/null || true

    sleep 2
    log_success "Services stopped"
}

step3_stop_simulation() {
    log_step 3 "Stopping Simulation (tmuxinator)"

    if interface_available; then
        log_info "Calling POST /stop_sim..."
        curl -s -X POST "http://localhost:$INTERFACE_PORT/stop_sim" || true
        echo ""
    else
        log_warn "Dashboard interface not available, stopping directly..."
        tmuxinator stop ihi_p2_final_demo 2>/dev/null || true
    fi

    # Kill tmux session if still exists
    tmux kill-session -t ihi_phase_2_final_demo 2>/dev/null || true
    tmux kill-session -t ihi_p2_final_demo 2>/dev/null || true

    sleep 2
    log_success "Simulation stopped"
}

step4_stop_broker() {
    log_step 4 "Stopping Broker (IOCS)"

    if interface_available; then
        log_info "Calling POST /stop_iocs..."
        curl -s -X POST "http://localhost:$INTERFACE_PORT/stop_iocs" || true
        echo ""
    else
        log_warn "Dashboard interface not available, stopping directly..."
        "$SCRIPT_DIR/rmf2_res_broker_control.sh" stop 2>/dev/null || true
        "$SCRIPT_DIR/rmf2_res_mqtt_control.sh" stop 2>/dev/null || true
    fi

    # Stop IOCS docker compose (iocs_compose.yaml)
    log_info "Stopping IOCS containers via docker compose..."
    local IOCS_COMPOSE="$COMPOSE_DIR/iocs_compose.yaml"
    local PROJECT_DIR="$(dirname "$ROS_INDUSTRIAL_DIR")/rmf2_broker_repo"
    if [ -f "$IOCS_COMPOSE" ] && [ -d "$PROJECT_DIR" ]; then
        docker compose -f "$IOCS_COMPOSE" --project-directory "$PROJECT_DIR" down 2>/dev/null || true
    fi

    # Also try the old compose.yml for backwards compatibility
    docker compose -f "$COMPOSE_DIR/compose.yml" down 2>/dev/null || true

    # Force remove any named IOCS containers that might be orphaned
    log_info "Cleaning up named IOCS containers..."
    local IOCS_CONTAINERS="monitor evt_mgr rmf-logger orion it_connector rmf_proxy rproxy rmf-swagger rmf-mongodb"
    for container in $IOCS_CONTAINERS; do
        docker rm -f "$container" 2>/dev/null || true
    done

    # Also remove containers with rmf2_broker_repo prefix
    docker ps -aq --filter "name=rmf2_broker_repo" 2>/dev/null | xargs -r docker rm -f 2>/dev/null || true

    # Stop mosquitto if running
    docker rm -f mosquitto 2>/dev/null || true

    sleep 3
    log_success "Broker stopped"
}

step5_stop_interface() {
    log_step 5 "Stopping Dashboard Interface"

    # Kill by PID file if exists
    if [ -f /tmp/dashboard_interface.pid ]; then
        pid=$(cat /tmp/dashboard_interface.pid)
        if kill -0 $pid 2>/dev/null; then
            log_info "Killing dashboard interface (PID: $pid)..."
            kill $pid 2>/dev/null || true
            sleep 1
            kill -9 $pid 2>/dev/null || true
        fi
        rm -f /tmp/dashboard_interface.pid
    fi

    # Also kill by process name
    pkill -f "dashboard_interface.py" 2>/dev/null || true

    log_success "Dashboard interface stopped"
}

step6_stop_dashboard() {
    log_step 6 "Stopping Dashboard Frontend"

    # Kill by PID file if exists
    if [ -f /tmp/dashboard_frontend.pid ]; then
        pid=$(cat /tmp/dashboard_frontend.pid)
        if kill -0 $pid 2>/dev/null; then
            log_info "Killing dashboard frontend (PID: $pid)..."
            kill $pid 2>/dev/null || true
            sleep 1
            kill -9 $pid 2>/dev/null || true
        fi
        rm -f /tmp/dashboard_frontend.pid
    fi

    # Kill any node/vite processes on port 3000
    if port_in_use 3000; then
        log_info "Killing processes on port 3000..."
        fuser -k 3000/tcp 2>/dev/null || true
    fi

    # Kill pnpm/vite processes related to dashboard
    pkill -f "vite.*dashboard" 2>/dev/null || true
    pkill -f "pnpm.*start" 2>/dev/null || true

    log_success "Dashboard frontend stopped"
}

# Force kill everything
force_cleanup() {
    log_step "X" "Force Cleanup - Killing Everything"

    log_info "Stopping all Docker containers related to the demo..."

    # Stop IOCS compose stack (use correct file)
    local IOCS_COMPOSE="$COMPOSE_DIR/iocs_compose.yaml"
    local PROJECT_DIR="$(dirname "$ROS_INDUSTRIAL_DIR")/rmf2_broker_repo"
    if [ -f "$IOCS_COMPOSE" ] && [ -d "$PROJECT_DIR" ]; then
        docker compose -f "$IOCS_COMPOSE" --project-directory "$PROJECT_DIR" down 2>/dev/null || true
    fi
    docker compose -f "$COMPOSE_DIR/compose.yml" down 2>/dev/null || true
    docker compose -f "$COMPOSE_DIR/vda5050_fiware.yml" down 2>/dev/null || true

    # Stop all MAPF-related containers directly
    log_info "Removing MAPF containers..."
    for container in mapf_unified mapf_solver adg_executor mapf_mrs movement_request_server fiware_map load_map vda5050_fiware task_orchestrator; do
        docker rm -f "$container" 2>/dev/null || true
    done

    # Stop all IOCS containers by name
    log_info "Removing IOCS containers..."
    for container in monitor evt_mgr rmf-logger orion it_connector rmf_proxy rproxy rmf-swagger rmf-mongodb mosquitto; do
        docker rm -f "$container" 2>/dev/null || true
    done

    # Remove containers with rmf2_broker_repo prefix (postgres, redis, rabbitmq, scorpio, etc.)
    log_info "Removing rmf2_broker_repo containers..."
    docker ps -aq --filter "name=rmf2_broker_repo" 2>/dev/null | xargs -r docker rm -f 2>/dev/null || true

    log_info "Killing related processes..."
    pkill -f "rmf2_scheduler_server" 2>/dev/null || true
    pkill -f "rmf2_task_estimator_server" 2>/dev/null || true
    pkill -f "dashboard_interface.py" 2>/dev/null || true
    pkill -f "task_orchestrator" 2>/dev/null || true
    pkill -f "vite.*dashboard" 2>/dev/null || true

    log_info "Killing tmux sessions..."
    tmux kill-session -t ihi_phase_2_final_demo 2>/dev/null || true
    tmux kill-session -t ihi_p2_final_demo 2>/dev/null || true

    log_info "Freeing ports..."
    for port in 3000 8083 8089 8090; do
        fuser -k $port/tcp 2>/dev/null || true
    done

    # Clean up PID files
    rm -f /tmp/dashboard_frontend.pid /tmp/dashboard_interface.pid

    log_success "Force cleanup completed"
}

# Print step list
print_steps() {
    echo "Cleanup steps (reverse order of startup):"
    echo "  1. Stop Devices (VDA5050)"
    echo "  2. Stop Services (MAPF, TTE, RTS)"
    echo "  3. Stop Simulation (tmuxinator)"
    echo "  4. Stop Broker (IOCS + Docker containers)"
    echo "  5. Stop Dashboard Interface"
    echo "  6. Stop Dashboard Frontend"
    echo ""
    echo "Use --force to kill everything without graceful shutdown"
}

# Run all steps from a given starting point
run_from_step() {
    local start=$1

    [ $start -le 1 ] && step1_stop_devices
    [ $start -le 2 ] && step2_stop_services
    [ $start -le 3 ] && step3_stop_simulation
    [ $start -le 4 ] && step4_stop_broker
    [ $start -le 5 ] && step5_stop_interface
    [ $start -le 6 ] && step6_stop_dashboard
}

# Run a single step
run_single_step() {
    case $1 in
        1) step1_stop_devices ;;
        2) step2_stop_services ;;
        3) step3_stop_simulation ;;
        4) step4_stop_broker ;;
        5) step5_stop_interface ;;
        6) step6_stop_dashboard ;;
        *) log_error "Invalid step number: $1"; exit 1 ;;
    esac
}

# Print status summary
print_status() {
    echo -e "\n${GREEN}=== ENVIRONMENT STATUS ===${NC}"

    # Check ports
    echo -e "\nPorts:"
    for port in 3000 8083 8089 5672 15672 8000 9090; do
        if port_in_use $port; then
            echo -e "  ${RED}[STILL ACTIVE]${NC} Port $port"
        else
            echo -e "  ${GREEN}[DOWN]${NC} Port $port"
        fi
    done

    # Check Docker containers
    echo -e "\nMAPF containers:"

    # Check unified container first
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "mapf_unified"; then
        echo -e "  ${RED}[STILL RUNNING]${NC} mapf_unified"
    else
        echo -e "  ${GREEN}[STOPPED]${NC} mapf_unified"
    fi

    for container in vda5050_fiware adg_executor mapf_solver fiware_map task_orchestrator; do
        if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${container}$"; then
            echo -e "  ${RED}[STILL RUNNING]${NC} $container"
        else
            echo -e "  ${GREEN}[STOPPED]${NC} $container"
        fi
    done

    echo -e "\nIOCS containers:"
    for container in monitor evt_mgr rmf-logger orion it_connector rmf_proxy rproxy rmf-swagger rmf-mongodb mosquitto; do
        if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${container}$"; then
            echo -e "  ${RED}[STILL RUNNING]${NC} $container"
        else
            echo -e "  ${GREEN}[STOPPED]${NC} $container"
        fi
    done

    # Check rmf2_broker_repo containers (rabbitmq, redis, postgres, scorpio)
    local broker_containers=$(docker ps --format '{{.Names}}' 2>/dev/null | grep "rmf2_broker_repo" || true)
    if [ -n "$broker_containers" ]; then
        echo -e "\nBroker infrastructure:"
        echo "$broker_containers" | while read c; do
            echo -e "  ${RED}[STILL RUNNING]${NC} $c"
        done
    fi

    # Check tmux
    echo -e "\nTmux sessions:"
    if tmux list-sessions 2>/dev/null | grep -qE "ihi_phase_2|ihi_p2"; then
        tmux list-sessions 2>/dev/null | grep -E "ihi_phase_2|ihi_p2"
    else
        echo "  No IHI tmux sessions running"
    fi
}

# Main
main() {
    echo -e "${RED}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║       IHI Phase 2 Final Demo - Environment Cleanup       ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    case "${1:-}" in
        --list|-l)
            print_steps
            ;;
        --step|-s)
            if [ -z "${2:-}" ]; then
                log_error "Please specify step number"
                exit 1
            fi
            run_from_step $2
            print_status
            ;;
        --only|-o)
            if [ -z "${2:-}" ]; then
                log_error "Please specify step number"
                exit 1
            fi
            run_single_step $2
            ;;
        --force|-f)
            force_cleanup
            print_status
            ;;
        --status)
            print_status
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  (no args)     Stop everything gracefully (steps 1-6)"
            echo "  --step N      Stop from step N onwards"
            echo "  --only N      Stop only step N"
            echo "  --force       Force kill everything without graceful shutdown"
            echo "  --list        List all steps"
            echo "  --status      Show current environment status"
            echo "  --help        Show this help"
            echo ""
            print_steps
            ;;
        "")
            run_from_step 1
            print_status
            echo -e "\n${GREEN}Environment cleanup complete!${NC}"
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
}

main "$@"
