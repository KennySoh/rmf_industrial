import abc
from typing import List

from adg.models.plan_models import Plan
from adg.models.mapf_execution_models import MapfSendTaskPostRequestTaskItem


class Obstacle():
    def __init__(self, location):
        self.location = location

    def __str__(self):
        return str(self.location)

class MAPFSolverABC(abc.ABC):
    """
    Input: List[MapfSendTaskPostRequestTaskItem]
    Output: List[Plan]

    The `task_id` field of each Step should be provided to enable task tracking.

    """

    @abc.abstractmethod
    def request_mapf_plan(
        self, items: List[MapfSendTaskPostRequestTaskItem], obstacles: List[Obstacle]
    ) -> List[Plan]:
        pass
