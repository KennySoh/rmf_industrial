#!/bin/bash
curl --location 'http://0.0.0.0:8000/mapf/replace_destination' --header 'Content-Type: application/json' --data '{
"destinations": [
  {
    "task_id": "M006",
    "robot_id": "MiR_9006",
    "goal_location": "P342"
  },
  {
    "task_id": "M005",
    "robot_id": "MiR_9005",
    "goal_location": "P261"
  }
  ]
}'
