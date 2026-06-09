from typing import List, Optional

from pydantic import BaseModel

"""Models representing MAPF plans.
"""


class Location(BaseModel):
    node: str
    x: float | None = None
    y: float | None = None


class Step(BaseModel):
    """
    A step comprises an action to be executed, starting at timestep k, which will change the agent's Location from step_from to step_to.
    """

    timestep: int
    step_from: Location
    step_to: Location
    task_id: str


class Plan(BaseModel):
    """
    An agent's plan from a prior MAPF planner.
    """

    agent_name: str
    steps: List[Step]  # Must not be an empty list.


class GlobalPlan(BaseModel):
    plans: List[Plan]
