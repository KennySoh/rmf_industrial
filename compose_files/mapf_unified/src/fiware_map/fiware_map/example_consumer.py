import requests
import sys
import json


def register_map(endpoint, data):
    print("endpoint: " + str(endpoint))
    print("endpoint: " + str(data))
    requests.request(url=endpoint, data=str(data), method="POST", headers={})


def main():
    cb_endpoint = "http://localhost:9091"
    # Parse from Python Args
    if len(sys.argv) > 1:
        cb_endpoint = sys.argv[1]
    entity_name = "RMF1"
    headers = {
        "Accept": "application/ld+json",
        "Content-Type": "application/ld+json",
    }
    response = requests.get(
        cb_endpoint + "/ngsi-ld/v1/entities/urn:ngsi-ld:Map:" + entity_name,
        headers=headers,
    )
    if response.status_code == 404:
        print("entity " + entity_name + " does not exist")
        return
    print(json.dumps(json.loads(response.text), indent=2))


if __name__ == "__main__":
    main()
