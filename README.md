# ROS Industrial Demo

ROS Industrial Demo is an end-to-end warehouse automation reference implementation that demonstrates how TaskOrchestrator, MAPF ( multi-agent path finder ), Vda5050 and Simulation can operate together within a single interoperable platform.

The project provides a modular architecture for coordinating autonomous mobile robots (AMRs) in industrial and warehouse environments using open standards and reusable services.

## Core Modules
```mermaid
flowchart LR

    TO[Task Orchestrator]
    MAPF[MAPF]
    VDA[VDA5050]
    SIM[Simulation]

    TO --> MAPF
    MAPF --> VDA
    VDA --> SIM
```


| Module | Description |
|----------|-------------|
| Task Orchestrator | A workflow engine built on top of Crossflow's reactive event framework. It coordinates business workflows, executes tasks, and dispatches work to downstream systems. |
| MAPF | A Multi-Agent Path Finding service responsible for generating conflict-free routes and coordinating traffic for multiple robots operating in the same environment. |
| VDA5050 | An implementation of the VDA5050 v2.0 interoperability standard, providing a vendor-neutral interface between fleet management systems and autonomous mobile robots. |
| Simulation | A Unreal Engine 5 (UE5) simulation environment that implements VDA5050 and device interfaces, allowing workflows and robot integrations to be developed and validated in a virtual environment before deployment. |

## Quick Start

This guide takes you from a clean Ubuntu 22.04 / ROS 2 Humble machine to a running demo.

### Prerequisites

Install required packages
```bash
# Ubuntu 22.04 / ROS 2 Humble
sudo apt install python3-pip python3-venv tmux
pip3 install pika redis requests pymongo psutil
```

Create the shared Docker network (all containers attach to one shared network):
```bash
docker network create rmf2_broker_rmf-network
```

Stop any conflicting host services. The stack runs its own brokers, so stop any system-wide ones:
```bash
sudo systemctl stop mosquitto.service 2>/dev/null || true
sudo systemctl stop rabbitmq-server.service 2>/dev/null || true
```

### Setup
#### Core RMF Modules
Create a workspace and clone the required repositories:

```bash
mkdir -p ~/ros_industrial_ws
cd ~/ros_industrial_ws

# Clone repositories (legacy branch)
git clone -b legacy <https://github.com/ros-industrial/rmf_industrial.git> ros_industrial_demo
git clone -b legacy <https://github.com/ros-industrial/vda5050_core.git> vda5050_fiware_repo
git clone -b legacy <https://github.com/ros-industrial/res_mapf.git> mapf_unified_repo
git clone -b legacy <https://github.com/ros-industrial/rmf2_task_orchestrator.git> task_orchestrator_repo
git clone -b legacy <https://github.com/ros-industrial/rmf2_broker.git> rmf2_broker_repo
```

Build the required Docker images:

```bash
# VDA5050 FIWARE Bridge
cd ~/ros_industrial_ws/vda5050_fiware_repo
docker build -t vda5050_fiware_repo-vda5050_fiware:latest .

# MAPF Unified (includes map server, solver, executor)
cd ~/ros_industrial_ws/mapf_unified_repo
docker build -t mapf_unified:latest .

# Task Orchestrator
cd ~/ros_industrial_ws/task_orchestrator_repo/
docker build -t rmf2_task_orchestrator:latest .

# IOCS Broker Stack (Scorpio, Redis, RabbitMQ, Postgres)
cd ~/ros_industrial_ws/rmf2_broker_repo
docker  build -f ./Containers/rmf-base.Dockerfile . -t mctdis/rmf-base
docker compose build
```

> **Tip:** First-time builds are slow: MAPF ~10–15 min, VDA5050 ~5–10 min.

## Running the Environment

### Launch the Environment

The recommended launcher runs each startup step in its **own tmux pane** and gates on a health check before moving on.

Start all services:

```sh
cd ~/ros_industrial_ws/ros_industrial_demo/launch
./start_environment_tmux.sh
```

Stop all services (graceful, reverse order, kills the tmux session):

```sh
./stop_environment_tmux.sh
```

### Warehouse Simulation Setup

Download and unpack the latest UE5 simulation build:

```sh
cd ~/ros_industrial_ws
curl -OL https://downloads.rmf-industrial.org/UE5Demos/RMF2_SIM_20260606.zip
unzip RMF2_SIM_20260606.zip
mv RMF2_SIM_20260606 ~/ros_industrial_ws/simulation
```

You can launch it standalone to verify it runs (the launcher also starts it as one of its steps):

```sh
cd ~/ros_industrial_ws/simulation
./Linux/RMF2_SIM.sh
```

#### Controls

The simulation starts in fullscreen mode by default. Press Alt + Enter to toggle fullscreen.

- Move: `W A S D`
- Toggle Fullscreen: `Alt + Enter`
- Map Marker: `M`

## Send a Demo Task to the Task Orchestrator

Publish a parallel workflow to the Task Orchestrator. This workflow forks into multiple robot tasks and joins when all robots complete their work.

```bash
cd ~/ros_industrial_ws/ros_industrial_demo/test_scripts/taskorchestrator
python3 send_workflow.py
```

---
