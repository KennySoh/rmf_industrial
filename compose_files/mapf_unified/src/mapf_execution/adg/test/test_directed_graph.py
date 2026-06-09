from threading import Lock

import pytest

from adg.graph.directed_graph import DirectedGraph, execute_graph


class Vertex:
    def __init__(self, key):
        self.key = key

    def __str__(self):
        return str(self.key)


class TestDirectedGraph:
    g = DirectedGraph()

    def test_repeated_key(self):
        v1 = Vertex("v1")
        v2 = Vertex("v2")

        self.g.add_vertex(v1)

        with pytest.raises(ValueError):
            self.g.add_vertex(v1)

    def test_add_edges(self):
        v3 = Vertex("v3")
        v4 = Vertex("v4")
        self.g.add_vertex(v3)

        # v4 must be added before edge v3->v4 can be added
        with pytest.raises(ValueError):
            self.g.add_directed_edge(v3, v4, 100)

        self.g.add_vertex(v4)
        self.g.add_directed_edge(v3, v4, 100)

        edge = self.g.get_edge_data(v3, v4)
        assert edge == 100

        assert v4 in self.g._successors[v3]
        assert self.g._successors[v3] == {v4: 100}
        assert self.g._predecessors[v4] == {v3: 100}

    def test_remove_vertex(self):
        v5 = Vertex("v5")
        v6 = Vertex("v6")
        with pytest.raises(ValueError):
            self.g.remove_vertex(v5)

        self.g.add_vertex(v5)
        self.g.add_vertex(v6)

        self.g.add_directed_edge(v5, v6)

        self.g.remove_vertex(v5)
        assert v5 not in self.g
        assert v5 not in self.g.successors(v6)
        with pytest.raises(ValueError):
            v6 not in self.g.predecessors(v5)


@pytest.mark.parametrize(
    "graph, expected",
    [
        # No cycle
        ({0: [1], 1: [2], 2: []}, False),
        # Cycle present
        ({0: [1], 1: [2], 2: [0]}, True),
        # Disconnected graph with no cycles
        ({0: [1], 1: [2], 2: [], 3: [4], 4: []}, False),
        # Single node, no edges
        ({0: []}, False),
        # Single node with self-loop
        ({0: [0]}, True),
        # Multiple nodes with self-loops
        ({0: [0], 1: [1], 2: [2]}, True),
        # Multiple nodes with cycle
        ({0: [1], 1: [2], 2: [3], 3: [4], 4: [1], 5: []}, True),
        # Empty graph
        ({}, False),
    ],
)
def test_graphs(graph, expected):
    g = DirectedGraph()
    for node in graph:
        g.add_vertex(node)
    for node, edges in graph.items():
        for edge in edges:
            g.add_directed_edge(node, edge, 10)

    assert g.is_cyclic() == expected


class TestGraphExecution:
    g = DirectedGraph()

    agent_a = []
    agent_b = []
    for i in range(3):
        va = Vertex("A" + str(i))
        vb = Vertex("B" + str(i))

        g.add_vertex(va)
        g.add_vertex(vb)

        agent_a.append(va)
        agent_b.append(vb)

    """
            B0
            |
            v
      A0 -> A1 -> A2
            |
            v
            B1
            |
            v
            B2
    """

    # Type 1 edges for agent A
    g.add_directed_edge(agent_a[0], agent_a[1])
    g.add_directed_edge(agent_a[1], agent_a[2])

    # Type 1 edges for agent B
    g.add_directed_edge(agent_b[0], agent_b[1])
    g.add_directed_edge(agent_b[1], agent_b[2])

    # Type 2 edges between agents
    g.add_directed_edge(agent_b[0], agent_a[1])
    g.add_directed_edge(agent_a[1], agent_b[1])

    def test_execute_graph(self):
        lock = Lock()
        log = []

        def work_function(vertex, completed_cb):
            lock.acquire()
            log.append(vertex)
            lock.release()
            completed_cb()

        execute_graph(self.g, work_function)

        s = ""
        for i in log:
            s += str(i) + " "
        print(s)
        assert log.index(self.agent_a[2]) > log.index(self.agent_a[1])
        assert log.index(self.agent_b[1]) > log.index(self.agent_a[1])
        assert log.index(self.agent_b[2]) > log.index(self.agent_a[1])

        # ts = TopologicalSorter(self.g._predecessors)
        # for x in list(ts.static_order()):
        #     print(x)
