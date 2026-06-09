#!/bin/bash
# Initialize 25 robots for warehouse_os_setup map
# Updated: 2026-05-28 - VERIFIED via MQTT with actual robot positions
# Map: warehouse_os_setup (34 cols × 21 rows, 175cm spacing)
# VDA5050 2.0: uagv/v2/Manufacturer/{serialNumber}
# Robot IDs: Manufacturer_1 through Manufacturer_25 (25 robots)
# Verification: Manufacturer_2-25 at exact positions (0.0cm), Manufacturer_1 moved to P421 (nearest navigable)

curl --location 'http://0.0.0.0:8009/mapf/send_task' \
--header 'Content-Type: application/json' \
--data '{
    "tasks": [
        {
            "task_id": "1",
            "robot_id": "Manufacturer_1",
            "start_location": "P421",
            "goal_location": "P421"
        },
        {
            "task_id": "2",
            "robot_id": "Manufacturer_2",
            "start_location": "P174",
            "goal_location": "P174"
        },
        {
            "task_id": "3",
            "robot_id": "Manufacturer_3",
            "start_location": "P176",
            "goal_location": "P176"
        },
        {
            "task_id": "4",
            "robot_id": "Manufacturer_4",
            "start_location": "P178",
            "goal_location": "P178"
        },
        {
            "task_id": "5",
            "robot_id": "Manufacturer_5",
            "start_location": "P180",
            "goal_location": "P180"
        },
        {
            "task_id": "6",
            "robot_id": "Manufacturer_6",
            "start_location": "P182",
            "goal_location": "P182"
        },
        {
            "task_id": "7",
            "robot_id": "Manufacturer_7",
            "start_location": "P184",
            "goal_location": "P184"
        },
        {
            "task_id": "8",
            "robot_id": "Manufacturer_8",
            "start_location": "P242",
            "goal_location": "P242"
        },
        {
            "task_id": "9",
            "robot_id": "Manufacturer_9",
            "start_location": "P244",
            "goal_location": "P244"
        },
        {
            "task_id": "10",
            "robot_id": "Manufacturer_10",
            "start_location": "P246",
            "goal_location": "P246"
        },
        {
            "task_id": "11",
            "robot_id": "Manufacturer_11",
            "start_location": "P248",
            "goal_location": "P248"
        },
        {
            "task_id": "12",
            "robot_id": "Manufacturer_12",
            "start_location": "P250",
            "goal_location": "P250"
        },
        {
            "task_id": "13",
            "robot_id": "Manufacturer_13",
            "start_location": "P252",
            "goal_location": "P252"
        },
        {
            "task_id": "14",
            "robot_id": "Manufacturer_14",
            "start_location": "P310",
            "goal_location": "P310"
        },
        {
            "task_id": "15",
            "robot_id": "Manufacturer_15",
            "start_location": "P312",
            "goal_location": "P312"
        },
        {
            "task_id": "16",
            "robot_id": "Manufacturer_16",
            "start_location": "P314",
            "goal_location": "P314"
        },
        {
            "task_id": "17",
            "robot_id": "Manufacturer_17",
            "start_location": "P316",
            "goal_location": "P316"
        },
        {
            "task_id": "18",
            "robot_id": "Manufacturer_18",
            "start_location": "P318",
            "goal_location": "P318"
        },
        {
            "task_id": "19",
            "robot_id": "Manufacturer_19",
            "start_location": "P320",
            "goal_location": "P320"
        },
        {
            "task_id": "20",
            "robot_id": "Manufacturer_20",
            "start_location": "P378",
            "goal_location": "P378"
        },
        {
            "task_id": "21",
            "robot_id": "Manufacturer_21",
            "start_location": "P380",
            "goal_location": "P380"
        },
        {
            "task_id": "22",
            "robot_id": "Manufacturer_22",
            "start_location": "P382",
            "goal_location": "P382"
        },
        {
            "task_id": "23",
            "robot_id": "Manufacturer_23",
            "start_location": "P384",
            "goal_location": "P384"
        },
        {
            "task_id": "24",
            "robot_id": "Manufacturer_24",
            "start_location": "P386",
            "goal_location": "P386"
        },
        {
            "task_id": "25",
            "robot_id": "Manufacturer_25",
            "start_location": "P388",
            "goal_location": "P388"
        }
    ]
}'
