"""
Unit test for obstacle-blocking conflict detection with CBSAdapter.

This test uses INTEGER coordinates that CBSAdapter expects.
"""
import logging

from adg.models.mapf_execution_models import MapfSendTaskPostRequestTaskItem, ReplaceDestination
from adg.execution_context import MAPFProblemContext
from adg.enums import TaskState
from mapf_solve.cbs_adapter import CBSAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_obstacle_blocking_with_cbs():
    """
    Test obstacle-blocking detection with CBSAdapter using integer coordinates.

    Scenario:
    1. robot_1 at (3,3), staying at (3,3) - stationary obstacle
    2. robot_2 at (1,1), wants to go to (3,3) - BLOCKED
    3. robot_2 should be QUEUED, not sent to solver
    """
    logger.info("\n=== Testing obstacle-blocking with CBSAdapter (integer coords) ===\n")

    progress_updates = {}

    def progress_callback(task_id: str, state: TaskState, message: str):
        logger.info(f"Progress: {task_id} -> {state.value}: {message}")
        progress_updates[task_id] = (state, message)

    # Create initial MAPF items with INTEGER coordinates
    mapf_items = {
        "robot_1": MapfSendTaskPostRequestTaskItem(
            task_id="task_1",
            robot_id="robot_1",
            start_location="3,3",  # Integer coords
            goal_location="3,3",   # Stationary - will become obstacle
        ),
        "robot_2": MapfSendTaskPostRequestTaskItem(
            task_id="task_2_initial",
            robot_id="robot_2",
            start_location="1,1",  # Integer coords
            goal_location="1,1",   # Initially stationary
        ),
    }

    cbs_solver = CBSAdapter()
    context = MAPFProblemContext(cbs_solver, mapf_items)

    # Simulate replan: robot_2 wants to go to (3,3) - blocked by robot_1
    logger.info("Creating replan where robot_2 wants to go to 3,3 (blocked by stationary robot_1)")

    replace_destinations = [
        ReplaceDestination(
            task_id="task_2",
            robot_id="robot_2",
            goal_location="3,3"  # BLOCKED by robot_1!
        )
    ]

    class MockVertex:
        def __init__(self, agent_name, location):
            self.agent_name = agent_name
            self.location_end = location

    committed_vertices = {
        "robot_1": MockVertex("robot_1", "3,3"),  # At (3,3), staying at (3,3)
        "robot_2": MockVertex("robot_2", "1,1"),  # At (1,1)
    }

    stationary_agents = {"robot_1"}

    logger.info(f"Stationary agents: {stationary_agents}")
    logger.info(f"Incoming destination: robot_2 -> 3,3")

    # Call replan - this should queue robot_2 because (3,3) is blocked
    logger.info("\nCalling replan()...")
    result = context.replan(
        committed_vertices,
        replace_destinations,
        stationary_agents,
        progress_callback
    )

    logger.info(f"\nReplan result: {result}")
    logger.info(f"Progress updates: {progress_updates}")
    logger.info(f"Pending retry list: {[(r.robot_id, r.goal_location) for r in context.pending_retry_destinations]}")

    # Verify the results
    logger.info("\n=== Verification ===")

    # Check that replan returned empty plan (all agents were queued)
    assert result is not None, "Expected replan to return a plan (even if empty)"
    assert len(result.plans) == 0, f"Expected empty plan when all agents queued, got {len(result.plans)} plans"

    # Check that task_2 was queued
    assert "task_2" in progress_updates, "task_2 should have a progress update"
    state, message = progress_updates["task_2"]

    logger.info(f"task_2 state: {state.value}")
    logger.info(f"task_2 message: {message}")

    assert state == TaskState.QUEUED, \
        f"Expected task_2 to be QUEUED, but got {state.value}"

    assert "blocked by stationary robot" in message, \
        f"Expected message about being blocked, but got: {message}"

    assert "robot_1" in message, \
        f"Expected message to mention robot_1 as blocker, but got: {message}"

    # Check that task_2 was added to pending retry list
    assert len(context.pending_retry_destinations) == 1, \
        f"Expected 1 pending retry, got {len(context.pending_retry_destinations)}"

    retry_dest = context.pending_retry_destinations[0]
    assert retry_dest.robot_id == "robot_2", \
        f"Expected robot_2 in pending retry, got {retry_dest.robot_id}"
    assert retry_dest.goal_location == "3,3", \
        f"Expected goal 3,3, got {retry_dest.goal_location}"

    logger.info("\n✓ TEST PASSED!")
    logger.info("✓ robot_2 was correctly QUEUED (not sent to solver)")
    logger.info("✓ robot_2 was added to pending retry list")
    logger.info("✓ Conflict message correctly identifies robot_1 as blocker")
    logger.info("\nThe obstacle-blocking detection works with CBSAdapter!\\n")


def test_no_conflict_with_cbs():
    """
    Test that robots without conflicts are sent to solver and get plans.

    Scenario:
    1. robot_1 at (3,3), staying at (3,3) - stationary obstacle
    2. robot_2 at (1,1), wants to go to (5,5) - NOT blocked
    3. robot_2 should be sent to solver and get a plan
    """
    logger.info("\n=== Testing NO conflict scenario with CBSAdapter ===\n")

    progress_updates = {}

    def progress_callback(task_id: str, state: TaskState, message: str):
        logger.info(f"Progress: {task_id} -> {state.value}: {message}")
        progress_updates[task_id] = (state, message)

    # Create initial MAPF items with INTEGER coordinates
    mapf_items = {
        "robot_1": MapfSendTaskPostRequestTaskItem(
            task_id="task_1",
            robot_id="robot_1",
            start_location="3,3",
            goal_location="3,3",  # Stationary
        ),
        "robot_2": MapfSendTaskPostRequestTaskItem(
            task_id="task_2_initial",
            robot_id="robot_2",
            start_location="1,1",
            goal_location="1,1",
        ),
    }

    cbs_solver = CBSAdapter()
    context = MAPFProblemContext(cbs_solver, mapf_items)

    # Simulate replan: robot_2 wants to go to (5,5) - NOT blocked
    logger.info("Creating replan where robot_2 wants to go to 5,5 (NOT blocked)")

    replace_destinations = [
        ReplaceDestination(
            task_id="task_2",
            robot_id="robot_2",
            goal_location="5,5"  # NOT blocked by robot_1
        )
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

    logger.info(f"Stationary agents: {stationary_agents}")
    logger.info(f"Incoming destination: robot_2 -> 5,5 (NOT blocked)")

    # Call replan
    logger.info("\nCalling replan()...")
    result = context.replan(
        committed_vertices,
        replace_destinations,
        stationary_agents,
        progress_callback
    )

    logger.info(f"\nReplan result: {result}")
    logger.info(f"Progress updates: {progress_updates}")

    # Verify the results
    logger.info("\n=== Verification ===")

    # Check that task_2 was NOT queued (no progress update during filtering)
    # It should have been sent to solver and gotten a plan
    assert result is not None, "Expected solver to return a plan"
    assert len(result.plans) > 0, "Expected at least one plan"

    # Find robot_2's plan
    robot_2_plan = None
    for plan in result.plans:
        if plan.agent_name == "robot_2":
            robot_2_plan = plan
            break

    assert robot_2_plan is not None, "Expected robot_2 to have a plan"
    assert len(robot_2_plan.steps) > 0, "Expected robot_2 to have steps in plan"

    logger.info(f"robot_2 plan has {len(robot_2_plan.steps)} steps")
    logger.info(f"First step: {robot_2_plan.steps[0].step_from.node} -> {robot_2_plan.steps[0].step_to.node}")

    # Check that pending retry list is empty
    assert len(context.pending_retry_destinations) == 0, \
        f"Expected 0 pending retries, got {len(context.pending_retry_destinations)}"

    logger.info("\n✓ TEST PASSED!")
    logger.info("✓ robot_2 was sent to solver (not filtered)")
    logger.info("✓ robot_2 received a valid plan")
    logger.info("✓ No tasks were queued")
    logger.info("\nCBSAdapter works correctly when there are no conflicts!\\n")


if __name__ == "__main__":
    test_obstacle_blocking_with_cbs()
    test_no_conflict_with_cbs()
