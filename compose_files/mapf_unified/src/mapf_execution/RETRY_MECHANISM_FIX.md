# Retry Mechanism Fix Documentation

## Problem Summary

When two robots were sent to the same destination:
1. One robot was sent to the MAPF solver ✓
2. The other was filtered and added to `pending_retry_destinations` ✓
3. When a new task arrived triggering a replan, the pending retry was **NOT being retried** ✗

## Root Cause

The issue was in `adg/adg_execution.py` lines 244-252:

```python
replace_destinations_dict = {}
for rd in replace_destinations:
    replace_destinations_dict[rd.robot_id] = rd

stationary_agents = set()
for _, v in committed_vertices.items():
    if not find_same_agent_successor(self.adg, v) and v.agent_name not in replace_destinations_dict:
        # Previous task is completed, and new replan doesn't involve this agent.
        stationary_agents.add(v.agent_name)
```

**The problem**:
- `replace_destinations` only contained incoming messages (e.g., robot_1 → new destination)
- `pending_retry_destinations` (containing robot_2) was **NOT** included in the check
- Therefore robot_2 was marked as **stationary** even though it had a pending retry
- Stationary agents are **excluded** from the MAPF solver in `execution_context.py:141`

## Execution Flow

1. **User sends**: robot_1 → P647 (new destination)
2. **adg_execution.py** receives message and builds `replace_destinations_dict`:
   - Before fix: Only contains robot_1
   - **Robot_2 not in dict** → marked as stationary
3. **execution_context.py** `replan()` is called:
   - Merges `pending_retry_destinations` + `replace_destinations`
   - Creates replan info with both robot_1 AND robot_2
4. **execution_context.py** `_solve()` is called with `stationary_agents` set:
   - Line 141: `if agent.name not in stationary_agents`
   - **Robot_2 is in stationary_agents** → skipped, not sent to solver!
   - Only robot_1 sent to solver

## The Fix

Added lines 248-250 in `adg/adg_execution.py`:

```python
replace_destinations_dict = {}
for rd in replace_destinations:
    replace_destinations_dict[rd.robot_id] = rd

# FIX: Also include pending retry destinations when checking for stationary agents
for rd in self.problem_context.pending_retry_destinations:
    replace_destinations_dict[rd.robot_id] = rd

stationary_agents = set()
for _, v in committed_vertices.items():
    if not find_same_agent_successor(self.adg, v) and v.agent_name not in replace_destinations_dict:
        stationary_agents.add(v.agent_name)
```

**Now**:
- `replace_destinations_dict` contains robot_1 (from message) + robot_2 (from pending retries)
- Robot_2 is **NOT marked as stationary**
- Robot_2 is sent to the MAPF solver during replan

## Testing

Run the unit test to verify the fix:

```bash
cd /home/rosi/IHI_PHASE2_FINAL_DEMO/docker_modules/mapf_execution/mapf_execution/mapf_execution_bkp
source test_venv/bin/activate
export PYTHONPATH=$PWD:$PYTHONPATH
python3 test_retry_simple.py
```

Expected output:
```
✓ TEST PASSED!
✓ robot_2 (with pending retry) was NOT marked as stationary
✓ robot_1 (with new destination) was NOT marked as stationary
```

## Files Modified

1. **adg/adg_execution.py** (lines 248-250): Added pending retry destinations to replace_destinations_dict
2. **adg/execution_context.py** (lines 54, 64-72, 150-187, 191-227):
   - Added `pending_retry_destinations` list
   - Merge logic in `replan()`
   - Filtering and retry logic in `_solve()`
3. **adg/enums.py** (line 8): Added `QUEUED` state

## Integration Test

To test in the full system:

```bash
# 1. Rebuild docker image
cd /home/rosi/IHI_PHASE2_FINAL_DEMO/docker_modules/mapf_execution
docker build -t adg_executor:latest -f Dockerfile .

# 2. Restart container
docker restart adg_executor

# 3. Send conflicting tasks
docker exec adg_executor python3 /colcon_ws/src/mapf_execution/send_ngsi_task.py --conflict --goal_location P65 --redis_host rmf2_broker-redis-1

# 4. Check logs - should see robot_2 queued
docker logs adg_executor 2>&1 | grep -E "Duplicate goal|Queued|pending retry"

# 5. Send robot_1 to new destination to trigger retry
docker exec adg_executor python3 /colcon_ws/src/mapf_execution/send_ngsi_task.py --robot_id MiR_0001 --goal_location P647 --redis_host rmf2_broker-redis-1

# 6. Check logs - should see retry triggered and robot_2 sent to solver
docker logs adg_executor 2>&1 | grep -E "Retrying.*pending|MiR_0002"
```

Expected log output:
```
[INFO] Duplicate goal location detected during replan: MiR_0002 and MiR_0001 both going to P65
[INFO] Adding MiR_0002 to pending retry list
[INFO] Retrying 1 pending destinations from previous conflicts
[INFO] Incoming destinations: [MiR_0002→P65, MiR_0001→P647]
[INFO] MAPF request: 2 agents  <-- Both robots sent to solver!
```

## Summary

**Before fix**: Pending retries were ignored because they weren't checked when determining stationary agents.

**After fix**: Pending retries are included in the stationary check, ensuring they participate in replanning.

**Result**: The retry mechanism now works end-to-end, automatically retrying queued tasks when conflicts resolve.
