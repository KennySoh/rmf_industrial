#!/bin/bash
#
# IHI Phase 2 Final Demo - tmux Environment Teardown
#
# Stops everything start_environment_tmux.sh started, in REVERSE order, then kills
# the ihi_demo tmux session. Best-effort: a single failure never aborts the rest.
#
# Usage:
#   ./stop_environment_tmux.sh            # graceful stop + kill the tmux session
#   ./stop_environment_tmux.sh --hard     # graceful stop, then force-remove leftovers
#   ./stop_environment_tmux.sh --status   # show what's still up
#   ./stop_environment_tmux.sh --help     # usage

# Teardown is best-effort; do NOT abort on the first error.
set +e

# --- Paths (mirror start_environment_tmux.sh) --------------------------------
LAUNCH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # this script's dir
ROS_INDUSTRIAL_DIR="$(dirname "$LAUNCH")"
WS_DIR="$(dirname "$ROS_INDUSTRIAL_DIR")"

# Shared helpers (logging, port checks, cleanup, status)
# shellcheck source=start_environment_utils.sh
source "$LAUNCH/start_environment_utils.sh"

SESSION="RMF2_Demo"               # our orchestrator session (created by start)

# --- Small helpers -----------------------------------------------------------

# Call a control script's `stop` action if it exists.
stop_ctl() {  # $1 = script basename, $2 = label
    local script="$LAUNCH/$1"
    if [ -x "$script" ]; then
        log_info "Stopping $2..."
        if "$script" stop >/dev/null 2>&1; then
            log_success "$2 stopped"
        else
            log_warn "$2 stop reported an error (continuing)"
        fi
    else
        log_warn "$1 not found, skipping $2"
    fi
}

# Force-remove a container if it's still running.
remove_container() {  # $1 = name
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^$1$"; then
        log_info "Removing leftover container $1..."
        docker rm -f "$1" >/dev/null 2>&1 && log_success "$1 removed" || log_warn "could not remove $1"
    fi
}

# Free a TCP port by killing whatever holds it.
free_port() {  # $1 = port, $2 = label
    if port_in_use "$1"; then
        log_info "Freeing port $1 ($2)..."
        fuser -k "$1/tcp" >/dev/null 2>&1 || true
    fi
}

stop_dashboard() {
    log_info "Stopping Dashboard (rmf2-launcher, port 8083)..."
    pkill -f "rmf2-launcher" >/dev/null 2>&1 || true
    free_port 8083 "dashboard"
    log_success "Dashboard stopped"
}

stop_simulation() {
    # start_environment_tmux.sh runs the UE5 binary (RMF2_new_sim.sh) directly in the
    # Sim pane -- NOT tmuxinator -- so kill that process. Killing the ihi_demo session
    # at the end also reaps the pane; this is the explicit/robust path.
    log_info "Stopping simulation (RMF2_new_sim)..."
    pkill -f "RMF2_new_sim" >/dev/null 2>&1 || true
    log_success "Simulation stopped"
}

# --- Teardown (reverse order of the start steps) -----------------------------
# Start steps 8 (Init System) and 9 (Send Task) are one-shot scripts -- nothing to
# stop -- so teardown covers steps 7 down to 1.
teardown() {
    log_step 7 "Simulation"
    stop_simulation

    log_step 6 "Devices (VDA5050)"
    stop_ctl rmf2_res_vda5050_control.sh "Devices (VDA5050)"

    log_step 5 "Task Orchestrator"
    stop_ctl task_orchestrator_control.sh "Task Orchestrator"
    remove_container task_orchestrator

    log_step 4 "MAPF (unified)"
    # Stops the unified container (what start uses). Any separate mapf_* strays are
    # swept by --hard (cleanup_old_containers).
    stop_ctl rmf2_unified_mapf_control.sh "MAPF (unified)"

    log_step 3 "MQTT"
    stop_ctl rmf2_res_mqtt_control.sh "MQTT"

    log_step 2 "Broker (IOCS)"
    stop_ctl rmf2_res_broker_control.sh "Broker (IOCS)"

    log_step 1 "Dashboard"
    stop_dashboard
}

# Force-remove anything the graceful stop left behind.
hard_cleanup() {
    log_step "X" "Hard cleanup (force-remove leftovers)"
    cleanup_old_containers "$ROS_INDUSTRIAL_DIR"
    # Ports the start steps bind (dashboard, IOCS, MAPF, task orchestrator).
    for port in 8083 8000 8888 2727; do
        free_port "$port" "leftover"
    done
}

# True when this script is running from inside our own tmux session (so we must
# kill that session last, otherwise we'd cut ourselves off mid-teardown).
running_inside_session() {
    [ "$(tmux display-message -p '#S' 2>/dev/null)" = "$SESSION" ]
}

# Kill our tmux session now.
kill_session() {
    tmux kill-session -t "$SESSION" >/dev/null 2>&1 \
        && log_success "tmux session '$SESSION' killed" \
        || log_info "no '$SESSION' tmux session"
}

print_help() {
    cat <<'EOF'
RMF2 Demo - tmux Environment Teardown

Stops everything start_environment_tmux.sh started, in reverse order, then kills
the RMF2_Demo tmux session. Best-effort: a single failure never aborts the rest.

Usage:
  ./stop_environment_tmux.sh            # graceful stop + kill the tmux session
  ./stop_environment_tmux.sh --hard     # graceful stop, then force-remove leftovers
  ./stop_environment_tmux.sh --status   # show what's still up
  ./stop_environment_tmux.sh --help     # usage
EOF
}

# --- Main --------------------------------------------------------------------
main() {
    local do_hard=false
    case "${1:-}" in
        --status)  print_status; exit 0 ;;
        --help|-h) print_help; exit 0 ;;
        --hard|-f) do_hard=true ;;
        "")        ;;  # default: graceful
        *) log_error "Unknown option: $1"; echo "Use --help for usage."; exit 1 ;;
    esac

    echo -e "${RED}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║     RMF2 Demo - tmux Environment Teardown                ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    teardown
    [ "$do_hard" = true ] && hard_cleanup

    # Kill the tmux session -- but if we're inside it, defer to the very end so we
    # don't cut ourselves off before printing the summary.
    if running_inside_session; then
        log_warn "Running inside '$SESSION'; killing it last."
        print_status
        echo -e "\n${GREEN}Environment teardown complete!${NC}"
        log_info "Killing '$SESSION' now (we were running inside it)..."
        tmux kill-session -t "$SESSION" >/dev/null 2>&1
    else
        kill_session
        print_status
        echo -e "\n${GREEN}Environment teardown complete!${NC}"
    fi
}

main "$@"
