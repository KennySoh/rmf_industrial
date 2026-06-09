import argparse
import logging
from pathlib import Path
import queue
import threading

import yaml

from adg.adg import ActionDependencyGraph
from adg.enums import TaskState
from adg.adg_execution import ADGExecution
from adg.execution_context import MAPFProblemContext
from agents.shared_memory_dict_agent.agent_shmd import SharedMemoryAgent
from examples.utils import read_yaml
from mapf_solve.cbs_adapter import CBSAdapter

# Moves 4 robots in PyBullet according to the input plan in 4_robots.yaml.
# This example doesn't use the Executor interface.

logger = logging.getLogger("example_01")
formatter = logging.Formatter(
    "[%(levelname)s] %(asctime)s:%(msecs)03d %(name)s: %(message)s", datefmt="%H:%M:%S"
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False


default_plan_file = Path(__file__).with_name("4_robots.yaml")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input_plan",
        help="An input yaml file that can be loaded as a preprocess.GlobalPlan.",
        default=default_plan_file,
    )
    args = parser.parse_args()

    # Read from input file
    try:
        global_plan = read_yaml(args.input_plan)
    except yaml.YAMLError as exc:
        print(exc)

    adg = ActionDependencyGraph(global_plan)
    agent_names = adg.get_agent_names()
    adg_agents = {}
    agent_args = {}
    for agent_name in agent_names:
        adg_agents[agent_name] = SharedMemoryAgent(
            agent_name, agent_args
        )

    def progress_callback(task_id: str, task_state: TaskState, message: str):
        logger.info(f"-------- {task_id} reported {task_state} {message}\n")

    problem_context = MAPFProblemContext(CBSAdapter(), {})

    execution = ADGExecution(
                global_plan,
                adg,
                adg_agents,
                problem_context,
                queue.PriorityQueue(),
                threading.Event(),
                progress_callback
        )

    t = threading.Thread(
        target=execution.execute_adg,
        args=(),
    )
    t.start()


if __name__ == "__main__":
    main()
