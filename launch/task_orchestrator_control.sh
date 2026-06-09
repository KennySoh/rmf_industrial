#!/bin/bash
#
# Task Orchestrator (Rust) Control Script
# Manages the Docker container for the Crossflow-based task orchestrator
#

CONTAINER_NAME="task_orchestrator"
IMAGE_NAME="rmf2_task_orchestrator:latest"
NETWORK="rmf2_broker_rmf-network"

# Default configuration (can be overridden via environment)
AMQP_HOST="${AMQP_HOST:-rabbitmq}"
AMQP_PORT="${AMQP_PORT:-5672}"
MQTT_HOST="${MQTT_HOST:-mosquitto}"
MQTT_PORT="${MQTT_PORT:-1883}"
HTTP_PORT="${HTTP_PORT:-2727}"
LOG_LEVEL="${LOG_LEVEL:-info}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[task_orchestrator]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[task_orchestrator]${NC} $1"; }
log_error() { echo -e "${RED}[task_orchestrator]${NC} $1"; }

start() {
    # Check if already running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_warn "Container $CONTAINER_NAME is already running"
        return 0
    fi

    # Remove stopped container if exists
    docker rm -f $CONTAINER_NAME 2>/dev/null || true

    # Check if image exists
    if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${IMAGE_NAME}$"; then
        log_error "Image $IMAGE_NAME not found. Build it first with:"
        log_error "  cd task_orchestrator_repo && docker build -t rmf2_task_orchestrator:latest ."
        return 1
    fi

    log_info "Starting $CONTAINER_NAME..."
    docker run -d \
        --name $CONTAINER_NAME \
        --network $NETWORK \
        -p ${HTTP_PORT}:2727 \
        -e RUST_LOG=$LOG_LEVEL \
        -e TASK_ORCHESTRATOR__AMQP__HOST=$AMQP_HOST \
        -e TASK_ORCHESTRATOR__AMQP__PORT=$AMQP_PORT \
        -e TASK_ORCHESTRATOR__MQTT__HOST=$MQTT_HOST \
        -e TASK_ORCHESTRATOR__MQTT__PORT=$MQTT_PORT \
        --restart unless-stopped \
        $IMAGE_NAME

    if [ $? -eq 0 ]; then
        log_info "Container $CONTAINER_NAME started successfully"
        log_info "HTTP API: http://localhost:${HTTP_PORT}"
        log_info "Health check: http://localhost:${HTTP_PORT}/health_check"
    else
        log_error "Failed to start $CONTAINER_NAME"
        return 1
    fi
}

stop() {
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "Stopping $CONTAINER_NAME..."
        docker stop $CONTAINER_NAME
        docker rm $CONTAINER_NAME 2>/dev/null || true
        log_info "Container $CONTAINER_NAME stopped"
    else
        log_warn "Container $CONTAINER_NAME is not running"
    fi
}

restart() {
    stop
    sleep 2
    start
}

status() {
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${GREEN}[RUNNING]${NC} $CONTAINER_NAME"
        docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

        # Health check
        if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${HTTP_PORT}/health_check" 2>/dev/null | grep -q "200"; then
            echo -e "${GREEN}[HEALTHY]${NC} Health check passed"
        else
            echo -e "${YELLOW}[UNHEALTHY]${NC} Health check failed or not responding"
        fi
    else
        echo -e "${RED}[STOPPED]${NC} $CONTAINER_NAME"
    fi
}

logs() {
    docker logs $CONTAINER_NAME "${@:2}"
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs "$@"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Environment variables:"
        echo "  AMQP_HOST    RabbitMQ host (default: rmf2_broker-rabbitmq-1)"
        echo "  MQTT_HOST    MQTT broker host (default: mosquitto)"
        echo "  HTTP_PORT    HTTP API port (default: 2727)"
        echo "  LOG_LEVEL    Log level: debug|info|warn|error (default: info)"
        exit 1
        ;;
esac
