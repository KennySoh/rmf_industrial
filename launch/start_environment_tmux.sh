#!/bin/bash
#
# IHI Phase 2 Final Demo - tmux Environment Startup
#
# Runs ONE step table inside tmux: every step is visible in its own pane, and the
# orchestrator gates each step on a health probe before moving to the next.
#
# Usage:
#   ./start_environment_tmux.sh            # run all steps with health gates
#   ./start_environment_tmux.sh --step N   # re-run from step N onward (debugging)
#   ./start_environment_tmux.sh --status   # show ports/containers/tmux status
#   ./start_environment_tmux.sh --help     # usage
#
# On a failed gate the failing pane's last lines are dumped to the terminal and the
# session is LEFT RUNNING so you can `tmux attach -t ihi_demo`.

# Catch unset-variable typos and honest pipe failures. NOT -e: probes return 1 on
# timeout and we handle that ourselves.
set -uo pipefail

# --- Paths -------------------------------------------------------------------
# Expected layout (this script lives in ros_industrial_demo/launch):
#
#   ros_industrial_ws/              -> WS_DIR              (workspace root)
#   ├── ros_industrial_demo/        -> ROS_INDUSTRIAL_DIR
#   │   ├── launch/                 -> LAUNCH              (this script)
#   │   └── test_scripts/           -> TESTS
#   ├── rmf2_launcher_repo/         -> LAUNCHER_DIR        (dashboard / rmf2-launcher)
#   └── simulation/RMF2_new_sim.sh  -> SIM
#
LAUNCH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # this script's dir
ROS_INDUSTRIAL_DIR="$(dirname "$LAUNCH")"
WS_DIR="$(dirname "$ROS_INDUSTRIAL_DIR")"

LAUNCHER_DIR="$WS_DIR/rmf2_launcher_repo"
SIM="$WS_DIR/simulation/Linux/RMF2_SIM.sh"
TESTS="$ROS_INDUSTRIAL_DIR/test_scripts"

# Shared helpers (logging, probes, cleanup, status)
# shellcheck source=start_environment_utils.sh
source "$LAUNCH/start_environment_utils.sh"

SESSION="RMF2_Demo"
START_STEP=1

# --- Step table (SINGLE SOURCE OF TRUTH) -------------------------------------
# Fields:  num | title | window.pane | command | probe | timeout
#   probe:    port:N | url:URL | logmatch:container:pattern | sleep:S
#   timeout:  seconds for the gate; ignored (shown as "-") for sleep: probes,
#             which wait for the S inside the probe instead.
# Note: the Send Task default (send_parallel_workflow_3_robots.py) is a deliberate
# choice here; the old HTTP flow used the dashboard's /send_task instead.
STEPS=(
#   "1|Dashboard|Dashboard.0|cd '$LAUNCHER_DIR' && uv run rmf2-launcher --port 8083|port:8083|30"
  "2|Broker (IOCS)|IOCS.0|'$LAUNCH/rmf2_res_broker_control.sh' start|url:http://localhost:8000/status|120"
  "3|MQTT|IOCS.1|'$LAUNCH/rmf2_res_mqtt_control.sh' start|sleep:3|-"
  "4|MAPF (unified)|Services.0|'$LAUNCH/rmf2_unified_mapf_control.sh' start|port:8888|120"
  "5|Task Orchestrator|Services.1|'$LAUNCH/task_orchestrator_control.sh' start|url:http://localhost:2727/health_check|60"
  "6|Devices (VDA5050)|Devices.0|'$LAUNCH/rmf2_res_vda5050_control.sh' start|logmatch:vda5050_fiware:state|60"
  "7|Simulation|Sim.0|'$SIM'|sleep:10|-"
  "8|Init System|InitSystem.0|'$LAUNCH/send_init_warehouse_v2.sh'|sleep:5|-"
#   "9|Send Task|SendTask.0|cd '$TESTS' && python3 send_parallel_workflow_3_robots.py|sleep:3|-"
)

# Parse one "|"-delimited step record into named locals (call inside a function
# that has declared: num title target cmd probe timeout).
parse_step() {
    IFS='|' read -r num title target cmd probe timeout <<< "$1"
}

# --- tmux layout -------------------------------------------------------------
create_layout() {
    tmux new-session -d -s "$SESSION" -n Control -c "$LAUNCH"

    tmux new-window  -t "$SESSION" -n Dashboard -c "$LAUNCHER_DIR"

    tmux new-window  -t "$SESSION" -n IOCS -c "$LAUNCH"
    tmux split-window -v -t "$SESSION:IOCS" -c "$LAUNCH"
    tmux select-layout -t "$SESSION:IOCS" even-vertical

    tmux new-window  -t "$SESSION" -n Services -c "$LAUNCH"
    tmux split-window -v -t "$SESSION:Services" -c "$LAUNCH"
    tmux select-layout -t "$SESSION:Services" even-vertical

    tmux new-window  -t "$SESSION" -n Devices    -c "$LAUNCH"
    tmux new-window  -t "$SESSION" -n Sim        -c "$LAUNCH"
    tmux new-window  -t "$SESSION" -n InitSystem -c "$LAUNCH"
    tmux new-window  -t "$SESSION" -n SendTask   -c "$TESTS"

    tmux select-window -t "$SESSION:Control"
}

ensure_session() {
    if ! tmux has-session -t "$SESSION" 2>/dev/null; then
        log_info "Creating tmux session '$SESSION'..."
        create_layout
    fi
}

# Send a command to a window.pane so its output is visible there.
dispatch_to_pane() {
    local target=$1 cmd=$2
    tmux send-keys -t "$SESSION:$target" "$cmd" C-m
}

# Run the readiness probe for a step (in THIS terminal, so progress is visible).
run_probe() {
    local spec=$1 timeout=$2
    local kind="${spec%%:*}" rest="${spec#*:}"
    case "$kind" in
        port)  wait_for_port "$rest" "$timeout" ;;
        url)   wait_for_endpoint "$rest" "$timeout" ;;
        sleep) log_info "Waiting ${rest}s for step to settle..."; sleep "$rest" ;;
        logmatch)
            local c="${rest%%:*}" p="${rest#*:}"
            wait_for_log "$c" "$p" "$timeout" ;;
        *) log_warn "Unknown probe '$spec', sleeping 2s"; sleep 2 ;;
    esac
}

# Dump the last lines of a window's pane (used when a gate fails).
dump_pane() {
    local target=$1
    log_warn "---- last 20 lines of $SESSION:$target ----"
    tmux capture-pane -p -t "$SESSION:$target" 2>/dev/null | tail -20
    log_warn "---- end of pane ----"
}

# Run one step: dispatch its command to its pane, then gate on its probe.
run_step() {
    local num title target cmd probe timeout
    parse_step "$1"

    log_step "$num" "$title  (window: ${target%%.*})"
    dispatch_to_pane "$target" "$cmd"

    if run_probe "$probe" "$timeout"; then
        log_success "Step $num ($title) ready"
        return 0
    fi
    log_error "Step $num ($title) failed its health gate"
    dump_pane "$target"
    return 1
}

# Run all steps from $START_STEP onward, halting on the first failed gate.
run_all() {
    local s num title target cmd probe timeout
    for s in "${STEPS[@]}"; do
        parse_step "$s"
        [ "$num" -lt "$START_STEP" ] && continue
        if ! run_step "$s"; then
            echo ""
            log_error "Startup halted at step $num. Inspect with: tmux attach -t $SESSION"
            print_status
            exit 1
        fi
    done
}

attach_session() {
    if [ -n "${TMUX:-}" ]; then
        tmux switch-client -t "$SESSION"
    else
        tmux attach-session -t "$SESSION"
    fi
}

print_help() {
    cat <<'EOF'
IHI Phase 2 Final Demo - tmux Environment Startup

One step table runs inside tmux: every step is visible in its own pane while the
orchestrator gates each step on a health probe before moving on.

Usage:
  ./start_environment_tmux.sh            # run all steps with health gates
  ./start_environment_tmux.sh --step N   # re-run from step N onward (debugging)
  ./start_environment_tmux.sh --status   # show ports/containers/tmux status
  ./start_environment_tmux.sh --help     # usage

On a failed gate the failing pane's last lines are dumped to the terminal and the
session is LEFT RUNNING so you can: tmux attach -t ihi_demo
EOF
}

# --- Main --------------------------------------------------------------------
main() {
    command -v tmux >/dev/null || { log_error "tmux is not installed"; exit 1; }

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --step|-s)
                [[ "${2:-}" =~ ^[0-9]+$ ]] || { log_error "--step needs a number, got: ${2:-}"; exit 1; }
                START_STEP="$2"; shift 2 ;;
            --status)   print_status; exit 0 ;;
            --help|-h)  print_help; exit 0 ;;
            *) log_error "Unknown option: $1"; echo "Use --help for usage."; exit 1 ;;
        esac
    done

    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║    RMF2 Demo - tmux Environment Startup     ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    # Full run from step 1 → fresh start. Partial run → keep existing services.
    if [ "$START_STEP" -le 1 ]; then
        tmux kill-session -t "$SESSION" 2>/dev/null
        cleanup_old_containers "$ROS_INDUSTRIAL_DIR"
        create_layout
    else
        ensure_session
    fi

    run_all
    print_status
    echo -e "\n${GREEN}Environment startup complete!${NC}"
    attach_session
}

main "$@"
