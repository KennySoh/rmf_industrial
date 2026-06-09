curl --location 'http://localhost:8000/mapf/send_task' --header 'Content-Type: application/json' --data '{
"tasks": [
  {
    "task_id": "dummy_task_1",
    "robot_id": "robots_robot_1",
    "start_location" : "P5",
    "goal_location": "P1",
  },
  {
    "task_id": "dummy_task_2",
    "robot_id": "robots_robot_2",
    "start_location" : "P1",
    "goal_location": "P5",
  }
  ]
}'
