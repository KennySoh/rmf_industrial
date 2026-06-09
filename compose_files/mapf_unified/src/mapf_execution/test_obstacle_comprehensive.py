"""
Comprehensive test suite for obstacle-blocking detection with CBSAdapter.

Tests various scenarios including:
- Single obstacle blocking single robot
- Multiple obstacles blocking multiple robots
- Mixed scenario (some blocked, some not)
- Retry mechanism when obstacle moves
"""
import logging

from adg.models.mapf_execution_models import MapfSendTaskPostRequestTaskItem, ReplaceDestination
from adg.execution_context import MAPFProblemContext
from adg.enums import TaskState
from mapf_solve.cbs_adapter import CBSAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_mixed_blocking_scenario():
    """
    Test mixed scenario: some robots blocked, some not.

    Scenario:
    - robot_1 at (3,3), staying at (3,3) - obstacle
    - robot_2 at (5,5), staying at (5,5) - obstacle
    - robot_3 at (1,1), wants to go to (3,3) - BLOCKED
    - robot_4 at (0,0), wants to go to (5,5) - BLOCKED
    - robot_5 at (2,2), wants to go to (6,6) - NOT blocked

    Expected:
    - robot_3 and robot_4 queued
    - robot_5 gets a plan
    """
    logger.info("\n=== Testing mixed blocking scenario ===\n")

    progress_updates = {}

    def progress_callback(task_id: str, state: TaskState, message: str):
        logger.info(f"Progress: {task_id} -> {state.value}: {message}")
        progress_updates[task_id] = (state, message)

    # Create initial MAPF items
    mapf_items = {
        "robot_1": MapfSendTaskPostRequestTaskItem(
            task_id="task_1",
            robot_id="robot_1",
            start_location="3,3",
            goal_location="3,3",  # Stationary obstacle
        ),
        "robot_2": MapfSendTaskPostRequestTaskItem(
            task_id="task_2",
            robot_id="robot_2",
            start_location="5,5",
            goal_location="5,5",  # Stationary obstacle
        ),
        "robot_3": MapfSendTaskPostRequestTaskItem(
            task_id="task_3_init",
            robot_id="robot_3",
            start_location="1,1",
            goal_location="1,1",
        ),
        "robot_4": MapfSendTaskPostRequestTaskItem(
            task_id="task_4_init",
            robot_id="robot_4",
            start_location="0,0",
            goal_location="0,0",
        ),
        "robot_5": MapfSendTaskPostRequestTaskItem(
            task_id="task_5_init",
            robot_id="robot_5",
            start_location="2,2",
            goal_location="2,2",
        ),
    }

    cbs_solver = CBSAdapter()
    context = MAPFProblemContext(cbs_solver, mapf_items)

    # New destinations
    replace_destinations = [
        ReplaceDestination(task_id="task_3", robot_id="robot_3", goal_location="3,3"),  # Blocked
        ReplaceDestination(task_id="task_4", robot_id="robot_4", goal_location="5,5"),  # Blocked
        ReplaceDestination(task_id="task_5", robot_id="robot_5", goal_location="6,6"),  # NOT blocked
    ]

    class MockVertex:
        def __init__(self, agent_name, location):
            self.agent_name = agent_name
            self.location_end = location

    committed_vertices = {
        "robot_1": MockVertex("robot_1", "3,3"),
        "robot_2": MockVertex("robot_2", "5,5"),
        "robot_3": MockVertex("robot_3", "1,1"),
        "robot_4": MockVertex("robot_4", "0,0"),
        "robot_5": MockVertex("robot_5", "2,2"),
    }

    stationary_agents = {"robot_1", "robot_2"}

    logger.info(f"Stationary agents (obstacles): {stationary_agents}")
    logger.info(f"Incoming destinations:")
    for dest in replace_destinations:
        logger.info(f"  {dest.robot_id} -> {dest.goal_location}")

    # Call replan
    logger.info("\nCalling replan()...")
    result = context.replan(
        committed_vertices,
        replace_destinations,
        stationary_agents,
        progress_callback
    )

    logger.info(f"\nProgress updates: {progress_updates}")
    logger.info(f"Pending retry list: {[(r.robot_id, r.goal_location) for r in context.pending_retry_destinations]}")

    # Verify
    logger.info("\n=== Verification ===")

    # robot_3 and robot_4 should be QUEUED
    assert "task_3" in progress_updates, "task_3 should be queued"
    assert progress_updates["task_3"][0] == TaskState.QUEUED, "task_3 should be QUEUED"
    assert "robot_1" in progress_updates["task_3"][1], "task_3 should mention robot_1 as blocker"

    assert "task_4" in progress_updates, "task_4 should be queued"
    assert progress_updates["task_4"][0] == TaskState.QUEUED, "task_4 should be QUEUED"
    assert "robot_2" in progress_updates["task_4"][1], "task_4 should mention robot_2 as blocker"

    # robot_5 should NOT be in progress_updates (sent to solver)
    assert "task_5" not in progress_updates, "task_5 should not be queued (sent to solver)"

    # Check result has plan for robot_5
    assert result is not None, "Expected replan to return a plan"
    assert len(result.plans) == 1, f"Expected 1 plan (robot_5), got {len(result.plans)}"
    assert result.plans[0].agent_name == "robot_5", "Expected plan for robot_5"
    assert len(result.plans[0].steps) > 0, "Expected robot_5 to have steps"

    # Check pending retry list has 2 items
    assert len(context.pending_retry_destinations) == 2, \
        f"Expected 2 pending retries, got {len(context.pending_retry_destinations)}"

    retry_robots = {r.robot_id for r in context.pending_retry_destinations}
    assert retry_robots == {"robot_3", "robot_4"}, \
        f"Expected robot_3 and robot_4 in retry list, got {retry_robots}"

    logger.info("\n✓ TEST PASSED!")
    logger.info("✓ robot_3 and robot_4 were correctly QUEUED")
    logger.info("✓ robot_5 was sent to solver and got a plan")
    logger.info("✓ Both blocked robots added to pending retry list")
    logger.info("\nMixed scenario works correctly!\n")


def test_retry_when_obstacle_moves():
    """
    Test that queued robots are retried when the blocking obstacle moves.

    Scenario:
    1. robot_1 at (3,3), staying at (3,3) - obstacle
    2. robot_2 at (1,1), wants to go to (3,3) - BLOCKED (queued)
    3. robot_1 moves to (4,4) - no longer blocking
    4. Trigger replan - robot_2 should be retried and get a plan
    """
    logger.info("\n=== Testing retry when obstacle moves ===\n")

    progress_updates = {}

    def progress_callback(task_id: str, state: TaskState, message: str):
        logger.info(f"Progress: {task_id} -> {state.value}: {message}")
        progress_updates[task_id] = (state, message)

    # Initial setup
    mapf_items = {
        "robot_1": MapfSendTaskPostRequestTaskItem(
            task_id="task_1",
            robot_id="robot_1",
            start_location="3,3",
            goal_location="3,3",
        ),
        "robot_2": MapfSendTaskPostRequestTaskItem(
            task_id="task_2_init",
            robot_id="robot_2",
            start_location="1,1",
            goal_location="1,1",
        ),
    }

    cbs_solver = CBSAdapter()
    context = MAPFProblemContext(cbs_solver, mapf_items)

    # Step 1: robot_2 wants to go to (3,3) - blocked
    logger.info("Step 1: robot_2 wants to go to 3,3 (blocked by robot_1)")
    replace_destinations = [
        ReplaceDestination(task_id="task_2", robot_id="robot_2", goal_location="3,3"),
    ]

    class MockVertex:
        def __init__(self, agent_name, location):
            self.agent_name = agent_name
            self.location_end = location

    committed_vertices = {
        "robot_1": MockVertex("robot_1", "3,3"),
        "robot_2": MockVertex("robot_2", "1,1"),
    }

    stationary_agents = {"robot_1"}

    result1 = context.replan(committed_vertices, replace_destinations, stationary_agents, progress_callback)

    logger.info(f"After step 1: {len(context.pending_retry_destinations)} robots queued")
    assert len(context.pending_retry_destinations) == 1, "robot_2 should be queued"
    assert "task_2" in progress_updates, "task_2 should have been queued"
    assert progress_updates["task_2"][0] == TaskState.QUEUED, "task_2 should be QUEUED"

    # Step 2: robot_1 moves to (4,4) - trigger replan with empty replace_destinations
    logger.info("\nStep 2: robot_1 moves to 4,4 (no longer blocking)")
    progress_updates.clear()  # Clear for next replan

    # Update robot_1's position and give it a new destination
    committed_vertices = {
        "robot_1": MockVertex("robot_1", "4,4"),  # Moved to new position
        "robot_2": MockVertex("robot_2", "1,1"),  # Still at start
    }

    replace_destinations = [
        ReplaceDestination(task_id="task_1_new", robot_id="robot_1", goal_location="6,6"),  # robot_1 goes elsewhere
    ]

    stationary_agents = set()  # robot_1 is no longer stationary

    logger.info("Triggering replan - should retry robot_2")
    result2 = context.replan(committed_vertices, replace_destinations, stationary_agents, progress_callback)

    logger.info(f"\nAfter step 2: progress_updates = {progress_updates}")
    logger.info(f"Pending retry list: {[(r.robot_id, r.goal_location) for r in context.pending_retry_destinations]}")

    # Verify
    logger.info("\n=== Verification ===")

    # robot_2 should NOT be in progress_updates (not queued this time)
    # It should have been sent to solver and gotten a plan
    assert result2 is not None, "Expected replan to return a plan"
    assert len(result2.plans) > 0, "Expected plans to be returned"

    # Find robot_2's plan
    robot_2_plan = None
    for plan in result2.plans:
        if plan.agent_name == "robot_2":
            robot_2_plan = plan
            break

    assert robot_2_plan is not None, "Expected robot_2 to have a plan (retry successful)"
    assert len(robot_2_plan.steps) > 0, "Expected robot_2 to have steps"
    logger.info(f"robot_2 plan has {len(robot_2_plan.steps)} steps")

    # Pending retry list should be empty (retry was successful)
    assert len(context.pending_retry_destinations) == 0, \
        f"Expected 0 pending retries after successful retry, got {len(context.pending_retry_destinations)}"

    logger.info("\n✓ TEST PASSED!")
    logger.info("✓ robot_2 was initially QUEUED when blocked")
    logger.info("✓ robot_2 was automatically retried when obstacle moved")
    logger.info("✓ robot_2 received a valid plan after retry")
    logger.info("\nRetry mechanism works correctly!\n")


if __name__ == "__main__":
    test_mixed_blocking_scenario()
    test_retry_when_obstacle_moves()
