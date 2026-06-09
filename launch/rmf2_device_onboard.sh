#!/bin/bash

start_server() {
    # Load environment
    source /opt/ros/humble/setup.bash
    source ~/UE5_DEMOS/ihi.sh
    source ~/UE5_DEMOS/fastdds_setup.sh

    # Start server in background
    cd ~/ros_industrial_ws/device_connector_ws/rmf2_iot_agent/device_connector
    npm run start
}

stop_server() {
    curl -X 'GET' 'http://localhost:4000/api/kill' -H 'accept: */*'
    echo "Device Connector stopped"
    exit 0

}

# Check for arguments and execute accordingly
if [ "$1" == "start" ]; then
    start_server
elif [ "$1" == "stop" ]; then
    stop_server
else
    echo "Usage: $0 {start|stop}"
    exit 1
fi
