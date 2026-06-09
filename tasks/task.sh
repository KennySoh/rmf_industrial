#!/bin/bash
curl --location 'http://0.0.0.0:8000/mapf/send_task' --header 'Content-Type: application/json' --data '
{
    "tasks": [
    {
        "expected_start_time": 1717907040,
        "task_id": "custom_task_id_1",
        "robot_id": "robots_robot_1",
        "start_location": "P0",
        "goal_location": "P15",
        "status": "",
        "type": ""
    },
    {
        "expected_start_time": 1717907040,
        "task_id": "custom_task_id_2",
        "robot_id": "robots_robot_2",
        "start_location": "P1",
        "goal_location": "P14",
        "status": "",
        "type": ""
    }
    ]
}'
