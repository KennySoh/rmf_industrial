# ROS Industrial Demo

Multi-agent warehouse robotics demo with FIWARE integration, VDA5050 AGV communication, and MAPF path planning.

## Overview

This demo integrates:
- **VDA5050 AGV Communication**
- **MAPF Multi-Agent Path Finding** (ECBS solver)
- **Task Orchestrator** (cross-flow)
- **Simulation** (unreal-engine)
- **Context Broker**
---

## Directory Structure

```
ros_industrial_demo/
├── compose_files/
│   ├── rmf2_broker/           # IOCS broker compose files
│   │   ├── compose.yml        # Mosquitto broker config
│   │   ├── vda5050_fiware.yml # VDA5050 FIWARE bridge
│   │   ├── mosquitto/         # Mosquitto configuration
│   │   └── agv/               # AGV configuration files
│   └── standalone/            # Standalone compose (alternative)
├── launch/
│   ├── start_environment.sh   # Main startup script
│   ├── stop_environment.sh    # Shutdown script
│   ├── rmf2_unified_mapf_control.sh
│   ├── rmf2_res_broker_control.sh
│   ├── rmf2_res_mqtt_control.sh
│   ├── rmf2_res_vda5050_control.sh
│   ├── rmf2_tte_control.sh
│   ├── rmf2_rts_control.sh
│   ├── dashboard_interface.py # HTTP API server (port 8083)
│   └── ...
├── scripts/
│   └── send_init.sh           # System initialization
└── tasks/
    └── *.sh                   # Task sending scripts
```

---

## Prerequisites

### 1. Host Dependencies

```bash
# Ubuntu 22.04 / ROS2 Humble
sudo apt install python3-pip python3-venv

# Python packages
pip3 install pika redis requests pymongo psutil
```

### 2. Docker Network

Create the shared Docker network:
```bash
docker network create rmf2_broker_rmf-network
```

### 3. Stop Conflicting Services

```bash
sudo systemctl stop mosquitto.service 2>/dev/null || true
sudo systemctl stop rabbitmq-server.service 2>/dev/null || true
```

---

## Setup on Target Machine

### Step 1: Clone Required Repositories

```bash
# Create workspace
mkdir -p ~/ros_industrial_ws
cd ~/ros_industrial_ws

# Clone this demo package
git clone <demo-package-url> ros_industrial_demo

# Clone and build Docker images
git clone <vda5050-fiware-url> vda5050_fiware_repo
git clone <mapf-unified-url> mapf_unified_repo
git clone <task-orchestrator-url> task_orchestrator_repo
git clone <rmf2-broker-url> rmf2_broker_repo
```

### Step 2: Build Docker Images

```bash
# IOCS Broker Stack (Scorpio, Redis, RabbitMQ, Postgres)
cd ~/ros_industrial_ws/rmf2_broker_repo
docker  build -f ./Containers/rmf-base.Dockerfile . -t mctdis/rmf-base
docker compose build

# VDA5050 FIWARE Bridge
cd ~/ros_industrial_ws/vda5050_fiware_repo
docker build -t vda5050_fiware_repo-vda5050_fiware:latest .


# MAPF Unified (includes map server, solver, executor)
cd ~/ros_industrial_ws/mapf_unified_repo
docker build -t mapf_unified:latest .

# Task Orchestrator
cd ~/ros_industrial_ws/task_orchestrator_repo/
docker build -t task_orchestrator:latest .
```
---

## Running the Environment

### Quick Start (No Simulation, Unified MAPF)

```bash
cd ~/ros_industrial_ws/ros_industrial_demo/launch
./start_environment_tmux.sh

# ./stop_environment_tmux.sh
```

### Options

| Flag | Description |
|------|-------------|
| `--no-sim` | Skip UE5 simulation startup |
| `--unified` | Use unified MAPF container (recommended) |
| `--step N` | Start from step N |
| `--only N` | Run only step N |
| `--status` | Check what's running |

### Startup Steps

1. **IOCS Broker** - Scorpio, Redis, RabbitMQ, Postgres
2. **Mosquitto MQTT** - MQTT broker on ports 1883, 1928
3. **Unified MAPF** - Map server, solver, executor, MRS
4. **VDA5050 Bridge** - VDA5050 to FIWARE integration
5. **Services** - TTE estimator, RTS scheduler
6. **Initialization** - Register robots with Context Broker

### Stop Environment

```bash
./stop_environment.sh
# Or force kill:
./stop_environment.sh --force
```

---

## Ports Reference

| Service | Port | Description |
|---------|------|-------------|
| Scorpio | 9090 | Context Broker API |
| Redis | 6379 | Cache / Queue |
| RabbitMQ | 5672 | AMQP messaging |
| RabbitMQ UI | 15672 | Management UI (guest/guest) |
| Mosquitto | 1883, 1928, 1929 | MQTT broker |
| MAPF Solver | 8888 | Path planning API |
| Movement Request | 8009 | FastAPI REST gateway |
| Map Server | 7073 | FIWARE map service |
| Dashboard API | 8083 | HTTP control API |
| RTS Scheduler | 8089 | Scheduler API |

---

## Troubleshooting

### Check Container Status
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Check Service Logs
```bash
# MAPF Unified
docker logs mapf_unified --tail 50

# VDA5050 FIWARE
docker logs vda5050_fiware --tail 50

# IOCS Broker
docker logs rmf2_broker-scorpio-1 --tail 50
```

### Verify Network
```bash
docker network inspect rmf2_broker_rmf-network
```

### Common Issues

1. **Port already in use**: Stop conflicting services with systemctl
2. **Network not found**: Run `docker network create rmf2_broker_rmf-network`
3. **Image not found**: Build images with `docker build -t <name>:latest .`

---

## Sending Tasks

### Initialize System
```bash
./launch/send_init_warehouse_os_setup.sh
```

### Send Preset Tasks
```bash
./launch/rmf2_rts_send_order.sh
```

### Via Dashboard API
```bash
curl -X POST http://localhost:8083/send_task
```

---

## Related Repositories

- **mapf_unified_repo** - Unified MAPF Docker container
- **vda5050_fiware_repo** - VDA5050 FIWARE bridge
- **rmf2_broker** - IOCS broker stack (Scorpio, Redis, RabbitMQ)
