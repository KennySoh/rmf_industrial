import json
import logging
from pathlib import PosixPath
import time
import uuid
import yaml
import requests

from typing import List

from adg.models.mapf_execution_models import MapfSendTaskPostRequestTaskItem
from adg.models.plan_models import Plan
from mapf_solve.mapf_solver_interface import MAPFSolverABC, Obstacle

logger = logging.getLogger("MAPFServiceAdapter")
logger.setLevel(logging.INFO)
# Add console handler if not already present
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(levelname)s] %(asctime)s:%(msecs)03d %(name)s: %(message)s", datefmt="%H:%M:%S")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


class MAPFServiceAdapter(MAPFSolverABC):

    """
    TODO: Right now building.yaml files are picked up from the maps directory in the mapf solver service.
    Clean up the process for specifying the map.
    """    
    def __init__(self, map, solver_url, map_name):
        if type(map) is PosixPath:
            logger.debug("Using local building file..")
            self.map = self.load_rmf_map(map)
        else:
            self.map = map  # From fiware
        self.map_name = map_name
        logger.debug(f"map_name: {self.map_name}")
        self.solver_url = solver_url
        

    def generate_uuid(self):
        return str(uuid.uuid4())

    def load_rmf_map(self, map_filepath: str):
        vertices = dict()
        with open(map_filepath) as stream:
            try:
                self.parsed_map = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)

        if "warehouse" not in self.parsed_map["levels"]:
            return vertices
        if "vertices" not in self.parsed_map["levels"]["warehouse"]:
            return vertices

        for item in self.parsed_map["levels"]["warehouse"]["vertices"]:
            x = int(item[0])
            y = int(item[1])
            vertice_name = item[3]
            vertices[vertice_name] = [x, y]
        return vertices

    def request_mapf_plan(self, items: List[MapfSendTaskPostRequestTaskItem], input_obstacles: List[Obstacle] = None):
        logger.info(f"Requesting mapf plan for {len(items)} items")

        # Log summary of requested items
        item_summary = []
        for item in items[:5]:  # Log first 5 items
            item_summary.append(f"{item.robot_id}: {item.start_location} -> {item.goal_location}")
        if len(items) > 5:
            item_summary.append(f"... and {len(items) - 5} more items")
        logger.info(f"Item summary: {', '.join(item_summary)}")

        task_ids = {}  # Track task IDs.

        converted_output = {}
        tasks = []
        obstacles = []
        for item in items:
            robot_id = item.robot_id
            goal_location = self.map[item.goal_location]
            start_location = self.map[item.start_location]
            tasks.append(
                {
                    "agent_name": robot_id,
                    "start_position": {
                        "x": start_location[0],
                        "y": start_location[1],
                    },
                    "end_position": {
                        "x": goal_location[0],
                        "y": goal_location[1],
                    },
                }
            )

            if item.task_id:
                task_ids[item.robot_id] = item.task_id

        if input_obstacles:
            for input_obstacle in input_obstacles:
                location = self.map[input_obstacle.location]
                obstacles.append(
                    {
                        "coordinate": {
                            "x": location[0],
                            "y": location[1],
                        }
                    }
                )
            converted_output["obstacles"] = obstacles

        converted_output["tasks"] = tasks

        # Map content loaded from yaml. passing it wholesale to mapf service
        # converted_output["map"] = yaml.safe_load(self.map["raw"]["value"])

        # Currently hardcoded elements.
        converted_output["mapfile"] = self.map_name + ".yaml"

        converted_output["solver"] = "ECBS"
        converted_output["max_computation_time"] = 25000
        converted_output["max_timestep"] = 1000
        plans_instances = []

        try:
            print("send Mapf requests", flush=True)
            plans_json = self.send_mapf_request(converted_output)

            # Add task ID information to each step in solver result
            for p in plans_json:
                for step in p["steps"]:
                    step["task_id"] = task_ids[p["agent_name"]]
                plans_instances.append(Plan.model_validate(p))
            
        except (requests.exceptions.HTTPError, requests.exceptions.RequestException) as e:
            logger.error(f"Request failed: {e}")
            raise
        
        return plans_instances

    def send_mapf_request(self, json_string_input: str):
        """
        Args:
            json_string_input (str): _description_

        Returns:
            _type_:
        """
        max_retries = 3
        retry_count = 0

        # Log request details
        num_agents = len(json_string_input.get("tasks", []))
        request_json_str = json.dumps(json_string_input)
        request_size = len(request_json_str)

        logger.info(f"MAPF request: {num_agents} agents, payload size: {request_size} bytes")

        # Log agent summary
        if "tasks" in json_string_input:
            agent_summary = []
            for task in json_string_input["tasks"][:5]:  # Log first 5 tasks
                agent_summary.append(f"{task['agent_name']}: ({task['start_position']['x']},{task['start_position']['y']}) -> ({task['end_position']['x']},{task['end_position']['y']})")
            if num_agents > 5:
                agent_summary.append(f"... and {num_agents - 5} more agents")
            logger.info(f"Task summary: {', '.join(agent_summary)}")

        while retry_count < max_retries:
            try:
                response = requests.post(self.solver_url, json=json_string_input, timeout=10)
                status_code = response.status_code
                print(status_code, response.content, flush=True)

                # Success - return the result
                if 200 <= status_code < 300:
                    return response.json()

                # Client error (4xx) - invalid request, don't retry
                elif 400 <= status_code < 500:
                    error_msg = f"Bad request (status {status_code}): {response.content.decode('utf-8')}"
                    logger.error(error_msg)
                    logger.error(f"Request payload size: {request_size} bytes, num_agents: {num_agents}")
                    logger.error(f"Full request payload (first 2000 chars): {request_json_str[:2000]}")
                    raise requests.exceptions.HTTPError(error_msg)

                # Server error (5xx) - temporary issue, retry
                else:
                    logger.warning(f"Server error {status_code}, retrying... ({retry_count+1}/{max_retries})")
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(1.0)

            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error: {e}, retrying... ({retry_count+1}/{max_retries})")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(1.0)

            except requests.exceptions.Timeout as e:
                logger.warning(f"Timeout error: {e}, retrying... ({retry_count+1}/{max_retries})")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(1.0)

            except requests.exceptions.TooManyRedirects as e:
                # Don't retry - this is a configuration error
                logger.error(f"Too many redirects: {e}")
                raise requests.exceptions.RequestException(f"Too many redirects: {e}")

            except requests.exceptions.RequestException as e:
                # Catastrophic error - don't retry
                logger.error(f"Request exception: {e}")
                raise

        # Exhausted all retries
        raise requests.exceptions.RequestException(f"Max retries ({max_retries}) exceeded connecting to solver")
