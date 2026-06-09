#!/bin/bash
curl --location 'http://0.0.0.0:8000/mapf/send_task' --header 'Content-Type: application/json' --data '
{
    "tasks": [
    {
        "expected_start_time": 1717907040,
        "task_id": "R001",
        "robot_id": "MiR_9001",
        "start_location": "P97",
        "goal_location": "P17",
        "status": "",
        "type": ""
    },
    {
        "expected_start_time": 1717907040,
        "task_id": "R002",
        "robot_id": "MiR_9002",
        "start_location": "P137",
        "goal_location": "P18",
        "status": "",
        "type": ""
    },
    {
        "expected_start_time": 1717907040,
        "task_id": "R003",
        "robot_id": "MiR_9003",
        "start_location": "P177",
        "goal_location": "P19",
        "status": "",
        "type": ""
    },
    {
        "expected_start_time": 1717907040,
        "task_id": "R004",
        "robot_id": "MiR_9004",
        "start_location": "P217",
        "goal_location": "P20",
        "status": "",
        "type": ""
    },
    {
        "expected_start_time": 1717907040,
        "task_id": "R005",
        "robot_id": "MiR_9005",
        "start_location": "P257",
        "goal_location": "P21",
        "status": "",
        "type": ""
    },
    {
        "expected_start_time": 1717907040,
        "task_id": "R006",
        "robot_id": "MiR_9006",
        "start_location": "P337",
        "goal_location": "P22",
        "status": "",
        "type": ""
    }
    ]
}'
