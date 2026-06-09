from flask import Flask, request
import requests
import json
from datetime import datetime
import redis
import sys

import paho.mqtt.client as paho


class MAPFFiwareServer:
    def __init__(self, host, port, cb_endpoint, ld_link) -> None:
        print("connecting to " + host + " on port " + str(port))
        self.host = host
        self.port = port
        self.fiware_server = FiwareServer(cb_endpoint, ld_link)
        print("connecting to " + host + " on port " + str(port))

        # HTTP
        # self.app = Flask('fiware_mapf_server')
        # self.app.add_url_rule('/agv_states', 'agv_states', self.agv_update, methods=['POST'])
        # response = self.fiware_server.create_subscription_entities(
        #     'mapf_fiware',
        #     'http://' + str(host) + ':' + str(port) + '/agv_states',
        #     [{
        #         # "id": "urn:ngsi-ld:Robot:robots:robot_1:StateMessage",
        #         'type': 'StateMessage'
        #     }]
        # )

        # MQTT
        self.client = paho.Client(client_id="mapf_notifier")
        self.client.on_connect = self.on_connect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.on_message
        self.client.connect(host, port)
        self.client.subscribe("agv_states")
        print("Endpoint: " + "mqtts://" + host + ":" + str(port) + "/agv_states")
        response = self.fiware_server.create_subscription_entities(
            "mapf_fiware",
            "mqtt://" + host + ":" + str(port) + "/agv_states",
            [
                {
                    # "id": "urn:ngsi-ld:Robot:robots:robot_1:StateMessage",
                    "type": "StateMessage"
                }
            ],
        )

        print(response.text, flush=True)

    def on_connect(self, client, userdata, flags, rc):
        print("CONNACK received with code %d." % (rc), flush=True)

    def on_subscribe(self, client, userdata, mid, granted_qos):
        print("Subscribed: " + str(mid) + " " + str(granted_qos), flush=True)

    def on_message(self, client, userdata, msg):
        print(str(msg.payload.decode("utf-8", "ignore")), flush=True)

    def set_redis_connection(self, host, port):
        self.redis_host = host
        self.redis_port = port

    def run(self):
        # self.app.run(host=self.host, port=self.port)
        self.client.loop_forever()

    def agv_update(self):
        print("AGV UPDATE")
        json_msg = json.loads(request.get_data())
        print(json.dumps(json_msg, indent=2))
        return ""


class FiwareServer:
    def __init__(self, cb_endpoint, ld_link):
        self.subscription = {}
        self.cb_endpoint = cb_endpoint
        self.ld_link = ld_link

    def does_entity_exist(self, entity):
        response = self.get_entity(entity)
        if response.status_code == 404:
            print("entity " + entity + " does not exist")
            return False
        print("entity " + entity + "  exists")
        return True

    def create_new_entity(self, json_body):
        return requests.post(
            self.cb_endpoint + "/ngsi-ld/v1/entities/",
            data=json.dumps(json_body),
            headers=self.headers,
        )

    def update_entity(self, json_body, entity_name):
        return requests.patch(
            self.cb_endpoint + "/ngsi-ld/v1/entities/" + entity_name + "/attrs",
            data=json.dumps(json_body),
            headers=self.headers,
        )

    def get_entity(self, entity_id):
        headers = {
            "Accept": "application/ld+json",
            "Content-Type": "application/ld+json",
        }
        return requests.get(
            self.cb_endpoint + "/ngsi-ld/v1/entities/" + entity_id, headers=headers
        )

    def delete_subscription(self, subscription_id):
        return requests.delete(
            self.cb_endpoint + "/ngsi-ld/v1/subscriptions/" + subscription_id
        )

    def create_subscription_entities(self, id, subscription_endpoint, entities):
        msg = {}
        msg["id"] = "urn:subscription:" + id
        # msg['id'] = 'urn:ngsi-ld:Subscription:' + id
        msg["type"] = "Subscription"
        msg["entities"] = entities
        # msg['@context'] = ["https://smart-data-models.github.io/dataModel.AutonomousMobileRobot/StateMessage/examples/example-normalized.jsonld"]

        notification = {}
        notification["endpoint"] = {
            "uri": subscription_endpoint,
            "accept": "application/json",
        }
        msg["notification"] = notification
        headers = {"Content-Type": "application/json", "Link": self.ld_link}

        print("create subscriber: ")
        print(json.dumps(msg, indent=2))

        return requests.post(
            self.cb_endpoint + "/ngsi-ld/v1/subscriptions",
            data=json.dumps(msg),
            headers=headers,
        )


def main():
    # Default Parameters if nothing is set.
    ld_link = 'https://smart-data-models.github.io/dataModel.AutonomousMobileRobot/StateMessage/examples/example-normalized.jsonld; rel="https://www.w3.org/ns/json-ld#context"; type="application/ld+json"'
    cb_endpoint = "http://localhost:9090"
    server_host = "localhost"
    server_port = 2020
    redis_server_host = "localhost"
    redis_server_port = 6379

    # Parse from Python Args
    if len(sys.argv) > 1:
        cb_endpoint = sys.argv[1]
    if len(sys.argv) > 2:
        server_host = sys.argv[2]
    if len(sys.argv) > 3:
        server_port = sys.argv[3]

    print(server_host)
    print(server_port)

    mapf_server = MAPFFiwareServer(server_host, int(server_port), cb_endpoint, ld_link)
    mapf_server.set_redis_connection(redis_server_host, redis_server_port)
    mapf_server.run()


if __name__ == "__main__":
    main()
