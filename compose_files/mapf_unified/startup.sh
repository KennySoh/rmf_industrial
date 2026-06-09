#!/bin/bash
#==============================================================================
# MAPF Unified Container Startup Script
# Waits for dependencies and starts all services via supervisord
#==============================================================================

set -e

echo "=============================================="
echo "MAPF Unified Container Starting..."
echo "=============================================="

# Source ROS environment
source /opt/ros/humble/setup.bash
source /colcon_ws/install/setup.bash

# Export environment for supervisord
export ROS_DISTRO=humble

#------------------------------------------------------------------------------
# Wait for Redis
#------------------------------------------------------------------------------
wait_for_redis() {
    local host=${REDIS_HOST:-redis}
    local port=${REDIS_PORT:-6379}
    local max_attempts=30
    local attempt=1

    echo "Waiting for Redis at $host:$port..."

    while [ $attempt -le $max_attempts ]; do
        if python3 -c "import redis; r=redis.Redis(host='$host', port=$port); r.ping()" 2>/dev/null; then
            echo "Redis is ready!"
            return 0
        fi
        echo "  Attempt $attempt/$max_attempts - Redis not ready, waiting..."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo "WARNING: Redis not available after $max_attempts attempts. Continuing anyway..."
    return 1
}

#------------------------------------------------------------------------------
# Wait for MQTT (Mosquitto)
#------------------------------------------------------------------------------
wait_for_mqtt() {
    local host=${MQTT_SERVER_HOST:-mosquitto}
    local port=${ADG_MQTT_PORT:-1932}
    local max_attempts=30
    local attempt=1

    echo "Waiting for MQTT broker at $host..."

    while [ $attempt -le $max_attempts ]; do
        if mosquitto_sub -h "$host" -p 1883 -t '$SYS/#' -C 1 -W 2 2>/dev/null; then
            echo "MQTT broker is ready!"
            return 0
        fi
        echo "  Attempt $attempt/$max_attempts - MQTT not ready, waiting..."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo "WARNING: MQTT not available after $max_attempts attempts. Continuing anyway..."
    return 1
}

#------------------------------------------------------------------------------
# Wait for Context Broker (Scorpio)
#------------------------------------------------------------------------------
wait_for_context_broker() {
    local host=${CONTEXT_BROKER_HOST:-scorpio}
    local port=${CONTEXT_BROKER_PORT:-9090}
    local max_attempts=30
    local attempt=1

    echo "Waiting for Context Broker at $host:$port..."

    while [ $attempt -le $max_attempts ]; do
        if curl -s "http://$host:$port/ngsi-ld/v1/entities" > /dev/null 2>&1; then
            echo "Context Broker is ready!"
            return 0
        fi
        echo "  Attempt $attempt/$max_attempts - Context Broker not ready, waiting..."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo "WARNING: Context Broker not available after $max_attempts attempts. Continuing anyway..."
    return 1
}

#------------------------------------------------------------------------------
# Main
#------------------------------------------------------------------------------

echo ""
echo "Checking external dependencies..."
echo "----------------------------------------------"

# Wait for dependencies (non-blocking - will continue even if some fail)
wait_for_redis || true
wait_for_mqtt || true
wait_for_context_broker || true

echo ""
echo "----------------------------------------------"
echo "Starting services via supervisord..."
echo "----------------------------------------------"
echo ""
echo "Services to be started:"
echo "  1. fiware_map_server (port ${MAP_SERVER_PORT:-7073})"
echo "  2. load_maps (one-shot - uploads maps to Context Broker)"
echo "  3. mapf_solver (port ${MAPF_SOLVER_SERVER_PORT:-8888})"
echo "  4. adg_executor (ports ${ADG_MQTT_PORT:-1932}, ${AGV_STATE_SERVER_PORT:-6333})"
echo "  5. mapf_mrs (port ${MRS_MQTT_SERVER_PORT:-1933})"
echo "  6. movement_request_server (port ${MOVEMENT_REQUEST_SERVER_PORT:-8009})"
echo ""
echo "Logs available at: /var/log/supervisor/"
echo "=============================================="
echo ""

# Start supervisord in foreground
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
