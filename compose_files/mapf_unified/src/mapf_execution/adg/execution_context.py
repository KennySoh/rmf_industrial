import copy
import json
import logging
from typing import Callable, Dict, List, Set

import requests

from adg.enums import TaskState
from adg.models.plan_models import GlobalPlan
from adg.models.mapf_execution_models import (
    ReplaceDestination,
    MapfSendTaskPostRequestTaskItem,
)
from mapf_solve.mapf_solver_interface import MAPFSolverABC, Obstacle


logger = logging.getLogger("execution_context")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "[%(levelname)s] %(asctime)s:%(msecs)03d %(name)s: %(message)s", datefmt="%H:%M:%S"
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False


class MAPFProblemContext:

    class Agent:
        """Inner class to hold agent information."""

        def __init__(self, item: MapfSendTaskPostRequestTaskItem):
            self.task_id = item.task_id
            self.name = item.robot_id
            self.start_location = item.start_location
            self.goal_location = item.goal_location
        
        def __str__(self):
            return f"{str(self.task_id), str(self.name), str(self.start_location), str(self.goal_location)}"

    def __init__(
        self,
        mapf_solver_service: MAPFSolverABC,
        mapf_items_dict: Dict[str, MapfSendTaskPostRequestTaskItem],
    ):
        """ """
        self.mapf_solver_service = mapf_solver_service
        self.current_mapf_agents = {
            name: MAPFProblemContext.Agent(mapf_items_dict[name])
            for name in mapf_items_dict
        }
        # List to store tasks that were filtered due to duplicate destinations
        self.pending_retry_destinations = []

    def replan(
        self,
        committed_vertices,
        incoming_destinations: List[ReplaceDestination],
        stationary_agents: Set[str],
        progress_callback: Callable[[str, "TaskState", str], None],
    ):

        # Merge pending retry destinations with new incoming destinations
        all_destinations = self.pending_retry_destinations + incoming_destinations
        if len(self.pending_retry_destinations) > 0:
            logger.info(f"Retrying {len(self.pending_retry_destinations)} pending destinations from previous conflicts")
            for dest in self.pending_retry_destinations:
                logger.info(f"  Retry: {dest.robot_id} -> {dest.goal_location}")

        # Keep track of pending retry robot names before clearing
        # These robots are stuck and their current positions should be obstacles
        pending_retry_robot_names = {dest.robot_id for dest in self.pending_retry_destinations}

        # Clear the pending list - we'll repopulate it if conflicts still exist
        self.pending_retry_destinations = []

        replan_information = self._setup_replan(
            committed_vertices, all_destinations
        )
        solved_plan = self._solve(replan_information, stationary_agents, progress_callback, pending_retry_robot_names)  # TODO: timeout

        if solved_plan:
            # Save the new information.
            self.current_mapf_agents = replan_information
        else:
            # TODO: Behaviour of existing tasks when replace destination is unsuccessful.
            for agent_name, replan_task in replan_information.items():
                current_task_id = self.current_mapf_agents[agent_name].task_id
                if current_task_id != replan_task.task_id:
                    # TODO: track task states
                    progress_callback(
                        replan_task.task_id, TaskState.FAILED, "failed:no solution"
                    )

        return solved_plan

    def _setup_replan(
        self, committed_vertices, incoming_destinations: List[ReplaceDestination]
    ) -> Dict[str, MapfSendTaskPostRequestTaskItem]:
        """Construct a replanning problem for solving with MAPFSolverABC.

        Args:
            committed_vertices (_type_): _description_
            incoming_destinations (List[ReplaceDestination]): _description_
        """
        logger.info(f"Incoming destinations: {incoming_destinations}")

        replan_information = copy.deepcopy(self.current_mapf_agents)
        for agent_name, agent in replan_information.items():
            logger.debug(f"Original info: {replan_information[agent_name]}")

            agent.start_location = committed_vertices[agent_name].location_end
            logger.debug(f"Updated start info: {replan_information[agent_name]}")

        # Replace task IDs and goal locations if changed.
        for destination_request in incoming_destinations:
            agent_name = destination_request.robot_id
            if agent_name not in replan_information:
                logger.warning(
                    f"Ignoring invalid destination request for {agent_name} because it is not in the current context."
                )
                continue

            replan_information[agent_name].task_id = destination_request.task_id
            replan_information[agent_name].goal_location = (
                destination_request.goal_location
            )

        for k in replan_information:
            logger.debug(f"Replan info: {replan_information[k]}")
        return replan_information

    def _solve(self, replan_information: Dict[str, Agent], stationary_agents, progress_callback: Callable[[str, "TaskState", str], None] = None, pending_retry_robot_names: Set[str] = None):
        # Convert replan information to input for solver service
        # Agents which are stationary must have empty plans - currently the solver adapters take care of that.

        new_mapf_agents = []  # MapfSendTaskPostRequestTaskItem

        obstacles = []
        obstacle_locations = {}  # Map obstacle position -> agent name for conflict detection
        for agent_name in stationary_agents:
            # pass obstacle as wp name
            obstacle_location = replan_information[agent_name].start_location
            obstacles.append(Obstacle(obstacle_location))
            obstacle_locations[obstacle_location] = agent_name

        # Add current positions of pending retry robots as obstacles
        # These robots are stuck (their destinations are blocked) and can't move yet
        # So other robots should not try to go to their current positions
        if pending_retry_robot_names:
            for robot_name in pending_retry_robot_names:
                # Safety checks: robot exists, not already stationary, position not already obstacle
                if robot_name in replan_information and robot_name not in stationary_agents:
                    obstacle_location = replan_information[robot_name].start_location
                    if obstacle_location not in obstacle_locations:
                        obstacle_locations[obstacle_location] = robot_name
                        obstacles.append(Obstacle(obstacle_location))
                        logger.info(f"Pending retry robot {robot_name} at {obstacle_location} - added as obstacle")

        if len(obstacle_locations) > 0:
            logger.info(f"Stationary agents as obstacles: {[(agent, loc) for loc, agent in obstacle_locations.items()]}")

        for agent in replan_information.values():
            if agent.name not in stationary_agents:
                item = MapfSendTaskPostRequestTaskItem(
                    task_id=agent.task_id,
                    robot_id=agent.name,
                    start_location=agent.start_location,
                    goal_location=agent.goal_location,
                )
                new_mapf_agents.append(item)

        # Filter out robots with duplicate goal locations to avoid conflicts
        # AND filter out robots whose goals conflict with obstacle positions
        goal_location_map = {}
        filtered_agents = []
        filtered_out_items = []

        for item in new_mapf_agents:
            goal = item.goal_location

            # Check if goal conflicts with an obstacle (stationary robot or filtered robot)
            if goal in obstacle_locations:
                # Goal is blocked by a stationary or filtered robot
                blocking_agent = obstacle_locations[goal]
                logger.warning(f"Goal-obstacle conflict detected: {item.robot_id} trying to reach {goal} which is blocked by robot {blocking_agent}")
                logger.warning(f"Adding {item.robot_id} to pending retry list")
                filtered_out_items.append(item)

                # CRITICAL FIX: Mark filtered robot's current position as obstacle
                # so other robots in this batch can't be sent there
                if item.start_location not in obstacle_locations:
                    obstacle_locations[item.start_location] = item.robot_id
                    obstacles.append(Obstacle(item.start_location))
                    logger.info(f"Filtered robot {item.robot_id} staying at {item.start_location} - added as obstacle")

                # Update task status to QUEUED if callback available
                if progress_callback:
                    progress_callback(
                        str(item.task_id),
                        TaskState.QUEUED,
                        f"Queued: destination {goal} blocked by robot {blocking_agent}"
                    )
            elif goal in goal_location_map:
                # Duplicate goal found - skip this agent for now and add to retry list
                logger.warning(f"Duplicate goal location detected during replan: {item.robot_id} and {goal_location_map[goal]} both going to {goal}")
                logger.warning(f"Adding {item.robot_id} to pending retry list")
                filtered_out_items.append(item)

                # CRITICAL FIX: Mark filtered robot's current position as obstacle
                # so other robots in this batch can't be sent there
                if item.start_location not in obstacle_locations:
                    obstacle_locations[item.start_location] = item.robot_id
                    obstacles.append(Obstacle(item.start_location))
                    logger.info(f"Filtered robot {item.robot_id} staying at {item.start_location} - added as obstacle")

                # Update task status to QUEUED if callback available
                if progress_callback:
                    progress_callback(
                        str(item.task_id),
                        TaskState.QUEUED,
                        f"Queued: duplicate destination {goal} (conflict with {goal_location_map[goal]})"
                    )
            else:
                goal_location_map[goal] = item.robot_id
                filtered_agents.append(item)

        # Store filtered items for retry in next replan
        for item in filtered_out_items:
            retry_dest = ReplaceDestination(
                task_id=item.task_id,
                robot_id=item.robot_id,
                goal_location=item.goal_location
            )
            self.pending_retry_destinations.append(retry_dest)
            logger.info(f"Added to pending retry: {item.robot_id} -> {item.goal_location}")

        if len(filtered_agents) < len(new_mapf_agents):
            logger.info(f"Filtered {len(new_mapf_agents) - len(filtered_agents)} agents with duplicate destinations during replan")
            logger.info(f"Sending {len(filtered_agents)} agents to MAPF solver")
            logger.info(f"Pending retry list now has {len(self.pending_retry_destinations)} destinations")

        # If all agents were filtered, return empty plan (no need to call solver)
        if len(filtered_agents) == 0:
            logger.info("All agents were filtered (queued). No agents to send to solver.")
            # Return empty plan - this is considered a success because all agents were properly queued
            return GlobalPlan(plans=[])

        try:
            plans = self.mapf_solver_service.request_mapf_plan(filtered_agents, obstacles)
        except requests.exceptions.HTTPError as e:
            # HTTP errors (4xx - invalid request, 5xx - server error)
            logger.error(f"HTTP error from mapf solver: {e}")
            # Mark all tasks in this replan batch as failed
            if progress_callback:
                for item in filtered_agents:
                    progress_callback(
                        str(item.task_id),
                        TaskState.FAILED,
                        f"Invalid request to solver: {str(e)}"
                    )
            logger.error("Replan failed due to invalid request. Execution continues.")
            return None
        except requests.exceptions.ConnectionError as e:
            # Connection errors - solver unreachable
            logger.error(f"Connection error to mapf solver: {e}")
            if progress_callback:
                for item in filtered_agents:
                    progress_callback(
                        str(item.task_id),
                        TaskState.FAILED,
                        f"Could not connect to solver: {str(e)}"
                    )
            logger.error("Replan failed due to connection error. Execution continues.")
            return None
        except requests.exceptions.RequestException as e:
            # Other request errors (timeouts, etc.)
            logger.error(f"Request error to mapf solver: {e}")
            if progress_callback:
                for item in filtered_agents:
                    progress_callback(
                        str(item.task_id),
                        TaskState.FAILED,
                        f"Request error: {str(e)}"
                    )
            logger.error("Replan failed due to request error. Execution continues.")
            return None

        global_plan = GlobalPlan(plans=plans)
        if len(global_plan.plans) == 0:
            # r.set(str(item.task_id), "failed:Solver could not find a soluion.")
            logger.error("Failed: Solver could not find a solution.")
            logger.error("Execution will not be started.")
            return None
        #logger.debug(f"solution: {json.dumps(global_plan.model_dump(), indent=2)}")

        return global_plan

    def get_agent(self, agent_name):
        return self.current_mapf_agents[agent_name]

    def set_completed(self, agent_name):
        try:
            self.get_agent(agent_name).completed = True
        except KeyError:
            # This warning can be ignored if encountered during testing without a full executor because there's no need
            # to instantiate this context.
            logger.warning("Invalid agent name in set_completed.")
