from __future__ import annotations

from abc import abstractmethod, ABC
from enum import Enum
import json
from queue import Queue
from threading import Thread
from typing import List

from adg.adg import ActionVertex


class ActionState(Enum):
    NOT_QUEUED = 0
    QUEUED = 1
    COMPLETED = 2


class Activity:
    """Each Activity comprises an Action to be performed, its callback to be called upon completion, and its state for monitoring."""

    def __init__(self, action: ActionVertex, callback, state=ActionState.NOT_QUEUED):
        self.action = action
        self.state = state
        self.callback = callback

    def __str__(self):
        return f"{str(self.action), str(self.state)}"

    def to_dict(self):
        return {"action": self.action.to_dict(), "state": str(self.state)}

    def __hash__(self):
        return hash(str(self))


class ProgressTracker:
    """Currently, this is convenience for SharedMemoryAgent to track and publish actions.
    TODO: clean up interface and locking
    """

    def __init__(self):
        self.activities = []

    def __str__(self):
        status = []
        for x in self.activities:
            status.append(x.to_dict())
        return json.dumps(status)

    def get_action(self, index):
        return self.activities[index].action

    def get_activity(self, index):
        try:
            return self.activities[index]
        except IndexError:
            return None

    def get_all_activities(self):
        return self.activities

    def add_activity(self, new_activity):
        self.activities.append(new_activity)

    def size(self):
        return len(self.activities)

    def completed_indexes(self):
        completed = []
        for item in self.activities:
            if item.state == ActionState.COMPLETED:
                completed.append(item.action.step_index)
        return completed


class ADGAgent(ABC):
    """Subclasses must implement enqueue() and shutdown()."""

    def __init__(self, agent_name):
        self.agent_name = agent_name

        self.progress_tracker = ProgressTracker()
        self._shutdown = False


    def print_progress(self):
        for item in self.progress_tracker.activities:
            print(str(item))

    @abstractmethod
    def enqueue(self, actions: List[ActionWithCallback]):
        """
        Implement this method to handle ActionWithCallback-s.
        Each action has an associated callback.
        Agents are expected to execute the action, then call the associated callback upon completion.
        ActionWithCallback-s must be processed in FIFO order.
        """
        ...

    @abstractmethod
    def shutdown(self, interrupted: bool = False):
        """This method will be called when execution is interrupted or completed successfully
        and the agent can shut down.
        """
        ...
