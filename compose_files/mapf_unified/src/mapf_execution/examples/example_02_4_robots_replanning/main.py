import logging
import time


from adg.enums import TaskState
from adg.executor import Executor
from adg.models.mapf_execution_models import MapfSendTaskPostRequestTaskItem, ReplaceDestination
from agents.shared_memory_dict_agent.agent_shmd import SharedMemoryAgent
from mapf_solve.cbs_adapter import CBSAdapter

# Moves 4 robots in PyBullet.
# Executor solves for a plan.
# After some time, triggers replanning with a second plan.

logger = logging.getLogger("example_02")
formatter = logging.Formatter(
    "[%(levelname)s] %(asctime)s:%(msecs)03d %(name)s: %(message)s", datefmt="%H:%M:%S"
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False


def main():

    # Example tasks.
    # These start locations match the start locations in 4_robots.yaml - simulation reads the file to determine
    # spawn locations for robots.

    mapf_items_list = [
        MapfSendTaskPostRequestTaskItem(
            task_id="agent_0_task", robot_id="agent_0", start_location="0,0", goal_location="2,0"
        ),
        MapfSendTaskPostRequestTaskItem(
            task_id="agent_1_task", robot_id="agent_1", start_location="2,0", goal_location="0,0"
        ),
        MapfSendTaskPostRequestTaskItem(
            task_id="agent_2_task", robot_id="agent_2", start_location="1,0", goal_location="1,2"
        ),
        MapfSendTaskPostRequestTaskItem(
            task_id="agent_3_task", robot_id="agent_3", start_location="4,0", goal_location="4,4"
        )
    ]

    agent_names = [item.robot_id for item in mapf_items_list]
    adg_agents = {}
    agent_args = {}
    for agent_name in agent_names:
        adg_agents[agent_name] = SharedMemoryAgent(
            agent_name, agent_args
        )

    cbs_solver = CBSAdapter()

    def progress_callback(task_id: str, task_state: TaskState, message: str):
        logger.info(f"-------- {task_id} reported {task_state} {message}\n")

    mapf_items = {}

    for item in mapf_items_list:
        if item.robot_id in mapf_items:
            raise ValueError(f"Duplicate robot_id found: {item.robot_id}")
        mapf_items[item.robot_id] = item

    executor = Executor(adg_agents, cbs_solver, progress_callback)
    executor.begin_execution(mapf_items)

    # Set to 30 to test for replanning after full completion of the initial plan.
    time.sleep(10)

    replace_destinations = [
        ReplaceDestination(
            task_id="agent_1_replace", robot_id="agent_1", goal_location="1,2"
        ),
        ReplaceDestination(
            task_id="agent_2_replace", robot_id="agent_2", goal_location="1,0"
        ),
        ReplaceDestination(
            task_id="agent_3_replace", robot_id="agent_3", goal_location="4,0"
        ),
    ]

    executor.replace_destinations(replace_destinations)


if __name__ == "__main__":
    main()
