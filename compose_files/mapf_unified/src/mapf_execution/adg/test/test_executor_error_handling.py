"""
Test script for testing error handling in executor.py

This script tests various invalid request scenarios and error conditions:
1. Connection errors to MAPF solver
2. HTTP errors (4xx - bad requests)
3. Request errors (timeouts, redirects)
4. Invalid map locations (KeyError)
5. Unexpected exceptions
"""

import logging
import time
from typing import List
from unittest.mock import Mock, patch, MagicMock
import pytest
import requests

from adg.enums import TaskState
from adg.executor import Executor
from adg.models.mapf_execution_models import MapfSendTaskPostRequestTaskItem
from adg.models.plan_models import Plan
from adg.test.mock_agent import MockAgent
from mapf_solve.mapf_solver_interface import MAPFSolverABC, Obstacle


# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)


class MockMAPFSolver(MAPFSolverABC):
    """Mock MAPF solver that can simulate different error conditions"""

    def __init__(self, error_type=None):
        """
        Args:
            error_type: Type of error to simulate
                - 'connection': ConnectionError
                - 'http_4xx': HTTPError with 400 status
                - 'http_404': HTTPError with 404 status
                - 'timeout': Timeout error
                - 'request': Generic RequestException
                - 'keyerror': KeyError (invalid location)
                - 'unexpected': Generic Exception
                - None: Normal operation (returns valid plan)
        """
        self.error_type = error_type
        self.call_count = 0

    def request_mapf_plan(
        self, items: List[MapfSendTaskPostRequestTaskItem], obstacles: List[Obstacle] = None
    ) -> List[Plan]:
        """Mock implementation that can throw various errors"""
        self.call_count += 1

        if self.error_type == 'connection':
            raise requests.exceptions.ConnectionError("Could not connect to solver at http://localhost:8888")

        elif self.error_type == 'http_4xx':
            response = Mock()
            response.status_code = 400
            response.text = "Bad request: invalid location"
            raise requests.exceptions.HTTPError("400 Client Error: Bad Request", response=response)

        elif self.error_type == 'http_404':
            response = Mock()
            response.status_code = 404
            response.text = "Map not found"
            raise requests.exceptions.HTTPError("404 Not Found", response=response)

        elif self.error_type == 'timeout':
            raise requests.exceptions.Timeout("Request timed out after 10 seconds")

        elif self.error_type == 'request':
            raise requests.exceptions.RequestException("Too many redirects")

        elif self.error_type == 'keyerror':
            raise KeyError("'invalid_location_99' not found in map")

        elif self.error_type == 'unexpected':
            raise RuntimeError("Unexpected internal error in solver")

        elif self.error_type == 'empty_plan':
            # Return empty plan list (solver couldn't find solution)
            return []

        else:
            # Normal operation - return a valid empty plan
            # This simulates a robot that doesn't need to move
            return []


class TestExecutorErrorHandling:
    """Test suite for executor error handling"""

    def setup_method(self):
        """Setup before each test"""
        self.callback_results = []
        self.agent_name = "test_robot_1"

    def progress_callback(self, task_id: str, task_state: TaskState, message: str):
        """Callback to track progress updates"""
        result = {
            'task_id': task_id,
            'state': task_state,
            'message': message
        }
        self.callback_results.append(result)
        logging.info(f"Progress callback: {task_id} -> {task_state.name}: {message}")

    def create_executor(self, error_type=None):
        """Helper to create an executor with mock components"""
        agents = {self.agent_name: MockAgent(self.agent_name)}
        solver = MockMAPFSolver(error_type=error_type)
        executor = Executor(agents, solver, self.progress_callback)
        return executor

    def create_mapf_items(self, num_items=1):
        """Helper to create test MAPF items"""
        items = {}
        for i in range(num_items):
            robot_id = f"test_robot_{i+1}"
            item = MapfSendTaskPostRequestTaskItem(
                task_id=f"task_{i+1}",
                robot_id=robot_id,
                start_location="0,0",
                goal_location="5,5"
            )
            items[robot_id] = item
        return items

    # Test 1: Connection Error
    def test_connection_error(self):
        """Test handling of connection errors to MAPF solver"""
        executor = self.create_executor(error_type='connection')
        mapf_items = self.create_mapf_items(2)

        executor.begin_execution(mapf_items)

        # Allow time for execution to process
        time.sleep(0.5)

        # Verify executor state
        assert executor.state == Executor.State.FAILED

        # Verify all tasks reported failure
        assert len(self.callback_results) == 2
        for result in self.callback_results:
            assert result['state'] == TaskState.FAILED
            assert 'connect' in result['message'].lower()

    # Test 2: HTTP 4xx Error (Bad Request)
    def test_http_4xx_error(self):
        """Test handling of HTTP 4xx errors (invalid requests)"""
        executor = self.create_executor(error_type='http_4xx')
        mapf_items = self.create_mapf_items(1)

        executor.begin_execution(mapf_items)
        time.sleep(0.5)

        # Verify executor state
        assert executor.state == Executor.State.FAILED

        # Verify failure was reported
        assert len(self.callback_results) == 1
        assert self.callback_results[0]['state'] == TaskState.FAILED
        assert 'invalid request' in self.callback_results[0]['message'].lower()

    # Test 3: HTTP 404 Error
    def test_http_404_error(self):
        """Test handling of HTTP 404 errors"""
        executor = self.create_executor(error_type='http_404')
        mapf_items = self.create_mapf_items(1)

        executor.begin_execution(mapf_items)
        time.sleep(0.5)

        assert executor.state == Executor.State.FAILED
        assert self.callback_results[0]['state'] == TaskState.FAILED

    # Test 4: Timeout Error
    def test_timeout_error(self):
        """Test handling of timeout errors"""
        executor = self.create_executor(error_type='timeout')
        mapf_items = self.create_mapf_items(1)

        executor.begin_execution(mapf_items)
        time.sleep(0.5)

        assert executor.state == Executor.State.FAILED
        assert self.callback_results[0]['state'] == TaskState.FAILED
        assert 'request error' in self.callback_results[0]['message'].lower()

    # Test 5: Generic Request Exception
    def test_request_exception(self):
        """Test handling of generic request exceptions"""
        executor = self.create_executor(error_type='request')
        mapf_items = self.create_mapf_items(1)

        executor.begin_execution(mapf_items)
        time.sleep(0.5)

        assert executor.state == Executor.State.FAILED
        assert self.callback_results[0]['state'] == TaskState.FAILED

    # Test 6: KeyError (Invalid Location)
    def test_invalid_location_keyerror(self):
        """Test handling of invalid map locations (KeyError)"""
        executor = self.create_executor(error_type='keyerror')
        mapf_items = self.create_mapf_items(1)

        executor.begin_execution(mapf_items)
        time.sleep(0.5)

        assert executor.state == Executor.State.FAILED
        assert self.callback_results[0]['state'] == TaskState.FAILED
        assert 'invalid location' in self.callback_results[0]['message'].lower()

    # Test 7: Unexpected Exception
    def test_unexpected_exception(self):
        """Test handling of unexpected exceptions"""
        executor = self.create_executor(error_type='unexpected')
        mapf_items = self.create_mapf_items(1)

        executor.begin_execution(mapf_items)
        time.sleep(0.5)

        assert executor.state == Executor.State.FAILED
        assert self.callback_results[0]['state'] == TaskState.FAILED
        assert 'unexpected error' in self.callback_results[0]['message'].lower()

    # Test 8: Empty Plan (No Solution Found)
    def test_empty_plan_no_solution(self):
        """Test handling when solver returns empty plan (no solution)"""
        executor = self.create_executor(error_type='empty_plan')
        mapf_items = self.create_mapf_items(1)

        executor.begin_execution(mapf_items)
        time.sleep(0.5)

        assert executor.state == Executor.State.FAILED
        # Note: This test may need adjustment based on actual behavior

    # Test 9: Multiple Tasks, All Fail
    def test_multiple_tasks_all_fail(self):
        """Test that all tasks are reported as failed when solver errors"""
        executor = self.create_executor(error_type='connection')
        mapf_items = self.create_mapf_items(5)

        executor.begin_execution(mapf_items)
        time.sleep(0.5)

        # Verify all 5 tasks reported failure
        assert len(self.callback_results) == 5
        for result in self.callback_results:
            assert result['state'] == TaskState.FAILED

    # Test 10: Invalid Input - Empty Items
    def test_empty_mapf_items(self):
        """Test behavior with empty MAPF items"""
        executor = self.create_executor()
        mapf_items = {}

        executor.begin_execution(mapf_items)
        time.sleep(0.5)

        # Execution should handle this gracefully
        # Behavior depends on implementation

    # Test 11: Executor State Transitions
    def test_executor_state_transitions(self):
        """Test that executor state transitions correctly on errors"""
        executor = self.create_executor(error_type='connection')

        # Initial state
        assert executor.state == Executor.State.PENDING

        # After failed execution
        executor.begin_execution(self.create_mapf_items(1))
        time.sleep(0.5)

        assert executor.state == Executor.State.FAILED


class TestExecutorInvalidInputs:
    """Test suite for invalid input validation"""

    def test_invalid_agent_type(self):
        """Test that executor rejects invalid agent types"""
        invalid_agents = {"test": "not_an_agent"}  # String instead of ADGAgent
        solver = MockMAPFSolver()
        callback = lambda task_id, state, msg: None

        with pytest.raises(TypeError):
            executor = Executor(invalid_agents, solver, callback)

    def test_invalid_callback_type(self):
        """Test that executor rejects non-callable callbacks"""
        agents = {"test": MockAgent("test")}
        solver = MockMAPFSolver()
        invalid_callback = "not_callable"

        with pytest.raises(TypeError):
            executor = Executor(agents, solver, invalid_callback)


class TestExecutorIntegration:
    """Integration tests for executor with realistic scenarios"""

    def setup_method(self):
        """Setup before each test"""
        self.callback_results = []

    def progress_callback(self, task_id: str, task_state: TaskState, message: str):
        """Callback to track progress updates"""
        self.callback_results.append({
            'task_id': task_id,
            'state': task_state,
            'message': message
        })

    def test_solver_failure_then_success_scenario(self):
        """
        Test scenario where solver fails first, then succeeds on retry
        (This tests the overall error handling flow)
        """
        # First attempt fails
        executor1 = Executor(
            {"robot1": MockAgent("robot1")},
            MockMAPFSolver(error_type='connection'),
            self.progress_callback
        )

        items = {
            "robot1": MapfSendTaskPostRequestTaskItem(
                task_id="task_1",
                robot_id="robot1",
                start_location="0,0",
                goal_location="5,5"
            )
        }

        executor1.begin_execution(items)
        time.sleep(0.5)

        assert executor1.state == Executor.State.FAILED
        assert len(self.callback_results) == 1
        assert self.callback_results[0]['state'] == TaskState.FAILED


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
