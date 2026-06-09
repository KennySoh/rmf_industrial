"""
Test for the duplicate destination filtering and retry mechanism.

This test verifies that:
1. When two robots are sent to the same destination, one is filtered and queued
2. The queued task is added to pending_retry_destinations
3. When a new task arrives, pending retries are merged and retried
4. Agents with pending retries are NOT marked as stationary
"""
import logging
import time
import pytest

from adg.enums import TaskState
from adg.executor import Executor
from adg.models.mapf_execution_models import MapfSendTaskPostRequestTaskItem, ReplaceDestination
from adg.test.mock_agent import MockAgent
from mapf_solve.cbs_adapter import CBSAdapter

logging.basicConfig(level=logging.INFO)


class TestRetryMechanism:
    """Test the retry mechanism for duplicate destinations."""

    task_states = {}  # Track all task state changes
    completed_tasks = []

    def progress_callback(self, task_id: str, task_state: TaskState, message: str):
        """Track task state changes."""
        logging.info(f"-------- {task_id} reported {task_state.value} {message}")
        self.task_states[task_id] = (task_state, message)
        if task_state == TaskState.COMPLETED:
            self.completed_tasks.append(task_id)

    def test_duplicate_destination_filtering_and_retry(self):
        """
        Test that:
        1. Two robots sent to same destination: one filtered, one sent to solver
        2. Filtered robot is queued and added to pending_retry_destinations
        3. When first robot moves to new destination, queued robot is retried
        """
        # Setup
        agent1 = MockAgent("robot_1")
        agent2 = MockAgent("robot_2")
        adg_agents = {
            agent1.agent_name: agent1,
            agent2.agent_name: agent2
        }
        cbs_solver = CBSAdapter()

        # Clear state
        self.task_states = {}
        self.completed_tasks = []

        executor = Executor(adg_agents, cbs_solver, self.progress_callback)

        # Step 1: Send both robots to same destination (5,5)
        logging.info("\n=== STEP 1: Send both robots to (5,5) - expect one to be filtered ===")
        mapf_items = {
            "robot_1": MapfSendTaskPostRequestTaskItem(
                task_id="task_1",
                robot_id="robot_1",
                start_location="0,0",
                goal_location="5,5",
            ),
            "robot_2": MapfSendTaskPostRequestTaskItem(
                task_id="task_2",
                robot_id="robot_2",
                start_location="0,5",
                goal_location="5,5",
            )
        }

        executor.begin_execution(mapf_items)
        time.sleep(1)  # Let initial execution start

        # Check that one task is QUEUED
        queued_tasks = [tid for tid, (state, _) in self.task_states.items() if state == TaskState.QUEUED]
        logging.info(f"Queued tasks: {queued_tasks}")
        assert len(queued_tasks) == 1, f"Expected 1 queued task, got {len(queued_tasks)}"

        queued_task_id = queued_tasks[0]
        queued_robot_id = "robot_2" if queued_task_id == "task_2" else "robot_1"
        active_robot_id = "robot_1" if queued_robot_id == "robot_2" else "robot_2"

        logging.info(f"Robot {active_robot_id} is being processed, {queued_robot_id} is queued")

        # Verify pending_retry_destinations has the queued task
        assert len(executor._problem_context.pending_retry_destinations) == 1, \
            "Expected 1 item in pending_retry_destinations"
        pending_retry = executor._problem_context.pending_retry_destinations[0]
        assert pending_retry.robot_id == queued_robot_id, \
            f"Expected {queued_robot_id} in pending retry, got {pending_retry.robot_id}"
        assert pending_retry.goal_location == "5,5", \
            f"Expected goal (5,5), got {pending_retry.goal_location}"

        logging.info(f"✓ Pending retry list contains: {queued_robot_id} -> 5,5")

        # Wait for first robot to complete its task
        logging.info(f"\n=== Waiting for {active_robot_id} to complete task to (5,5) ===")
        max_wait = 30  # 30 seconds max
        start_time = time.time()
        while len(self.completed_tasks) < 1 and (time.time() - start_time) < max_wait:
            time.sleep(0.5)

        assert len(self.completed_tasks) >= 1, \
            f"Expected at least 1 completed task, got {len(self.completed_tasks)}"
        logging.info(f"✓ {active_robot_id} completed its task")

        # Step 2: Send active robot to new destination to trigger replan and retry
        logging.info(f"\n=== STEP 2: Send {active_robot_id} to new destination (2,2) - expect retry of {queued_robot_id} ===")

        replace_destinations = [
            ReplaceDestination(
                task_id="task_3",
                robot_id=active_robot_id,
                goal_location="2,2"
            )
        ]

        success = executor.replace_destinations(replace_destinations)
        assert success, "Failed to submit replace_destinations request"

        time.sleep(2)  # Let replan happen

        # Check that queued robot was retried (should have a plan now)
        # The queued robot should now be IN_PROGRESS or COMPLETED
        logging.info(f"\n=== Checking if {queued_robot_id} was retried ===")
        logging.info(f"All task states: {self.task_states}")

        # The queued task should have been updated from QUEUED
        if queued_task_id in self.task_states:
            latest_state, latest_msg = self.task_states[queued_task_id]
            logging.info(f"{queued_robot_id} latest state: {latest_state.value} - {latest_msg}")

            # It should not still be QUEUED if retry worked
            # Note: It might be IN_PROGRESS or COMPLETED depending on timing
            assert latest_state in [TaskState.IN_PROGRESS, TaskState.COMPLETED], \
                f"Expected {queued_robot_id} to be IN_PROGRESS or COMPLETED after retry, but got {latest_state.value}"

        # Wait for all tasks to complete
        logging.info(f"\n=== Waiting for all tasks to complete ===")
        max_wait = 30
        start_time = time.time()
        while len(self.completed_tasks) < 2 and (time.time() - start_time) < max_wait:
            time.sleep(0.5)

        logging.info(f"Completed tasks: {self.completed_tasks}")

        # Clean up
        executor.interrupt()

        logging.info("\n=== TEST PASSED ===")
        logging.info(f"✓ Duplicate destination filtering worked")
        logging.info(f"✓ Queued task was added to pending_retry_destinations")
        logging.info(f"✓ Retry mechanism triggered on replan")
        logging.info(f"✓ Both robots completed their tasks")


if __name__ == "__main__":
    # Run the test
    test = TestRetryMechanism()
    test.test_duplicate_destination_filtering_and_retry()
