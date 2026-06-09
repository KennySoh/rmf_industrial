import json
import sys
import requests
import queue
import threading
import pika
from fiware_api.context_broker.scorpio import ScorpioAPI, ScorpioEventSubscriber
from fiware_api.utils import (
    printRed,
    printGreen,
    printYellow,
    printPurple,
    printCyan,
    printLightGray,
)
from rmf2_tasks.TaskRequest import TaskRequest
from time import sleep
import redis


class RabbitMQTaskRequestSubscriber:
    """Subscribe directly to RabbitMQ for TaskRequest messages (bypasses Scorpio)."""

    def __init__(self, host, port, exchange, on_message_callback):
        self.host = host
        self.port = port
        self.exchange = exchange
        self.on_message_callback = on_message_callback
        self.connection = None
        self.channel = None
        self._thread = None

    def connect(self):
        while True:
            try:
                self.connection = pika.BlockingConnection(
                    pika.ConnectionParameters(host=self.host, port=self.port)
                )
                self.channel = self.connection.channel()
                self.channel.exchange_declare(
                    exchange=self.exchange, exchange_type='fanout', durable=True
                )
                result = self.channel.queue_declare(queue='', exclusive=True)
                queue_name = result.method.queue
                self.channel.queue_bind(exchange=self.exchange, queue=queue_name)
                self.channel.basic_consume(
                    queue=queue_name, on_message_callback=self._handle_message, auto_ack=True
                )
                printGreen(f"RabbitMQ subscriber connected to exchange: {self.exchange}")
                return True
            except pika.exceptions.AMQPConnectionError as e:
                printRed(f"RabbitMQ connection error: {e}, retrying...")
                sleep(2.0)

    def _handle_message(self, ch, method, properties, body):
        try:
            data = json.loads(body.decode('utf-8'))
            if data.get('type') == 'TaskRequest':
                printYellow(f"[RabbitMQ] Received TaskRequest: {data.get('id')}")
                self.on_message_callback(data)
        except Exception as e:
            printRed(f"RabbitMQ message error: {e}")

    def run(self):
        self._thread = threading.Thread(target=self._consume, daemon=True)
        self._thread.start()

    def _consume(self):
        self.connect()
        printGreen("RabbitMQ consumer started, waiting for TaskRequest messages...")
        self.channel.start_consuming()


# Integration Class for MAPF to Context Broker
class MovementRequestServerFiware:
    def __init__(self, context_broker, mqtt_host, mqtt_port, mapf_endpoint, use_rabbitmq=False, rabbitmq_host=None, rabbitmq_port=5672):
        self.robots = {}
        self.commands = {}
        self.map = None
        self.context_broker = context_broker
        self.namespace = "ngsi-ld:default-context/"
        self.task_queue = queue.Queue()
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mapf_endpoint = mapf_endpoint
        self.use_rabbitmq = use_rabbitmq
        self.ld_link = 'https://smart-data-models.github.io/dataModel.AutonomousMobileRobot/StateMessage/examples/example-normalized.jsonld; rel="https://www.w3.org/ns/json-ld#context"; type="application/ld+json"'

        self.task_event_subscriber = ScorpioEventSubscriber(
            self.context_broker.endpoint,
            id="tasks_fiware",
            host=self.mqtt_host,
            port=self.mqtt_port,
            topic="tasks",
            message_type="Task",
            ld_link=self.ld_link,
            on_message_callback=self.fiware_task_handler,
        )

        if use_rabbitmq:
            # Use direct RabbitMQ subscription (bypasses Scorpio/ngsi-ld)
            printYellow("Using RabbitMQ mode for TaskRequest subscription")
            self.task_request_subscriber = RabbitMQTaskRequestSubscriber(
                host=rabbitmq_host or "rmf2_broker-rabbitmq-1",
                port=rabbitmq_port,
                exchange="@RECEIVE@",
                on_message_callback=self.rabbitmq_task_request_handler,
            )
        else:
            # Use Scorpio MQTT subscription (requires ngsi-ld sink)
            printYellow("Using Scorpio mode for TaskRequest subscription")
            self.task_request_subscriber = ScorpioEventSubscriber(
                self.context_broker.endpoint,
                id="task_requests",
                host=self.mqtt_host,
                port=self.mqtt_port,
                topic="task_requests",
                message_type="TaskRequest",
                ld_link=self.ld_link,
                on_message_callback=self.task_request_handler,
            )

    def run(self):
        self.task_event_subscriber.run()
        self.task_request_subscriber.run()
        while True:
            sleep(1.0)

        # self.task_event_subscriber.mqtt_client.mqtt_thread.join()

    def set_redis_connection(self, host, port):
        pool = redis.ConnectionPool(host=host, port=port, db=0)
        while True:
            sleep(1.0)
            try:
                self.redis_client = redis.Redis(connection_pool=pool)
                self.redis_client.ping()
                break
            except redis.exceptions.ConnectionError as e:
                printRed(str(e))
                pass
        printGreen("Connected to REDIS")

    def send_to_replace_destination(self, json_body):
        response = requests.post(
            self.mapf_endpoint + "/mapf/replace_destination",
            data=json.dumps(json_body),
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

    def send_to_send_tasks(self, json_body):
        response = requests.post(
            self.mapf_endpoint + "/mapf/send_task",
            data=json.dumps(json_body),
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

    def task_request_handler(self, client, userdata, msg):
        """Handle TaskRequest from Scorpio MQTT subscription (NGSI format)."""
        json_body = json.loads(str(msg.payload.decode("utf-8", "ignore")))
        for data in json_body["body"]["data"]:
            task_request = TaskRequest.from_subscriber_json(data)
            self._push_task_to_redis(task_request)

    def rabbitmq_task_request_handler(self, data):
        """Handle TaskRequest from direct RabbitMQ subscription (flat JSON format)."""
        try:
            task_request = TaskRequest.from_flat_json(data)
            self._push_task_to_redis(task_request)
        except Exception as e:
            printRed(f"Error parsing TaskRequest from RabbitMQ: {e}")

    def _push_task_to_redis(self, task_request):
        """Push TaskRequest to the appropriate Redis queue.

        Only amr_mapf tasks are pushed to Redis (mapf_replace_destinations queue).
        Other task types (amr_ue5, warehouse_item_transfer, etc.) are handled
        elsewhere (e.g., ROS2) and should not go through MAPF.

        Note: Initialization tasks come via HTTP POST /mapf/send_task, not here.
        """
        if task_request.taskType == "amr_mapf":
            mapf_redis_endpoint = "mapf_replace_destinations"
        else:
            # Skip non-MAPF task types - they're handled elsewhere
            printYellow(f"Skipping TaskRequest with taskType '{task_request.taskType}' - not for MAPF")
            return

        task_body = json.dumps(
            TaskRequest.to_json(id=task_request.id, input_msg=task_request)
        )

        try:
            self.redis_client.lpush(mapf_redis_endpoint, task_body)
            printGreen(f"Pushed TaskRequest to Redis: {mapf_redis_endpoint}")
        except redis.ConnectionError as e:
            printRed("Redis connection error: " + str(e))
            return
        except Exception as e:
            printRed("Redis Exception: " + str(e))
            return

    def fiware_task_handler(self, client, userdata, msg):
        json_body = json.loads(str(msg.payload.decode("utf-8", "ignore")))
        sent_body = {}
        for data in json_body["body"]["data"]:
            if data["taskType"]["value"] == "replace_destination":
                destination_list = data["taskDestinations"]["value"]
                destination_nodes = []
                if isinstance(destination_list, dict):
                    destination_nodes.append(destination_list)
                else:
                    destination_nodes = destination_list
                sent_body["destinations"] = destination_nodes
                self.send_to_replace_destination(sent_body)
            elif data["taskType"]["value"] == "send_task":
                task_list = data["tasks"]["value"]
                task_nodes = []
                if isinstance(task_list, dict):
                    task_nodes.append(task_list)
                else:
                    task_nodes = task_list
                sent_body["tasks"] = task_nodes
                self.send_to_send_tasks(sent_body)


def main():
    # Default Parameters if nothing is set.
    cb_endpoint = "http://localhost:9090"
    mqtt_server_host = "localhost"
    mqtt_server_port = 1929
    mapf_endpoint = "http://0.0.0.0:8002"
    redis_server_host = "http://redis"
    redis_server_port = "6379"
    use_rabbitmq = False
    rabbitmq_host = "rmf2_broker-rabbitmq-1"
    rabbitmq_port = 5672

    # Parse from Python Args
    if len(sys.argv) > 1:
        cb_endpoint = sys.argv[1]
    if len(sys.argv) > 2:
        mqtt_server_host = sys.argv[2]
    if len(sys.argv) > 3:
        mqtt_server_port = sys.argv[3]
    if len(sys.argv) > 4:
        mapf_endpoint = sys.argv[4]
    if len(sys.argv) > 5:
        redis_server_host = sys.argv[5]
    if len(sys.argv) > 6:
        redis_server_port = sys.argv[6]
    # New arguments for RabbitMQ mode
    if len(sys.argv) > 7:
        use_rabbitmq = sys.argv[7].lower() in ("true", "1", "yes", "rabbitmq")
    if len(sys.argv) > 8:
        rabbitmq_host = sys.argv[8]
    if len(sys.argv) > 9:
        rabbitmq_port = int(sys.argv[9])

    context_broker = ScorpioAPI(cb_endpoint)
    mapf_server = MovementRequestServerFiware(
        context_broker=context_broker,
        mqtt_host=mqtt_server_host,
        mqtt_port=int(mqtt_server_port),
        mapf_endpoint=mapf_endpoint,
        use_rabbitmq=use_rabbitmq,
        rabbitmq_host=rabbitmq_host,
        rabbitmq_port=rabbitmq_port,
    )
    mapf_server.set_redis_connection(redis_server_host, redis_server_port)
    mapf_server.run()


if __name__ == "__main__":
    main()
