from collections.abc import Iterable
from collections.abc import Callable as ABCCallable
from enum import Enum
import logging
import queue
import threading
from typing import Callable, Dict, List

import requests
import yaml


from adg.adg import ActionDependencyGraph
from adg.adg_agent import ADGAgent
from adg.enums import TaskState
from adg.adg_execution import ADGExecution
from adg.execution_context import MAPFProblemContext
from adg.execution_messages import BaseMessage, ReplaceDestinationsMessage
from adg.models.mapf_execution_models import (
    MapfSendTaskPostRequestTaskItem,
    ReplaceDestination,
)
from mapf_solve.mapf_solver_interface import MAPFSolverABC

from adg.models.plan_models import GlobalPlan, Location, Step


class Executor:
    """
    API.
    Uses context to track and give progress callbacks

    Raises:
        TypeError: _description_
        TypeError: _description_
        NotImplementedError: _description_
        NotImplementedError: _description_

    Returns:
        _type_: _description_
    """    

    class State(Enum):
        COMPLETED = "completed"
        FAILED = "failed"
        INTERRUPTED = "interrupted"
        PENDING = "pending"
        RUNNING = "running"

    def __init__(
        self,
        agents: Dict[str, ADGAgent],
        mapf_solver: MAPFSolverABC,
        progress_callback: Callable[[str, TaskState, str], None],
    ):
        """_summary_

        Args:
            input_plan (GlobalPlan): _description_
            adg (ActionDependencyGraph): _description_
            agents (Dict[str, ADGAgent]): _description_
            mapf_solver (MAPFSolverABC): _description_
            progress_callback (Callable[[str, TaskState, str], None]): The provided function will be called with task_id, TaskState and additional details.

        Raises:
            TypeError: _description_
        """
        for _, agent in agents.items():
            if not isinstance(agent, ADGAgent):
                raise TypeError

        if not isinstance(progress_callback, ABCCallable):
            raise TypeError("progress_callback must be callable")

        self.logger = logging.getLogger("executor")

        self.agents = agents
        self.mapf_solver = mapf_solver
        self.progress_callback = progress_callback
        self.state = Executor.State.PENDING

        self._problem_context = None
        self._interrupt_event = threading.Event()
        self._execution = None

        # Messages for action completions and replanning.
        self._message_queue = queue.PriorityQueue()  # Lowest priority first
        BaseMessage.count = 0

    def _initialise_empty_plans(
        self, global_plan, mapf_items: Dict[str, MapfSendTaskPostRequestTaskItem]
    ):
        """If the MAPF solution does not require a robot to move, its plan might be empty.
        This function adds a Step from "start_location" to "end_location" (which have the same value)
        to allow initialisation of the ADG.
        Alternatively, we could do this at each solver's adapter.

        Args:
            global_plan (GlobalPlan):
            mapf_items (List[MapfSendTaskPostRequestTaskItem]):
        """


        for plan in global_plan.plans:
            item = mapf_items[plan.agent_name]
            if len(plan.steps) == 0 and item.start_location == item.goal_location:
                plan.steps.append(
                    Step(
                        timestep=0,
                        step_from=Location(node=item.start_location),
                        step_to=Location(node=item.goal_location),
                        task_id=item.task_id,
                    )
                )
        return global_plan

    def begin_execution(self, mapf_items: Dict[str, MapfSendTaskPostRequestTaskItem]):

        self._problem_context = MAPFProblemContext(self.mapf_solver, mapf_items)

        # Filter out robots with duplicate goal locations to avoid conflicts
        goal_location_map = {}
        filtered_items = {}
        queued_items = {}

        for robot_id, item in mapf_items.items():
            goal = item.goal_location
            if goal in goal_location_map:
                # Duplicate goal found - queue this task instead of sending to solver
                self.logger.warning(f"Duplicate goal location detected: {robot_id} and {goal_location_map[goal]} both going to {goal}")
                self.logger.warning(f"Queueing task for {robot_id} to avoid conflict")
                queued_items[robot_id] = item
                self.progress_callback(
                    str(item.task_id), TaskState.QUEUED, f"Task queued: duplicate destination {goal}"
                )
            else:
                goal_location_map[goal] = robot_id
                filtered_items[robot_id] = item

        if len(queued_items) > 0:
            self.logger.info(f"Filtered {len(queued_items)} tasks with duplicate destinations")
            self.logger.info(f"Sending {len(filtered_items)} tasks to MAPF solver")

        # If all items were filtered out (all duplicates), fail the execution
        if len(filtered_items) == 0:
            self.logger.error("All tasks have duplicate destinations - cannot proceed")
            for item in mapf_items.values():
                self.progress_callback(
                    str(item.task_id), TaskState.FAILED, "All tasks have conflicting destinations"
                )
            self.state = Executor.State.FAILED
            return

        try:
            plans = self.mapf_solver.request_mapf_plan(list(filtered_items.values()))
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection error to mapf solver: {e}")
            for item in mapf_items.values():
                self.progress_callback(
                    str(item.task_id), TaskState.FAILED, "Could not connect to solver."
                )
            self.logger.error(f"Execution will not be started.")
            self.state = Executor.State.FAILED
            return
        except requests.exceptions.HTTPError as e:
            # 4xx errors - invalid request (bad locations, invalid parameters, etc.)
            self.logger.error(f"Invalid request to mapf solver: {e}")
            for item in mapf_items.values():
                self.progress_callback(
                    str(item.task_id), TaskState.FAILED, f"Invalid request: {e}"
                )
            self.logger.error(f"Execution will not be started.")
            self.state = Executor.State.FAILED
            return
        except requests.exceptions.RequestException as e:
            # Other request errors (timeouts, too many redirects, etc.)
            self.logger.error(f"Request error to mapf solver: {e}")
            for item in mapf_items.values():
                self.progress_callback(
                    str(item.task_id), TaskState.FAILED, f"Request error: {e}"
                )
            self.logger.error(f"Execution will not be started.")
            self.state = Executor.State.FAILED
            return
        except KeyError as e:
            # Location not found in map
            self.logger.error(f"Invalid location in map: {e}")
            for item in mapf_items.values():
                self.progress_callback(
                    str(item.task_id), TaskState.FAILED, f"Invalid location: {e}"
                )
            self.logger.error(f"Execution will not be started.")
            self.state = Executor.State.FAILED
            return
        except Exception as e:
            # Catch-all for unexpected errors
            self.logger.error(f"Unexpected error requesting mapf plan: {e}")
            self.logger.exception(e)  # Print full traceback
            for item in mapf_items.values():
                self.progress_callback(
                    str(item.task_id), TaskState.FAILED, f"Unexpected error: {e}"
                )
            self.logger.error(f"Execution will not be started.")
            self.state = Executor.State.FAILED
            return

        global_plan = GlobalPlan(plans=plans)

        # Save to file for debugging
        # yaml_str = yaml.dump(global_plan.model_dump())
        # with open("global_plan.yaml", "w") as f:
        #     f.write(yaml_str)

        if len(global_plan.plans) == 0:
            for item in mapf_items.values():
                self.progress_callback(
                    str(item.task_id), TaskState.FAILED, "Solver failed to find a solution."
                )
            self.logger.error("Failed: Solver failed to find a solution.")
            self.logger.error("Execution will not be started.")
            self.state = Executor.State.FAILED
            return

        # This initialises an empty starting plan which allows destinations to be replaced subsequently.
        global_plan = self._initialise_empty_plans(global_plan, mapf_items)

        adg = ActionDependencyGraph(global_plan)

        self._execution = ADGExecution(
                global_plan,
                adg,
                self.agents,
                self._problem_context,
                self._message_queue,
                self._interrupt_event,
                self.progress_callback
        )

        t = threading.Thread(
            target=self._execution.execute_adg,
            args=(),
        )
        t.start()
        self.state = Executor.State.RUNNING

    def replace_destinations(self, destinations):
        """_summary_

        Args:
            destinations (_type_): _description_

        Raises:
            queue.Full: _description_

        Returns:
            bool: True if the request was submitted.
        """
        if not self._problem_context:
            self.logger.error(
                "Error trying to replace destinations: no current context."
            )
            return False
        if not (
            isinstance(destinations, Iterable)
            and all(isinstance(dest, ReplaceDestination) for dest in destinations)
        ):
            self.logger.error("Error with replace destination message")
            return False

        try:
            self._message_queue.put(
                ReplaceDestinationsMessage(content=destinations), block=False
            )
        except queue.Full:
            raise
        return True

    def interrupt(self):
        self.logger.info(f"Interrupt handler called")
        self._interrupt_event.set()
        self.state = Executor.State.INTERRUPTED

    def shutdown(self):
        raise NotImplementedError

    def pause(self):
        raise NotImplementedError
