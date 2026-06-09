import logging
import os
from pathlib import Path
import time


from adg.enums import TaskState
from adg.executor import Executor
from adg.models.mapf_execution_models import (
    MapfSendTaskPostRequestTaskItem,
    ReplaceDestination,
)
from agents.shared_memory_dict_agent.agent_shmd import SharedMemoryAgent
from mapf_solve.mapf_solve_request import MAPFServiceAdapter

# Test using obstacles to keep robots in place when replanning.
# Uses the mapf solver service (ros2 run mapf run_mapf_service) and a building file.

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "[%(levelname)s] %(asctime)s:%(msecs)03d %(name)s: %(message)s", datefmt="%H:%M:%S"
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def main():

    # Example tasks.
    # These start locations match the start locations in 4_robots.yaml - simulation reads the file to determine
    # spawn locations for robots.

    mapf_items_list = [
        MapfSendTaskPostRequestTaskItem(
            task_id="agent_0_task",
            robot_id="agent_0",
            start_location="P90",
            goal_location="P90",
        ),
        MapfSendTaskPostRequestTaskItem(
            task_id="agent_1_task",
            robot_id="agent_1",
            start_location="P91",
            goal_location="P91",
        ),
        MapfSendTaskPostRequestTaskItem(
            task_id="agent_2_task",
            robot_id="agent_2",
            start_location="P81",
            goal_location="P82",
        )
    ]

    agent_names = [item.robot_id for item in mapf_items_list]
    adg_agents = {}
    agent_args = {}
    for agent_name in agent_names:
        adg_agents[agent_name] = SharedMemoryAgent(agent_name, agent_args)

    map_filename = "building10x10.yaml"
    base_map_name = "building10x10"
    solver_adapter = MAPFServiceAdapter(Path(__file__).with_name(map_filename), "http://localhost:8888", base_map_name)

    def progress_callback(task_id: str, task_state: TaskState, message: str):
        logger.info(f"-------- {task_id} reported {task_state} {message}\n")

    mapf_items = {}

    for item in mapf_items_list:
        if item.robot_id in mapf_items:
            raise ValueError(f"Duplicate robot_id found: {item.robot_id}")
        mapf_items[item.robot_id] = item

    executor = Executor(adg_agents, solver_adapter, progress_callback)
    executor.begin_execution(mapf_items)

    time.sleep(2)

    replace_destinations = [
        ReplaceDestination(
            task_id="0", robot_id="agent_0", goal_location="P92"
        ),
        # ReplaceDestination(
        #     task_id="0", robot_id="agent_1", goal_location="1,1"
        # ),
    ]

    executor.replace_destinations(replace_destinations)


if __name__ == "__main__":
    main()
