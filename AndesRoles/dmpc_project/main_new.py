import threading
import time
import requests
import os
import sys
from config import Config

# Adjust the path so that ANDES and your Flask app can be imported
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)

from AndesApp.Scripts.scripts.api_andes import app
from coordinator import Coordinator  
from andes_interface import AndesInterface  

def run_flask_app():
    host = "0.0.0.0"
    app.run(host=host, port=5000, debug=False, threaded=True)

def wait_for_server(url, timeout=10):
    print(f"[Main] Waiting for Flask server at {url}...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(url + '/ping')
            if response.status_code == 200:
                print("[Main] Flask server is up!")
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(0.5)
    raise TimeoutError("Flask server did not start in time")

def main():
    # 1. Start Flask server in background
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True
    flask_thread.start()
    print("[Main] Flask server started")

    # 2. Wait until server is ready
    wait_for_server(Config.andes_url)

    # 4. Create Andes interface
    andes_interface = AndesInterface()

    # 5.. Create Coordinator and run simulation
    print("[Main] Initializing Coordinator...")
    coordinator = Coordinator(andes_interface, agents=[1, 2]) #NOTE: to automitize 

    coordinator.run_simulation()
    print("[Main] Simulation completed.")

if __name__ == '__main__':
    main()
