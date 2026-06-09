import json
import logging
from threading import Thread
import time
from typing import List

from shared_memory_dict import SharedMemoryDict

from adg.adg_agent import ActionState, ADGAgent, Activity
from adg.adg_execution import ActionWithCallback


class SharedMemoryAgent(ADGAgent):
    """ """

    def __init__(self, agent_name, agent_kwargs):
        super().__init__(agent_name)

        self.logger = logging.getLogger(agent_name)
        formatter = logging.Formatter(
            "[%(levelname)s] %(asctime)s:%(msecs)03d %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        self.logger.propagate = False

        # Configs
        self._shmd = SharedMemoryDict(name=agent_name, size=8192)

        # IDs
        self.robot_id = agent_name

        # Internal tracking variables
        self._completed = set()
        self._order_created = False
        self._shutdown = False

    def begin_status_checking(self):
        def _fn():
            while not self._shutdown:
                time.sleep(0.5)
                try:
                    res = self._shmd["action_completion_feedback"]
                    # self.logger.debug(f"action_completion_feedback: {res}")
                    if res:
                        current_activity = self.progress_tracker.get_activity(0)
                        if current_activity:
                            # Check if current activity is completed
                            for result in json.loads(res):
                                if (
                                    result["action"]
                                    == current_activity.action.to_dict()
                                    and result["state"] == "ActionState.COMPLETED"
                                ):
                                    current_activity.state = ActionState.COMPLETED
                                    if current_activity not in self._completed:
                                        self._completed.add(current_activity)
                                        self.logger.info(
                                            f"Agent has finished action: {str(current_activity.action)}"
                                        )
                                        current_activity.callback()
                                        self.progress_tracker.activities.pop(0)
                except KeyError:
                    pass
                except json.decoder.JSONDecodeError:
                    self.logger.info(f"Invalid message from pybullet result")
            self._cleanup()

        t = Thread(target=_fn)
        t.start()

    def enqueue(self, actions_with_callbacks: List[ActionWithCallback]):
        """
        Get this agent to enqueue actions for execution

        Args:
            actions_with_callbacks (ActionWithCallback): List of ActionWithCallback objects
        """

        if not actions_with_callbacks:
            self.logger.info(
                f"Warning: enqueued() was called with no actions for {self.agent_name}"
            )
            return

        for action_w_cb in actions_with_callbacks:
            self.logger.info(f"Enqueued: {action_w_cb.action}")
            activity = Activity(
                action_w_cb.action, action_w_cb.callback, ActionState.QUEUED
            )
            self.progress_tracker.add_activity(activity)

        self.publish()

        if not self._order_created:
            self.begin_status_checking()
            self._order_created = True

    def publish(self):
        self.logger.info(f"Publishing command: {self.progress_tracker}")
        try:
            self._shmd["command"] = str(self.progress_tracker)
        except ValueError as e:
            self.logger.error(f"ValueError: {str(e)}.")
            self.logger.error(
                f"Increase the size of the SharedMemoryDict for all users of the dict so that it can hold the command."
            )
            raise e

    # Differentiate between completion and errors.
    def shutdown(self, interrupted: bool = False):
        if interrupted:
            self.logger.info(f"{self.robot_id} was interrupted.")
        self._shutdown = True
        self.logger.info(f"{self.robot_id} shutting down.")

    def _cleanup(self):
        self._shmd.shm.close()
        self._shmd.shm.unlink()
        del self._shmd
