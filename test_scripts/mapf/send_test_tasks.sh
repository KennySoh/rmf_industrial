#!/bin/bash
# Send test tasks to the first N robots (MAPF replace-destination commands).
# Combined: 2026-06-09
#
# Usage:
#   ./send_test_tasks.sh              # all 24 robots
#   ./send_test_tasks.sh 6            # first 6 robots
#   ./send_test_tasks.sh 12 --dry-run # print the commands, send nothing
#
# --dry-run prints one `python3 test_replace_destination.py <robot> <dest>` line
# per robot without executing; loop_tasks.sh and check_robot_orders.sh consume
# that output to recover the robot -> goal mapping.
#
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"  # ros_industrial_demo

# Ordered robot -> destination map. The N-robot set is the first N entries.
TASKS=(
    "Manufacturer_2 P165"  "Manufacturer_3 P231"  "Manufacturer_4 P297"
    "Manufacturer_5 P167"  "Manufacturer_6 P233"  "Manufacturer_7 P299"
    "Manufacturer_8 P171"  "Manufacturer_9 P235"  "Manufacturer_10 P301"
    "Manufacturer_11 P173" "Manufacturer_12 P239" "Manufacturer_13 P303"
    "Manufacturer_14 P175" "Manufacturer_15 P241" "Manufacturer_16 P307"
    "Manufacturer_17 P177" "Manufacturer_18 P243" "Manufacturer_19 P309"
    "Manufacturer_20 P363" "Manufacturer_21 P365" "Manufacturer_22 P367"
    "Manufacturer_23 P369" "Manufacturer_24 P245" "Manufacturer_25 P311"
)

N="${#TASKS[@]}"; DRY_RUN=false
for arg in "$@"; do
    case "$arg" in
        --dry-run|-n) DRY_RUN=true ;;
        ''|*[!0-9]*) echo "Invalid argument: $arg" >&2; exit 1 ;;
        *) N="$arg" ;;
    esac
done
if [ "$N" -lt 1 ] || [ "$N" -gt "${#TASKS[@]}" ]; then
    echo "N must be between 1 and ${#TASKS[@]} (got $N)" >&2; exit 1
fi

cd "$DEMO_DIR"
if [ "$DRY_RUN" = false ]; then
    echo -e "Sending tasks to $N robots...\n"
fi
for ((i = 0; i < N; i++)); do
    read -r robot dest <<< "${TASKS[$i]}"
    if [ "$DRY_RUN" = true ]; then
        echo "python3 test_replace_destination.py $robot $dest"
    else
        python3 test_replace_destination.py "$robot" "$dest"
    fi
done
if [ "$DRY_RUN" = false ]; then
    echo -e "\nDone. Check logs with: docker logs adg_executor --tail 20"
fi
