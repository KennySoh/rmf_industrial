import time
import requests
import json
import queue
from datetime import datetime
import threading
from collections import deque

from fiware_api.context_broker.scorpio import ScorpioAPI, ScorpioEventSubscriber

from rmf2_agv.CommandMessage import CommandMessage
from rmf2_agv.CommandMessage import Type as CommandMessageType

from rmf2_agv.CommandStatusMessage import CommandStatusMessage, PathItem
from rmf2_agv.CommandStatusMessage import Type as CommandStatusMessageType

from rmf2_agv.StateMessage import Type as StateMessageType
from rmf2_agv.StateMessage import StateMessage

from rmf2_building.Map import Map

from fiware_api.utils import (
    printRed,
    printGreen,
    printYellow,
    printPurple,
    printCyan,
    printLightGray,
)


# Query the Context Broker to get the Map.
def load_fiware_map(cb_endpoint: str, map_id) -> Map:
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


# Merges a new command update with an existing master copy
def merge_command(
    robot_id: str, original_command: CommandMessage, updated_command: CommandMessage
) -> CommandMessage:
    if original_command is None:
        printYellow(robot_id + " : Original command is None")
        return updated_command

    if updated_command is None:
        printYellow(robot_id + " : Updated command is None")
        return original_command
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
        (merged_waypoints[k]) for k in sorted(merged_waypoints, key=lambda i: int(i))
    ]

    printGreen(
        "Order "
        + original_command.commandId
        + " has been updated. Latest Update ID: "
        + str(original_command.commandUpdateId + 1)
    )

    return CommandMessage(
        type=str(CommandMessageType.CommandMessage.value),
        command=original_command.command,
        commandId=original_command.commandId,
        commandTime=updated_command.commandTime,
        commandUpdateId=original_command.commandUpdateId + 1,
        waypoints=sorted_waypoints,
    )


# Function that Returns Path Status based on command and state messages
def updated_command_status(command: CommandMessage, agv_state: StateMessage):
    updated_path = []
    if len(command.waypoints) == 0:
        return updated_path

    # Log the comparison values for debugging (helps diagnose fake completion issues)
    state_order_id = getattr(agv_state, 'orderId', 'N/A')
    printLightGray(
        "[updated_command_status] Comparing state vs command:\n"
        + "  State orderId: " + str(state_order_id) + "\n"
        + "  State lastNodeSequenceId: " + str(agv_state.pose.lastNodeSequenceId) + "\n"
        + "  State waypoints count: " + str(len(agv_state.waypoints)) + "\n"
        + "  Command commandId: " + str(command.commandId) + "\n"
        + "  Command waypoints count: " + str(len(command.waypoints))
    )

    if len(agv_state.waypoints) == 0:
        # No more current paths in VDA5050 state
        printLightGray("[updated_command_status] VDA5050 has no pending waypoints - checking completion by sequenceId")
        for command_waypoint in command.waypoints:
            path_item = PathItem(waypoint=command_waypoint, completed=False)
            # If the current waypoint is released and has been traversed by the AGV, mark as complete
            if (
                command_waypoint.released
                and agv_state.pose.lastNodeSequenceId >= command_waypoint.sequenceId
            ):
                path_item.completed = True
                # Verbose completion logging commented out to reduce log spam
                # printLightGray(
                #     "  [COMPLETED] Waypoint " + str(command_waypoint.nodeId)
                #     + " (seq=" + str(command_waypoint.sequenceId) + ")"
                #     + " because lastNodeSequenceId(" + str(agv_state.pose.lastNodeSequenceId)
                #     + ") >= sequenceId(" + str(command_waypoint.sequenceId) + ")"
                # )
            updated_path.append(path_item)
    else:
        # VDA5050 still has pending waypoints
        next_state_path = agv_state.waypoints[0]
        printLightGray(
            "[updated_command_status] VDA5050 has " + str(len(agv_state.waypoints))
            + " pending waypoints, next is seq=" + str(next_state_path.sequenceId)
        )
        for command_waypoint in command.waypoints:
            path_item = PathItem(waypoint=command_waypoint, completed=False)

            # If the command waypoint sequence is before the next VDA5050 waypoint
            if command_waypoint.sequenceId < next_state_path.sequenceId:
                # If the current waypoint is released and has been traversed by the AGV, mark as complete
                if (
                    command_waypoint.released
                    and agv_state.pose.lastNodeSequenceId >= command_waypoint.sequenceId
                ):
                    path_item.completed = True
                    # Verbose completion logging commented out to reduce log spam
                    # printLightGray(
                    #     "  [COMPLETED] Waypoint " + str(command_waypoint.nodeId)
                    #     + " (seq=" + str(command_waypoint.sequenceId) + ")"
                    # )

            updated_path.append(path_item)
    return updated_path


class FiwareAgentInterface:
    def __init__(
        self,
        agent_id: str,
        cb_endpoint: str,
        mqtt_host: str,
        mqtt_port: int,
        command_status_callback=None,
    ):
        self.agent_name = agent_id
        self.manufacturer = self.agent_name.split("_")[0]
        self.robot_id = self.agent_name.removeprefix(self.manufacturer + "_")
        self.ld_link = 'https://smart-data-models.github.io/dataModel.AutonomousMobileRobot/StateMessage/examples/example-normalized.jsonld; rel="https://www.w3.org/ns/json-ld#context"; type="application/ld+json"'
        self.context_broker = ScorpioAPI(cb_endpoint)
        self.command = None
        self.command_status = None
        self.command_status_callback = command_status_callback
        self.state_queue = queue.Queue()
        self.queue_thread_running = False
        self.fiware_setup(mqtt_host, mqtt_port)
        self.executing = False
        self.queued_commands = []

    def queue_state(self, client, userdata, msg):
        entity_string = str(msg.payload.decode("utf-8", "ignore"))
        json_content = json.loads(entity_string)
        robot_uuid = ""
        manufacturer = ""
        robot_id = ""
        for data_entry in json_content["body"]["data"]:
            manufacturer = data_entry["id"].split(":")[-2]
            robot_id = data_entry["id"].split(":")[-1]
            robot_uuid = manufacturer + "_" + robot_id
        if robot_uuid == self.agent_name:
            self.state_queue.put(json_content)
            if not self.queue_thread_running:
                # printYellow(self.agent_name + ": Start Thread")
                self.queue_thread = threading.Thread(
                    target=lambda: self.process_states()
                ).start()
                self.queue_thread_running = True
        # else:
        #     printRed("Wrong Message:\n Agent Name " + self.agent_name + "\n Message Name: " + robot_uuid + "\n\n")

    def process_states(self):
        while not self.state_queue.empty():
            item = self.state_queue.get()
            self.process_state(json_msg=item)
            self.state_queue.task_done()
        # printGreen(self.agent_name + ": Thread Done")
        self.queue_thread_running = False

    # State Subscriber Callback
    def process_state(self, client, userdata, msg):
        json_msg = json.loads(str(msg.payload.decode("utf-8", "ignore")))
        # def process_state(self, json_msg: json):
        # state_msg = StateMessage.from_subscriber_json(json_msg)

        # Add in an additional field to represent the robot's unique UUID
        robot_uuid = ""
        manufacturer = ""
        robot_id = ""
        for data_entry in json_msg["body"]["data"]:
            manufacturer = data_entry["id"].split(":")[-2]
            robot_id = data_entry["id"].split(":")[-1]
            robot_uuid = manufacturer + "_" + robot_id

        if robot_id != self.robot_id:
            # printRed("self.robot_id: " + self.robot_id + "\nrobot_id: " + robot_id)
            return

        if self.command is None:
            print("Command Is None")
            return

        # Parse state message first to get orderId for validation
        agv_state = StateMessage.from_subscriber_json(json_msg)

        # CRITICAL FIX: Validate orderId matches current command
        # This prevents fake completions when VDA5050 state is from a different command
        state_order_id = getattr(agv_state, 'orderId', None) or ""
        if state_order_id and state_order_id != self.command.commandId:
            printRed(
                "[" + self.agent_name + "] ORDER ID MISMATCH - Ignoring stale state update!\n"
                + "  VDA5050 state orderId: " + str(state_order_id) + "\n"
                + "  ADG command commandId: " + str(self.command.commandId) + "\n"
                + "  This state is from a different/previous command. Skipping to prevent fake completion."
            )
            return

        self.command_status = CommandStatusMessage(
            type=str(CommandStatusMessageType.CommandStatusMessage.value),
            robotId=robot_uuid,
            commandId=self.command.commandId,
            commandStatusTime=str(datetime.now().isoformat()),
            commandUpdateId=self.command.commandUpdateId,
            completed=True,
            path=updated_command_status(
                command=self.command,
                agv_state=agv_state,  # Reuse parsed state instead of parsing again
            ),
        )

        for path_item in self.command_status.path:
            if not path_item.completed:
                self.command_status.completed = False
                break

        self.command_status_callback(self.command_status)
        if self.command_status.completed and self.executing:
            self.print_report()
            self.executing = False

            if len(self.queued_commands) != 0:
                printCyan("Executing queued commands")
                self.set_command(deque(self.queued_commands).popleft(), from_queue=True)
                self.set_command(self.queued_commands.pop(0), from_queue=True)

    def fiware_setup(self, subscriber_mqtt_host, subscriber_mqtt_port):
        self.agv_state_event_subscriber = ScorpioEventSubscriber(
            self.context_broker.endpoint,
            id="agv_states_" + self.agent_name,
            host=subscriber_mqtt_host,
            port=subscriber_mqtt_port,
            topic="agv_states_" + self.agent_name,
            message_type=str(StateMessageType.StateMessage.value),
            ld_link=self.ld_link,
            # on_message_callback=self.queue_state,
            on_message_callback=self.process_state,
            qos=0,
        )
        self.agv_state_event_subscriber.run()

    def print_report(self):
        state_string = "========================================== AGV State Report ==========================================\n"
        state_string += "AGV ID: " + self.command_status.robotId + "\n"
        state_string += "Command ID: " + self.command_status.commandId + "\n"
        state_string += "Order Completed: " + str(self.command_status.completed) + "\n"

        for path_item in self.command_status.path:
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

    def set_command(self, command: CommandMessage, from_queue: bool = False):
        if len(self.queued_commands) != 0 and not from_queue:
            printRed(
                "["
                + self.agent_name
                + "] WARNING: There are still commands queued up, storing as part of the queue "
            )
            self.queued_commands.append(command)
            return
        if self.command is not None:
            if command.commandId != self.command.commandId:
                printYellow(
                    "["
                    + self.agent_name
                    + "] "
                    + "New Command with ID "
                    + command.commandId
                    + " received. Check if existing command with ID "
                    + self.command.commandId
                    + " is completed..."
                )
                if (
                    self.command
                    and self.command.commandId == self.command_status.commandId
                    and self.command_status.completed
                ):
                    self.command_completed()
                    # self.command = None
                else:
                    printRed(
                        "["
                        + self.agent_name
                        + "] "
                        + "Error: command with commandId "
                        + self.command.commandId
                        + " not done yet, cannot replace with command with commandId "
                        + command.commandId
                        + " storing it in queue"
                    )
                    self.queued_commands.append(command)
        merged_command = merge_command(
            robot_id=self.agent_name,
            original_command=self.command,
            updated_command=command,
        )
        self.context_broker.send_entity_message(
            CommandMessage.to_json(
                "urn:ngsi-ld:CommandMessage:" + self.manufacturer + ":" + self.robot_id,
                merged_command,
            ),
            {"Content-Type": "application/json", "Link": self.ld_link},
        )
        self.command = merged_command
        self.executing = True
        # TODO retry until acknowledgement or terminate ADG execution
        return True

    def command_completed(self):
        printRed(
            "["
            + self.agent_name
            + "] "
            + "Removing Command for "
            + self.command.commandId
            + " executed by "
            + self.agent_name
        )
        self.command_status = None
        self.command = None
