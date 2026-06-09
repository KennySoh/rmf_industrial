# Movement Request Server
Web application that is the interface for submission and monitoring of movement tasks.
These requests are enqueued to Redis for execution by mapf_execution.


## Installation
```shell
pip install -r requirements.txt

```

## To run the demo

1. Run the server. The default port is 8000.
```shell
uvicorn --app-dir app main:app --reload
```

2. Start the redis service.
```shell
docker run -d --name redis-stack -p 6379:6379 -p 8001:8001 redis/redis-stack:latest
docker start redis-stack # if container was stopped.
# docker exec -it redis-stack redis-cli FLUSHALL # clear data in Redis
```

3. Submit a request with curl and monitor it.

```shell
cd examples
./send_request.bash
./monitor_request.bash
```

Example output from /mapf/monitor_task:
```json
{"tasks": [
    {"task_id":"agv_1_dummy_task_id","status":"executing"},
    {"task_id":"agv_2_dummy_task_id","status":"completed"},
    {"task_id":"agv_3_dummy_task_id","status":"completed"}
 ]
}
```
