from collections import defaultdict
import logging
from typing import Dict, Iterable, List


from adg.adg import ActionDependencyGraph, ActionVertex
from adg.models.plan_models import GlobalPlan

logger = logging.getLogger("execution")

# TODO: Args to specify how many actions the user would like queued up at once for each agent.
NUM_DESIRED_ENQUEUED = 3

def find_same_agent_predecessor(
    graph: ActionDependencyGraph, vertex: ActionVertex
) -> ActionVertex:
    """
    Returns an immediate same-agent predecessor if it exists.
    """
    for predecessor in graph.predecessors(vertex):
        if predecessor.agent_name == vertex.agent_name:
            return predecessor
    return None


def find_same_agent_successor(
    graph: ActionDependencyGraph, vertex: ActionVertex
) -> ActionVertex:
    """
    Returns an immediate same-agent successor if it exists.
    """
    for successor in graph.successors(vertex):
        if successor.agent_name == vertex.agent_name:
            return successor
    return None


def get_action_vertices(graph: ActionDependencyGraph, agent_name, beginning_from=0):
    """Returns list of all ActionVertex-s in the ADG belonging to this agent.

    Returns:
        _type_: _description_
    """
    steps = []
    starting_vertex = graph.lookup_vertex(agent_name, beginning_from)
    if starting_vertex:
        current = starting_vertex
        steps.append(current)
        next = find_same_agent_successor(graph, current)
        while next:
            steps.append(next)
            next = find_same_agent_successor(graph, next)

    return steps


def is_task_completed(graph: ActionDependencyGraph, vertex: ActionVertex):
    """Checks if this completed vertex is the last for its task.

    Args:
        graph (ActionDependencyGraph):
        vertex (ActionVertex):

    Returns:
        bool: True if this vertex has no child with the same task ID.
    """

    current_task_id = vertex.task_id

    child = None
    for successor in graph.successors(vertex):
        if successor.agent_name == vertex.agent_name:
            child = successor
            if successor.task_id == current_task_id:
                logger.debug(f"{vertex}'s child has the same task_id.")
                return False
            else:
                logger.debug(f"{vertex}'s child has a different task_id.")
            break

    if child == None:
        logger.info(f"{vertex} has no child.")
    logger.debug(f"{vertex}'s task is completed.")
    return True


def count_num_parents_in_state(
    graph: ActionDependencyGraph,
    vertex: ActionVertex,
    state: ActionVertex.State,
    num_parents_to_count: int,
) -> int:
    """Counts how many same-agent predecessors are in the specified state.

    Args:
        graph (ActionDependencyGraph):
        vertex (ActionVertex):
        num_parents (int): The maximum number of parents to count.
    """

    count = 0
    iter = 0

    current = vertex
    while iter < num_parents_to_count:
        iter += 1
        parent = find_same_agent_predecessor(graph, current)
        if not parent:
            break
        if parent.state == state:
            count += 1
            current = parent
    return count


def is_valid_candidate(graph: ActionDependencyGraph, candidate):

    logger.debug(f"Checking if candidate should be enqueued: {str(candidate)}")

    if candidate.state != ActionVertex.State.PENDING:
        logger.debug(
            f"Candidate was previously already enqueued or completed and does not need to be enqueued."
        )
        return False

    num_enqueued_parents = count_num_parents_in_state(
        graph,
        candidate,
        ActionVertex.State.ENQUEUED,
        NUM_DESIRED_ENQUEUED,
    )  # number of actions already enqueued for this agent
    if num_enqueued_parents >= NUM_DESIRED_ENQUEUED:
        logger.debug(
            f"Candidate already has {num_enqueued_parents} parents enqueued."
        )
        return False

    logger.debug(
        f"Candidate has immediate predecessors {list([str(x) for x in graph.predecessors(candidate)])}"
    )
    is_valid = True
    for pred in graph.predecessors(candidate):

        if pred.agent_name != candidate.agent_name:
            # Different-agent predecessor
            if pred.state != ActionVertex.State.COMPLETED:
                is_valid = False
                logger.debug(
                    f"Candidate is not valid yet because it has an uncompleted diff-agent predecessor."
                )
                break
        else:
            # Same-agent predecessor
            if pred.state not in {
                ActionVertex.State.COMPLETED,
                ActionVertex.State.ENQUEUED,
            }:
                logger.debug(
                    f"Candidate is not valid yet because it has an uncompleted/unqueued same-agent predecessor."
                )
                is_valid = False
                break
    if is_valid:
        logger.debug(f"Candidate is valid.")
    return is_valid


def find_new_candidates(
    graph: ActionDependencyGraph,
) -> Dict[str, List[ActionVertex]]:
    """Search the entire graph for new candidate actions.

    A candidate is new if it is pending and all its predecessors are completed.

    Args:
        current_graph (ActionDependencyGraph): ADG to search for successors.

    Returns:
        dict: {agent name : [valid candidates belonging to the agent]}
    """
    new_candidates = []

    for candidate in graph:
        logger.debug(
            f"  -- Current candidate: {str(candidate)} has predecessors {list([str(x) for x in graph.predecessors(candidate)])}"
        )
        if candidate.state != ActionVertex.State.PENDING:
            logger.debug(f"  This candidate is already enqueued or completed.")
            continue

        is_new = True
        for pred in graph.predecessors(candidate):
            if pred.state != ActionVertex.State.COMPLETED:
                is_new = False
                logger.debug(
                    f"  This candidate requires at least pred {str(pred)} to be completed in order to be considered new."
                )
                break
        if is_new:
            logger.debug(f"  This candidate is new.")
            new_candidates.append(candidate)

    for v in new_candidates:
        if v.state != ActionVertex.State.PENDING:
            raise ValueError
    return new_candidates


def find_and_enqueue_valid_candidates(
    candidates: Iterable[ActionVertex],
    current_graph: ActionDependencyGraph,
    agents,
    _get_actions_with_callbacks,
) -> Dict[str, List[ActionVertex]]:
    """Iterates over provided candidates to determine if they are valid for execution.
    Enqueues them if valid.
    Next checks for some number of same-agent successors.
    All are enqueued at once if possible to allow smoother movement.

    A candidate is valid for execution if:
        - all its different-agent predecessors are completed, and
        - its same-agent predecessor is completed or enqueued

    Args:
        candidates (Iterable[ActionVertex]): Candidate vertexes
        current_graph (ActionDependencyGraph): ADG to search for successors.

    Returns:
        dict: {agent name : [valid candidates belonging to the agent]}
    """
    valid_candidates = defaultdict(list)
    for candidate in candidates:
        logger.debug(f"Current candidate: {str(candidate)}")

        if is_valid_candidate(current_graph, candidate):
            valid_candidates[candidate.agent_name].append(candidate)

            # Update state to enable search for its children.
            candidate.state = ActionVertex.State.ENQUEUED

            # TODO: Clean up duplicate counting of parents.
            num_enqueued_parents = count_num_parents_in_state(
                current_graph,
                candidate,
                ActionVertex.State.ENQUEUED,
                NUM_DESIRED_ENQUEUED,
            )

            num_successors_to_check = NUM_DESIRED_ENQUEUED - num_enqueued_parents - 1
            # number of same-agent successors to check. -1 for this vertex itself.

            count = 0
            current = candidate
            while count < num_successors_to_check:
                # Enqueue immediate child if valid
                child = find_same_agent_successor(current_graph, current)
                if child is None:
                    break

                logger.debug(f"Checking child {count}: {str(child)}:")
                if is_valid_candidate(current_graph, child):
                    valid_candidates[child.agent_name].append(child)
                    child.state = ActionVertex.State.ENQUEUED
                    count += 1
                    current = child
                else:
                    break

    for agent_name, vertices in valid_candidates.items():
        for v in vertices:
            if v.state != ActionVertex.State.ENQUEUED:
                raise ValueError
        agents[agent_name].enqueue(_get_actions_with_callbacks(vertices))

    return valid_candidates


def finishing_soon(graph: ActionDependencyGraph, vertex, n):
    """
    True if this vertex has at most n same-agent successors.

    Args:
        graph (_type_): _description_
        vertex (_type_): _description_
        n (_type_): _description_

    Returns:
        _type_: _description_
    """
    count = 0

    current = vertex
    # This needs to be adjusted according to application and replanning duration.
    # Can check for moves remaining, or include waits
    # Alternatively: update moves_remaining for each new ADG so it can be looked up.
    while True:
        found_child = False
        for successor in graph.successors(current):
            if successor.agent_name == vertex.agent_name:
                current = successor
                count = count + 1
                found_child = True
                break  # No need to search siblings
        if not found_child:
            break
    if count <= n:
        logger.debug(f"Agent {vertex.agent_name} has {count} remaining.")
    return count <= n


def find_desired_vertex(graph: ActionDependencyGraph, vertex, n):
    """
    Returns the latest existing same-agent successor within n steps.
    Returns vertex itself if it has no same-agent successors.

    Args:
        graph (_type_): _description_
        vertex (_type_): _description_
        n (_type_): _description_

    Returns:
        _type_: _description_
    """
    count = 0
    latest_successor = vertex

    current = vertex
    while True and count < n:
        found_child = False
        for successor in graph.successors(current):
            if successor.agent_name == vertex.agent_name:
                latest_successor = successor
                current = successor
                count = count + 1
                found_child = True
                break  # No need to search siblings
        if not found_child:
            break
    logger.debug(
        f"[{latest_successor.agent_name}]'s current: {str(vertex)} -> desired vertex: {str(latest_successor)}."
    )
    return latest_successor


def find_latest_enqueued(graph: ActionDependencyGraph, vertex):
    """
    Returns the latest existing same-agent successor that has been enqueued.
    Returns vertex itself if it has no enqueued same-agent successor.

    Args:
        graph (_type_): _description_
        vertex (_type_): _description_

    Returns:
        _type_: _description_
    """
    if vertex.state == ActionVertex.State.PENDING:
        # Can't possibly have an enqueued successor.
        return vertex

    latest_successor = vertex
    current = vertex
    while True:
        found_child = False
        for successor in graph.successors(current):
            if (
                successor.agent_name == vertex.agent_name
                and successor.state == ActionVertex.State.ENQUEUED
            ):
                latest_successor = successor
                current = successor
                found_child = True
                break  # No need to search siblings
        if not found_child:
            break
    logger.debug(
        f"[{latest_successor.agent_name}]'s desired: {str(vertex)} -> latest-enqueued vertex: {str(latest_successor)}."
    )
    return latest_successor


def compute_desired_vertices(
    graph: ActionDependencyGraph, most_recently_completed, num_steps
):
    """The desired vertices is a dict of {agent_name, vertex} that we want to commit to.
    This should be tunable.

    Currently: actions that will be finished in `num_steps` GlobalPlan timesteps
    Desired vertices should comprise actions closer to minimise waiting for synchronisation, post-construction of the new plan,
    but further away such that replanning can complete.

    Args:
        num_steps (int): number of uncompleted steps to include.

    Returns:
        dict:
    """

    # Initialise desired set
    desired_vertices = {k: None for k in graph.get_agent_names()}

    for agent_name in desired_vertices:

        latest_vertex = most_recently_completed.get(agent_name)
        logger.debug(f"  latest_vertex: {str(latest_vertex)}")
        if latest_vertex is None:
            latest_vertex = graph.lookup_vertex(agent_name, 0)

        # Use the latest vertex to search for the desired vertex
        logger.debug(f"  latest_vertex: {str(latest_vertex)}")
        desired_vertices[agent_name] = find_desired_vertex(
            graph, latest_vertex, num_steps
        )

    return desired_vertices


def compute_reachable_set(graph: ActionDependencyGraph, desired_set):
    # Starting with desired set, find all reachable vertices.
    reachable = set()

    search_queue = [v for _, v in desired_set.items()]
    while search_queue:
        p = search_queue.pop()
        reachable.add(p)
        for pred in graph.predecessors(p):
            if pred not in reachable:
                search_queue.append(pred)
    return reachable


def compute_committed_vertices(agent_names, reachable_set):
    """
    Finds each agent's latest vertex in the reachable set.
    Returns None

    Args:
        agent_names (_type_): _description_
        reachable_set (_type_): _description_

    Returns:
        dict: Key: agent name, Value: this agent's latest vertex in the reachable set.
    """
    committed = {k: None for k in agent_names}
    for v in reachable_set:

        # First, find the latest step index stored so far for this agent.
        latest_index = -1
        if committed[v.agent_name] is not None:
            latest_index = committed[v.agent_name].step_index

        # If this vertex has a larger step index, store to committed.
        if v.step_index > latest_index:
            committed[v.agent_name] = v
    return committed


def increment_timesteps(global_plan: GlobalPlan, increment):
    for plan in global_plan.plans:
        for step in plan.steps:
            step.timestep += increment


def remove_completed_parents(graph: ActionDependencyGraph, vertex: ActionVertex):
    """Search the graph for completed same-agent predecessors and remove those.
    Does not remove vertex itself.

    Args:
        graph (ActionDependencyGraph): _description_
        vertex (ActionVertex): _description_
    """
    to_remove = []
    current = vertex

    while graph.predecessors(current):
        for predecessor in graph.predecessors(current):
            if predecessor.agent_name == current.agent_name:
                if predecessor.state == ActionVertex.State.COMPLETED:
                    to_remove.append(predecessor)
                current = predecessor
                break
        break

    for v in to_remove:
        graph.remove_vertex(v)
