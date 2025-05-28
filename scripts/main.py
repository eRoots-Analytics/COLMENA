import threading
import time
import requests
import sys
from pathlib import Path

# Move to one level up, i.e. project root folder (COLMENA). 
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.config.config import Config
from src.simulator.api_andes import app
from src.controller.coordinator import Coordinator  
from src.controller.andes_interface import AndesInterface  

import pdb

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
    wait_for_server(Config.andes_url)

    # 2. Create Andes interface
    andes_interface = AndesInterface()

    # 3. Create Coordinator and run simulation
    print("[Main] Initializing Coordinator...")
    coordinator = Coordinator(andes_interface, agents=[1, 2]) #TODO: to automitize 
    coordinator.run_simulation()
    print("[Main] Simulation completed.")

if __name__ == '__main__':
    main()
