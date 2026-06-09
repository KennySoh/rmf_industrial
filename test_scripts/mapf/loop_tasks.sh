#!/bin/bash
#
# Loop tasks - Send robots to destinations, wait for completion, send back home, repeat
#
# Usage:
#   ./loop_tasks.sh 6           # Use 6-robot task set, loop forever
#   ./loop_tasks.sh 12          # Use 12-robot task set, loop forever
#   ./loop_tasks.sh 24          # Use 24-robot task set, loop forever
#   ./loop_tasks.sh 24 5        # Use 24-robot task set, run 5 loops
#   ./loop_tasks.sh 24 0        # Use 24-robot task set, loop forever (same as no arg)
#   ./loop_tasks.sh 24 --dry-run # Show planned movements without executing
#

# Note: not using set -e due to bash arithmetic quirks with ((x++))

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")" 
LAUNCH_DIR="$DEMO_DIR/launch"
POLL_INTERVAL=2      # seconds between polls
DRY_RUN=false

# Parse arguments
TASK_SET="24"
MAX_LOOPS="0"
POSITIONAL=()

for arg in "$@"; do
    case "$arg" in
        --dry-run|-n)
            DRY_RUN=true
            ;;
        *)
            POSITIONAL+=("$arg")
            ;;
    esac
done

# Set positional args
if [ ${#POSITIONAL[@]} -ge 1 ]; then
    TASK_SET="${POSITIONAL[0]}"
fi
if [ ${#POSITIONAL[@]} -ge 2 ]; then
    MAX_LOOPS="${POSITIONAL[1]}"
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Arrays for positions
declare -A HOME_POSITIONS
declare -A TASK_POSITIONS
declare -A CURRENT_POSITIONS
ROBOT_IDS=()

# Parse home positions from send_init_warehouse_os_setup.sh
parse_home_positions() {
    local init_script="$LAUNCH_DIR/send_init_warehouse_v2.sh"

    if [ ! -f "$init_script" ]; then
        echo -e "${RED}Error: Home positions file not found: $init_script${NC}"
        exit 1
    fi

    # Extract robot_id and goal_location pairs
    while IFS= read -r line; do
        if [[ "$line" =~ \"robot_id\":[[:space:]]*\"(Manufacturer_([0-9]+))\" ]]; then
            local robot_num="${BASH_REMATCH[2]}"
            local robot_id="${BASH_REMATCH[1]}"
        fi
        if [[ "$line" =~ \"goal_location\":[[:space:]]*\"(P[0-9]+)\" ]]; then
            local goal="${BASH_REMATCH[1]}"
            if [ -n "$robot_num" ]; then
                HOME_POSITIONS[$robot_num]="$goal"
            fi
        fi
    done < "$init_script"
}

# Parse task positions from send_test_tasks.sh (first TASK_SET robots)
parse_task_positions() {
    local task_script="$SCRIPT_DIR/send_test_tasks.sh"

    if [ ! -x "$task_script" ]; then
        echo -e "${RED}Error: Task script not found: $task_script${NC}"
        exit 1
    fi

    # --dry-run prints the test_replace_destination.py commands without sending
    local task_cmds
    if ! task_cmds=$("$task_script" "$TASK_SET" --dry-run); then
        echo -e "${RED}Error: $task_script rejected task set '$TASK_SET' (valid: 1-24)${NC}"
        exit 1
    fi

    while IFS= read -r line; do
        if [[ "$line" =~ test_replace_destination.py[[:space:]]+(Manufacturer_([0-9]+))[[:space:]]+(P[0-9]+) ]]; then
            local robot_num="${BASH_REMATCH[2]}"
            local goal="${BASH_REMATCH[3]}"
            TASK_POSITIONS[$robot_num]="$goal"
            ROBOT_IDS+=("$robot_num")
        fi
    done <<< "$task_cmds"
}

# Get current positions - checks VDA5050 for last order's final node
get_current_positions() {
    CURRENT_POSITIONS=()

    local vda_log=$(docker logs vda5050_fiware 2>&1 | sed 's/\x1b\[[0-9;]*m//g' 2>/dev/null || echo "")

    if [ -z "$vda_log" ]; then
        return 1
    fi

    for robot_num in "${ROBOT_IDS[@]}"; do
        # Get last order for this robot
        local last_order=$(echo "$vda_log" | grep -A2 "MQTT Topic: uagv/v2/Manufacturer/$robot_num/order" | grep "Update ID" | tail -1)

        if [ -n "$last_order" ]; then
            local final_node=$(echo "$last_order" | grep -oP '\\"nodeId\\":\\"P\d+\\"' | tail -1 | grep -oP 'P\d+')
            if [ -n "$final_node" ]; then
                # Check if this order completed
                local completed=$(echo "$vda_log" | grep "Manufacturer_$robot_num" | grep "completed" | tail -1)
                if [ -n "$completed" ]; then
                    CURRENT_POSITIONS[$robot_num]="$final_node"
                else
                    CURRENT_POSITIONS[$robot_num]="moving→$final_node"
                fi
            fi
        fi
    done

    [ ${#CURRENT_POSITIONS[@]} -gt 0 ]
}

# Send robots to specified positions
send_to_positions() {
    local -n positions=$1
    local description=$2

    echo -e "${BLUE}Sending robots to ${description}...${NC}"

    cd "$DEMO_DIR"

    for robot_num in "${ROBOT_IDS[@]}"; do
        local goal="${positions[$robot_num]}"
        if [ -n "$goal" ]; then
            echo -n "  Manufacturer_$robot_num → $goal ... "
            local result=$(python3 test_replace_destination.py "Manufacturer_$robot_num" "$goal" 2>&1)
            if echo "$result" | grep -q "successfully"; then
                echo -e "${GREEN}OK${NC}"
            else
                echo -e "${RED}FAILED${NC}"
                echo "$result" | head -5
            fi
        fi
    done

    echo -e "${GREEN}All tasks sent${NC}"
}

# Wait for all robots to reach expected positions
wait_for_positions() {
    local -n expected=$1
    local description=$2
    local start_time=$(date +%s)

    echo -e "${YELLOW}Waiting for robots to reach ${description}...${NC}"

    while true; do
        if ! get_current_positions; then
            echo -e "  ${RED}Cannot read ADG positions, retrying...${NC}"
            sleep $POLL_INTERVAL
            continue
        fi

        local matched=0
        local total=${#ROBOT_IDS[@]}
        local pending=""

        for robot_num in "${ROBOT_IDS[@]}"; do
            local expected_pos="${expected[$robot_num]}"
            local current_pos="${CURRENT_POSITIONS[$robot_num]:-"?"}"

            # Check if position matches (completed at destination)
            if [ "$current_pos" = "$expected_pos" ]; then
                matched=$((matched + 1))
            else
                pending+=" $robot_num:$current_pos"
            fi
        done

        local elapsed=$(( $(date +%s) - start_time ))

        if [ $matched -eq $total ]; then
            echo -e "\n${GREEN}All $total robots reached ${description}! (${elapsed}s)${NC}"
            return 0
        fi

        # Show progress
        printf "\r  Progress: %d/%d (elapsed: %ds) " $matched $total $elapsed

        sleep $POLL_INTERVAL
    done
}

# Print status table
print_status() {
    echo ""
    printf "| %-5s | %-8s | %-8s | %-8s |\n" "Robot" "Current" "Task" "Home"
    printf "|-------|----------|----------|----------|\n"

    for robot_num in "${ROBOT_IDS[@]}"; do
        local current="${CURRENT_POSITIONS[$robot_num]:-"?"}"
        local task="${TASK_POSITIONS[$robot_num]}"
        local home="${HOME_POSITIONS[$robot_num]}"
        printf "| %-5s | %-8s | %-8s | %-8s |\n" "$robot_num" "$current" "$task" "$home"
    done
    echo ""
}

# Main
main() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║              Loop Tasks - MAPF Robot Control             ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    echo "Configuration:"
    echo "  Task set: $TASK_SET robots"
    echo "  Max loops: $([ "$MAX_LOOPS" -eq 0 ] && echo "infinite" || echo "$MAX_LOOPS")"
    echo "  Poll interval: ${POLL_INTERVAL}s"
    echo ""

    # Parse positions
    echo "Loading positions..."
    parse_home_positions
    parse_task_positions

    echo "  Loaded ${#ROBOT_IDS[@]} robots"
    echo "  Robots: ${ROBOT_IDS[*]}"
    echo ""

    # Get initial positions
    if get_current_positions; then
        echo "Current robot positions:"
        print_status
    fi

    # Dry run - just show positions and exit
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}DRY RUN - showing planned movements:${NC}"
        echo ""
        echo "Phase 1 (to TASK):"
        for robot_num in "${ROBOT_IDS[@]}"; do
            echo "  Manufacturer_$robot_num → ${TASK_POSITIONS[$robot_num]}"
        done
        echo ""
        echo "Phase 2 (to HOME):"
        for robot_num in "${ROBOT_IDS[@]}"; do
            echo "  Manufacturer_$robot_num → ${HOME_POSITIONS[$robot_num]}"
        done
        echo ""
        echo -e "${YELLOW}Use without --dry-run to execute${NC}"
        exit 0
    fi

    # Main loop
    local loop_count=0

    while true; do
        loop_count=$((loop_count + 1))

        echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}                      LOOP $loop_count                      ${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"

        # Phase 1: Send to task positions
        echo ""
        echo -e "${BLUE}>>> PHASE 1: Moving to TASK positions${NC}"
        send_to_positions TASK_POSITIONS "task destinations"
        wait_for_positions TASK_POSITIONS "task destinations"

        # Phase 2: Send back home
        echo ""
        echo -e "${BLUE}>>> PHASE 2: Returning to HOME positions${NC}"
        send_to_positions HOME_POSITIONS "home positions"
        wait_for_positions HOME_POSITIONS "home positions"

        echo ""
        echo -e "${GREEN}Loop $loop_count completed!${NC}"

        # Check if we should stop
        if [ "$MAX_LOOPS" -gt 0 ] && [ $loop_count -ge "$MAX_LOOPS" ]; then
            echo ""
            echo -e "${GREEN}Completed $MAX_LOOPS loops. Stopping.${NC}"
            break
        fi

        echo ""
        echo "Starting next loop in 3 seconds... (Ctrl+C to stop)"
        sleep 3
    done
}

# Handle Ctrl+C gracefully
trap 'echo -e "\n${YELLOW}Interrupted. Exiting...${NC}"; exit 0' INT

main
