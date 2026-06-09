import argparse
import json
import logging
import threading
import time


from pydantic import TypeAdapter
from datetime import datetime,timedelta

from typing import List

import redis
import requests

from adg.enums import TaskState
from adg.executor import Executor
from adg.models.mapf_execution_models import (
    MapfSendTaskPostRequestTaskItem,
    ReplaceDestination,
)
from mapf_solve.mapf_solve_request import MAPFServiceAdapter
from agents.fiware_agent.agent_http_order import HTTPOrderAgent
from agents.shared_memory_dict_agent.agent_shmd import SharedMemoryAgent

# Fiware Components
from fiware_api.context_broker.scorpio import ScorpioAPI
from rmf2_building.Map import Map
from rmf2_tasks.TaskRequest import TaskRequest
from rmf2_tasks.TaskStatus import TaskStatus, Status

# Redis queue names that the movement_request_server pushes to.
MAPF_TASK_QUEUE_NAME = "mapf_tasks"
MAPF_REPLACE_DESTINATIONS_QUEUE_NAME = "mapf_replace_destinations"


# Dequeue messages and generate and execute ADG

# Query the Context Broker to get the Map.
def load_fiware_map(cb_endpoint: str, map_id)->Map:
    print("Get Map from Context Broker", flush=True)
    status_code = 0
    response = ""
    while status_code > 299 or status_code < 200:
        time.sleep(2.0)
        try:
            response = requests.get(
                cb_endpoint + "/ngsi-ld/v1/entities/urn:ngsi-ld:Map:" + map_id,
                headers={
                    "Accept": "application/ld+json",
                    "Content-Type": "application/ld+json",
                },
            )
            status_code = response.status_code
            if status_code == 404:
                print(
                    "\033[91m {}\033[00m".format("map " + map_id + " does not exist"),
                    flush=True,
                )
        except requests.exceptions.ConnectionError as e:
            print(
                "\033[91m {}\033[00m".format(e),
                flush=True,
            )
            pass
        except requests.exceptions.HTTPError as e:
            print(
                "\033[91m {}\033[00m".format(e),
                flush=True,
            )
            pass
        except requests.exceptions.Timeout as e:
            print(
                "\033[91m {}\033[00m".format(e),
                flush=True,
            )
            pass
            # Maybe set up for a retry, or continue in a retry loop
        except requests.exceptions.TooManyRedirects as e:
            print(
                "\033[91m {}\033[00m".format(e),
                flush=True,
            )
            pass
            # Tell the user their URL was bad and try a different one
        except requests.exceptions.RequestException as e:
            # catastrophic error. bail.
            print(
                "\033[91m {}\033[00m".format(e),
                flush=True,
            )
            raise SystemExit(e)
    print(
        "\033[92m {}\033[00m".format("Map " + map_id + " Loaded Successfully"),
        flush=True,
    )

    return Map.from_json(json.loads(response.text))
    

logger = logging.getLogger("main_adg_executor")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "[%(levelname)s] %(asctime)s:%(msecs)03d %(name)s: %(message)s", datefmt="%H:%M:%S"
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False

def create_agent_task_dict(items: List[MapfSendTaskPostRequestTaskItem]):
    mapf_items = {}

    for item in items:
        if item.robot_id in mapf_items:
            raise ValueError(f"Duplicate robot_id found: {item.robot_id}")
        mapf_items[item.robot_id] = item

    return mapf_items

def dequeue_messages(redis_client, queue_name, limit: int = 1000):
    """Retrieves messages from the queue, up to the limit.
    Blocks for up to 1 second if queue is empty.

    Args:
        queue_name (_type_): _description_
        limit (int, optional): _description_. Defaults to 1000.

    Returns:
        _type_: _description_
    """
    try:
        messages = []
        for _ in range(min(limit, redis_client.llen(queue_name))):
            message = redis_client.brpop(queue_name, timeout=1)[1]
            # brpop returns tuple of (key, element)
            if message:
                messages.append(message.decode("utf-8"))
        return messages
    except redis.RedisError as e:
        print(f"Redis error: {e}")
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--building", help="Path to building.yaml file.", default="building.yaml"
    )
    parser.add_argument(
        "--context_broker_url", help="url for context broker", default="http://scorpio:9090"
    )
    parser.add_argument(
        "--mock_complete_actions",
        help="Mock action completion without querying the robot control server",
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--solver_url",
        help="URL of MAPF solver service.",
        default="http://localhost:8888",
    )
    parser.add_argument(
        "--agent",
        required=True,
        help="Type of agent.",
        choices=["shmd", "vda"],
    )
    parser.add_argument(
        "--redis_host", help="URL of MAPF solver service.", default="localhost"
    )
    parser.add_argument(
        "--redis_port", help="URL of MAPF solver service.", default=6379
    )
    parser.add_argument(
        "--mqtt_host", help="MQTT Broker Host.", default="mosquitto"
    )
    parser.add_argument(
        "--mqtt_port", help="MQTT Broker Port.", default=1844
    )
    parser.add_argument(
        "--map_name", help="Map Name.", default="building"
    )
    args = parser.parse_args()

    # TODO args, update task statuses on exit
    pool = redis.ConnectionPool(
        host= args.redis_host,
        port= args.redis_port,
        health_check_interval=30,
        db=0)
    

    while True:
        time.sleep(1.0)
        try:
            r = redis.Redis(connection_pool=pool)
            r.ping()
            #Check If Redis Server Connected. Exception Thrown here if redis is not connected
            break
        except redis.exceptions.ConnectionError as e:
            print(e, flush=True)
            pass
    print('Connected to redis', flush=True)
    fiware_map = load_fiware_map(args.context_broker_url, args.map_name)
    vertices = dict()
    for node in fiware_map.nodes:
        vertices[node.nodeId] = [
            node.point2D.x,
            node.point2D.y,
        ]
    vertices["raw"] = fiware_map.raw

    mapf_solve = MAPFServiceAdapter(
        vertices, args.solver_url, args.map_name
    )

    def execute_mapf(mapf_items_list: List[MapfSendTaskPostRequestTaskItem], map : Map):
        """Initialises an Executor and Agents to perform the tasks.

        Args:
            mapf_items (List[MapfSendTaskPostRequestTaskItem]): _description_

        Returns:
            _type_: _description_
        """

        task_status_map = {}

        try:
            # Keyed by robot ID.
            mapf_items = create_agent_task_dict(mapf_items_list)
        except ValueError as e:
            print(e)
            for item in mapf_items_list:
                task_id = item.task_id
                task_state = TaskState.FAILED
                r.set(task_id, f"{task_state.name}")
                r.set(str(task_id) + "_v", f"{task_state.name}, {str(e)}")
            return None
        
        # Create a dictionary of the map nodes (no edges for npw)
        map_node_dict = {}
        for node in map.nodes:
            map_node_dict[node.nodeId] = node

        adg_agents = {}
        agent_args = {
            "pool": pool,
            "mock_complete_actions": True if args.mock_complete_actions else False,
            "mqtt_host" : args.mqtt_host,
            "mqtt_port" : args.mqtt_port,
            "context_broker_endpoint" : args.context_broker_url,
            "map" : map_node_dict
        }
        for agent_name in mapf_items.keys():
            if args.agent == "vda":
                adg_agents[agent_name] = HTTPOrderAgent(agent_name, agent_args)
            elif args.agent == "shmd":
                adg_agents[agent_name] = SharedMemoryAgent(
                    agent_name, "agent_name_task_id", agent_args
                )

        # Create persistent AMQP connection for status updates (reused across all callbacks)
        import amqp
        try:
            amqp_connection = amqp.Connection(host="rmf2_broker-rabbitmq-1:5672")
            amqp_channel = amqp_connection.channel()
            amqp_channel.queue_declare(queue="@RECEIVE@-event_mgr", durable=True, auto_delete=True)
            logger.info("AMQP connection established for TaskStatus updates")
        except Exception as e:
            logger.error(f"Failed to establish AMQP connection: {e}")
            amqp_connection = None
            amqp_channel = None

        # Function signature: Callable[[str, TaskState, str], None]
        def progress_callback(task_id: str, task_state: TaskState, message: str):
            r.set(task_id, f"{task_state.name}")
            r.set(str(task_id) + "_v", f"{task_state.name}, {message}")
            logger.info(f"-------- {task_id} reported {task_state.name} {message}\n")

            # Upload task status to fiware context broker
            if task_id not in task_status_map:
                print("Error: Requesting for task " + task_id + " which is not currently tracked.", flush=True)
            else:
                task_status_msg = task_status_map[task_id]
                timedelta_adapter = TypeAdapter(timedelta)
                time_delta = (datetime.now() - datetime.fromisoformat(task_status_msg.taskStart))
                task_status_msg.taskElapsedDuration = timedelta_adapter.dump_python(time_delta, mode="json")

                if task_state ==  TaskState.COMPLETED:
                    task_status_msg.status = Status.COMPLETED
                    task_status_msg.taskEnd = str(datetime.now().isoformat())
                elif task_state == TaskState.FAILED:
                    task_status_msg.status = Status.ERROR
                    task_status_msg.taskEnd = str(datetime.now().isoformat())
                elif task_state == TaskState.IN_PROGRESS:
                    task_status_msg.status = Status.IN_PROGRESS
                elif task_state == TaskState.QUEUED:
                    # Map QUEUED to IN_PROGRESS for FIWARE (no schema change needed)
                    task_status_msg.status = Status.IN_PROGRESS
                
                tokens = task_id.split(":")
                tokens[-1] = "TaskStatus"
                task_status_id = ':'.join(tokens)

                # Reuse persistent AMQP connection instead of creating new one
                if amqp_channel is not None:
                    try:
                        amqp_channel.basic_publish(
                            msg=amqp.Message(body=json.dumps(TaskStatus.to_json(task_status_id,task_status_msg))),
                            exchange="@RECEIVE@",
                            routing_key=""
                        )
                    except Exception as e:
                        logger.error(f"Failed to publish TaskStatus for {task_id}: {e}")
                else:
                    logger.warning(f"AMQP channel not available, skipping TaskStatus publish for {task_id}")

        executor = Executor(adg_agents, mapf_solve, progress_callback)
        executor.begin_execution(mapf_items)

        def dequeue_replace_destinations(executor):
            while executor.state == Executor.State.RUNNING:  # TODO: While execution context alive
                # Check the queue at intervals.
                time.sleep(2.5)
                messages = dequeue_messages(r, MAPF_REPLACE_DESTINATIONS_QUEUE_NAME)
                if not messages:
                    continue

                # TODO: validation of ReplaceDestination messages.
                replace_dict = {}
                for msg in messages:

                    task_request = TaskRequest.from_json(json.loads(msg))
                    
                    for json_params in task_request.taskParams:
                        if "goal_location" in json_params and "robot_id" in json_params:

                            rd = ReplaceDestination(
                                task_id=task_request.id,
                                robot_id=json_params["robot_id"],
                                goal_location=json_params["goal_location"]
                            )
                            replace_dict[rd.robot_id] = rd
                        #TODO: Report cancellation of task if replaced in the last 0.5s.

                    task_status_map[task_request.id] = TaskStatus(
                        type="TaskStatus",
                        id=task_request.id,
                        taskType=task_request.taskType,
                        taskStart=str(datetime.now().isoformat()),
                        taskEnd="",
                        taskElapsedDuration="PT0S",
                        status=Status.IN_PROGRESS
                    )
                logger.info("Batched ReplaceDestinations:")
                replace_destinations = list(replace_dict.values())
                for v in replace_dict.values():
                    logger.info(f"-- {str(v)}")

                executor.replace_destinations(replace_destinations)

        t = threading.Thread(target=dequeue_replace_destinations, args=[executor])
        t.start()

        return executor

    current_executor = None
    logger.info("Waiting for messages..")
    while True:
        try:
            messages = dequeue_messages(r, MAPF_TASK_QUEUE_NAME)
            if not messages:
                continue

            # Define behaviour for processing the message queue.
            # Each message is a list of destinations for robots.
            # TODO: batch and validate before sending for execution.

            mapf_items = []
            # Holds the requested items. Represents a MAPF problem to be solved.

            # Currently, this ignores earlier messages, and only handles the most recent one.
            for msg in messages:

                j = json.loads(msg)
                print("Received new mapf task request:", j)
                mapf_items = [
                    MapfSendTaskPostRequestTaskItem(**json.loads(item)) for item in j
                ]

            if current_executor:
                current_executor.interrupt()
            current_executor = execute_mapf(mapf_items, fiware_map)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from queue: {e}")
            logger.exception(e)
            # Continue to next message
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
            if current_executor:
                current_executor.interrupt()
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            logger.exception(e)
            # Continue to next message to keep system running


if __name__ == "__main__":
    main()
