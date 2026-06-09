import requests
import sys
import json
from datetime import datetime
import yaml
from flask import Flask, Response, request
from fiware_api.context_broker.scorpio import ScorpioAPI
from fiware_api.utils import (
    printRed,
    printGreen,
    printYellow,
    printPurple,
    printCyan,
    printLightGray,
)

from rmf2_building.Map import Map, Edge, Node, Point2D, ConnectedNode


class FiwareMapServer:
    app = None

    def __init__(self, fiware_map) -> None:
        self.app = Flask("fiware_map_server")
        self.fiware_map = fiware_map
        self.app.add_url_rule(
            "/rmf1", "load_map", self.fiware_map.load_rmf1_map, methods=["POST"]
        )

    def run(self, host, port):
        self.app.run(host=host, port=port)


class FiwareMap:
    def __init__(self, context_broker, ld_link) -> None:
        self.context_broker = context_broker
        self.ld_link = ld_link
        self.headers = {"Content-Type": "application/json", "Link": self.ld_link}

    def load_rmf1_map(self):
        data = request.get_data()
        try:
            parsed_map = yaml.safe_load(data)
        except yaml.YAMLError as exc:
            print(exc)
        if "warehouse" not in parsed_map["levels"]:
            return ""
        if "vertices" not in parsed_map["levels"]["warehouse"]:
            return ""
        if "lanes" not in parsed_map["levels"]["warehouse"]:
            return ""

        nodes = []
        index_dict = dict()
        index = 0
        for item in parsed_map["levels"]["warehouse"]["vertices"]:
            node_name = item[3]
            nodes.append(
                Node(
                    nodeId=node_name,
                    point2D=Point2D(x=float(item[0]), y=float(item[1])),
                )
            )

            index_dict[index] = node_name
            index += 1

        edges = []
        for lane in parsed_map["levels"]["warehouse"]["lanes"]:
            connected_nodes = []

            connected_nodes.append(ConnectedNode(nodeID=index_dict[int(lane[0])]))
            connected_nodes.append(ConnectedNode(nodeID=index_dict[int(lane[1])]))

            edges.append(
                Edge(
                    edgeId=index_dict[int(lane[0])] + "_" + index_dict[int(lane[1])],
                    connectedNodes=connected_nodes,
                )
            )

        map = Map(
            type="Map",
            id=parsed_map["name"],
            updateTime=datetime.now().isoformat(),
            edges=edges,
            nodes=nodes,
            raw=str(parsed_map),
        )

        self.create_map(map)
        return ""

    def create_map(self, map: Map):
        response = self.context_broker.send_entity_message(
            Map.to_json(map), self.headers
        )
        printGreen("Sent map message. Context Broker Response: " + response.text)
        return response


def main():
    # Default Parameters if nothing is set.
    cb_endpoint = "http://localhost:9090"
    server_host = "localhost"
    server_port = "7070"

    # Parse from Python Args
    if len(sys.argv) > 1:
        cb_endpoint = sys.argv[1]
    if len(sys.argv) > 2:
        server_host = sys.argv[2]
    if len(sys.argv) > 3:
        server_port = sys.argv[3]

    context_broker = ScorpioAPI(cb_endpoint)
    fiware_map = FiwareMap(
        context_broker,
        'https://smart-data-models.github.io/dataModel.AutonomousMobileRobot/StateMessage/examples/example-normalized.jsonld; rel="https://www.w3.org/ns/json-ld#context"; type="application/ld+json"',
    )
    map_server = FiwareMapServer(fiware_map)
    map_server.run(server_host, server_port)


if __name__ == "__main__":
    main()
