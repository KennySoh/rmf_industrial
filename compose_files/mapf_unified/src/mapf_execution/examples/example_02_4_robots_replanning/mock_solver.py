from pathlib import Path

from examples.utils import read_yaml
from mapf_solve.mapf_solver_interface import MAPFSolverABC


class MockSolver(MAPFSolverABC):
    # TODO Setup test instead

    def __init__(self):
        self.call_count = 0

    def request_mapf_plan(self, _):
        """
        Mock solver mocking mapf_solve_request

        Returns:
            _type_: List[Plan]
        """
        self.call_count += 1

        if self.call_count == 1:
            replan_plan_file = Path(__file__).with_name("4_robots.yaml")
        elif self.call_count == 2:
            replan_plan_file = Path(__file__).with_name("4_robots_replan.yaml")
        else:
            replan_plan_file = Path(__file__).with_name("4_robots_replan.yaml")

        global_plan = read_yaml(replan_plan_file)
        return [plan.model_dump() for plan in global_plan.plans]
