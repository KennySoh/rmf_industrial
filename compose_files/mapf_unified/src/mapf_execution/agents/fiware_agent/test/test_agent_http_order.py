from functools import partial
import json
import time
import pytest
import yaml

from adg.adg import ActionVertex
from adg.adg_execution import ActionWithCallback
from adg.models.plan_models import GlobalPlan
from agents.fiware_agent.agent_http_order import HTTPOrderAgent


@pytest.fixture(scope="function")
def http_order_agent_fixture():
    print("Setting up..")

    agent_args = {"url": "http://localhost:8080"}
    agent_name = "test_agent"
    agent = HTTPOrderAgent(agent_name, agent_args)

    yield agent

    print("Tearing down..")
    agent.shutdown()
    time.sleep(
        0.5
    )  # TODO: fix shutdown errors when test ends.


class TestHTTPOrderAgent:
    @pytest.mark.usefixtures("http_order_agent_fixture")
    def test_mock_responses(self, http_order_agent_fixture):
        agent = http_order_agent_fixture

        def cb(content):
            result.append(content)

        result = []
        # Test order creation
        awcs = [
            ActionWithCallback(
                ActionVertex(agent.robot_id, 0, "s0", "e0", "task1"),
                partial(cb, "first"),
            ),
            ActionWithCallback(
                ActionVertex(agent.robot_id, 1, "s1", "e1", "task1"),
                partial(cb, "second"),
            ),
        ]
        agent.enqueue(awcs)

        assert agent.current_order.model_dump() == {
            "robot_id": "test_agent",
            "task_id": "task1",
            "order_id": "task1",
            "path": [
                # Must have initial starting point
                {"sequence_id": 0, "node": "s0", "released": True},
                {"sequence_id": 1, "node": "e0", "released": True},
                {"sequence_id": 2, "node": "e1", "released": True},
            ],
        }

        # Test that waits are not added to the order
        agent.enqueue(
            [
                ActionWithCallback(
                    ActionVertex(agent.robot_id, 2, "e1", "e1", "task1"),
                    partial(cb, "third"),
                )
            ]
        )

        assert agent.current_order.model_dump() == {
            "robot_id": "test_agent",
            "task_id": "task1",
            "order_id": "task1",
            "path": [
                {"sequence_id": 0, "node": "s0", "released": True},
                {"sequence_id": 1, "node": "e0", "released": True},
                {"sequence_id": 2, "node": "e1", "released": True},
                # Wait action should not be added
            ],
        }

        # Test addition of another node.
        agent.enqueue(
            [
                ActionWithCallback(
                    ActionVertex(agent.robot_id, 2, "e1", "e2", "task1"),
                    partial(cb, "fourth"),
                )
            ]
        )

        assert agent.current_order.model_dump() == {
            "robot_id": "test_agent",
            "task_id": "task1",
            "order_id": "task1",
            "path": [
                {"sequence_id": 0, "node": "s0", "released": True},
                {"sequence_id": 1, "node": "e0", "released": True},
                {"sequence_id": 2, "node": "e1", "released": True},
                {"sequence_id": 3, "node": "e2", "released": True},
            ],
        }

        mock_response_text = json.dumps(
            {
                "robot_id": "test_agent",
                "task_id": "task1",
                "order_id": "task1",
                "path": [
                    {
                        "sequence_id": 0,
                        "node": "s0",
                        "released": True,
                        "completed": True,
                    },
                    {
                        "sequence_id": 1,
                        "node": "e0",
                        "released": True,
                        "completed": True,
                    },
                    {
                        "sequence_id": 2,
                        "node": "e1",
                        "released": True,
                        "completed": True,
                    },
                    {
                        "sequence_id": 3,
                        "node": "e2",
                        "released": True,
                        "completed": True,
                    },
                ],
            }
        )

        agent.process_status(mock_response_text)

        assert result == ["first", "second", "third", "fourth"]

    def test_repeated_waits(self, http_order_agent_fixture):
        agent = http_order_agent_fixture

        result = []
        def cb(content):
            result.append(content)


        # Initialise order
        awcs = [
            ActionWithCallback(
                ActionVertex(agent.robot_id, 0, "s0", "e0", "task1"),
                partial(cb, "first"),
            ),
            ActionWithCallback(
                ActionVertex(agent.robot_id, 1, "s1", "e1", "task1"),
                partial(cb, "second"),
            ),
        ]
        agent.enqueue(awcs)

        mock_response_text = json.dumps(
            {
                "robot_id": "test_agent",
                "task_id": "task1",
                "order_id": "task1",
                "path": [
                    {
                        "sequence_id": 0,
                        "node": "s0",
                        "released": True,
                        "completed": True,
                    },
                    {
                        "sequence_id": 1,
                        "node": "e0",
                        "released": True,
                        "completed": True,
                    },
                    {
                        "sequence_id": 2,
                        "node": "e1",
                        "released": True,
                        "completed": True,
                    }
                ],
            }
        )

        agent.process_status(mock_response_text)

        # Test that repeated waits are automatically completed once enqueued - without having to provide a response
        agent.enqueue(
            [
                ActionWithCallback(
                    ActionVertex(agent.robot_id, 2, "e1", "e1", "task1"),
                    partial(cb, "third"),
                ),
                ActionWithCallback(
                    ActionVertex(agent.robot_id, 3, "e1", "e1", "task1"),
                    partial(cb, "fourth"),
                )
            ]
        )

        assert result == ["first", "second", "third", "fourth"]
