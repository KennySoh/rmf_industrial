#!/bin/bash

# Configure your starting ROS2 workspace
ROSWS="/home/rosi/workspaces/rmf2_ws"

#Untouched if Instructions are followed
SESSIONNAME="rmf_broker_demo"
RMF2BROKERDIR="$ROSWS/src/rmf2_broker"
DOCKERDIR="$ROSWS/src/fiware_demo/compose_files/rmf2_broker"
LOGDIR="$ROSWS/logs/$(date '+%Y-%m-%d_%H-%M-%S')log"


PREP="cd $ROSWS && source /opt/ros/humble/setup.bash && source $ROSWS/install/setup.bash"

mkdir -p $LOGDIR
tmux has-session -t apr &> /dev/null

if [ $? != 0 ]
  then
    # tmux new-session -d -s $SESSIONNAME:0
    # APP_NAME=default_containers
    # tmux new-window -t $SESSIONNAME -n $APP_NAME 
    # tmux send-keys -t $SESSIONNAME "$PREP" C-m
    # tmux send-keys -t $SESSIONNAME "docker compose -f compose_files/compose.yml up --build | tee -a -i $LOGDIR/$APP_NAME.log" C-m

    tmux new-session -d -s $SESSIONNAME:0
    
    APP_NAME=default_containers
    tmux new-window -t $SESSIONNAME -n $APP_NAME 
    tmux send-keys -t $SESSIONNAME "$PREP" C-m
    tmux send-keys -t $SESSIONNAME "docker compose -f $RMF2BROKERDIR/compose.yaml up --build | tee -a -i $LOGDIR/$APP_NAME.log" C-m

    APP_NAME=mosquitto
    tmux new-window -t $SESSIONNAME -n $APP_NAME 
    tmux send-keys -t $SESSIONNAME "$PREP" C-m
    tmux send-keys -t $SESSIONNAME "docker compose -f $DOCKERDIR/compose.yml up --build | tee -a -i $LOGDIR/$APP_NAME.log" C-m

    APP_NAME=mapf
    tmux new-window -t $SESSIONNAME -n $APP_NAME
    tmux send-keys -t $SESSIONNAME "$PREP" C-m
    tmux send-keys -t $SESSIONNAME "#docker compose -f $DOCKERDIR/mapf_fiware.yml up 2>&1 | tee -a -i $LOGDIR/$APP_NAME.log" C-m

    APP_NAME=vda5050
    tmux new-window -t $SESSIONNAME -n $APP_NAME
    tmux send-keys -t $SESSIONNAME "$PREP" C-m
    tmux send-keys -t $SESSIONNAME "#docker compose -f $DOCKERDIR/vda5050_fiware.yml run vda5050_fiware | tee -a -i $LOGDIR/$APP_NAME.log" C-m

    APP_NAME=mir_866
    tmux new-window -t $SESSIONNAME -n $APP_NAME
    tmux send-keys -t $SESSIONNAME "$PREP" C-m
    tmux send-keys -t $SESSIONNAME "#docker compose -f $DOCKERDIR/vda5050_fiware.yml run mock_agv | tee -a -i $LOGDIR/$APP_NAME.log" C-m   
    tmux send-keys -t $SESSIONNAME "export MOCK_AGV_CONFIG=/$DOCKERDIR/agv/mir_866.yaml" C-m    
    tmux send-keys -t $SESSIONNAME "docker compose -f $DOCKERDIR/lvl1_robots.yml run mir_866 2>&1  | tee -a -i $LOGDIR/$APP_NAME.log" C-m

    APP_NAME=mir_1353
    tmux new-window -t $SESSIONNAME -n $APP_NAME
    tmux send-keys -t $SESSIONNAME "$PREP" C-m
    tmux send-keys -t $SESSIONNAME "#docker compose -f $DOCKERDIR/vda5050_fiware.yml run mock_agv | tee -a -i $LOGDIR/$APP_NAME.log" C-m   
    tmux send-keys -t $SESSIONNAME "export MOCK_AGV_CONFIG=/$DOCKERDIR/agv/mir_1353.yaml" C-m    
    tmux send-keys -t $SESSIONNAME "docker compose -f $DOCKERDIR/lvl1_robots.yml run mir_1353 2>&1  | tee -a -i $LOGDIR/$APP_NAME.log" C-m

    APP_NAME=mock_agv
    tmux new-window -t $SESSIONNAME -n $APP_NAME
    tmux send-keys -t $SESSIONNAME "$PREP" C-m
    tmux send-keys -t $SESSIONNAME "export MOCK_AGV_CONFIG=/$DOCKERDIR/agv/agv_config.yaml" C-m    
    tmux send-keys -t $SESSIONNAME "docker compose -f $ROSWS/src/vda5050_client/compose_files/mock_fleet_compose.yml up" C-m
    
    # APP_NAME=mock_agv
    # tmux new-window -t $SESSIONNAME -n $APP_NAME
    # tmux send-keys -t $SESSIONNAME "$PREP" C-m
    # tmux send-keys -t $SESSIONNAME "#docker compose -f $DOCKERDIR/vda5050_fiware.yml run mock_agv | tee -a -i $LOGDIR/$APP_NAME.log" C-m   
    # tmux send-keys -t $SESSIONNAME "export MOCK_AGV_CONFIG=/$DOCKERDIR/agv/agv_config.yaml" C-m    
    # tmux send-keys -t $SESSIONNAME "docker compose -p mir_1 -f $DOCKERDIR/mock.yml up" C-m

    APP_NAME=interface_server_test
    tmux new-window -t $SESSIONNAME -n $APP_NAME
    tmux send-keys -t $SESSIONNAME "$PREP" C-m
    tmux send-keys -t $SESSIONNAME "#docker compose -f $DOCKERDIR/ui_test.yml up | tee -a -i $LOGDIR/$APP_NAME.log" C-m

    APP_NAME=task_orchestrator
    tmux new-window -t $SESSIONNAME -n $APP_NAME -c $ROSWS
    tmux send-keys -t $SESSIONNAME "$PREP" C-m 
    tmux send-keys -t $SESSIONNAME "#ros2 run rmf2_task_orchestrator simple_tree_executor | tee -a -i $LOGDIR/$APP_NAME.log" C-m

    APP_NAME=gazebo
    tmux new-window -t $SESSIONNAME -n $APP_NAME  -c $ROSWS
    tmux send-keys -t $SESSIONNAME "$PREP" C-m
    tmux send-keys -t $SESSIONNAME "#ros2 launch vda5050_bringup_py agv_client.launch.py num_of_robots:=6 | tee -a -i $LOGDIR/$APP_NAME.log" C-m
fi
tmux select-window -t $SESSIONNAME:1
tmux attach -t $SESSIONNAME
