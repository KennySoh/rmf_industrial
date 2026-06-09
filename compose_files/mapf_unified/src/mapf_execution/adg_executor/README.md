# ADG Executor 

This application connects to other components to provide execution of an MAPF plan.

## How it works  
1. Periodically dequeues available messages from a queue. Each message is a list of movement tasks.
    - A movement task is a [MapfSendTaskPostRequestItem](models.py) for one robot to move.
    - Currently, only the most recent message is handled in each dequeue.
    - Queue is a Redis queue.
2. The list of movement tasks is used to generate and solve an MAPF problem
    - A MAPFSolveRequest is created which calls the HTTP server provided by `run_mapf_service`
    - The resulting solution is converted into a GlobalPlan object.
3. The GlobalPlan is the input to generate an ADG
4. The ADG is executed to completion. Agents are defined to perform the action at each vertex.
    - In this instance, `HTTPOrderAgent`s communicate with a HTTP server provided by a VDA5050 master control to:
    - Create and update Orders
    - Check order completion status
5. Currently, if a new list of tasks is dequeued in step 1, the current ADG is interrupted and a new ADG begins.

## Running the applications required
Refer to individual repos for build instructions.

#### 1. Run the `movement_request_server`
```
cd $WORKSPACE/src/movement_request_server/app
uvicorn main:app --reload
```
This HTTP server listens to requests on /mapf/monitor_task and enqueues the requests onto the message queue.

#### 2. Run the ADG Executor in `mapf_execution`
```
docker run -d --name redis-stack -p 6379:6379 -p 8001:8001 redis/redis-stack:latest
# Place building.yaml in directory mapf_execution
cd $WORKSPACE/src/mapf_execution
python3 -m adg_executor.main
```

#### 3. Run the [mapf_service](https://gitlab.com/ROSI-AP/rmf2/mapf_service)'s `develop` branch
```
cd $WORKSPACE
source install/setup.bash
ros2 run mapf run_mapf_service
```

#### 4. Run the VDA5050 master control and clients
See the vda5050 repo for instructions.

Now we can send movement requests to make the VDA5050 clients move.

### Create a movement request
```
curl --location 'http://localhost:8000/mapf/send_task' --header 'Content-Type: application/json' --data '{
"tasks": [
  {
    "expected_start_time": 1717907040,
    "task_id": "agv_0_dummy_task_id",
    "robot_id": "robots_robot_1",
    "start_location" : "P5",
    "goal_location": "P1",
    "status": "",
    "type": ""
  },
  {
    "expected_start_time": 1717907040,
    "task_id": "agv_1_dummy_task_id",
    "robot_id": "robots_robot_2",
    "start_location" : "P1",
    "goal_location": "P5",
    "status": "",
    "type": ""
  }
  ]
}'

```

### Monitor the status of the movement request
```
curl -X 'GET'   'http://localhost:8000/mapf/monitor_task?task_id=agv_0_dummy_task_id&task_id=agv_1_dummy_task_id'   -H 'accept: application/json'
```

Responses:
- executing
- completed
- interrupted
- failed


## Development instructions

### Run the executor in isolation
Temporary instructions for testing, will be moved to examples later.
- Use the service at `ros2 run mapf run_mapf_service` to generate a MAPF solution
- Convert the solution into a GlobalPlan and save it as a yaml file. An example file is provided [here](../examples/global_plan.yaml)
- Place building.yaml in directory mapf_execution
- `python3 -m adg_executor.mainfromplan examples/global_plan.yaml`
- add --mock_complete_actions to complete all actions without checking with the robot controller.
