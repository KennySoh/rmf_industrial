from flask import Flask, request, make_response
from typing import List
import json
import sys
import threading
from datetime import datetime
import queue
import time
from fiware_api.context_broker.scorpio import ScorpioAPI, ScorpioEventSubscriber
from fiware_api.utils import (
    printRed,
    printGreen,
    printYellow,
    printPurple,
    printCyan,
    printLightGray,
)

from rmf2_agv.CommandMessage import CommandMessage
from rmf2_agv.CommandMessage import Type as CommandMessageType
from rmf2_agv.CommonClasses import Waypoint, Orientation2D, Point2D
from rmf2_agv.StateMessage import Type as StateMessageType
from rmf2_agv.StateMessage import (
    StateMessage,
    Destination,
    Pose,
    Velocity,
    Battery,
)

from rmf2_agv.CommandStatusMessage import CommandStatusMessage, PathItem
from rmf2_agv.CommandStatusMessage import Type as CommandStatusMessageType

from rmf2_building.Map import Map, Node


# Integration Class for MAPF to Context Broker
class MAPFFiware:
    def __init__(self):
        self.commands = {}
        self.map = {}
        self.context_broker = None
        self.namespace = "ngsi-ld:default-context/"

    def on_agv_message(self, client, userdata, msg):
        json_msg = json.loads(str(msg.payload.decode("utf-8", "ignore")))

        # Add in an additional field to represent the robot's unique UUID
        robot_uuid = ""
        manufacturer = ""
        robot_id = ""
        for data_entry in json_msg["body"]["data"]:
            manufacturer = data_entry["id"].split(":")[-2]
            robot_id = data_entry["id"].split(":")[-1]
            robot_uuid = manufacturer + "_" + robot_id

        if robot_uuid not in self.commands:
            printRed("No Command Assigned to robot " + robot_uuid)
            return None

        command_status = CommandStatusMessage(
            type=str(CommandStatusMessageType.CommandStatusMessage.value),
            robotId=robot_uuid,
            commandId=self.commands[robot_uuid].commandId,
            commandStatusTime=str(datetime.now().isoformat()),
            commandUpdateId=self.commands[robot_uuid].commandUpdateId,
            completed=True,
            path=self.updated_command_status(
                command=self.commands[robot_uuid],
                # might have bug
                agv_state=StateMessage.from_subscriber_json(json_msg),
            ),
        )

        for path_item in command_status.path:
            if not path_item.completed:
                command_status.completed = False
                break

        state_string = "========================================== AGV State Report ==========================================\n"
        state_string += "AGV ID: " + command_status.robotId + "\n"
        state_string += "Command ID: " + command_status.commandId + "\n"
        state_string += "Order Completed: " + str(command_status.completed) + "\n"

        for path_item in command_status.path:
            path_node_string = ""
            path_node_string += "\t Node Id: " + path_item.waypoint.nodeId + "\n"
            path_node_string += (
                "\t Released: " + str(path_item.waypoint.released) + "\n"
            )
            path_node_string += (
                "\t Sequence: " + str(path_item.waypoint.sequenceId) + "\n"
            )
            path_node_string += "\t Completed: " + str(path_item.completed) + "\n\n"

            state_string += path_node_string

        printYellow(state_string)

        printYellow("Push AGV state to MAPF...")
        # print(json.dumps(updated_agv_state, indent=2))
        if command_status.completed:
            printGreen("Command Is Completed. Remove from Context Broker")
            # del self.robots[uuid]

            # TODO(Glenn) : Remove Command Message from CB
            #
            #

        self.context_broker.send_entity_message(
            CommandStatusMessage.to_json(
                "urn:ngsi-ld:CommandStatusMessage:" + manufacturer + ":" + robot_id,
                command_status,
            ),
            {"Content-Type": "application/json", "Link": self.ld_link},
        )

        # Push AGV State Message to Queue

    def updated_command_status(self, command: CommandMessage, agv_state: StateMessage):
        updated_path = []
        if len(command.waypoints) == 0:
            return updated_path
        # TOCHECK: Do I still need to sort?
        if len(agv_state.waypoints) == 0:
            # No more current paths, path is completed.
            for command_waypoint in command.waypoints:
                path_item = PathItem(waypoint=command_waypoint, completed=False)
                # If the current waypoint is released in and has been traversed by the AGV, mark as complete
                if (
                    command_waypoint.released
                    and agv_state.pose.lastNodeSequenceId >= command_waypoint.sequenceId
                ):
                    path_item.completed = True
                updated_path.append(path_item)
        else:
            # TO CHECK: Is there a need to sort State Waypoints
            next_state_path = agv_state.waypoints[0]
            for command_waypoint in command.waypoints:
                path_item = PathItem(waypoint=command_waypoint, completed=False)

                # If the command waypoint sequence is before the supposed next waypoint the AGV is traversing,
                if command_waypoint.sequenceId < next_state_path.sequenceId:
                    # If the current waypoint is released in and has been traversed by the AGV, mark as complete
                    if (
                        command_waypoint.released
                        and agv_state.pose.lastNodeSequenceId
                        >= command_waypoint.sequenceId
                    ):
                        path_item.completed = True

                updated_path.append(path_item)
        return updated_path

    def on_command_message(self, client, userdata, msg):
        json_msg = json.loads(str(msg.payload.decode("utf-8", "ignore")))

        # Add in an additional field to represent the robot's unique UUID
        robot_uuid = ""
        for data_entry in json_msg["body"]["data"]:
            manufacturer = data_entry["id"].split(":")[-2]
            robot_id = data_entry["id"].split(":")[-1]
            robot_uuid = manufacturer + "_" + robot_id

        new_command_message = CommandMessage.from_subscriber_json(
            json_msg, "ngsi-ld:default-context/"
        )

        if (
            robot_uuid in self.commands
            and self.commands[robot_uuid].commandId == new_command_message.commandId
        ):
            self.commands[robot_uuid] = self.merge_command(
                self.commands[robot_uuid], new_command_message
            )

        else:
            self.commands[robot_uuid] = new_command_message

        printGreen("Command Update Registered.")

    def fiware_setup(
        self,
        subscriber_mqtt_host,
        subscriber_mqtt_port,
        context_broker,
        ld_link,
        agv_update_topic,
        command_update_topic,
    ):
        self.ld_link = ld_link
        self.context_broker = context_broker

        # Set up Message Queue to be Processed
        self.command_update_queue = queue.Queue()

        self.command_event_subscriber = ScorpioEventSubscriber(
            self.context_broker.endpoint,
            id="command_fiware",
            host=subscriber_mqtt_host,
            port=subscriber_mqtt_port,
            topic=command_update_topic,
            message_type=str(CommandMessageType.CommandMessage.value),
            ld_link=self.ld_link,
            on_message_callback=self.on_command_message,
        )

        self.agv_state_event_subscriber = ScorpioEventSubscriber(
            self.context_broker.endpoint,
            id="state_fiware",
            host=subscriber_mqtt_host,
            port=subscriber_mqtt_port,
            topic=agv_update_topic,
            message_type=str(StateMessageType.StateMessage.value),
            ld_link=self.ld_link,
            on_message_callback=self.on_agv_message,
        )
        self.agv_state_event_subscriber.run()
        self.command_event_subscriber.run()

    # Gets Map from Context Broker and stores it locally
    def set_map(self, map_id: str):
        status_code = 0
        while status_code > 299 or status_code < 200:
            if self.context_broker is None:
                printRed(
                    "Context Broker Connection not established yet, cannot set map."
                )
                continue
            # if response.status_code == 404:
            response = self.context_broker.get_entity(
                "urn:ngsi-ld:Map:" + map_id,
                {},
            )
            printRed("map " + map_id + " does not exist")
            status_code = response.status_code
            time.sleep(0.5)
        printGreen("Map Loaded Successfully")
        loaded_map = Map.from_json(json.loads(response.text))

        for node in loaded_map.nodes:
            self.map[node.nodeId] = node

    # Merges a new command update with an existing master copy
    def merge_command(
        self, original_command: CommandMessage, updated_command: CommandMessage
    ) -> CommandMessage:
        if (
            original_command.command != updated_command.command
            or original_command.commandId != updated_command.commandId
        ):
            printRed(
                "Error, Merging command not possible. The following doesnt match: \n"
                + "Original: \n\t Command: "
                + original_command.command
                + "\n\t ID: "
                + original_command.commandId
                + "\nUpdated: \n\t Command: "
                + updated_command.command
                + "\n\t ID: "
                + updated_command.commandId
            )

        merged_waypoints = {}
        original_waypoints = original_command.waypoints
        updated_waypoints = updated_command.waypoints

        for original_node in original_waypoints:
            if original_node.released:
                merged_waypoints[original_node.sequenceId] = original_node

        # Check and append stuff from updated plan
        for updated_node in updated_waypoints:
            if updated_node.sequenceId not in merged_waypoints:
                merged_waypoints[updated_node.sequenceId] = updated_node

        sorted_waypoints = [
            (merged_waypoints[k])
            for k in sorted(merged_waypoints, key=lambda i: int(i))
        ]

        return CommandMessage(
            type=str(CommandMessageType.CommandMessage.value),
            command=original_command.command,
            commandId=original_command.commandId,
            commandTime=updated_command.commandTime,
            commandUpdateId=original_command.commandUpdateId + 1,
            waypoints=sorted_waypoints,
        )

def main():
    # Default Parameters if nothing is set.
    cb_endpoint = "http://localhost:9090"

    mqtt_server_host = "localhost"
    mqtt_server_port = 1929
    agv_update_topic = "agv_states"
    command_update_topic = "command"
    map_name = "RMF1"

    # Parse from Python Args
    if len(sys.argv) > 1:
        cb_endpoint = sys.argv[1]
    if len(sys.argv) > 2:
        mqtt_server_host = sys.argv[2]
    if len(sys.argv) > 3:
        mqtt_server_port = sys.argv[3]
    if len(sys.argv) > 4:
        map_name = sys.argv[4]

    print("Context Broker Endpoint: " + cb_endpoint)
    context_broker = ScorpioAPI(cb_endpoint)

    mapf_fiware = MAPFFiware()
    mapf_fiware.fiware_setup(
        subscriber_mqtt_host=mqtt_server_host,
        subscriber_mqtt_port=int(mqtt_server_port),
        context_broker=context_broker,
        ld_link='https://smart-data-models.github.io/dataModel.AutonomousMobileRobot/StateMessage/examples/example-normalized.jsonld; rel="https://www.w3.org/ns/json-ld#context"; type="application/ld+json"',
        agv_update_topic=agv_update_topic,
        command_update_topic=command_update_topic,
    )
    mapf_fiware.set_map(map_name)

    while True:
        time.sleep(0.01)

if __name__ == "__main__":
    main()
