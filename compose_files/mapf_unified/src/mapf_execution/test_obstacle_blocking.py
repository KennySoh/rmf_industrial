"""
Unit test for obstacle-blocking conflict detection and queuing.

This tests that when a robot's goal is blocked by a stationary robot,
the task is queued instead of being sent to the solver (which would fail).
"""
import logging

from adg.models.mapf_execution_models import MapfSendTaskPostRequestTaskItem, ReplaceDestination
from adg.execution_context import MAPFProblemContext
from adg.enums import TaskState
from mapf_solve.cbs_adapter import CBSAdapter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_obstacle_blocking_queue():
    """
    Test that robots whose goals are blocked by stationary robots get queued.

    Scenario:
    1. robot_1 at P65, going to P65 (stationary - becomes obstacle)
    2. robot_2 at P536, wants to go to P65 (blocked by robot_1)
    3. robot_2 should be QUEUED, not sent to solver
    """
    logger.info("\n=== Testing obstacle-blocking conflict detection ===\n")

    # Track progress callbacks
    progress_updates = {}

    def progress_callback(task_id: str, state: TaskState, message: str):
        logger.info(f"Progress: {task_id} -> {state.value}: {message}")
        progress_updates[task_id] = (state, message)

    # Create initial MAPF items
    # robot_1 is at P65 and staying at P65 (stationary)
    # robot_2 is also in the system, at P536
    mapf_items = {
        "robot_1": MapfSendTaskPostRequestTaskItem(
            task_id="task_1",
            robot_id="robot_1",
            start_location="182.97,-111.75",  # P65 coordinates
            goal_location="182.97,-111.75",   # Stationary - will become obstacle
        ),
        "robot_2": MapfSendTaskPostRequestTaskItem(
            task_id="task_2_initial",
            robot_id="robot_2",
            start_location="168.85,-113.5",   # P536 coordinates
            goal_location="168.85,-113.5",    # Initially stationary
        ),
    }

    # Create problem context
    cbs_solver = CBSAdapter()
    context = MAPFProblemContext(cbs_solver, mapf_items)

    # Simulate replan: robot_2 wants to go to P65 (blocked by robot_1)
    logger.info("Creating replan where robot_2 wants to go to 182.97,-111.75 (blocked by stationary robot_1)")

    replace_destinations = [
        ReplaceDestination(
            task_id="task_2",
            robot_id="robot_2",
            goal_location="182.97,-111.75"  # P65 - Blocked by robot_1!
        )
    ]

    # Simulate committed vertices (current robot positions)
    class MockVertex:
        def __init__(self, agent_name, location):
            self.agent_name = agent_name
            self.location_end = location  # Need location_end attribute

    committed_vertices = {
        "robot_1": MockVertex("robot_1", "182.97,-111.75"),  # At P65, staying at P65
        "robot_2": MockVertex("robot_2", "168.85,-113.5"),   # At P536
    }

    # Simulate stationary agents (robot_1 doesn't need to move)
    stationary_agents = {"robot_1"}

    logger.info(f"Stationary agents: {stationary_agents}")
    logger.info(f"Incoming destination: robot_2 -> 182.97,-111.75 (P65)")

    # Call replan - this should queue robot_2 because P65 is blocked
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
    assert retry_dest.goal_location == "182.97,-111.75", \
        f"Expected goal 182.97,-111.75, got {retry_dest.goal_location}"

    logger.info("\n✓ TEST PASSED!")
    logger.info("✓ robot_2 was correctly QUEUED (not sent to solver)")
    logger.info("✓ robot_2 was added to pending retry list")
    logger.info("✓ Conflict message correctly identifies robot_1 as blocker")
    logger.info("\nThe obstacle-blocking detection is working correctly!\n")


def test_obstacle_blocking_multiple_robots():
    """
    Test multiple robots blocked by different stationary robots.

    Scenario:
    1. robot_1 at P65 (stationary - obstacle at P65)
    2. robot_3 at P70 (stationary - obstacle at P70)
    3. robot_2 wants P65 (blocked by robot_1)
    4. robot_4 wants P70 (blocked by robot_3)
    5. robot_5 wants P62 (not blocked)

    Expected:
    - robot_2 and robot_4 should be QUEUED
    - robot_5 should be sent to solver
    """
    logger.info("\n=== Testing multiple obstacle-blocking conflicts ===\n")

    progress_updates = {}

    def progress_callback(task_id: str, state: TaskState, message: str):
        logger.info(f"Progress: {task_id} -> {state.value}: {message}")
        progress_updates[task_id] = (state, message)

    # Initial robots (stationary)
    mapf_items = {
        "robot_1": MapfSendTaskPostRequestTaskItem(
            task_id="task_1",
            robot_id="robot_1",
            start_location="182.97,-111.75",  # P65
            goal_location="182.97,-111.75",
        ),
        "robot_2": MapfSendTaskPostRequestTaskItem(
            task_id="task_2_init",
            robot_id="robot_2",
            start_location="168.85,-113.5",  # P536
            goal_location="168.85,-113.5",
        ),
        "robot_3": MapfSendTaskPostRequestTaskItem(
            task_id="task_3",
            robot_id="robot_3",
            start_location="180.25,-106.13",  # P70
            goal_location="180.25,-106.13",
        ),
        "robot_4": MapfSendTaskPostRequestTaskItem(
            task_id="task_4_init",
            robot_id="robot_4",
            start_location="170.5,-109.24",  # P431
            goal_location="170.5,-109.24",
        ),
        "robot_5": MapfSendTaskPostRequestTaskItem(
            task_id="task_5_init",
            robot_id="robot_5",
            start_location="168.08,-119.73",  # P639
            goal_location="168.08,-119.73",
        ),
    }

    cbs_solver = CBSAdapter()
    context = MAPFProblemContext(cbs_solver, mapf_items)

    # New tasks
    replace_destinations = [
        ReplaceDestination(task_id="task_2", robot_id="robot_2", goal_location="182.97,-111.75"),  # P65 - Blocked
        ReplaceDestination(task_id="task_4", robot_id="robot_4", goal_location="180.25,-106.13"),  # P70 - Blocked
        ReplaceDestination(task_id="task_5", robot_id="robot_5", goal_location="184.18,-114.56"),  # P62 - Not blocked
    ]

    class MockVertex:
        def __init__(self, agent_name, location):
            self.agent_name = agent_name
            self.location_end = location  # Need location_end attribute

    committed_vertices = {
        "robot_1": MockVertex("robot_1", "182.97,-111.75"),  # P65
        "robot_2": MockVertex("robot_2", "168.85,-113.5"),   # P536
        "robot_3": MockVertex("robot_3", "180.25,-106.13"),  # P70
        "robot_4": MockVertex("robot_4", "170.5,-109.24"),   # P431
        "robot_5": MockVertex("robot_5", "168.08,-119.73"),  # P639
    }

    stationary_agents = {"robot_1", "robot_3"}

    logger.info(f"Stationary agents (obstacles): {stationary_agents}")
    logger.info(f"Incoming destinations:")
    for dest in replace_destinations:
        logger.info(f"  {dest.robot_id} -> {dest.goal_location}")

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

    # robot_2 and robot_4 should be QUEUED
    assert "task_2" in progress_updates, "task_2 should be queued"
    assert progress_updates["task_2"][0] == TaskState.QUEUED, "task_2 should be QUEUED"
    assert "robot_1" in progress_updates["task_2"][1], "task_2 should mention robot_1 as blocker"

    assert "task_4" in progress_updates, "task_4 should be queued"
    assert progress_updates["task_4"][0] == TaskState.QUEUED, "task_4 should be QUEUED"
    assert "robot_3" in progress_updates["task_4"][1], "task_4 should mention robot_3 as blocker"

    # robot_5 should NOT be in progress_updates (sent to solver successfully)
    # (progress_callback is only called for QUEUED tasks during filtering)

    # Check pending retry list has 2 items
    assert len(context.pending_retry_destinations) == 2, \
        f"Expected 2 pending retries, got {len(context.pending_retry_destinations)}"

    retry_robots = {r.robot_id for r in context.pending_retry_destinations}
    assert retry_robots == {"robot_2", "robot_4"}, \
        f"Expected robot_2 and robot_4 in retry list, got {retry_robots}"

    logger.info("\n✓ TEST PASSED!")
    logger.info("✓ robot_2 and robot_4 were correctly QUEUED")
    logger.info("✓ robot_5 was sent to solver (not blocked)")
    logger.info("✓ Both blocked robots added to pending retry list")
    logger.info("\nMultiple obstacle-blocking detection is working correctly!\n")


if __name__ == "__main__":
    test_obstacle_blocking_queue()
    test_obstacle_blocking_multiple_robots()
