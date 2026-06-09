import logging
import time


from adg.enums import TaskState
from adg.executor import Executor
from adg.models.mapf_execution_models import (
    MapfSendTaskPostRequestTaskItem,
    ReplaceDestination,
)
from agents.fiware_agent.agent_http_order import HTTPOrderAgent
from agents.shared_memory_dict_agent.agent_shmd import SharedMemoryAgent
from mapf_solve.cbs_adapter import CBSAdapter

logger = logging.getLogger("example_04")
formatter = logging.Formatter(
    "[%(levelname)s] %(asctime)s:%(msecs)03d %(name)s: %(message)s", datefmt="%H:%M:%S"
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False


done_flag = False


def main():

    # Example tasks.
    # These start locations match the start locations in 4_robots.yaml - simulation reads the file to determine
    # spawn locations for robots.

    # Test with starts == goals
    mapf_items_list = [
        MapfSendTaskPostRequestTaskItem(
            task_id="agent_0_task",
            robot_id="agent_0",
            start_location="0,0",
            goal_location="0,0",
        ),
        MapfSendTaskPostRequestTaskItem(
            task_id="agent_1_task",
            robot_id="agent_1",
            start_location="2,0",
            goal_location="2,0",
        ),
        MapfSendTaskPostRequestTaskItem(
            task_id="agent_2_task",
            robot_id="agent_2",
            start_location="1,0",
            goal_location="1,0",
        ),
        MapfSendTaskPostRequestTaskItem(
            task_id="agent_3_task",
            robot_id="agent_3",
            start_location="4,0",
            goal_location="4,0",
        ),
    ]

    agent_names = [item.robot_id for item in mapf_items_list]
    adg_agents = {}
    agent_args = {
        "url": "",
        "mock_complete_actions": True
    }
    for agent_name in agent_names:
        adg_agents[agent_name] = HTTPOrderAgent(
            agent_name, agent_args
        )

    cbs_solver = CBSAdapter()

    def progress_callback(task_id: str, task_state: TaskState, message: str):
        global done_flag
        logger.info(f"-------- {task_id} reported {task_state} {message}\n")

        # Test a ReplaceDestination immediately after the first completion
        if not done_flag and task_state == TaskState.COMPLETED and task_id == "agent_3_task":
            replace_destinations = [
                ReplaceDestination(
                    task_id="agent_3_replace", robot_id="agent_3", goal_location="4,4"
                ),
            ]
            executor.replace_destinations(replace_destinations)
            done_flag = True

    mapf_items = {}

    for item in mapf_items_list:
        if item.robot_id in mapf_items:
            raise ValueError(f"Duplicate robot_id found: {item.robot_id}")
        mapf_items[item.robot_id] = item

    executor = Executor(adg_agents, cbs_solver, progress_callback)
    executor.begin_execution(mapf_items)

    time.sleep(3)

    # Test consecutive ReplaceDestinations without completions in between.

    replace_destinations = [
        ReplaceDestination(
            task_id="agent_3_replace", robot_id="agent_3", goal_location="4,0"
        ),
    ]

    time.sleep(1)
    executor.replace_destinations(replace_destinations)

    replace_destinations = [
        ReplaceDestination(
            task_id="agent_3_replace1", robot_id="agent_3", goal_location="4,4"
        ),
    ]
    executor.replace_destinations(replace_destinations)




if __name__ == "__main__":
    main()
