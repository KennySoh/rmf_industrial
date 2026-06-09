import pytest
import yaml

from adg.adg import ActionDependencyGraph, ActionVertex
from adg.adg_functions import count_num_parents_in_state, find_and_enqueue_valid_candidates
from adg.models.plan_models import GlobalPlan

from adg.test.mock_agent import MockAgent

@pytest.fixture(scope="class")
def test_adg_functions_fixture():
    
    # Initialise empty plan with agent_1 and agent_2
    global_plan_dict = yaml.safe_load(
"""
plans:
- agent_name: agent_1
  steps: []
- agent_name: agent_2
  steps: []
"""
    )
    global_plan = GlobalPlan(**global_plan_dict)
    adg = ActionDependencyGraph(global_plan)

    # Add test vertices
    v_a_0 = ActionVertex("agent_a", 0, "_", "_", "_")
    v_a_0.state = ActionVertex.State.ENQUEUED
    v_a_1 = ActionVertex("agent_a", 1, "_", "_", "_")
    v_a_1.state = ActionVertex.State.ENQUEUED
    v_a_2 = ActionVertex("agent_a", 2, "_", "_", "_")
    v_a_2.state = ActionVertex.State.ENQUEUED
    v_a_3 = ActionVertex("agent_a", 3, "_", "_", "_")
    v_a_3.state = ActionVertex.State.PENDING
    v_a_4 = ActionVertex("agent_a", 4, "_", "_", "_")
    v_a_4.state = ActionVertex.State.PENDING

    adg.add_vertex(v_a_0)
    adg.add_vertex(v_a_1)
    adg.add_vertex(v_a_2)
    adg.add_vertex(v_a_3)
    adg.add_vertex(v_a_4)

    adg.add_directed_edge(v_a_0, v_a_1)
    adg.add_directed_edge(v_a_1, v_a_2)
    adg.add_directed_edge(v_a_2, v_a_3)
    adg.add_directed_edge(v_a_3, v_a_4)

    v_b_0 = ActionVertex("agent_b", 0, "_", "_", "_")
    v_b_0.state = ActionVertex.State.COMPLETED
    v_b_1 = ActionVertex("agent_b", 1, "_", "_", "_")
    v_b_1.state = ActionVertex.State.PENDING
    v_b_2 = ActionVertex("agent_b", 2, "_", "_", "_")
    v_b_2.state = ActionVertex.State.PENDING
    v_b_3 = ActionVertex("agent_b", 3, "_", "_", "_")
    v_b_3.state = ActionVertex.State.PENDING
    v_b_4 = ActionVertex("agent_b", 4, "_", "_", "_")
    v_b_4.state = ActionVertex.State.PENDING

    adg.add_vertex(v_b_0)
    adg.add_vertex(v_b_1)
    adg.add_vertex(v_b_2)
    adg.add_vertex(v_b_3)
    adg.add_vertex(v_b_4)

    adg.add_directed_edge(v_b_0, v_b_1)
    adg.add_directed_edge(v_b_1, v_b_2)
    adg.add_directed_edge(v_b_2, v_b_3)
    adg.add_directed_edge(v_b_3, v_b_4)

    adg.add_directed_edge(v_b_0, v_a_3)

    yield adg


class TestADGFunctions:
    
    @pytest.mark.usefixtures("test_adg_functions_fixture")
    def test_count(self, test_adg_functions_fixture):
        
        adg = test_adg_functions_fixture

        assert count_num_parents_in_state(adg, adg.lookup_vertex("agent_a", 4), ActionVertex.State.PENDING, 5) == 1
        assert count_num_parents_in_state(adg, adg.lookup_vertex("agent_a", 4), ActionVertex.State.PENDING, 1) == 1
        assert count_num_parents_in_state(adg, adg.lookup_vertex("agent_a", 4), ActionVertex.State.PENDING, 0) == 0


    def test_find_and_enqueue_valid_candidates(self, test_adg_functions_fixture):
        

        adg = test_adg_functions_fixture
        agents = {}
        agents["agent_a"] = MockAgent("agent_a")
        agents["agent_b"] = MockAgent("agent_b")

        candidates = [adg.lookup_vertex("agent_b", 1), adg.lookup_vertex("agent_a", 3)]

        mock_cb = lambda x: None
        valid = find_and_enqueue_valid_candidates(candidates, adg, agents, mock_cb)
        # v_a_3 should not be enqueued because it already has 3 enqueued parents.
        assert adg.lookup_vertex("agent_a", 3) not in valid.values()

        # after v_a_3's parent is completed, it gets enqueued.
        adg.lookup_vertex("agent_a", 0).state = ActionVertex.State.COMPLETED
        valid = find_and_enqueue_valid_candidates(candidates, adg, agents, mock_cb)
        assert adg.lookup_vertex("agent_a", 3) in valid["agent_a"]
