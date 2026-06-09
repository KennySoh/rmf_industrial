import json
import time
import os
import subprocess
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from pymongo import MongoClient, errors
import signal
import sys
from threading import Thread
import psutil  # For handling server process management
import fcntl  # For file locking

# MongoDB connection details
mongo_host = "localhost"
mongo_port = 27016  # Correct port as per your setup
mongo_db = "orion"
mongo_collection = "entities"

# File details
output_file = "exported_entities.json"
upload_directory = "./"  # Directory where the JSON file will be located

# Graceful shutdown flag
running = True
poll_interval = 5  # Poll every 5 seconds
server_timeout = 3  # Timeout for server shutdown

# PID management
server_pid = None  # Save the PID in this variable instead of a file

# Get script directory - all other scripts are in the same launch/ folder
script_dir = os.path.dirname(os.path.abspath(__file__))

class SimpleHandler(BaseHTTPRequestHandler):
    
    def do_POST(self):
        if self.path == '/start_sim': # to be change to /start_sim
            ## pg2 ##
            # subprocess.Popen("tmuxinator start new_logistech", shell=True) 
            ## pg3 ##
            subprocess.Popen("tmuxinator start ihi_p2_final_demo", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) 
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"tmuxinator started")
        elif self.path == '/stop_sim': # to be change to /stop_sim
            ## pg2 ##
            # subprocess.Popen("tmuxinator stop new_logistech", shell=True) # pg2
            ## pg3 ##
            subprocess.Popen("tmuxinator stop ihi_p2_final_demo", shell=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"tmuxinator stopped")
        elif self.path == '/start_iocs':
            # subprocess.Popen("~/IHI_PHASE2_FINAL_DEMO/rmf2_broker_control.sh start", shell=True)
            subprocess.Popen(f"{script_dir}/rmf2_res_broker_control.sh start", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # subprocess.Popen(f"{script_dir}/rmf2_res_broker_control.sh start", shell=True)
            # subprocess.Popen("~/IHI_PHASE2_FINAL_DEMO/rmf2_res_mqtt_control.sh start", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            #subprocess.Popen("~/IHI_PHASE2_FINAL_DEMO/rmf2_res_amqp_control.sh start", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.Popen(f"{script_dir}/rmf2_res_mqtt_control.sh start", shell=True)
            # subprocess.Popen(f"{script_dir}/rmf2_res_amqp_control.sh start", shell=True) #LF comment
            subprocess.Popen(f"{script_dir}/rmf2_device_onboard.sh start", shell=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"IOCS Network started")
        elif self.path == '/stop_iocs':
            subprocess.Popen(f"{script_dir}/rmf2_res_broker_control.sh stop", shell=True)
            subprocess.Popen(f"{script_dir}/rmf2_res_mqtt_control.sh stop", shell=True)
            # subprocess.Popen(f"{script_dir}/rmf2_res_amqp_control.sh stop", shell=True) #LF comment
            subprocess.Popen(f"{script_dir}/rmf2_device_onboard.sh stop", shell=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"IOCS Network stopped")
        elif self.path == '/restart': # to be change to /restart_sim
            subprocess.Popen("tmuxinator stop new_logistech && tmuxinator start new_logistech", shell=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"tmuxinator restarted")
        elif self.path == '/deploy_ai':  # to be changed to /restart_sim
            script_path = os.path.expanduser(f"{script_dir}/run_evaluate_cube_cvrp_v1.sh")
            subprocess.Popen([script_path, "start"], shell=False)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"AI deployed")
        elif self.path == '/stop_ai':
            script_path = os.path.expanduser(f"{script_dir}/run_evaluate_cube_cvrp_v1.sh")
            subprocess.Popen([script_path, "stop"], shell=False)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"AI stopped")
        elif self.path == '/device_onboard': # VDA5050 Initialize
            subprocess.Popen(f"{script_dir}/rmf2_res_vda5050_control.sh start", shell=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"AMR onboarded")
        elif self.path == '/device_offboard': # VDA5050 Down
            subprocess.Popen(f"{script_dir}/rmf2_res_vda5050_control.sh stop", shell=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"AMR offboarded")
        elif self.path == '/service_onboard': # MAPF Initialize
            # subprocess.Popen(f"{script_dir}/rmf2_res_mapf_control.sh start", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.Popen(f"{script_dir}/rmf2_res_mapf_control.sh start", shell=True)
            subprocess.Popen(f"{script_dir}/rmf2_tte_control.sh start", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.Popen(f"{script_dir}/rmf2_rts_control.sh start", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Services onboarded")
        elif self.path == '/service_offboard': # MAPF Down
            subprocess.Popen(f"{script_dir}/rmf2_res_mapf_control.sh stop", shell=True)
            subprocess.Popen(f"{script_dir}/rmf2_tte_control.sh stop", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.Popen(f"{script_dir}/rmf2_rts_control.sh stop", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Services offboarded")
        elif self.path == '/init_system': # Initialize services with devices
            subprocess.Popen(f"{script_dir}/send_init.sh", shell=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"System is initialized")
        elif self.path == '/send_task': # Start rmf2 scheduler and job loader
            subprocess.Popen(f"{script_dir}/rmf2_rts_send_order.sh", shell=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Send task")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Endpoint not found")

    def do_GET(self):
        if self.path == '/exported_entities':
            file_path = os.path.join(upload_directory, output_file)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'rb') as file:
                        # Acquire file lock for reading
                        fcntl.flock(file, fcntl.LOCK_SH)
                        self.send_response(200)
                        self.send_header("Content-type", "application/json")
                        self.send_header("Content-Disposition", f"attachment; filename={output_file}")
                        self.end_headers()
                        self.wfile.write(file.read())
                        fcntl.flock(file, fcntl.LOCK_UN)  # Release lock
                except Exception as e:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(f"Error: {e}".encode())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"File not found")
        elif self.path == '/iocs_heartbeat':
            try:
                # Attempt to fetch the IOCS status
                response = requests.get("http://localhost:8000/status", timeout=3)
                response.raise_for_status()  # Raise an error if the status code is not 200

                # Parse the JSON response
                status_data = response.json().get("data", {})
                all_services_running = all(service.get("status", False) for service in status_data.values())

                if all_services_running:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"IOCS is online.")
                else:
                    self.send_response(503)
                    self.end_headers()
                    self.wfile.write(b"Some IOCS services are not running.")

            except requests.exceptions.RequestException:
                # Handle any error in connecting to the status endpoint
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"IOCS is offline.")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Endpoint not found")

    # Override the log_message method to suppress logging
    def log_message(self, format, *args):
        pass  # This suppresses the standard request logging

    def check_iocs_heartbeat(self):
        try:
            # Make a GET request to the status endpoint
            response = requests.get("http://localhost:8000/status")
            response.raise_for_status()
            
            # Extract status data
            data = response.json()["data"]
            all_status_true = all(service["status"] is True for service in data.values())

            # Return the result
            if all_status_true:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"All IOCS services are running.")
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Some IOCS services are not running.")
        except requests.exceptions.RequestException as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error fetching IOCS status: {e}".encode())


def export_collection():
    try:
        # Establish MongoDB connection
        client = MongoClient(mongo_host, mongo_port, serverSelectionTimeoutMS=5000)
        db = client[mongo_db]
        collection = db[mongo_collection]
        
        # Test the connection
        client.admin.command('ping')
        
        # Query the entire collection
        entities = list(collection.find({}))
        
        # Convert MongoDB documents to JSON serializable format
        for entity in entities:
            if "_id" in entity:
                entity["_id"] = str(entity["_id"])  # Convert ObjectId to string
        
        # Save to a local JSON file with file locking
        file_path = os.path.join(upload_directory, output_file)
        with open(file_path, 'w') as file:
            fcntl.flock(file, fcntl.LOCK_EX)  # Acquire exclusive lock for writing
            json.dump(entities, file, indent=4)
            fcntl.flock(file, fcntl.LOCK_UN)  # Release lock
        
        # print(f"Exported {len(entities)} documents to {file_path}")
        return file_path

    except errors.ServerSelectionTimeoutError as err:
        print(f"Error: Could not connect to MongoDB: {err}")
    except Exception as e:
        print(f"Error during collection export: {e}")
    return None


def signal_handler(sig, frame):
    global running
    print("\nGracefully shutting down...")
    running = False


def run_server(server_class=HTTPServer, handler_class=SimpleHandler):
    global running, server_pid
    server_address = ('', 8083)
    httpd = server_class(server_address, handler_class)
    print("Starting server on port 8083...")

    # Save PID in a variable
    server_pid = os.getpid()
    
    while running:
        try:
            httpd.handle_request()
        except KeyboardInterrupt:
            break
    print("Server is shutting down...")
    httpd.server_close()


if __name__ == "__main__":
    # Register signal handler for SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)

    # Start the HTTP server in a separate thread
    server_thread = Thread(target=run_server)
    server_thread.start()

    try:
        while running:
            start_time = time.time()
            # export_collection()
            while running and (time.time() - start_time < poll_interval):
                time.sleep(1)  # Sleep in small increments, allowing interruption
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        print("Exiting...")
        running = False
        server_thread.join(timeout=server_timeout)  # Ensure server thread finishes

        # Attempt to force kill if necessary
        if server_pid:
            try:
                process = psutil.Process(server_pid)
                process.terminate()  # Attempt graceful termination
                process.wait(timeout=server_timeout)
            except psutil.NoSuchProcess:
                print("Process already terminated.")
            except psutil.TimeoutExpired:
                print("Process did not terminate in time, force killing...")
                process.kill()
        sys.exit(0)
