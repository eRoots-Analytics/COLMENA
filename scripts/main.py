import threading
import time
import requests
import sys
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

# Move to one level up, i.e. project root folder (COLMENA). 
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.config.config import Config
from src.simulator.andes_api import app
from src.controller.coordinator import Coordinator  
from src.simulator.andes_wrapper import AndesWrapper  

def run_flask_app():
    # Stop Flask logs
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    # Run app
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
    raise TimeoutError("Flask server did not start in time.")

def main():
    # 1. Start Flask server in background
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True
    flask_thread.start()
    print("[Main] Flask server started")
    wait_for_server(Config.andes_url)

    # 2. Create Andes interface
    print("[Main] Initializing Simulator...")
    andes = AndesWrapper()

    # 3. Create Coordinator
    print("[Main] Initializing Coordinator...")
    coordinator = Coordinator(andes) #TODO: to automitize 
    print(f"[Main] Coordinator run loop finished at t = {coordinator.t}")
    
    return coordinator

if __name__ == '__main__':
    sim = main()

    if sim.terminated:
        print("[Main] Simulation completed succesfully.")
    else: 
        print("[Main] Simulation failed.")

    # Plotting
    import matplotlib
    matplotlib.use("TkAgg") 
    from utils.plotting import plot_omegas, plot_omega_coi
    plot_omegas(sim)
    plot_omega_coi(sim) 
    


