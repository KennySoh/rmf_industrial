from adg.models.plan_models import Plan
from adg.models.mapf_execution_models import MapfSendTaskPostRequestTaskItem
from mapf_solve.cbs_adapter import CBSAdapter


class TestCBSAdapter:
    cbs_adapter = CBSAdapter()

    def test_request_mapf_plan(self):
        items = [
            MapfSendTaskPostRequestTaskItem(
                task_id="test0",
                robot_id="0",
                start_location="0,0",
                goal_location="2,0",
            ),
            MapfSendTaskPostRequestTaskItem(
                task_id="test1",
                robot_id="1",
                start_location="2,0",
                goal_location="0,0",
            ),
            MapfSendTaskPostRequestTaskItem(
                task_id="test2",
                robot_id="2",
                start_location="1,0",
                goal_location="1,2",
            ),
            MapfSendTaskPostRequestTaskItem(
                task_id="test3",
                robot_id="3",
                start_location="4,0",
                goal_location="4, 4",
            ),
        ]

        plans = self.cbs_adapter.request_mapf_plan(items)

        assert all(isinstance(item, Plan) for item in plans)
