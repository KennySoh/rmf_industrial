from functools import partial
import logging
import queue
import threading
from typing import Callable, Dict


from adg.adg import ActionDependencyGraph, ActionVertex
from adg.adg_agent import ADGAgent
from adg.adg_functions import (
    find_and_enqueue_valid_candidates,
    find_latest_enqueued,
    find_same_agent_predecessor,
    find_same_agent_successor,
    is_task_completed,
    compute_committed_vertices,
    compute_desired_vertices,
    compute_reachable_set,
    increment_timesteps,
    remove_completed_parents,
)

from adg.execution_messages import ActionCompletionMessage, GracefulPauseMessage, ReplaceDestinationsMessage
from adg.enums import TaskState
from adg.execution_context import MAPFProblemContext


logger = logging.getLogger("execution")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "[%(levelname)s] %(asctime)s:%(msecs)03d %(name)s: %(message)s", datefmt="%H:%M:%S"
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False


class ActionWithCallback:
    def __init__(self, action, callback):
        self.action = action
        self.callback = callback


class ADGExecution:
    def __init__(self,
                global_plan,
                adg: ActionDependencyGraph,
                agents: Dict[str, ADGAgent],
                problem_context: MAPFProblemContext,
                message_queue: queue.PriorityQueue,
                interrupt_event,
                progress_callback: Callable[[str, "TaskState", str], None]
                ):

        self.global_plan = global_plan
        self.adg = adg
        self.agents = agents
        self.problem_context = problem_context
        self.message_queue = message_queue
        self.interrupt_event = interrupt_event
        self.progress_callback = progress_callback


    def mark_vertex_completed(
        self,
        vertex: ActionVertex,
        most_recently_completed: dict,
    ):
        """

        Args:
            completed (ActionVertex): Completed vertex.
            most_recently_completed (dict): Dict that tracks most recently completed vertex for each agent.
        """
        try:
            logger.debug(f"Marking {vertex} as completed..")
            if vertex.state == ActionVertex.State.COMPLETED:
                logger.warning(f"{vertex} was already previously completed.")
                return

            vertex.state = ActionVertex.State.COMPLETED

            # Track which vertex was most recently completed for each agent
            # Assumes that completions are always received in order.
            most_recently_completed[vertex.agent_name] = vertex

        except KeyError:
            logger.info(
                f"Warning: attempted to complete a vertex {vertex} that does not belong to an existing agent."
            )


    def execute_adg(self):
        """Executes an ActionDependencyGraph

        An ActionDependencyGraph differs from a typical dependency graph:
        - Each vertex belongs to an agent
        - If a vertex has exactly one immediate predecessor belonging to the same agent,
        both can be queued for execution together.

        Args:
            g (ActionDependencyGraph):
                An ActionDependencyGraph. It must not be modified during this execution.
            agents:
                dict of Instances of subclasses of ADGAgent, keyed by name.
        """

        def _get_actions_with_callbacks(candidates):
            # Failure callback?
            actions_cbs = []
            for candidate in candidates:

                def callback(completed_action):
                    with _lock:
                        action_completion_msg = ActionCompletionMessage(completed_action)
                        self.message_queue.put(action_completion_msg)

                actions_cbs.append(
                    ActionWithCallback(candidate, partial(callback, candidate))
                )
            return actions_cbs

        def _interrupt_agents():
            for _, agent in self.agents.items():
                agent.shutdown(interrupted=True)

        def _stop_agents():
            for _, agent in self.agents.items():
                agent.shutdown()

        _lock = threading.Lock()

        # Check for cycles in updated graph. Can skip if planner ensures no cycles.
        if self.adg.is_cyclic():
            logger.error("Initial ADG contains a cycle and execution cannot be completed.")
        logger.debug(
            f"Initialising ADG, number of actions to be executed: {len(self.adg)}"
        )

        # Track most-recent completions. This is used to determine desired set, and what actions to enqueue next.
        # Dictionary format: {agent name: completed vertex}
        most_recently_completed = {
            k: None for k in self.adg.get_agent_names()
        }  

        # Enqueue starting vertices
        t0_vertices = [
            self.adg.lookup_vertex(agent_name, 0) for agent_name in self.agents.keys()
        ]
        find_and_enqueue_valid_candidates(
            t0_vertices, self.adg, self.agents, _get_actions_with_callbacks
        )

        while True:

            # TODO: Shutdown condition
            if self.interrupt_event.is_set():
                logger.info(f"ActionDependencyGraph Execution interrupted.")
                _interrupt_agents()
                break

            try:
                msg = self.message_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if isinstance(msg, ActionCompletionMessage):
                completed = msg.content

                logger.info(f"Completed vertex: {completed}")
                self.mark_vertex_completed(completed, most_recently_completed)

                # Temporary fix to filter out candidates 
                # If completed is from robot B, and its successor X from robot A already has an enqueued parent,
                # leave it to A's completion to enqueue vertex X.
                candidate_successors = list(self.adg.successors(completed))
                to_remove = []
                for c in candidate_successors:
                    if c.agent_name != completed.agent_name:
                        parent = find_same_agent_predecessor(self.adg, c)
                        if parent is not None:
                            if parent.state == ActionVertex.State.ENQUEUED:
                                to_remove.append(c)
                for item in to_remove:
                    if item in candidate_successors:
                        candidate_successors.remove(item)

                # Enqueue valid successors and their children, of this completed vertex.
                find_and_enqueue_valid_candidates(
                    candidate_successors,
                    self.adg,
                    self.agents,
                    _get_actions_with_callbacks,
                )

                # context.get_task->progress_step()
                self.progress_callback(completed.task_id, TaskState.IN_PROGRESS, str(completed))

                # Check if this task is completed.
                # TODO Consider using Executor to track instead.
                if is_task_completed(self.adg, completed):
                    self.progress_callback(completed.task_id, TaskState.COMPLETED, "completed")

                logger.debug("Most recently completed:")
                for k, v in sorted(most_recently_completed.items()):
                    logger.debug(f"{k}, {v}")

            elif isinstance(msg, ReplaceDestinationsMessage):
                logger.info(f"Replanning initiated.")

                replace_destinations = msg.content

                # Compute desired vertices (one vertex per agent)
                desired_vertices = compute_desired_vertices(
                    self.adg, most_recently_completed, 1
                )

                # This ensures that the last-enqueued vertex becomes the desired vertex, if it is a successor
                # of the original desired vertex.
                for agent_name, desired_vertex in desired_vertices.items():
                    desired_vertices[agent_name] = find_latest_enqueued(
                        self.adg, desired_vertex
                    )
                    logger.debug(
                        f"Latest enqueued vertex is: {str(desired_vertices[agent_name])}"
                    )

                reachable_set = compute_reachable_set(self.adg, desired_vertices)
                committed_vertices = compute_committed_vertices(
                    self.adg.get_agent_names(), reachable_set
                )

                # Find the maximum timestep of committed vertices.
                max_step = 0
                for _, v in committed_vertices.items():
                    logger.debug(f"Committed: {str(v)}")
                    if v.step_index > max_step:
                        max_step = v.step_index
                logger.debug(
                    f"Maximum of timesteps across agents' committed vertices: {str(max_step)}"
                )

                replace_destinations_dict = {}
                for rd in replace_destinations:
                    replace_destinations_dict[rd.robot_id] = rd

                # Also include pending retry destinations when checking for stationary agents
                for rd in self.problem_context.pending_retry_destinations:
                    replace_destinations_dict[rd.robot_id] = rd

                stationary_agents = set()
                for _, v in committed_vertices.items():
                    if not find_same_agent_successor(self.adg, v) and v.agent_name not in replace_destinations_dict:
                        # Previous task is completed, and new replan doesn't involve this agent.
                        stationary_agents.add(v.agent_name)

                # Create MAPF problem for all agents using the committed vertices.
                solved_plan = self.problem_context.replan(committed_vertices, replace_destinations, stationary_agents, self.progress_callback)

                if solved_plan is None:
                    logger.error(
                        "Unable to proceed with this replan request, ignoring.."
                    )

                else:

                    # Increment all timesteps in incoming plan so that they begin at (max timestep + 1)
                    increment_timesteps(solved_plan, max_step + 1)

                    # Update the original plans
                    for plan in self.global_plan.plans:
                        logger.debug(
                            f"Original plan before removing completed vertices: {plan}"
                        )
                        # Remove completed vertices from the original plan.
                        if most_recently_completed[plan.agent_name] is not None:
                            most_recently_completed_index = most_recently_completed[
                                plan.agent_name
                            ].step_index

                            plan.steps = [
                                x
                                for x in plan.steps
                                if x.timestep > most_recently_completed_index
                            ]

                        # Discard steps after the commit cut from the original plan.
                        committed_vertex = committed_vertices[plan.agent_name]
                        plan.steps = [
                            x for x in plan.steps if x.timestep <= committed_vertex.step_index
                        ]
                        logger.debug(
                            f"Updated plan after removing completed vertices and discarded vertices: {plan}"
                        )

                    # Discard vertices after the commit cut from the current ADG.
                    to_delete = [v for v in self.adg if v not in reachable_set]
                    for v in to_delete:
                        logger.debug(f"Removing vertex {v}")
                        self.adg.remove_vertex(v)

                    # Add the incoming plan to the current plan and the current graph.
                    self.adg.append_plan(committed_vertices, self.global_plan, solved_plan)

                    # Check for cycles in updated graph. Can skip if planner ensures no cycles.
                    if self.adg.is_cyclic():
                        logger.error("ADG contains a cycle and execution cannot be completed.")
                        # TODO Interrupt execution here.

                    logger.info(
                        f"After adding the incoming ADG, size of graph: {len(self.adg)}"
                    )

                    # Remove completed vertices to prevent graph from growing indefinitely.
                    # Retain the most recent ones because they are required to find the next set of desired.
                    for v in most_recently_completed.values():
                        if v:
                            remove_completed_parents(self.adg, v)

                    logger.info(
                        f"After removing completed vertices (except the most recent), size of graph: {len(self.adg)}"
                    )

                    # Use most_recently_completed to search for new vertices that need to be enqueued.
                    # Note that previous plans may have been fully completed.
                    logger.debug(f"Finding new candidates..")

                    candidates = []
                    for x in most_recently_completed.values():
                        if x is not None:
                            candidates.extend(self.adg.successors(x))

                    # TODO Investigate effects enqueuing one successor as opposed to two here,
                    # if replanning is extremely frequent
                    logger.debug(f"Searching for successors of new candidates..")
                    find_and_enqueue_valid_candidates(
                        candidates, self.adg, self.agents, _get_actions_with_callbacks
                    )
                    logger.debug(f"Replanning completed.")

            elif isinstance(msg, GracefulPauseMessage):
                logger.info(f"GracefulPause initiated.")
                graceful_pauses = msg.content
                raise NotImplementedError


        return
