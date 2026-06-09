"""
Action Dependency Graph (ADG)

Adapted from:
    Construction of Temporal Plan Graph (TPG)
    author: Ashwin Bose (@atb033)

"""

from enum import Enum
from itertools import count, permutations
import logging

import matplotlib.pyplot as plt
import networkx as nx

from cbs.cbs import Location

from .graph.directed_graph import DirectedGraph
from adg.models.plan_models import GlobalPlan, Step

logger = logging.getLogger("adg")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "[%(levelname)s] %(asctime)s:%(msecs)03d %(name)s: %(message)s", datefmt="%H:%M:%S"
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False


class ActionDependencyGraph(DirectedGraph):
    """
    As described in "Persistent and Robust Execution of MAPF Schedules in Warehouses"
    Captures the dependencies between actions of the agents in the plan.
    """

    def __init__(self, input_plan: GlobalPlan):
        """
        Initialise the ADG

        Args:
            input_plan (GlobalPlan): GlobalPlan object
        """
        super().__init__()

        self.vertex_catalogue = {}  # Keyed (agent_name,step) for lookup of Vertices
        self.start_vertices = {}  # holds starting vertices for each agent
        self.agent_names = set()

        self.generate_adg(input_plan)

    def _create_vertex(self, name, step: Step):
        v = ActionVertex(
            name,
            step.timestep,
            step.step_from.node,
            step.step_to.node,
            step.task_id
        )
        return v

    def add_vertex(self, vertex):
        super().add_vertex(vertex)
        self.vertex_catalogue[(vertex.agent_name, vertex.step_index)] = vertex

    def lookup_vertex(self, agent_name, step_index):
        return self.vertex_catalogue.get((agent_name, step_index), None)

    def print(self):
        logger.info(f"vertices")
        for v in self.vertex_catalogue:
            logger.info(f"{v}")

    def _count_moves_remaining(self, steps):
        """
        Returns a list.
        list[x] holds the number of moves (as opposed to waits) remaining after
        the step at x has been completed by the agent.
        This is used to determine when to trigger replanning.
        """
        # TODO Rethink this. This needs to be updated when combined with another ADG.
        # Or remove entirely if not using.
        num_moves = 0
        result = []
        for step in reversed(steps):
            result.insert(0, num_moves)
            if step.step_from != step.step_to:
                num_moves += 1
        return result

    def _create_type_one_edges(self, plan):
        """Add same-robot dependencies within the input plan for one agent to this ADG.
        Returns the starting vertex of the input plan.
        """
        # Create type-1 edges
        steps = plan.steps

        if len(steps) == 0:
            return None

        start_vertex = self._create_vertex(
            plan.agent_name, steps[0]
        )
        self.add_vertex(start_vertex)

        vertex_prev = start_vertex

        for i in range(1, len(steps)):
            vertex = self._create_vertex(
                plan.agent_name, steps[i]
            )
            self.add_vertex(vertex)

            self.add_directed_edge(vertex_prev, vertex)
            vertex_prev = vertex

        return start_vertex

    def _create_type_two_edges(self, input_global_plan):
        """Add inter-robot dependencies within the input global plan to this ADG."""
        for plan_i, plan_j in permutations(input_global_plan.plans, 2):
            agent_i = plan_i.agent_name
            steps_i = plan_i.steps

            agent_j = plan_j.agent_name
            steps_j = plan_j.steps

            for k_i in range(len(steps_i)):  # in Algorithm 1, 'k' denotes timestep
                for k_j in range(len(steps_j)):
                    from_ki = Location(
                        # steps_i[k_i].step_from.x, steps_i[k_i].step_from.y
                        steps_i[k_i].step_from.node
                    )
                    timestep_ki = steps_i[k_i].timestep

                    # to_kj = Location(steps_j[k_j].step_to.x, steps_j[k_j].step_to.y)
                    to_kj = Location(steps_j[k_j].step_to.node)
                    timestep_kj = steps_j[k_j].timestep

                    # Ensure i leaves from_ki before j can move to that location.
                    if from_ki == to_kj and timestep_ki <= timestep_kj:
                        self.add_directed_edge(
                            self.lookup_vertex(agent_i, timestep_ki),
                            self.lookup_vertex(agent_j, timestep_kj),
                        )
                        break

    def generate_adg(self, input_plan):
        logger.debug("Generating ADG on initialisation..")

        for plan in input_plan.plans:
            # Create type one edges
            starting_vertex = self._create_type_one_edges(plan)

            # Tracking variables
            self.start_vertices[plan.agent_name] = starting_vertex
            self.agent_names.add(plan.agent_name)

        self._create_type_two_edges(input_plan)

    def append_plan(
        self, committed_vertices, existing_global_plan, incoming_global_plan
    ):
        """Modifies this graph and existing_global_plan by adding the incoming plan.

        Args:
            committed_vertices (_type_): _description_
            existing_plan (_type_): The existing Global Plan with completed steps removed.
            incoming_plan (_type_): _description_
        """
        logger.debug("Appending incoming plan to ADG..")

        for plan in incoming_global_plan.plans:
            logger.debug(f"incoming plan: {str(plan)}")
            # Create type-1 edges
            first_vertex = self._create_type_one_edges(plan)

            if (
                first_vertex is not None
            ):  # There might not be a need to move in this plan.
                # Create the edge from the existing committed vertices to the incoming ones.
                committed_vertex = committed_vertices[plan.agent_name]
                self.add_directed_edge(committed_vertex, first_vertex)

        for plan in existing_global_plan.plans:
            # TODO Switch Global Plan to dict
            for incoming_plan in incoming_global_plan.plans:
                if plan.agent_name == incoming_plan.agent_name:
                    plan.steps.extend(incoming_plan.steps)

        self._create_type_two_edges(existing_global_plan)
        # Can optimise to skip some edges previously found in the existing plan.

        for plan in existing_global_plan.plans:
            logger.debug(f"Plan after appending: {str(plan)}")

    def generate_nx_graph(self):
        g = nx.DiGraph()
        for node, node_successors in self._successors.items():
            for s in node_successors:
                g.add_edge(node, s)
        return g

    def display_nx_graph(self):
        """
        Visualises the ADG.
        """
        g = self.generate_nx_graph()

        groups = set(n.agent_name for n in g.nodes)
        mapping = dict(zip(sorted(groups), count()))
        nodes = g.nodes()
        colors = [mapping[n.agent_name] for n in nodes]
        nx.draw_planar(
            g,
            with_labels=True,
            font_weight="bold",
            node_color=colors,
            cmap=plt.cm.Pastel1,
        )
        plt.show()

    def get_agent_name(self, vertex):
        """Get agent that vertex belongs to"""
        return vertex.agent_name

    def get_agent_names(self):
        return self.agent_names


class ActionVertex:
    """
    TODO: From information in the ActionVertex, its Agent should automatically generate
    the object representing this action (eg serialised for IPC)
    """

    class State(Enum):
        ENQUEUED = "action_enqueued"   # Sent for execution to agents
        COMPLETED = "action_completed"
        PENDING = "action_pending"

    def __init__(
        self,
        agent_name,
        step_index,
        location_start,
        location_end,
        task_id,
    ):
        self.agent_name = agent_name
        self.location_start = location_start
        self.location_end = location_end
        self.step_index = step_index  # The index of this step in this Agent's plan.
        self.task_id = task_id  # Task ID, may be None

        self.state = self.State.PENDING


    def __str__(self):
        return str(
            "<"
            + self.agent_name
            + "; t"
            + str(self.step_index)
            + "; "
            + f"({str(self.location_start)})"
            + "-"
            + f"({str(self.location_end)})"
            + "; "
            + f"({str(self.state.value)})"
            + "; "
            + f"({str(self.task_id)})"
            
            + ">"
        )

    def to_dict(self):
        data = {
            "agent_name": self.agent_name,
            "step_index": self.step_index,
            "location_start": self.location_start,
            "location_end": self.location_end,
            "state": self.state.value,
        }
        return data

    def __eq__(self, other):
        if other is None:
            return False
        if not isinstance(other, ActionVertex):
            return False

        # Don't consider state in test for equality.
        return (
            self.agent_name == other.agent_name
            and self.location_start == other.location_start
            and self.location_end == other.location_end
            and self.step_index == other.step_index
        )

    def __hash__(self):
        # Don't include state in hash function
        return hash(str(
                "<"
                + self.agent_name
                + "; t"
                + str(self.step_index)
                + "; "
                + f"({str(self.location_start)})"
                + "-"
                + f"({str(self.location_end)})"
                + "; "
                + f"({str(self.task_id)})"
                + ">"
            )
        )
