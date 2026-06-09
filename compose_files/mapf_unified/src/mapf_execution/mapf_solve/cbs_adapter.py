import argparse
import yaml

from typing import List

from adg.models.plan_models import GlobalPlan, Location, Plan, Step
from adg.models.mapf_execution_models import MapfSendTaskPostRequestTaskItem
from cbs.cbs import CBS, Environment
from mapf_solve.mapf_solver_interface import MAPFSolverABC, Obstacle


class CBSAdapter(MAPFSolverABC):
    """Limited adapter to the cbs solver.
    Missing specification of map: obstacles and dimensions

    start_location or end_location must be a string "x, y"
    """

    def request_mapf_plan(self, items: List[MapfSendTaskPostRequestTaskItem], input_obstacles: List[Obstacle] = []):
        task_ids = {}  # Track task IDs

        dimension = [7, 7]
        agents = []

        for item in items:
            agent = {}
            agent["start"] = [int(i) for i in item.start_location.split(",")]
            agent["goal"] = [int(i) for i in item.goal_location.split(",")]
            agent["name"] = item.robot_id
            agents.append(agent)

            task_ids[item.robot_id] = item.task_id if item.task_id else ""

        obstacles = []
        print("Number of obstacles:", len(input_obstacles), flush=True)
        for input_obstacle in input_obstacles:
            print("obstacle:", input_obstacle, flush=True)
            xy_tuple = tuple(map(int, input_obstacle.location.split(',')))
            obstacles.append(xy_tuple)
        print("solving..", flush=True)
        output = self.solve(dimension, agents, obstacles)
        plans = convert_cbs(output, task_ids)
        print("solved..", flush=True)

        return plans

    def solve(self, dimension, agents, obstacles):
        env = Environment(dimension, agents, obstacles)

        # Searching
        cbs = CBS(env)
        solution = cbs.search()
        if not solution:
            print(" Solution not found")
            return

        # Write to output file
        output = dict()
        output["schedule"] = solution
        output["cost"] = env.compute_solution_cost(solution)
        with open("cbs_output", "w") as output_yaml:
            yaml.safe_dump(output, output_yaml)

        return output


def convert_cbs(cbs_output, task_ids):
    """
    Convert output from cbs.py.

    Args:
        cbs_output (dict): Object loaded from cbs.py's output.yaml
    """
    plans = []
    for agent_name, agent_path in cbs_output["schedule"].items():
        steps = []

        for idx, waypoint in enumerate(agent_path):
            if not idx == len(agent_path) - 1:  # skip Step creation for final waypoint
                timestep = waypoint["t"]
                step_from = Location(
                    node=str(waypoint["x"]) + "," + str(waypoint["y"]),
                    x=waypoint["x"],
                    y=waypoint["y"],
                )
                next_waypoint = agent_path[idx + 1]
                step_to = Location(
                    node=str(next_waypoint["x"]) + "," + str(next_waypoint["y"]),
                    x=next_waypoint["x"],
                    y=next_waypoint["y"],
                )

                steps.append(
                    Step(
                        timestep=timestep,
                        step_from=step_from,
                        step_to=step_to,
                        task_id=task_ids[agent_name],
                    )
                )
        plans.append(Plan(agent_name=agent_name, steps=steps))

    return plans
