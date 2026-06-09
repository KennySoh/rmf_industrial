#!/bin/bash
# Initialize 25 robots for warehouse_os_setup_v2 map
# Updated: 2026-06-08 - VERIFIED via MQTT (uagv/v2/.../state agvPosition) against live sim
# Map: warehouse_os_setup_v2 (active BUILDING_NAME; 34 cols × 21 rows, 175cm spacing)
# VDA5050 2.0: uagv/v2/Manufacturer/{serialNumber}
# Robot IDs: Manufacturer_1 through Manufacturer_25 (25 robots)
# Verification: all 25 robots parked exactly on nodes (0.00m snap); 5x5 block P74..P354

curl --location 'http://0.0.0.0:8009/mapf/send_task' \
--header 'Content-Type: application/json' \
--data '{
    "tasks": [
        {
            "task_id": "1",
            "robot_id": "Manufacturer_1",
            "start_location": "P82",
            "goal_location": "P82"
        },
        {
            "task_id": "2",
            "robot_id": "Manufacturer_2",
            "start_location": "P80",
            "goal_location": "P80"
        },
        {
            "task_id": "3",
            "robot_id": "Manufacturer_3",
            "start_location": "P78",
            "goal_location": "P78"
        },
        {
            "task_id": "4",
            "robot_id": "Manufacturer_4",
            "start_location": "P76",
            "goal_location": "P76"
        },
        {
            "task_id": "5",
            "robot_id": "Manufacturer_5",
            "start_location": "P74",
            "goal_location": "P74"
        },
        {
            "task_id": "6",
            "robot_id": "Manufacturer_6",
            "start_location": "P150",
            "goal_location": "P150"
        },
        {
            "task_id": "7",
            "robot_id": "Manufacturer_7",
            "start_location": "P148",
            "goal_location": "P148"
        },
        {
            "task_id": "8",
            "robot_id": "Manufacturer_8",
            "start_location": "P146",
            "goal_location": "P146"
        },
        {
            "task_id": "9",
            "robot_id": "Manufacturer_9",
            "start_location": "P144",
            "goal_location": "P144"
        },
        {
            "task_id": "10",
            "robot_id": "Manufacturer_10",
            "start_location": "P142",
            "goal_location": "P142"
        },
        {
            "task_id": "11",
            "robot_id": "Manufacturer_11",
            "start_location": "P218",
            "goal_location": "P218"
        },
        {
            "task_id": "12",
            "robot_id": "Manufacturer_12",
            "start_location": "P216",
            "goal_location": "P216"
        },
        {
            "task_id": "13",
            "robot_id": "Manufacturer_13",
            "start_location": "P214",
            "goal_location": "P214"
        },
        {
            "task_id": "14",
            "robot_id": "Manufacturer_14",
            "start_location": "P212",
            "goal_location": "P212"
        },
        {
            "task_id": "15",
            "robot_id": "Manufacturer_15",
            "start_location": "P210",
            "goal_location": "P210"
        },
        {
            "task_id": "16",
            "robot_id": "Manufacturer_16",
            "start_location": "P286",
            "goal_location": "P286"
        },
        {
            "task_id": "17",
            "robot_id": "Manufacturer_17",
            "start_location": "P284",
            "goal_location": "P284"
        },
        {
            "task_id": "18",
            "robot_id": "Manufacturer_18",
            "start_location": "P282",
            "goal_location": "P282"
        },
        {
            "task_id": "19",
            "robot_id": "Manufacturer_19",
            "start_location": "P280",
            "goal_location": "P280"
        },
        {
            "task_id": "20",
            "robot_id": "Manufacturer_20",
            "start_location": "P278",
            "goal_location": "P278"
        },
        {
            "task_id": "21",
            "robot_id": "Manufacturer_21",
            "start_location": "P354",
            "goal_location": "P354"
        },
        {
            "task_id": "22",
            "robot_id": "Manufacturer_22",
            "start_location": "P352",
            "goal_location": "P352"
        },
        {
            "task_id": "23",
            "robot_id": "Manufacturer_23",
            "start_location": "P350",
            "goal_location": "P350"
        },
        {
            "task_id": "24",
            "robot_id": "Manufacturer_24",
            "start_location": "P348",
            "goal_location": "P348"
        },
        {
            "task_id": "25",
            "robot_id": "Manufacturer_25",
            "start_location": "P346",
            "goal_location": "P346"
        }
    ]
}'
