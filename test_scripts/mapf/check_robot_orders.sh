#!/bin/bash
#
# Check the last order issued to each robot via VDA5050 and verify against expected goals
# Also shows ADG executor's "Most recently completed" positions
#
# Usage:
#   ./check_robot_orders.sh           # Check all robots (no verification)
#   ./check_robot_orders.sh 6         # Verify against 6-robot task set
#   ./check_robot_orders.sh 12        # Verify against 12-robot task set
#   ./check_robot_orders.sh 24        # Verify against 24-robot task set
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_SET="${1:-}"

# Build expected goals from task script if specified
declare -A EXPECTED_GOALS
declare -A ADG_POSITIONS

if [ -n "$TASK_SET" ]; then
    TASK_SCRIPT="$SCRIPT_DIR/send_test_tasks.sh"
    if [ ! -x "$TASK_SCRIPT" ]; then
        echo "Error: Task script not found: $TASK_SCRIPT"
        exit 1
    fi

    # --dry-run prints the test_replace_destination.py commands without sending
    if ! TASK_CMDS=$("$TASK_SCRIPT" "$TASK_SET" --dry-run); then
        echo "Error: $TASK_SCRIPT rejected task set '$TASK_SET' (valid: 1-24)"
        exit 1
    fi

    echo "=== Verifying Against ${TASK_SET}-Robot Task Set ==="
    echo "Task script: $TASK_SCRIPT $TASK_SET"
    echo ""

    # Parse the task commands to extract robot -> goal mappings
    while IFS= read -r line; do
        if [[ "$line" =~ test_replace_destination.py[[:space:]]+(Manufacturer_([0-9]+))[[:space:]]+(P[0-9]+) ]]; then
            ROBOT_NUM="${BASH_REMATCH[2]}"
            GOAL="${BASH_REMATCH[3]}"
            EXPECTED_GOALS[$ROBOT_NUM]="$GOAL"
        fi
    done <<< "$TASK_CMDS"
else
    echo "=== Last Order Issued to Each Robot ==="
    echo "(Run with argument 6, 12, or 24 to verify against task set)"
    echo ""
fi

# Get ADG executor's "Most recently completed" status from stderr log (DEBUG level)
echo "Fetching ADG executor status..."
ADG_ERR_LOG=$(docker exec mapf_unified tail -1000 /var/log/supervisor/adg_executor_err.log 2>/dev/null || echo "")

ADG_FOUND=false
ADG_TIMESTAMP=""
if [ -n "$ADG_ERR_LOG" ]; then
    # Find the most recent "Most recently completed" block and extract positions
    # Format: [DEBUG] 17:48:29:319 execution: Most recently completed:
    # Format: Manufacturer_2, <Manufacturer_2; t26; (P164)-(P165); (action_completed); (task_id)>

    # Get the last occurrence line with timestamp
    LAST_COMPLETED_LINE=$(echo "$ADG_ERR_LOG" | grep "Most recently completed" | tail -1)

    if [ -n "$LAST_COMPLETED_LINE" ]; then
        ADG_FOUND=true
        # Extract timestamp (format: HH:MM:SS:mmm)
        ADG_TIMESTAMP=$(echo "$LAST_COMPLETED_LINE" | grep -oP '\d{2}:\d{2}:\d{2}:\d{3}' | head -1)

        # Get the line number and extract robot positions after it
        COMPLETED_LINE_NUM=$(echo "$ADG_ERR_LOG" | grep -n "Most recently completed" | tail -1 | cut -d: -f1)
        ROBOT_LINES=$(echo "$ADG_ERR_LOG" | tail -n +$COMPLETED_LINE_NUM | head -30)

        while IFS= read -r line; do
            if [[ "$line" =~ Manufacturer_([0-9]+),[[:space:]]*\<Manufacturer_[0-9]+\;[[:space:]]*t[0-9]+\;[[:space:]]*\(P[0-9]+\)-\((P[0-9]+)\) ]]; then
                ROBOT_NUM="${BASH_REMATCH[1]}"
                CURRENT_POS="${BASH_REMATCH[2]}"
                ADG_POSITIONS[$ROBOT_NUM]="$CURRENT_POS"
            fi
        done <<< "$ROBOT_LINES"
    fi
fi

# Get current time in UTC for comparison (container logs are in UTC)
CURRENT_TIME=$(date -u +%H:%M:%S)

echo ""

if [ -n "$TASK_SET" ]; then
    printf "| %-5s | %-8s | %-8s | %-8s | %-8s | %-10s |\n" "Robot" "Expected" "VDA5050" "ADG Pos" "Match" "Status"
    printf "|-------|----------|----------|----------|----------|------------|\n"
else
    printf "| %-5s | %-10s | %-10s | %-10s |\n" "Robot" "VDA5050" "ADG Pos" "Status"
    printf "|-------|------------|------------|------------|\n"
fi

# Get all VDA5050 logs and strip ANSI color codes
VDA_LOGS=$(docker logs vda5050_fiware 2>&1 | sed 's/\x1b\[[0-9;]*m//g' 2>/dev/null || echo "")

MATCH_COUNT=0
MISMATCH_COUNT=0
TOTAL_CHECKED=0

for i in $(seq 2 25); do
    # Skip robots not in the task set (if verifying)
    if [ -n "$TASK_SET" ] && [ -z "${EXPECTED_GOALS[$i]}" ]; then
        continue
    fi

    # Find the last order block for this robot (get Update ID line which contains the JSON)
    LAST_ORDER_JSON=""
    if [ -n "$VDA_LOGS" ]; then
        LAST_ORDER_JSON=$(echo "$VDA_LOGS" | grep -A2 "MQTT Topic: uagv/v2/Manufacturer/$i/order" | grep "Update ID" | tail -1)
    fi

    FINAL_NODE="(none)"
    STATUS="❓ N/A"

    if [ -n "$LAST_ORDER_JSON" ]; then
        # Extract all nodeIds from the order (escaped JSON format: \"nodeId\":\"P233\")
        NODES=$(echo "$LAST_ORDER_JSON" | grep -oP '\\"nodeId\\":\\"P\d+\\"' | grep -oP 'P\d+')

        # Get the last node (final destination)
        FINAL_NODE=$(echo "$NODES" | tail -1)
        [ -z "$FINAL_NODE" ] && FINAL_NODE="(none)"

        # Check if this robot's order was completed
        COMPLETED=$(echo "$VDA_LOGS" | grep "Manufacturer_$i" | grep -i "completed" | tail -1)

        if [ -n "$COMPLETED" ]; then
            STATUS="✅ Done"
        else
            STATUS="⏳ Running"
        fi
    fi

    # Get ADG position
    ADG_POS="${ADG_POSITIONS[$i]:-"-"}"

    if [ -n "$TASK_SET" ]; then
        EXPECTED="${EXPECTED_GOALS[$i]}"
        TOTAL_CHECKED=$((TOTAL_CHECKED + 1))

        # Check if either VDA5050 final node OR ADG position matches expected
        if [ "$FINAL_NODE" = "$EXPECTED" ] || [ "$ADG_POS" = "$EXPECTED" ]; then
            MATCH="✅ Yes"
            MATCH_COUNT=$((MATCH_COUNT + 1))
        else
            MATCH="❌ No"
            MISMATCH_COUNT=$((MISMATCH_COUNT + 1))
        fi

        printf "| %-5s | %-8s | %-8s | %-8s | %-8s | %-10s |\n" "$i" "$EXPECTED" "$FINAL_NODE" "$ADG_POS" "$MATCH" "$STATUS"
    else
        printf "| %-5s | %-10s | %-10s | %-10s |\n" "$i" "$FINAL_NODE" "$ADG_POS" "$STATUS"
    fi
done

echo ""
echo "=== Summary ==="

if [ -n "$VDA_LOGS" ]; then
    TOTAL_ORDERS=$(echo "$VDA_LOGS" | grep -c "MQTT Topic: uagv/v2/Manufacturer/.*/order" || echo "0")
    COMPLETED_COUNT=$(echo "$VDA_LOGS" | grep -c "Order .* completed" || echo "0")
    echo "VDA5050 - Orders sent: $TOTAL_ORDERS, Completed: $COMPLETED_COUNT"
else
    echo "VDA5050 - Container not running or no logs"
fi

if [ "$ADG_FOUND" = true ]; then
    echo "ADG Executor - Last update: $ADG_TIMESTAMP UTC (current: $CURRENT_TIME UTC)"
else
    echo "ADG Executor - No 'Most recently completed' block in recent logs"
fi

if [ -n "$TASK_SET" ]; then
    echo ""
    echo "=== Verification Results ==="
    echo "Robots checked: $TOTAL_CHECKED"
    echo "Goals matched: $MATCH_COUNT"
    echo "Goals mismatched: $MISMATCH_COUNT"

    if [ $MISMATCH_COUNT -eq 0 ] && [ $TOTAL_CHECKED -gt 0 ]; then
        echo ""
        echo "✅ ALL ROBOTS REACHED THEIR EXPECTED GOALS!"
    elif [ $MISMATCH_COUNT -gt 0 ]; then
        echo ""
        echo "⚠️  Some robots did not reach their expected goals"
    fi
fi
