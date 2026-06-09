#!/bin/bash

start_server() {
    # Load environment
    source ~/ros_industrial_ws/modules/install/setup.bash
    source ~/ros_industrial_ws/modules/rts-venv/bin/activate

    # Start server in background
    rmf2_task_estimator_server --port 8090 &
    echo "rmf2_task_estimator_server started on port 8089"
}

stop_server() {
    # Use pkill to terminate process by name
    if pkill -f "rmf2_task_estimator_server --port 8090"; then
        echo "rmf2_task_estimator_server stopped"
        exit 0
    else
        echo "rmf2_task_estimator_server is not running"
        exit 1
    fi
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
