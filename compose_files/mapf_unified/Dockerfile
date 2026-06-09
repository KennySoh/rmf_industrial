#==============================================================================
# MAPF Unified Container
# Combines: mapf_solver, adg_executor, mapf_mrs, movement_request_server,
#           fiware_map_server, load_maps
#
# SELF-CONTAINED REPO VERSION
# Build: docker build -t mapf_unified:latest .
#==============================================================================

FROM ros:humble-ros-base-jammy

#------------------------------------------------------------------------------
# Stage 1: Install all dependencies
#------------------------------------------------------------------------------

RUN apt-get update && apt-get install -y \
    cmake \
    curl \
    git \
    python3-colcon-common-extensions \
    python3-vcstool \
    wget \
    python3-pip \
    clang lldb lld \
    openssh-client \
    libmosquitto-dev mosquitto-clients \
    libcpprest-dev \
    nlohmann-json3-dev \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install all Python dependencies (combined from all services)
RUN pip3 install --no-cache-dir \
    # From mapf_execution
    PyYAML pydantic redis requests matplotlib networkx \
    shared-memory-dict paho-mqtt amqp pika \
    # From movement_request_server
    fastapi uvicorn python-dotenv \
    # From mapf_fiware/vda5050
    rich \
    # From fiware_map (flask with version constraints)
    "flask<3.0" "werkzeug<3.0"

# Setup Gazebo keys (required by some ROS packages)
RUN apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys D2486D2DD83DB69272AFE98867170598AF249743 || true
RUN . /etc/os-release && \
    echo "deb http://packages.osrfoundation.org/gazebo/$ID-stable `lsb_release -sc` main" > /etc/apt/sources.list.d/gazebo-latest.list || true

#------------------------------------------------------------------------------
# Stage 2: Setup workspace
#------------------------------------------------------------------------------

RUN mkdir -p /colcon_ws/src
WORKDIR /colcon_ws

RUN rosdep update --rosdistro $ROS_DISTRO || true

ENV DEBIAN_FRONTEND=noninteractive

#------------------------------------------------------------------------------
# Stage 3: Copy source code from all services
# NOTE: This is a self-contained repo - build from repo root
#       Run: docker build -t mapf_unified:latest .
#------------------------------------------------------------------------------

# === MAPF Solver (mapf_service) ===
COPY src/mapf /colcon_ws/src/mapf

# === MAPF FIWARE / MRS (mapf_fiware) ===
COPY src/mapf_fiware /colcon_ws/src/mapf_fiware
COPY src/fiware_api /colcon_ws/src/fiware_api
COPY src/rmf2_agv /colcon_ws/src/rmf2_agv
COPY src/rmf2_building /colcon_ws/src/rmf2_building
COPY src/rmf2_tasks /colcon_ws/src/rmf2_tasks

# === ADG Executor (mapf_execution) ===
COPY src/mapf_execution /colcon_ws/src/mapf_execution

# === Movement Request Server ===
COPY movement_request_server /app/movement_request_server

# === FIWARE Map Server (fiware_map) ===
COPY src/fiware_map /colcon_ws/src/fiware_map

#------------------------------------------------------------------------------
# Stage 4: Build ROS2 packages
#------------------------------------------------------------------------------

RUN . /opt/ros/$ROS_DISTRO/setup.sh && \
    colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release

#------------------------------------------------------------------------------
# Stage 5: Setup supervisord and startup scripts
#------------------------------------------------------------------------------

# Copy configuration files (from repo root)
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY startup.sh /startup.sh
RUN chmod +x /startup.sh

# Create log directory
RUN mkdir -p /var/log/supervisor

#------------------------------------------------------------------------------
# Expose all ports
#------------------------------------------------------------------------------

# mapf_solver
EXPOSE 8888
# adg_executor
EXPOSE 6333
EXPOSE 1932
# mapf_mrs
EXPOSE 1933
# movement_request_server
EXPOSE 8009
# fiware_map_server
EXPOSE 7073

#------------------------------------------------------------------------------
# Entrypoint
#------------------------------------------------------------------------------

WORKDIR /colcon_ws

CMD ["/startup.sh"]
