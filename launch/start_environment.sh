#!/bin/bash
#
# IHI Phase 2 Final Demo - Environment Startup Script
# This script automates the full startup sequence for debugging
#
# Usage:
#   ./start_environment.sh                    # Run full startup (separate MAPF containers)
#   ./start_environment.sh --unified-mapf     # Run with unified MAPF container
#   ./start_environment.sh --no-sim           # Skip simulation and tasks (steps 4,8)
#   ./start_environment.sh --init-script X    # Use specified init script
#   ./start_environment.sh --step N           # Run from step N onwards
#   ./start_environment.sh --only N           # Run only step N
#   ./start_environment.sh --list             # List all steps
#   ./start_environment.sh --status           # Show current status
#

set -e

# Get script directory and derive paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROS_INDUSTRIAL_DIR="$(dirname "$SCRIPT_DIR")"
INTERFACE_PORT=8083
IOCS_CHECK_TIMEOUT=120  # seconds to wait for IOCS heartbeat
VDA5050_CHECK_TIMEOUT=60  # seconds to wait for robot status
SKIP_SIMULATION=false  # Set to true to skip simulation (Step 4) and send tasks (Step 8)
USE_UNIFIED_MAPF=false  # Set to true to use unified MAPF container instead of separate containers
#INIT_SCRIPT="send_init_warehouse_v2.sh"  # Init script to use (map-specific)
INIT_SCRIPT="send_init_warehouse_os_setup.sh"  # Init script to use (map-specific)
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
log_step() { echo -e "\n${GREEN}=== STEP $1: $2 ===${NC}"; }

# Check if a port is in use (works with Docker ports)
port_in_use() {
    # Try ss first (works with Docker), fallback to lsof
    ss -tlnp 2>/dev/null | grep -q ":$1 " || lsof -i :$1 >/dev/null 2>&1
}

# Wait for a port to become available
wait_for_port() {
    local port=$1
    local timeout=$2
    local elapsed=0

    log_info "Waiting for port $port to be available..."
    while ! port_in_use $port; do
        sleep 1
        elapsed=$((elapsed + 1))
        if [ $elapsed -ge $timeout ]; then
            log_error "Timeout waiting for port $port"
            return 1
        fi
    done
    log_success "Port $port is now available"
}

# Wait for HTTP endpoint to return 200
wait_for_endpoint() {
    local url=$1
    local timeout=$2
    local elapsed=0

    log_info "Waiting for $url to respond..."
    while true; do
        if curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q "200"; then
            log_success "$url is responding"
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
        if [ $elapsed -ge $timeout ]; then
            log_error "Timeout waiting for $url"
            return 1
        fi
        echo -n "."
    done
}

# Check vda5050_fiware container for robot status
check_vda5050_robots() {
    local timeout=$1
    local elapsed=0

    log_info "Checking vda5050_fiware for robot status..."
    while true; do
        # Check if container is running
        if ! docker ps --format '{{.Names}}' | grep -q "vda5050_fiware"; then
            log_warn "vda5050_fiware container not running yet..."
        else
            # Check logs for robot status messages
            robot_count=$(docker logs vda5050_fiware 2>&1 | grep -c "state" 2>/dev/null || echo "0")
            robot_count=$(echo "$robot_count" | tr -d '[:space:]')
            if [ "${robot_count:-0}" -gt 0 ] 2>/dev/null; then
                log_success "Found $robot_count robot state messages in vda5050_fiware"
                docker logs vda5050_fiware 2>&1 | tail -10
                return 0
            fi
        fi

        sleep 3
        elapsed=$((elapsed + 3))
        if [ $elapsed -ge $timeout ]; then
            log_warn "Timeout waiting for robot status (continuing anyway)"
            return 0
        fi
        echo -n "."
    done
}

# Cleanup function to ensure fresh containers and state
cleanup_old_containers() {
    log_info "Cleaning up old containers and state for fresh start..."

    # List of container name patterns to remove (includes unified container and orchestrator)
    local patterns="vda5050 mapf adg fiware rmf mosquitto orion movement_request load_map task_orchestrator"

    for pattern in $patterns; do
        local containers=$(docker ps -aq --filter "name=$pattern" 2>/dev/null)
        if [ -n "$containers" ]; then
            docker rm -f $containers >/dev/null 2>&1 || true
        fi
    done

    # Explicitly remove unified container if exists
    docker rm -f mapf_unified >/dev/null 2>&1 || true

    # Clear stale job completion state
    > "$ROS_INDUSTRIAL_DIR/completed_jobs.txt" 2>/dev/null || true

    log_success "Old containers and state cleared"
}

# Step functions
step1_start_dashboard() {
    log_step 1 "Starting Dashboard Frontend"

    if port_in_use 3000; then
        log_warn "Port 3000 already in use, dashboard may already be running"
        return 0
    fi

    # Dashboard is optional - skip if not found
    log_warn "Dashboard frontend not included in ros_industrial_demo"
    log_info "Start dashboard separately if needed"
    return 0
}

step2_start_interface() {
    log_step 2 "Starting Dashboard Interface"

    if port_in_use $INTERFACE_PORT; then
        log_warn "Port $INTERFACE_PORT already in use, interface may already be running"
        return 0
    fi

    log_info "Starting dashboard_interface.py in background..."
    nohup python3 "$SCRIPT_DIR/dashboard_interface.py" > /tmp/dashboard_interface.log 2>&1 &
    echo $! > /tmp/dashboard_interface.pid

    wait_for_port $INTERFACE_PORT 30
    log_success "Dashboard interface started (PID: $(cat /tmp/dashboard_interface.pid))"
}

step3_start_broker() {
    log_step 3 "Starting Broker (IOCS)"

    log_info "Calling POST /start_iocs..."
    curl -s -X POST "http://localhost:$INTERFACE_PORT/start_iocs"
    echo ""

    log_info "Waiting for IOCS status endpoint (port 8000) to respond..."
    wait_for_endpoint "http://localhost:8000/status" $IOCS_CHECK_TIMEOUT

    log_success "Broker started and IOCS is healthy"
}

step4_start_simulation() {
    log_step 4 "Starting Simulation"

    if [ "$SKIP_SIMULATION" = true ]; then
        log_warn "SKIP_SIMULATION=true - Skipping simulation startup"
        log_info "Assuming simulation is running separately"
        return 0
    fi

    local sim_script="$ROS_INDUSTRIAL_DIR/../simulation/RMF2_new_sim.sh"

    if [ ! -x "$sim_script" ]; then
        log_error "Simulation script not found or not executable: $sim_script"
        return 1
    fi

    log_info "Launching RMF2 simulation: $sim_script"
    nohup "$sim_script" > /tmp/rmf2_new_sim.log 2>&1 &
    echo $! > /tmp/rmf2_new_sim.pid

    # Give the simulation time to start
    log_info "Waiting for simulation to initialize..."
    sleep 10

    local sim_pid
    sim_pid=$(cat /tmp/rmf2_new_sim.pid 2>/dev/null)
    if [ -n "$sim_pid" ] && kill -0 "$sim_pid" 2>/dev/null; then
        log_success "Simulation started (PID: $sim_pid, log: /tmp/rmf2_new_sim.log)"
    else
        log_warn "Could not verify simulation process (check /tmp/rmf2_new_sim.log)"
    fi
}

step5_start_services() {
    log_step 5 "Starting Services (MAPF, TTE, RTS, Task Orchestrator)"

    if [ "$USE_UNIFIED_MAPF" = true ]; then
        log_info "Using UNIFIED MAPF container..."

        # Start unified MAPF container directly
        "$SCRIPT_DIR/rmf2_unified_mapf_control.sh" start

        # Start TTE and RTS separately (not part of unified container)
        # TODO: Re-enable when modules are available
        # log_info "Starting TTE..."
        # "$SCRIPT_DIR/rmf2_tte_control.sh" start >/dev/null 2>&1 &

        # log_info "Starting RTS Scheduler..."
        # "$SCRIPT_DIR/rmf2_rts_control.sh" start &
    else
        log_info "Using SEPARATE MAPF containers..."
        log_info "Calling POST /service_onboard..."
        curl -s -X POST "http://localhost:$INTERFACE_PORT/service_onboard"
        echo ""
    fi

    # Start Task Orchestrator (Rust)
    log_info "Starting Task Orchestrator..."
    if [ -x "$SCRIPT_DIR/task_orchestrator_control.sh" ]; then
        "$SCRIPT_DIR/task_orchestrator_control.sh" start
    else
        log_warn "task_orchestrator_control.sh not found, skipping Task Orchestrator"
    fi

    # Wait for RTS scheduler to be available
    # TODO: Re-enable when modules are available
    # log_info "Waiting for RTS Scheduler (port 8089)..."
    # wait_for_port 8089 60

    # Wait for MAPF solver to be available
    # Note: Unified container needs more time to start all services (~90-120s)
    log_info "Waiting for MAPF Solver (port 8888)..."
    if [ "$USE_UNIFIED_MAPF" = true ]; then
        wait_for_port 8888 120
    else
        wait_for_port 8888 60
    fi

    # Wait for Task Orchestrator to be available
    log_info "Waiting for Task Orchestrator (port 2727)..."
    wait_for_port 2727 60 || log_warn "Task Orchestrator not responding (may not be built)"

    log_success "Services started"
}

step6_start_devices() {
    log_step 6 "Starting Devices (VDA5050)"

    log_info "Calling POST /device_onboard..."
    curl -s -X POST "http://localhost:$INTERFACE_PORT/device_onboard"
    echo ""

    # Check vda5050_fiware for robot status
    check_vda5050_robots $VDA5050_CHECK_TIMEOUT

    log_success "Devices started"
}

step7_init_system() {
    log_step 7 "Initializing System"

    log_info "Running init script: $INIT_SCRIPT"
    if [ -x "$SCRIPT_DIR/$INIT_SCRIPT" ]; then
        "$SCRIPT_DIR/$INIT_SCRIPT"
    else
        log_error "Init script not found or not executable: $SCRIPT_DIR/$INIT_SCRIPT"
        return 1
    fi

    # Give init script time to complete
    sleep 5

    log_success "System initialized"
}

step8_send_tasks() {
    log_step 8 "Sending Scheduled Tasks"

    if [ "$SKIP_SIMULATION" = true ]; then
        log_warn "SKIP_SIMULATION=true - Skipping task sending"
        log_info "Tasks should be sent manually when ready"
        return 0
    fi

    log_info "Calling POST /send_task..."
    curl -s -X POST "http://localhost:$INTERFACE_PORT/send_task"
    echo ""

    # Give time for tasks to be sent
    sleep 3

    log_success "Tasks sent to scheduler"
}

# Print step list
print_steps() {
    echo "Available steps:"
    echo "  1. Start Dashboard Frontend (pnpm start)"
    echo "  2. Start Dashboard Interface (dashboard_interface.py)"
    echo "  3. Start Broker (IOCS) - waits for heartbeat"
    echo "  4. Start Simulation (tmuxinator)"
    echo "  5. Start Services (MAPF, TTE, RTS, Task Orchestrator)"
    echo "  6. Start Devices (VDA5050)"
    echo "  7. Initialize System (send_init.sh)"
    echo "  8. Send Scheduled Tasks"
}

# Run all steps from a given starting point
run_from_step() {
    local start=$1

    # Always cleanup old containers for fresh start
    [ $start -le 1 ] && cleanup_old_containers
    [ $start -le 1 ] && step1_start_dashboard
    [ $start -le 2 ] && step2_start_interface
    [ $start -le 3 ] && step3_start_broker
    [ $start -le 4 ] && step4_start_simulation
    [ $start -le 5 ] && step5_start_services
    [ $start -le 6 ] && step6_start_devices
    [ $start -le 7 ] && step7_init_system
    [ $start -le 8 ] && step8_send_tasks
}

# Run a single step
run_single_step() {
    case $1 in
        1) step1_start_dashboard ;;
        2) step2_start_interface ;;
        3) step3_start_broker ;;
        4) step4_start_simulation ;;
        5) step5_start_services ;;
        6) step6_start_devices ;;
        7) step7_init_system ;;
        8) step8_send_tasks ;;
        *) log_error "Invalid step number: $1"; exit 1 ;;
    esac
}

# Print status summary
print_status() {
    echo -e "\n${GREEN}=== ENVIRONMENT STATUS ===${NC}"

    # Check ports
    echo -e "\nPorts:"
    for port in 3000 8083 8089 2727 5672 15672; do
        if port_in_use $port; then
            echo -e "  ${GREEN}[ACTIVE]${NC} Port $port"
        else
            echo -e "  ${RED}[DOWN]${NC} Port $port"
        fi
    done

    # Check Docker containers
    echo -e "\nDocker containers:"

    # Check for unified MAPF container first
    if docker ps --format '{{.Names}}' | grep -q "mapf_unified"; then
        echo -e "  ${GREEN}[RUNNING]${NC} mapf_unified (unified: map_server+solver+executor+mrs+movement)"
    else
        # Check separate containers
        for container in mapf_solver adg_executor mapf_mrs movement_request_server; do
            if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
                echo -e "  ${GREEN}[RUNNING]${NC} $container"
            else
                echo -e "  ${RED}[STOPPED]${NC} $container"
            fi
        done
        # fiware_map only needed when not using unified container
        if docker ps --format '{{.Names}}' | grep -q "fiware_map"; then
            echo -e "  ${GREEN}[RUNNING]${NC} fiware_map"
        else
            echo -e "  ${RED}[STOPPED]${NC} fiware_map"
        fi
    fi

    # Check other containers (always needed)
    for container in vda5050_fiware rmf2_broker-rabbitmq-1 task_orchestrator; do
        if docker ps --format '{{.Names}}' | grep -q "$container"; then
            echo -e "  ${GREEN}[RUNNING]${NC} $container"
        else
            echo -e "  ${RED}[STOPPED]${NC} $container"
        fi
    done

    # Check tmux
    echo -e "\nTmux sessions:"
    tmux list-sessions 2>/dev/null || echo "  No tmux sessions"
}

# Main
main() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║       IHI Phase 2 Final Demo - Environment Startup       ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    # Parse flags
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --no-sim)
                SKIP_SIMULATION=true
                shift
                ;;
            --unified-mapf|--unified)
                USE_UNIFIED_MAPF=true
                log_info "Using UNIFIED MAPF container mode"
                shift
                ;;
            --init-script)
                if [ -z "${2:-}" ]; then
                    log_error "Please specify init script name"
                    exit 1
                fi
                INIT_SCRIPT="$2"
                log_info "Using init script: $INIT_SCRIPT"
                shift 2
                ;;
            --list|-l)
                print_steps
                exit 0
                ;;
            --step|-s)
                if [ -z "${2:-}" ]; then
                    log_error "Please specify step number"
                    exit 1
                fi
                run_from_step $2
                print_status
                exit 0
                ;;
            --only|-o)
                if [ -z "${2:-}" ]; then
                    log_error "Please specify step number"
                    exit 1
                fi
                run_single_step $2
                exit 0
                ;;
            --status)
                print_status
                exit 0
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  (no args)       Run full startup sequence (steps 1-8)"
                echo "  --no-sim        Skip simulation and task sending (steps 4,8)"
                echo "  --unified-mapf  Use unified MAPF container instead of separate containers"
                echo "  --init-script X Use specified init script (default: $INIT_SCRIPT)"
                echo "  --step N        Run from step N onwards"
                echo "  --only N        Run only step N"
                echo "  --list          List all steps"
                echo "  --status        Show current environment status"
                echo "  --help          Show this help"
                echo ""
                echo "Examples:"
                echo "  $0                           # Full startup with separate MAPF containers"
                echo "  $0 --unified-mapf            # Full startup with unified MAPF container"
                echo "  $0 --unified-mapf --no-sim   # Unified MAPF, skip simulation"
                echo ""
                print_steps
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done

    # Run full startup if no command specified
    run_from_step 1
    print_status
    echo -e "\n${GREEN}Environment startup complete!${NC}"
    echo "Dashboard: http://localhost:3000"
    echo "RTS Scheduler: http://localhost:8089/schedule/"
    echo "Task Orchestrator: http://localhost:2727/health_check"
}

main "$@"
