from collections import deque
from collections.abc import Callable
from queue import Queue
from threading import Thread
from typing import Any


class DirectedGraph:
    """
    Directed graph class.
    Vertexes must be hashable.
    """

    def __init__(self):
        self._successors = {}  # key: Vertex, value: dict of successors and edge data
        self._predecessors = {}

    def __contains__(self, vertex):
        return vertex in self._successors

    def __iter__(self):
        return iter(self._successors)

    def __len__(self):
        return len(self._successors)

    def add_vertex(self, vertex):
        if vertex in self:
            raise ValueError(f"Vertex already exists: {str(vertex)}")
        self._successors[vertex] = {}
        self._predecessors[vertex] = {}

    def add_directed_edge(self, vertex_from, vertex_to, edge_data=None):
        """
        For now, edges can only be added if the vertexes are already in the graph.

        Args:
            vertex_from (_type_): _description_
            vertex_to (_type_): _description_
            edge_data (_type_, optional): _description_. Defaults to None.

        Raises:
            ValueError: _description_
        """
        if not vertex_from in self:
            raise ValueError(
                "vertex_from " + str(vertex_from) + " does not exist in the graph."
            )
        if not vertex_to in self:
            raise ValueError("vertex_to does not exist in the graph.")

        self._successors[vertex_from][vertex_to] = edge_data
        self._predecessors[vertex_to][vertex_from] = edge_data

    def get_edge_data(self, vertex_from, vertex_to):
        if not vertex_from in self:
            raise ValueError("vertex_from does not exist in the graph.")
        if not vertex_to in self:
            raise ValueError("vertex_to does not exist in the graph.")
        return self._successors[vertex_from][vertex_to]

    def predecessors(self, v):
        try:
            return iter(self._predecessors[v])
        except KeyError:
            raise ValueError(f"Vertex {str(v)} does not exist in the graph.")

    def remove_vertex(self, v):
        if v not in self:
            raise ValueError(f"Vertex {str(v)} does not exist in the graph.")

        neighbours = self._successors[v]
        for u in neighbours:
            del self._predecessors[u][v]
        del self._successors[v]
        for u in self._predecessors[v]:
            del self._successors[u][v]
        del self._predecessors[v]

    def successors(self, v):
        try:
            return iter(self._successors[v])
        except KeyError:
            raise ValueError(f"Vertex {str(v)} does not exist in the graph.")

    def get_indegrees(self):
        indegrees = {}
        for v, successors in self._successors.items():
            if v not in indegrees:
                indegrees[v] = 0
            for s in successors:
                if s not in indegrees:
                    indegrees[s] = 1
                else:
                    indegrees[s] += 1
        # for k, v in indegrees.items():
        #     print(str(k), str(v))
        return indegrees

    def is_cyclic(self):
        indegrees = self.get_indegrees()
        queue = deque([node for node in self._successors if indegrees[node] == 0])
        processed_count = 0

        while queue:
            node = queue.popleft()
            processed_count += 1
            for succ in self.successors(node):
                indegrees[succ] -= 1
                if indegrees[succ] == 0:
                    queue.append(succ)
        return processed_count != len(self._successors)


def execute_graph(g: DirectedGraph, work_function: Callable[[Any, Callable], Any]):
    """
    Executes a generic dependency graph represented as a directed graph.
    Processes each vertex in the graph when their predecessors have been processed.
    Caller must provide a work_function that accepts two parameters:
      param 1: the vertex to be processed.
      param 2: a callback to be called on completion of the action at the vertex.

    Args:
        g (DirectedGraph): An instance of the DirectedGraph.
        work_function (Callable[[Any, Callable]])): Function that accepts a Vertex and a callback function as parameters.
        It should perform the work to be done by the vertex, and call the provided callback function upon completion.
    """
    indegrees = g.get_indegrees()

    # Only one consumer each for completed_jobs and job_queue.
    # Here, None is used to signal the consumer to shut down. Regular work items (Vertices) must never be None

    job_queue = Queue()
    completed_jobs = Queue()
    staged = set()

    def process_job_queue():
        def _do_job(vertex):
            print("Executing vertex:", str(vertex))

            def _completed_cb():
                completed_jobs.put(vertex, block=False)

            work_function(vertex, _completed_cb)
            print("Completed:", str(vertex))

        while True:
            w = job_queue.get(block=True)
            if w:
                # Switch to Queue.shutdown() when available https://github.com/python/cpython/pull/104750
                t = Thread(target=_do_job, args=[w])
                t.start()
            else:
                break

    t = Thread(target=process_job_queue)
    t.start()

    while indegrees:
        for k, v in indegrees.items():
            # Can reduce some iterations by checking only candidates after initial vertexes
            if v == 0 and k not in staged:
                job_queue.put(
                    k, block=False
                )  # Queue Full exception is not expected to occur
                staged.add(k)

        completed = completed_jobs.get(block=True)  # timeout?
        for successor in g.successors(completed):
            indegrees[successor] -= 1
        del indegrees[completed]

    job_queue.put(None, block=False)
    print("Graph Execution completed")
