#!/bin/bash

# Configure your starting ROS2 workspace
ROSWS="/home/rosi/workspaces/rmf2_ws"

#Untouched if Instructions are followed
SESSIONNAME="rmf_broker_demo"
RMF2BROKERDIR="$ROSWS/src/rmf2_broker"
DOCKERDIR="$ROSWS/src/fiware_demo/compose_files/standalone"
LOGDIR="$ROSWS/logs/$(date '+%Y-%m-%d_%H-%M-%S')log"

PREP="cd $ROSWS && source /opt/ros/humble/setup.bash && source $ROSWS/install/setup.bash"

mkdir -p $LOGDIR
tmux has-session -t apr &> /dev/null

if [ $? != 0 ]
  then
    tmux new-session -d -s $SESSIONNAME:0
    APP_NAME=default_containers
    tmux new-window -t $SESSIONNAME -n $APP_NAME 
    tmux send-keys -t $SESSIONNAME "$PREP" C-m
    tmux send-keys -t $SESSIONNAME "docker compose -f $DOCKERDIR/compose.yml up --build | tee -a -i $LOGDIR/$APP_NAME.log" C-m

    APP_NAME=mapf
    tmux new-window -t $SESSIONNAME -n $APP_NAME
    tmux send-keys -t $SESSIONNAME "$PREP" C-m
    tmux send-keys -t $SESSIONNAME "#docker compose -f $DOCKERDIR/mapf_fiware.yml up --build | tee -a -i $LOGDIR/$APP_NAME.log" C-m

    APP_NAME=vda5050
    tmux new-window -t $SESSIONNAME -n $APP_NAME
    tmux send-keys -t $SESSIONNAME "$PREP" C-m
    tmux send-keys -t $SESSIONNAME "#docker compose -f $DOCKERDIR/vda5050_fiware.yml up | tee -a -i $LOGDIR/$APP_NAME.log" C-m

    APP_NAME=task_orchestrator
    tmux new-window -t $SESSIONNAME -n $APP_NAME -c $STARTDIR
    tmux send-keys -t $SESSIONNAME "$PREP" C-m 
    tmux send-keys -t $SESSIONNAME "#ros2 run rmf2_task_orchestrator simple_tree_executor | tee -a -i $LOGDIR/$APP_NAME.log" C-m

    APP_NAME=gazebo
    tmux new-window -t $SESSIONNAME -n $APP_NAME  -c $STARTDIR
    tmux send-keys -t $SESSIONNAME "$PREP" C-m
    tmux send-keys -t $SESSIONNAME "#ros2 launch vda5050_bringup_py agv_client.launch.py num_of_robots:=6 | tee -a -i $LOGDIR/$APP_NAME.log" C-m
fi
tmux select-window -t $SESSIONNAME:1
tmux attach -t $SESSIONNAME
