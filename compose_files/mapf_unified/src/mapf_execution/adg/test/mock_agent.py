import json
import logging
from threading import Thread
import time
from typing import List

import redis

from adg.adg_agent import ActionState, ADGAgent, Activity
from adg.adg_execution import ActionWithCallback


class MockAgent(ADGAgent):
    """Completes actions when requested.
    """    

    def __init__(self, agent_name, agent_args={}):
        super().__init__(agent_name)

        self.logger = logging.getLogger("mock_" + agent_name)
        formatter = logging.Formatter(
            "[%(levelname)s] %(asctime)s:%(msecs)03d %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        self.logger.propagate = False

        # IDs
        self.robot_id = agent_name

    def enqueue(self, actions_with_callbacks: List[ActionWithCallback]):
        """
        Get this agent to enqueue actions for execution

        Args:
            actions_with_callbacks (ActionWithCallback): List of ActionWithCallback objects
        """

        if not actions_with_callbacks:
            self.logger.info(
                f"MockAgent: enqueued() was called with no actions for {self.agent_name}"
            )
            return

        for action_w_cb in actions_with_callbacks:
            self.logger.info(f"Enqueued: {action_w_cb.action}")

            def _fn(action_w_cb: ActionWithCallback):
                time.sleep(0.5)
                self.logger.info(f"Completing action: {action_w_cb.action} and calling its callback.")
                action_w_cb.callback()
            Thread(target=_fn, args=[action_w_cb]).start()

    # Differentiate between completion and errors.
    def shutdown(self, interrupted: bool = False):
        if interrupted:
            self.logger.info(f"{self.robot_id} was interrupted.")
        self._shutdown = True
        self.logger.info(f"{self.robot_id} shutting down.")
