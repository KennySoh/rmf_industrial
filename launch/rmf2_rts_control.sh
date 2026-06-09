#!/bin/bash

start_server() {
    # Load environment
    source ~/ros_industrial_ws/modules/install/setup.bash
    source ~/ros_industrial_ws/modules/rts-venv/bin/activate

    # Log file location
    LOG_FILE=~/ros_industrial_ws/scheduler.log

    # Start server in background with logging
    rmf2_scheduler_server --host localhost --port 8089 >> "$LOG_FILE" 2>&1 &
    echo "rmf2_scheduler_server started on port 8089"
    echo "Logs: $LOG_FILE"
}

stop_server() {
    # Use pkill to terminate process by name
    if pkill -f "rmf2_scheduler_server --host localhost --port 8089"; then
        echo "rmf2_scheduler_server stopped"
        exit 0
    else
        echo "rmf2_scheduler_server is not running"
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
