#!/bin/bash
#
# start_environment_utils.sh - Shared helpers for start_environment_tmux.sh.
# Keeps logging, health probes, cleanup and status reporting in ONE place.
#
# This file only defines functions/colours; it runs nothing on its own.

# --- Colours -----------------------------------------------------------------
# Only emit escape codes when stdout is a terminal, so piped/captured output
# (e.g. --status) stays clean.
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; NC=''
fi

# --- Logging -----------------------------------------------------------------
log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()    { echo -e "\n${GREEN}=== STEP $1: $2 ===${NC}"; }

# --- Health probes -----------------------------------------------------------

# Check if a port is in use (works with Docker-published ports).
port_in_use() {
    ss -tlnp 2>/dev/null | grep -q ":$1 " || lsof -i :$1 >/dev/null 2>&1
}

# Wait until a TCP port is listening, or time out.
wait_for_port() {
    local port=$1 timeout=$2 elapsed=0
    log_info "Waiting for port $port to be available..."
    while ! port_in_use "$port"; do
        sleep 1
        elapsed=$((elapsed + 1))
        if [ "$elapsed" -ge "$timeout" ]; then
            log_error "Timeout waiting for port $port"
            return 1
        fi
    done
    log_success "Port $port is now available"
}

# Wait until an HTTP endpoint returns 200, or time out.
wait_for_endpoint() {
    local url=$1 timeout=$2 elapsed=0
    log_info "Waiting for $url to respond..."
    while true; do
        if curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q "200"; then
            log_success "$url is responding"
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
        if [ "$elapsed" -ge "$timeout" ]; then
            log_error "Timeout waiting for $url"
            return 1
        fi
        echo -n "."
    done
}

# Wait until a container's logs contain a pattern, or time out (non-fatal).
# Generalises the old check_vda5050_robots helper.
wait_for_log() {
    local container=$1 pattern=$2 timeout=$3 elapsed=0
    log_info "Waiting for '$pattern' in $container logs..."
    while true; do
        if ! docker ps --format '{{.Names}}' | grep -q "$container"; then
            : # container not up yet
        else
            local count
            count=$(docker logs "$container" 2>&1 | grep -c "$pattern" 2>/dev/null || echo "0")
            count=$(echo "$count" | tr -d '[:space:]')
            if [ "${count:-0}" -gt 0 ] 2>/dev/null; then
                log_success "Found $count '$pattern' lines in $container"
                return 0
            fi
        fi
        sleep 3
        elapsed=$((elapsed + 3))
        if [ "$elapsed" -ge "$timeout" ]; then
            log_warn "Timeout waiting for '$pattern' in $container (continuing anyway)"
            return 0   # non-fatal, mirrors original behaviour
        fi
        echo -n "."
    done
}

# --- Cleanup -----------------------------------------------------------------

# Remove old containers and stale state for a fresh start.
# Pass the ros_industrial_demo dir as $1 so completed_jobs.txt can be cleared.
cleanup_old_containers() {
    local demo_dir="$1"
    log_info "Cleaning up old containers and state for fresh start..."

    local patterns="vda5050 mapf adg fiware rmf mosquitto orion movement_request load_map task_orchestrator"
    for pattern in $patterns; do
        local containers
        containers=$(docker ps -aq --filter "name=$pattern" 2>/dev/null)
        if [ -n "$containers" ]; then
            docker rm -f $containers >/dev/null 2>&1 || true
        fi
    done
    docker rm -f mapf_unified >/dev/null 2>&1 || true

    [ -n "$demo_dir" ] && > "$demo_dir/completed_jobs.txt" 2>/dev/null || true
    log_success "Old containers and state cleared"
}

# --- Status ------------------------------------------------------------------

print_status() {
    echo -e "\n${GREEN}=== ENVIRONMENT STATUS ===${NC}"

    echo -e "\nPorts:"
    for port in 3000 8083 8000 8888 2727 5672 15672; do
        if port_in_use "$port"; then
            echo -e "  ${GREEN}[ACTIVE]${NC} Port $port"
        else
            echo -e "  ${RED}[DOWN]${NC} Port $port"
        fi
    done

    echo -e "\nDocker containers:"
    if docker ps --format '{{.Names}}' | grep -q "mapf_unified"; then
        echo -e "  ${GREEN}[RUNNING]${NC} mapf_unified (unified: map_server+solver+executor+mrs+movement)"
    else
        for container in mapf_solver adg_executor mapf_mrs movement_request_server; do
            if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
                echo -e "  ${GREEN}[RUNNING]${NC} $container"
            else
                echo -e "  ${RED}[STOPPED]${NC} $container"
            fi
        done
        if docker ps --format '{{.Names}}' | grep -q "fiware_map"; then
            echo -e "  ${GREEN}[RUNNING]${NC} fiware_map"
        else
            echo -e "  ${RED}[STOPPED]${NC} fiware_map"
        fi
    fi

    for container in vda5050_fiware rmf2_broker-rabbitmq-1 task_orchestrator; do
        if docker ps --format '{{.Names}}' | grep -q "$container"; then
            echo -e "  ${GREEN}[RUNNING]${NC} $container"
        else
            echo -e "  ${RED}[STOPPED]${NC} $container"
        fi
    done

    echo -e "\nTmux sessions:"
    tmux list-sessions 2>/dev/null || echo "  No tmux sessions"
}
