from abc import ABC
from typing import Iterable

from adg.adg import ActionVertex
from adg.models.mapf_execution_models import GracefulPause, ReplaceDestination

"""Internal messages.
"""


class BaseMessage(ABC):
    """Has priority and order within the PriorityQueue"""

    count = 0  # TODO: Handle indefinite growing of this count

    def __init__(self, content):
        self.content = content
        self.count = BaseMessage.count  # used to maintain order of messages
        self.priority = None
        BaseMessage.count += 1

    def __lt__(self, other: "BaseMessage") -> bool:
        if self.priority == other.priority:
            return self.count < other.count
        else:
            return self.priority < other.priority


class GracefulPauseMessage(BaseMessage):
    def __init__(self, content: Iterable[GracefulPause]):
        super().__init__(content)
        self.priority = 1


class ReplaceDestinationsMessage(BaseMessage):
    def __init__(self, content: Iterable[ReplaceDestination]):
        super().__init__(content)
        self.priority = 2


class ActionCompletionMessage(BaseMessage):
    def __init__(self, content: ActionVertex):
        super().__init__(content)
        self.priority = 3

