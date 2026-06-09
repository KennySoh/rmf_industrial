#!/bin/bash
curl --location 'http://0.0.0.0:8000/mapf/send_task' --header 'Content-Type: application/json' --data '
{
    "tasks": [
    {
        "expected_start_time": 1717907040,
        "task_id": "001",
        "robot_id": "MiR_9001",
        "start_location": "P17",
        "goal_location": "P297",
        "status": "",
        "type": ""
    },
    {
        "expected_start_time": 1717907040,
        "task_id": "002",
        "robot_id": "MiR_9002",
        "start_location": "P18",
        "goal_location": "P298",
        "status": "",
        "type": ""
    },
    {
        "expected_start_time": 1717907040,
        "task_id": "003",
        "robot_id": "MiR_9003",
        "start_location": "P19",
        "goal_location": "P299",
        "status": "",
        "type": ""
    },
    {
        "expected_start_time": 1717907040,
        "task_id": "004",
        "robot_id": "MiR_9004",
        "start_location": "P20",
        "goal_location": "P300",
        "status": "",
        "type": ""
    },
    {
        "expected_start_time": 1717907040,
        "task_id": "005",
        "robot_id": "MiR_9005",
        "start_location": "P21",
        "goal_location": "P301",
        "status": "",
        "type": ""
    },
    {
        "expected_start_time": 1717907040,
        "task_id": "006",
        "robot_id": "MiR_9006",
        "start_location": "P22",
        "goal_location": "P302",
        "status": "",
        "type": ""
    }
    ]
}'
