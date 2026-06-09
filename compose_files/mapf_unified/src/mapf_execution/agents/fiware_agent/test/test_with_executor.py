import logging
import time
import pytest

from adg.enums import TaskState
from adg.executor import Executor
from adg.models.mapf_execution_models import MapfSendTaskPostRequestTaskItem, ReplaceDestination
from adg.test.mock_agent import MockAgent
from agents.fiware_agent.agent_http_order import HTTPOrderAgent
from mapf_solve.cbs_adapter import CBSAdapter



@pytest.fixture(scope="class")
def http_order_agent_fixture():
    print("Setting up..")

    agent_args = {"url": "http://localhost:8080", "mock_complete_actions": True}
    agent_name = "test_agent"
    agent = HTTPOrderAgent(agent_name, agent_args)

    yield agent


class TestAgentWithExecutor:

    first_completion_flag = False
    completions = []

    @pytest.mark.usefixtures("http_order_agent_fixture")
    def test_replanning_with_executor(self, http_order_agent_fixture):

        agent = http_order_agent_fixture

        mapf_items_list = [
            MapfSendTaskPostRequestTaskItem(
                task_id="agent_0_task",
                robot_id="test_agent",
                start_location="0,0",
                goal_location="5,0",
            )
        ]
        
        adg_agents = {agent.agent_name: agent}
        cbs_solver = CBSAdapter()

        def progress_callback(task_id: str, task_state: TaskState, message: str):
            logging.info(f"-------- {task_id} reported {task_state} {message}\n")
            if task_state == TaskState.COMPLETED:
                self.completions.append(task_id)
                print(self.completions)
            if not self.first_completion_flag:
                replace_destinations = [
                    ReplaceDestination(
                        task_id="agent_0_replace", robot_id=agent.agent_name, goal_location="0,1"
                    ),
                ]
                executor.replace_destinations(replace_destinations)
                self.first_completion_flag = True

        mapf_items = {}
        for item in mapf_items_list:
            if item.robot_id in mapf_items:
                raise ValueError(f"Duplicate robot_id found: {item.robot_id}")
            mapf_items[item.robot_id] = item

        executor = Executor(adg_agents, cbs_solver, progress_callback)
        executor.begin_execution(mapf_items)
        while True:
            if len(self.completions) == 2:
                executor.interrupt()
                break
        assert agent.current_order.task_id == "agent_0_replace"
