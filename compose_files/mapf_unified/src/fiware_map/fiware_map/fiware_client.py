import requests
from requests.exceptions import ConnectionError
import json
import os
import sys
import time
from ament_index_python.packages import get_package_share_directory


def register_map(endpoint, data):
    print("Register map", flush=True)
    response = None
    for i in range(10):
        try:
            response = requests.request(
                url=endpoint, data=str(data), method="POST", headers={}, timeout=None
            )
        except ConnectionError:
            print("ConnectionError, Try again")
            time.sleep(3.0)
        else:
            print(response.text, flush=True)
            return


def main():
    route_name = "rmf1"
    endpoint = "http://localhost:9091"
    # Parse from Python Args
    if len(sys.argv) > 1:
        endpoint = sys.argv[1]
    if len(sys.argv) > 2:
        route_name = sys.argv[2]

    folder_path = os.path.join(
        get_package_share_directory("fiware_map"),
        "maps",
    )
    files = [
        f
        for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f))
    ]

    for file in files:
        print("Load Map from file: " + str(folder_path) + "/" + str(file))

        with open(folder_path + "/" + file) as file:
            register_map(endpoint + "/" + route_name, file.read())


if __name__ == "__main__":
    main()
