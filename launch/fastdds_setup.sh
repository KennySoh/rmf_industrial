#!/bin/bash

export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_DISCOVERY_SERVER="127.0.0.1:11811"
export ROS_DOMAIN_ID=0

export FASTRTPS_DEFAULT_PROFILES_FILE=$HOME/.ros/super_client.xml

echo "$FASTRTPS_DEFAULT_PROFILES_FILE"

