# Movement Request Server

from __future__ import annotations
import logging
from typing import List

from fastapi import FastAPI, Query, HTTPException
import json
import redis
import os
from models import (
    MapfCancelTaskPostRequestItem,
    MapfPauseTaskPutRequestItem,
    MapfResumeTaskPutRequestItem,
    MapfSendTaskPostRequestItem,
    MapfReplaceDestinationPostRequestItem,
)

logger = logging.getLogger("uvicorn.error")
from time import sleep
logger.setLevel(logging.DEBUG)

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

MAPF_TASK_QUEUE_NAME = "mapf_tasks"
MAPF_REPLACE_DESTINATIONS_QUEUE_NAME = "mapf_replace_destinations"

app = FastAPI(
    title="RMF2",
    version="1.0.0",
    contact={},
    servers=[{"url": "http://0.0.0.0:" + os.getenv("MOVEMENT_REQUEST_SERVER_PORT")}],
)
pool = redis.ConnectionPool(
    host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), db=0
)

while True:
    sleep(1.0)
    try:
        r = redis.Redis(connection_pool=pool)
        r.ping()
        #Check If Redis Server Connected. Exception Thrown here if redis is not connected
        break
    except redis.exceptions.ConnectionError as e:
        print(e, flush=True)
        pass
print('Connected to redis "{}"'.format(os.getenv("REDIS_HOST")), flush=True)


@app.post("/mapf/cancel_task", response_model=None, tags=["MAPF"])
def cancel_task(body: List[MapfCancelTaskPostRequestItem] = None) -> None:
    """
    cancel task
    """
    raise NotImplementedError


def get_task_statuses(task_ids: List[str], verbose=False):
    try:
        if verbose:
            keys = [str(x) + "_v" for x in task_ids]
        else:
            keys = [str(x) for x in task_ids]
        statuses = r.mget(keys)

        for index, status in enumerate(statuses):
            if status is None:
                statuses[index] = "missing"
    except redis.ConnectionError:
        print("Connection to Redis server failed")
        statuses = ["connection failed"] * len(task_ids)

    return statuses


@app.get("/mapf/monitor_task", response_model=None)
def monitor_task(task_id: List[str] = Query(None)) -> None:
    """_summary_

    Args:
        task_id (List[str], optional): List of task IDs. Defaults to Query(None).

    Returns:
        _type_: _description_
    """
    result = {}
    result["tasks"] = []

    statuses = get_task_statuses(task_id)
    for index, key in enumerate(task_id):

        obj = {"task_id": key, "status": statuses[index]}
        result["tasks"].append(obj)

    return result


@app.get("/mapf/monitor_task_verbose", response_model=None)
def monitor_task_verbose(task_id: List[str] = Query(None)) -> None:
    """
    monitor task verbose
    """
    result = {}
    result["tasks"] = []
    statuses = get_task_statuses(task_id, verbose=True)
    for index, key in enumerate(task_id):

        obj = {"task_id": key, "status": statuses[index]}
        result["tasks"].append(obj)
    return result


@app.put("/mapf/pause_task", response_model=None, tags=["MAPF"])
def pause_task(body: List[MapfPauseTaskPutRequestItem] = None) -> None:
    """
    pause task
    """
    pass


@app.put("/mapf/resume_task", response_model=None, tags=["MAPF"])
def resume_task(body: List[MapfResumeTaskPutRequestItem] = None) -> None:
    """
    resume task
    """
    pass


@app.post("/mapf/send_task", response_model=None, tags=["MAPF"])
async def send_task(body: MapfSendTaskPostRequestItem):
    logging.warning(f"POST /mapf/send_task")
    items_strs = [item.model_dump_json() for item in body.tasks]
    redis_input = json.dumps(items_strs)
    logging.warning(f"{str(redis_input)}")
    try:
        r.lpush(MAPF_TASK_QUEUE_NAME, redis_input)

        response = {}
        response["tasks"] = []

        for item in body.tasks:
            response["tasks"].append({"task_id": item.task_id, "status": "submitted"})

        # TODO
        response["response"] = {}
        response["response"]["code"] = 0
        response["response"]["message"] = "submitted"

        return response
    except redis.ConnectionError as e:
        logging.error(f"{str(e)}")
        logging.error(f"Ensure Redis is started.")
        raise HTTPException(status_code=500, detail="Redis connection error: " + str(e))
    except Exception as e:
        # TODO exception handling
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mapf/replace_destination", response_model=None, tags=["MAPF"])
async def replace_destination(body: MapfReplaceDestinationPostRequestItem):
    logging.warning(f"POST /mapf/replace_destination")
    items_strs = [item.model_dump_json() for item in body.destinations]
    redis_input = json.dumps(items_strs)
    logging.warning(f"{str(redis_input)}")
    try:
        r.lpush(MAPF_REPLACE_DESTINATIONS_QUEUE_NAME, redis_input)
        # TODO replace with execution context id?

        response = {}
        response["destinations"] = []

        for item in body.destinations:
            response["destinations"].append(
                {"task_id": item.task_id, "status": "submitted"}
            )

        # TODO
        response["destinations"] = {}
        response["destinations"]["code"] = 0
        response["destinations"]["message"] = "submitted"

        return response
    except redis.ConnectionError as e:
        logging.error(f"{str(e)}")
        logging.error(f"Ensure Redis is started.")
        raise HTTPException(status_code=500, detail="Redis connection error: " + str(e))
    except Exception as e:
        # TODO exception handling
        raise HTTPException(status_code=500, detail=str(e))
