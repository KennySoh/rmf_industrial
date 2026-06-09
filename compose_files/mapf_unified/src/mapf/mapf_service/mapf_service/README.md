# mapf-IR-ros2
This Package provides a HTTP server service for MAPF based planning

# Inputs and outputs

## Inputs

1. Building.yaml
   
A building yaml file is needed to be loaded and converted into a MAPF representation of a map. We currently use the building yaml format output from the [RMF1 Traffic Editor](https://github.com/open-rmf/rmf_traffic_editor)

Please ensure that all nodes are named.

The yaml file should be stored in the `maps` folder of this package. It will automatically be converted into a `.map` file when processed.

**NOTE:**
\
As of now, it is **REQUIRED** to include a columns and rows field in the yaml file. Do specify the number of rows and columns in the yaml file. For example:
```yaml
columns: 10
rows: 15
coordinate_system:
crowd_sim: 
  agent_groups:
levels:
```
2. HTTP Client Call

In order to send a plan request, you would need to send it through a http client in the following input. This service expects the following JSON string input:

```json
{
  "mapfile":"building.yaml",
  "solver" : "ECBS",
  "max_computation_time" : 100000,
  "max_timestep" : 100000,
  "obstacles": [
      {
          "coordinate" : {
              "x": 20,
              "y": 4
          }
      }
  ], 
  "tasks": [
    {
      "agent_name" : "agent_1",
      "start_position" :
      {
        "x" : 120,
        "y" : 100
      },
      "end_position" :
      {
        "x" : 120,
        "y" : 100
      }
    },
    {
      "agent_name" : "agent_2",
      "start_position" :
      {
        "x" : 300,
        "y" : 30
      },
      "end_position" :
      {
        "x" : 100,
        "y" : 300
      }
    }
  ]
}
```

## Outputs

The output will be in a form of a JSON string as follows:

```json
[
  {
    "agent_name": "agent_1",
    "steps": [
      {
        "step_from": {
          "x": 30,
          "y": 60
        },
        "step_to": {
          "x": 30,
          "y": 30
        },
        "timestep": 0
      }
    ]
  },
  {
    "agent_name": "agent_2",
    "steps": [
      {
        "step_from": {
          "x": 300,
          "y": 90
        },
        "step_to": {
          "x": 300,
          "y": 60
        },
        "timestep": 0
      }
    ]
  }
]
```
# How it works

1. When parsing a `building.yaml` file, the `x`, `y` and `point` values in the `vertices` field are recorded.

2. Points with no associated traffic lanes are recorded as obstacles.

3. A `.map` file is created using the indices of the points parsed in the `building.yaml` file.
   Obstacles are labelled with a `T` while valid points are labelled with a `.` in the `.map` file.
   The indices and coordinates of the `building.yaml` file are then tagged to MAPF's coordinate system.

4. When the service receives a request, the real-world start/end coordinate specified will be translated
   into the MAPF coordinate which will then be fed into the MAPF Solver.

5. The MAPF Solver outputs steps in the MAPF coordinate system which will then be translated back to real-world
   coordinates and sent back to the client. 

# Installation
```bash
mkdir -p $COLCON_WS/src

cd $COLCON_WS/src

git clone git@gitlab.com:ROSI-AP/rmf2/mapf_service.git

```
## Dependencies

There are 2 main dependencies for this library

1. (MAPF-IR ROS2)[https://github.com/tanjpg/mapf-IR-ros2]
   This is a custom wrapper around the original (MAPF-IR)[https://github.com/Kei18/mapf-IR] Library 

```bash
cd $COLCON_WS/src

git clone --recursive git@github.com:tanjpg/mapf-IR-ros2.git

```
2. yaml-cpp
```bash
cd $COLCON_WS/src

git clone https://github.com/jbeder/yaml-cpp.git

```

# Running Demo

Run the Example Service

```bash

ros2 run mapf run_mapf_service

```

**THE CLIENT EXAMPLE DOESNT WORK FOR NOW**

Run the Example Client

```bash

ros2 run mapf run_example_client

```