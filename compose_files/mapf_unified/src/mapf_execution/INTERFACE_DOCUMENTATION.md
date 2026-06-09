# MAPF Execution Module - External Interface Documentation

This document describes how external systems can interface with the MAPF Execution module.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [HTTP API Endpoints](#http-api-endpoints)
3. [Request/Response Models](#requestresponse-models)
4. [Task Lifecycle](#task-lifecycle)
5. [Monitoring Tasks](#monitoring-tasks)
6. [Replanning (Dynamic Destination Changes)](#replanning-dynamic-destination-changes)
7. [Redis Queue Interface](#redis-queue-interface)
8. [Error Handling](#error-handling)
9. [Integration Examples](#integration-examples)

---

## Architecture Overview

External systems communicate with MAPF Execution through an HTTP REST API provided by the **Movement Request Server**.

```
┌──────────────────────┐      HTTP        ┌─────────────────────────┐
│   External System    │ ───────────────► │  Movement Request Server │
│  (Dashboard, API,    │                  │  (FastAPI)               │
│   Scheduler, etc.)   │                  │  Port: configurable      │
└──────────────────────┘                  └────────────┬─────────────┘
                                                       │
                                                       │ Redis Queue
                                                       ▼
                                          ┌─────────────────────────┐
                                          │      Redis Server       │
                                          │  - mapf_tasks           │
                                          │  - mapf_replace_dest.   │
                                          └────────────┬─────────────┘
                                                       │
                                                       │ Dequeue
                                                       ▼
                                          ┌─────────────────────────┐
                                          │    ADG Executor         │
                                          │  (mapf_execution)       │
                                          │  - MAPF Solver          │
                                          │  - Agents (Robots)      │
                                          └─────────────────────────┘
```

### Components

| Component | Description | Location |
|-----------|-------------|----------|
| Movement Request Server | FastAPI HTTP server for external requests | `docker_modules/movement_request_server/` |
| Redis | Message queue between server and executor | External service |
| ADG Executor | Core MAPF execution engine | `docker_modules/mapf_execution/mapf_execution/adg_executor/` |

---

## HTTP API Endpoints

Base URL: `http://<host>:<port>` (default port configured via `MOVEMENT_REQUEST_SERVER_PORT` env var)

### POST /mapf/send_task

Submit movement tasks to the MAPF system.

**Request:**
```http
POST /mapf/send_task
Content-Type: application/json
```

**Request Body:**
```json
{
  "tasks": [
    {
      "task_id": "task_001",
      "robot_id": "agv_1",
      "start_location": "wp1",
      "goal_location": "wp5"
    },
    {
      "task_id": "task_002",
      "robot_id": "agv_2",
      "start_location": "wp3",
      "goal_location": "wp8"
    }
  ]
}
```

**Response (200 OK):**
```json
{
  "tasks": [
    {"task_id": "task_001", "status": "submitted"},
    {"task_id": "task_002", "status": "submitted"}
  ],
  "response": {
    "code": 0,
    "message": "submitted"
  }
}
```

**Response (500 Error):**
```json
{
  "detail": "Redis connection error: <error message>"
}
```

---

### GET /mapf/monitor_task

Monitor the status of one or more tasks.

**Request:**
```http
GET /mapf/monitor_task?task_id=task_001&task_id=task_002
```

**Response (200 OK):**
```json
{
  "tasks": [
    {"task_id": "task_001", "status": "IN_PROGRESS"},
    {"task_id": "task_002", "status": "COMPLETED"}
  ]
}
```

**Possible Status Values:**
| Status | Description |
|--------|-------------|
| `QUEUED` | Task is queued, waiting to start |
| `IN_PROGRESS` | Task is currently being executed |
| `COMPLETED` | Task finished successfully |
| `FAILED` | Task failed (check verbose endpoint for details) |
| `missing` | Task ID not found in system |

---

### GET /mapf/monitor_task_verbose

Monitor tasks with detailed status information.

**Request:**
```http
GET /mapf/monitor_task_verbose?task_id=task_001
```

**Response (200 OK):**
```json
{
  "tasks": [
    {
      "task_id": "task_001",
      "status": "IN_PROGRESS, <agv_1; t3; (wp3)-(wp4); (action_completed); (task_001)>"
    }
  ]
}
```

The verbose status includes details about the current action being executed.

---

### POST /mapf/replace_destination

Change the destination of robots during execution (triggers replanning).

**Request:**
```http
POST /mapf/replace_destination
Content-Type: application/json
```

**Request Body:**
```json
{
  "destinations": [
    {
      "task_id": "task_001",
      "robot_id": "agv_1",
      "goal_location": "wp10"
    }
  ]
}
```

**Response (200 OK):**
```json
{
  "destinations": {
    "code": 0,
    "message": "submitted"
  }
}
```

---

### PUT /mapf/pause_task (Not Implemented)

Gracefully pause a task.

**Request Body:**
```json
[
  {"task_id": "task_001"}
]
```

---

### PUT /mapf/resume_task (Not Implemented)

Resume a paused task.

**Request Body:**
```json
[
  {"task_id": "task_001"}
]
```

---

### POST /mapf/cancel_task (Not Implemented)

Cancel a task.

**Request Body:**
```json
[
  {"task_id": "task_001"}
]
```

---

## Request/Response Models

### MapfSendTaskPostRequestTaskItem

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task_id` | string | No | Unique identifier for the task. Auto-generated if not provided. |
| `robot_id` | string | Yes | Identifier of the robot/AGV to perform the task |
| `start_location` | string | Yes | Starting waypoint/node identifier |
| `goal_location` | string | Yes | Destination waypoint/node identifier |

**Example:**
```json
{
  "task_id": "urn:ngsi-ld:TaskRequest:12345",
  "robot_id": "agv_1",
  "start_location": "P1",
  "goal_location": "P5"
}
```

### ReplaceDestination

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task_id` | string | No | Task ID associated with this change |
| `robot_id` | string | Yes | Robot whose destination should change |
| `goal_location` | string | Yes | New destination waypoint |

---

## Task Lifecycle

```
                    ┌──────────┐
                    │ SUBMITTED│
                    └────┬─────┘
                         │
                         ▼
                    ┌──────────┐
                    │  QUEUED  │  ◄── Task waiting in queue
                    └────┬─────┘
                         │
                         ▼
                  ┌─────────────┐
                  │ IN_PROGRESS │  ◄── Robot actively moving
                  └──────┬──────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
        ┌──────────┐ ┌──────────┐ ┌───────────┐
        │COMPLETED │ │  FAILED  │ │INTERRUPTED│
        └──────────┘ └──────────┘ └───────────┘
```

### State Transitions

1. **SUBMITTED → QUEUED**: Task received and queued in Redis
2. **QUEUED → IN_PROGRESS**: MAPF solver computed plan, execution started
3. **IN_PROGRESS → COMPLETED**: Robot reached destination
4. **IN_PROGRESS → FAILED**: Error occurred (solver failed, robot error, etc.)
5. **IN_PROGRESS → INTERRUPTED**: New task batch received, current execution interrupted

---

## Monitoring Tasks

### Polling for Status

```python
import requests
import time

def monitor_tasks(task_ids: list, base_url: str = "http://localhost:8000"):
    """Poll task status until all complete or fail."""
    while True:
        params = "&".join([f"task_id={tid}" for tid in task_ids])
        response = requests.get(f"{base_url}/mapf/monitor_task?{params}")
        tasks = response.json()["tasks"]

        all_done = True
        for task in tasks:
            status = task["status"]
            print(f"Task {task['task_id']}: {status}")

            if status not in ["COMPLETED", "FAILED", "missing"]:
                all_done = False

        if all_done:
            break

        time.sleep(1.0)  # Poll interval
```

### Task Status in Redis

Task statuses are stored in Redis with two keys:
- `<task_id>` - Simple status (e.g., "COMPLETED")
- `<task_id>_v` - Verbose status with details

---

## Replanning (Dynamic Destination Changes)

During execution, you can redirect robots to new destinations:

```python
import requests

def redirect_robot(robot_id: str, new_destination: str, task_id: str = None):
    """Redirect a robot to a new destination during execution."""
    payload = {
        "destinations": [
            {
                "robot_id": robot_id,
                "goal_location": new_destination,
                "task_id": task_id
            }
        ]
    }
    response = requests.post(
        "http://localhost:8000/mapf/replace_destination",
        json=payload
    )
    return response.json()
```

### How Replanning Works

1. Request is added to `mapf_replace_destinations` Redis queue
2. ADG Executor dequeues the request
3. Current execution state is analyzed to find "committed vertices" (actions that cannot be undone)
4. MAPF solver is called with new goals and current robot positions
5. Action Dependency Graph is updated with the new plan
6. Execution continues seamlessly with updated routes

---

## Redis Queue Interface

For systems that need to bypass the HTTP API and write directly to Redis:

### Queue Names

| Queue Name | Purpose |
|------------|---------|
| `mapf_tasks` | New task requests |
| `mapf_replace_destinations` | Destination replacement requests |

### Message Format for mapf_tasks

```python
import redis
import json

r = redis.Redis(host='localhost', port=6379, db=0)

# Each task as JSON string
tasks = [
    json.dumps({
        "task_id": "task_001",
        "robot_id": "agv_1",
        "start_location": "P1",
        "goal_location": "P5"
    }),
    json.dumps({
        "task_id": "task_002",
        "robot_id": "agv_2",
        "start_location": "P3",
        "goal_location": "P8"
    })
]

# Push as JSON array of JSON strings
r.lpush("mapf_tasks", json.dumps(tasks))
```

### Message Format for mapf_replace_destinations

The format follows the NGSI-LD TaskRequest structure used in FIWARE:

```python
task_request = {
    "id": "urn:ngsi-ld:TaskRequest:redirect_001",
    "type": "TaskRequest",
    "taskType": "ReplaceDestination",
    "taskParams": [
        {
            "robot_id": "agv_1",
            "goal_location": "P10"
        }
    ]
}
r.lpush("mapf_replace_destinations", json.dumps(task_request))
```

### Reading Task Status from Redis

```python
# Simple status
status = r.get("task_001")  # Returns: b"COMPLETED"

# Verbose status
status_v = r.get("task_001_v")  # Returns: b"COMPLETED, completed"

# Multiple tasks
statuses = r.mget(["task_001", "task_002"])
```

---

## Error Handling

### HTTP API Errors

| HTTP Code | Meaning | Common Causes |
|-----------|---------|---------------|
| 200 | Success | Request accepted |
| 500 | Server Error | Redis connection failed |

### Task-Level Errors

Check verbose status for error details:

```python
response = requests.get(
    "http://localhost:8000/mapf/monitor_task_verbose?task_id=task_001"
)
status = response.json()["tasks"][0]["status"]

if "FAILED" in status:
    # Parse error details from verbose status
    # Format: "FAILED, <error details>"
    print(f"Task failed: {status}")
```

### Common Failure Reasons

| Error | Description |
|-------|-------------|
| `Could not connect to solver` | MAPF solver service unavailable |
| `Invalid location` | Start or goal location not in map |
| `Solver failed to find a solution` | No valid path exists |
| `Duplicate robot_id` | Same robot assigned multiple tasks |
| `All tasks have conflicting destinations` | Multiple robots targeting same location |

---

## Integration Examples

### Python Client

```python
import requests
from typing import List, Dict
import time

class MAPFClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    def send_tasks(self, tasks: List[Dict]) -> Dict:
        """Submit movement tasks."""
        response = requests.post(
            f"{self.base_url}/mapf/send_task",
            json={"tasks": tasks}
        )
        response.raise_for_status()
        return response.json()

    def get_status(self, task_ids: List[str]) -> Dict:
        """Get status of tasks."""
        params = "&".join([f"task_id={tid}" for tid in task_ids])
        response = requests.get(f"{self.base_url}/mapf/monitor_task?{params}")
        return response.json()

    def replace_destination(self, robot_id: str, new_goal: str, task_id: str = None) -> Dict:
        """Redirect a robot."""
        payload = {
            "destinations": [{
                "robot_id": robot_id,
                "goal_location": new_goal,
                "task_id": task_id
            }]
        }
        response = requests.post(
            f"{self.base_url}/mapf/replace_destination",
            json=payload
        )
        return response.json()

    def wait_for_completion(self, task_ids: List[str], timeout: int = 300) -> bool:
        """Wait for all tasks to complete."""
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_status(task_ids)
            all_done = all(
                t["status"] in ["COMPLETED", "FAILED", "missing"]
                for t in status["tasks"]
            )
            if all_done:
                return True
            time.sleep(1.0)
        return False


# Usage
client = MAPFClient("http://localhost:8000")

# Send tasks
result = client.send_tasks([
    {"task_id": "t1", "robot_id": "agv_1", "start_location": "P1", "goal_location": "P5"},
    {"task_id": "t2", "robot_id": "agv_2", "start_location": "P3", "goal_location": "P8"}
])
print(f"Submitted: {result}")

# Wait for completion
task_ids = ["t1", "t2"]
completed = client.wait_for_completion(task_ids, timeout=120)
print(f"All completed: {completed}")

# Check final status
final_status = client.get_status(task_ids)
print(f"Final status: {final_status}")
```

### cURL Examples

**Send Tasks:**
```bash
curl -X POST "http://localhost:8000/mapf/send_task" \
  -H "Content-Type: application/json" \
  -d '{
    "tasks": [
      {
        "task_id": "task_001",
        "robot_id": "agv_1",
        "start_location": "P1",
        "goal_location": "P5"
      },
      {
        "task_id": "task_002",
        "robot_id": "agv_2",
        "start_location": "P3",
        "goal_location": "P8"
      }
    ]
  }'
```

**Monitor Tasks:**
```bash
curl -X GET "http://localhost:8000/mapf/monitor_task?task_id=task_001&task_id=task_002"
```

**Replace Destination:**
```bash
curl -X POST "http://localhost:8000/mapf/replace_destination" \
  -H "Content-Type: application/json" \
  -d '{
    "destinations": [
      {
        "robot_id": "agv_1",
        "goal_location": "P10",
        "task_id": "task_001"
      }
    ]
  }'
```

---

## Environment Configuration

The Movement Request Server uses these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `MOVEMENT_REQUEST_SERVER_PORT` | HTTP server port | - |
| `REDIS_HOST` | Redis server hostname | - |
| `REDIS_PORT` | Redis server port | - |

The ADG Executor uses these command-line arguments:

| Argument | Description | Default |
|----------|-------------|---------|
| `--redis_host` | Redis server hostname | `localhost` |
| `--redis_port` | Redis server port | `6379` |
| `--solver_url` | MAPF solver service URL | `http://localhost:8888` |
| `--agent` | Agent type (`shmd` or `vda`) | Required |
| `--context_broker_url` | FIWARE Context Broker URL | `http://scorpio:9090` |
| `--map_name` | Map entity name | `building` |

---

## Related Files

| File | Description |
|------|-------------|
| `docker_modules/movement_request_server/app/main.py` | HTTP API server |
| `docker_modules/movement_request_server/app/models.py` | Request/response models |
| `mapf_execution/adg_executor/main.py` | Main executor entry point |
| `mapf_execution/adg/executor.py` | Core Executor class |
| `mapf_execution/adg/models/` | Internal data models |
