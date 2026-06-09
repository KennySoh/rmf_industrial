from collections import defaultdict
import json
import logging
from threading import Thread
import threading
import time
from datetime import datetime
from typing import List

import requests

from adg.adg_agent import ActionState, ADGAgent, Activity
from adg.adg_execution import ActionWithCallback
from agents.fiware_agent.models import McUpdateOrderPostRequestItem, PathItem
from rmf2_agv.CommandMessage import CommandMessage
from rmf2_agv.CommandMessage import Type as CommandMessageType
from rmf2_agv.CommandStatusMessage import CommandStatusMessage
from rmf2_agv.CommonClasses import Waypoint, Orientation2D, Point2D

from fiware_api.utils import (
    printRed,
    printGreen,
    printYellow,
    printPurple,
    printCyan,
    printLightGray,
)

from agents.fiware_agent.utils import FiwareAgentInterface

class HTTPOrderAgent(ADGAgent):
    """
    - Calls the provided HTTP endpoint to create and update VDA5050 Orders.
    - Calls another endpoint to receive robot completion of nodes.
    - Reports status to Redis.
    """

    def __init__(self, agent_name, agent_kwargs):
        super().__init__(agent_name)

        self.logger = logging.getLogger(agent_name)
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "[%(levelname)s] %(asctime)s:%(msecs)03d %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            handler.close()
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        self.logger.propagate = False

        self.map = agent_kwargs["map"]

        # Set to True to auto-complete nodes.
        # Set to False to query server for actual statuses.
        self.mock_complete_actions = agent_kwargs.get("mock_complete_actions", False)

        # IDs
        self.robot_id = agent_name
        self.task_id = ""

        # Internal tracking variables
        self._completed_sequence_ids = set()
        self._order_created = False
        self._lock = threading.Lock()
        self.status_thread = None

        self._sequence_to_activity_mapping = defaultdict(list)

        self.fiware_interface = FiwareAgentInterface(
            agent_id = self.robot_id,
            cb_endpoint= agent_kwargs.get("context_broker_endpoint"),
            command_status_callback=self.process_status,
            mqtt_port=agent_kwargs.get("mqtt_port"),
            mqtt_host=agent_kwargs.get("mqtt_host"))

        with self._lock:
            self.current_order = None

    def report(self, state):
        """
        Debug information is written to two Redis keys:
        one for summary: agent_[task_id] : executing, completed, interrupted
        one for debug: agent_[task_id]_v : full progress

        Args:
            state (str): #TODO: Enum
        """
        if self.r:
            self.r.set("agent_" + self.task_id, state)
            # Verbose report
            s = ""
            sorted_keys = sorted(self._sequence_to_activity_mapping)
            for key in sorted_keys:
                value = [str(x) for x in self._sequence_to_activity_mapping[key]]
                s += "sequence " + str(key) + ":" + str(value) + " "
            self.r.set("agent_" + self.task_id + "_v", s)
        else:
            if not self.mock_complete_actions:
                self.logger.warning(
                    "Redis connection is not configured. Status in redis will not be available."
                )

    def process_status(self, command_status : CommandStatusMessage):
        if command_status.robotId != self.robot_id or command_status.commandId != self.task_id:
            printRed(" Command Status robotId: " + command_status.robotId + "\n robot_id: " + self.robot_id
             + "\n\n Command Status commandId: " + command_status.commandId + "\n task_id: " + self.task_id)
            return
        # TODO Consider better approach by tracking uncompleted activities instead of
        # iterating over all items in path.
        for node_item in command_status.path:
            if node_item.completed:
                new_sequence_id = node_item.waypoint.sequenceId

                for activity in self._sequence_to_activity_mapping[new_sequence_id]:
                    if activity.state != ActionState.COMPLETED:
                        activity.callback()
                        activity.state = ActionState.COMPLETED

    def initialise_order(self, task_id, start_location: str) -> McUpdateOrderPostRequestItem:
        """Returns an initialised order object with its start location as the first path item.

        Args:
            start_location (str): Start location of the first enqueued action.

        Returns:
            McUpdateOrderPostRequestItem: A new order with one item in the path.
        """
        new_order = McUpdateOrderPostRequestItem(
            robot_id=self.agent_name,
            task_id=task_id,
            order_id=task_id,
            path=[],
        )

        # sequence_id 0 is reserved for the movement to start location.
        # Create the path item for the movement to the start location
        path_item = PathItem(sequence_id=0, node=start_location, released=True)
        new_order.path.append(path_item)
        return new_order

    def enqueue(self, actions_with_callbacks: List[ActionWithCallback]):
        """
        Get this agent to enqueue actions for execution

        Args:
            actions_with_callbacks (ActionWithCallback): List of ActionWithCallback objects
        """

        with self._lock:
            new = []  # test
            new_path_item = False

            if not actions_with_callbacks:
                self.logger.error(
                    f"Error: enqueued() was called with no actions for {self.agent_name}"
                )
                return

            if self.current_order is None or self.current_order.task_id != actions_with_callbacks[0].action.task_id:
                # This is a new order and its first waypoint must be its start location.
                self.task_id = actions_with_callbacks[0].action.task_id
                self.current_order = self.initialise_order(
                    actions_with_callbacks[0].action.task_id,
                    actions_with_callbacks[0].action.location_start,
                )
                self._sequence_to_activity_mapping[0] = []
                new_path_item = True

            current_sequence_id = self.current_order.path[-1].sequence_id

            for action_w_cb in actions_with_callbacks:
                self.logger.info(f"Agent received enqueued item: {action_w_cb.action}")
                activity = Activity(
                    action_w_cb.action, action_w_cb.callback, ActionState.QUEUED
                )

                # Check if this activity is a wait.
                if activity.action.location_start == activity.action.location_end:
                    self._sequence_to_activity_mapping[current_sequence_id].append(
                        activity
                    )

                    # Complete the action if its parent is done
                    try:
                        if self._sequence_to_activity_mapping[current_sequence_id][-2].state == ActionState.COMPLETED:
                            activity.callback()
                            self.logger.debug(f"Instantly completing this wait action {str(activity.to_dict())} because its parent is completed.")
                            activity.state = ActionState.COMPLETED
                    except IndexError:
                        self.logger.error(f"Wait action: {activity.action} does not have a preceding action for this sequence id {current_sequence_id}")
                
                else:
                    # This activity is a move to a new location. Increment the sequence id.
                    current_sequence_id = current_sequence_id + 1
                    self._sequence_to_activity_mapping[current_sequence_id].append(activity)

                    path_item = PathItem(
                        sequence_id=current_sequence_id,
                        node=activity.action.location_end,
                        released=True,
                    )
                    self.current_order.path.append(path_item)
                    new_path_item = True

                    new.append(current_sequence_id)

            if (
                new_path_item
            ):  # If this is a new order, or a new path item needs to be added to the order (as opposed to a wait)
                submitted = self.submit_order_request(new)
                if not submitted:
                    self.logger.error(f"failed:Unable to submit order.")
                # TODO: Find a way to translate the report to fiware model
                # if submitted:
                #     self.report("executing")
                # else:
                #     self.report("failed:Unable to submit order.")
                #     self.logger.error(f"failed:Unable to submit order.")

            if not self._order_created:
                self._order_created = True

    # TODO: We should not be converting and reconverting data models. find a way to create CommandMessage from the start
    def convert_to_command_message(self, input_json : json)-> CommandMessage:
        output_command = CommandMessage(
            type=str(CommandMessageType.CommandMessage.value),
            command="",
            commandId=input_json["order_id"],
            commandTime=str(datetime.now().isoformat()),
            commandUpdateId=0,
            waypoints=[],
        )

        for path_point in input_json["path"]:
            if path_point["node"] not in self.map:
                printRed("Error: Point " + path_point["node"] + " is not in Map")
            output_command.waypoints.append(
                Waypoint(
                    nodeId=path_point["node"],
                    orientation2D=Orientation2D(theta=0.0),
                    point2D=Point2D(
                        x=self.map[path_point["node"]].point2D.x,
                        y=self.map[path_point["node"]].point2D.y,
                    ),
                    released=path_point["released"],
                    sequenceId=path_point["sequence_id"],
                )
            )
        

        return output_command

    def submit_order_request(self, new=None):
        """Submits a HTTP request to the VDA5050 master to create/update a movement order for this agent.
        Note: Currently, all steps are included and duplicates are removed.
        """
        # TODO: Convert this json to CommandMessage, and push to CB
        j = self.current_order.model_dump()
        self.fiware_interface.set_command(self.convert_to_command_message(j))
        # TODO retry until acknowledgement or terminate ADG execution
        return True

    # Differentiate between completion and errors.
    def shutdown(self, interrupted: bool = False):
        self.logger.info(f"{self.agent_name} shutting down..")
        # if interrupted:
        #     # TODO: Find a way to translate the report to fiware model
        #     self.report("interrupted")
        self.status_thread.join()
