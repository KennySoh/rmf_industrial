#!/bin/bash
#
# Send all 24 robots to their home positions
# Uses test_replace_destination.py to send MAPF replace destination commands
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"  # Parent of test_scripts

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "  Sending all 24 robots to HOME positions"
echo "=========================================="
echo ""

cd "$DEMO_DIR"

# Home positions from launch/send_init_warehouse_v2.sh (warehouse_os_setup_v2)
declare -A HOME_POSITIONS=(
    [2]="P80"    [3]="P78"    [4]="P76"    [5]="P74"
    [6]="P150"   [7]="P148"   [8]="P146"   [9]="P144"   [10]="P142"
    [11]="P218"  [12]="P216"  [13]="P214"  [14]="P212"  [15]="P210"
    [16]="P286"  [17]="P284"  [18]="P282"  [19]="P280"  [20]="P278"
    [21]="P354"  [22]="P352"  [23]="P350"  [24]="P348"  [25]="P346"
)

success=0
failed=0

for num in 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25; do
    pos="${HOME_POSITIONS[$num]}"
    echo -n "Manufacturer_$num -> $pos ... "

    result=$(python3 test_replace_destination.py "Manufacturer_$num" "$pos" 2>&1)

    if echo "$result" | grep -q "successfully"; then
        echo -e "${GREEN}OK${NC}"
        ((success++))
    else
        echo -e "${RED}FAILED${NC}"
        ((failed++))
    fi
done

echo ""
echo "=========================================="
echo "  Done: $success success, $failed failed"
echo "=========================================="
