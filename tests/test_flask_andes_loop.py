import threading
import time
import requests
import sys
import numpy as np
from pathlib import Path

# Move to one level up, i.e. project root folder (COLMENA). 
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.config.config import Config
from src.simulator.app import app
from src.controller.coordinator import Coordinator  
from src.simulator.simulator import Simulator  

import pdb

def run_flask_app():
    host = "0.0.0.0"
    app.run(host=host, port=5000, debug=False, threaded=True, use_reloader=False)

def wait_for_server(url, timeout=10):
    print(f"[Test] Waiting for Flask server at {url}...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(url + '/ping')
            if response.status_code == 200:
                print("[Test] Flask server is up!")
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
    print("[Test] Flask server started")
    wait_for_server(Config.andes_url)

    # 2. Create Andes interface
    print("[Test] Initializing Simulator...")
    andes = Simulator()
    print("[Test] Simulator initialized.")

    # 3. Create Coordinator and Run System
    print("[Test] Initializing Coordinator...")
    coordinator = Coordinator(andes, agents=[1, 2]) #TODO: to automitize 
    print("[Test] Coordinator initialized.")

    all_generators = []

    for agent in coordinator.agents.values():
        all_generators.extend(agent.generators if isinstance(agent.generators, list) else list(agent.generators.keys()))

    # 3.1 Send one setpoint at the beginning
    setpoint = {
        "model": "GENROU",
        "idx": "GENROU_1",
        "var": "tm0",
        "value": 0.5
    }

    print("[Send] Sending setpoint...")
    andes.send_setpoint(setpoint)
    print(f"[Send] Sent tm0 setpoint.")
    
    # 3.2 Iteration loop 
    t = 0
    T = Config.tf
    dt = Config.tstep
    omega_log = []  # To log omega arrays at each step
    # print("[Init] Initializing TDS...")
    # success, start_time = andes.init_tds()
    # if success:
    #     print("[Error] Simulation init failed.")
    # else: 
    #     print("[Error] Simulation init failed.")

    t = andes.start_time
    while t < T:
        print(f"[Loop] Time {t:.2f}")

        # Run one simulation step
        success, new_time = andes.run_step()
        if not success:
            print("[Error] Simulation step failed.")
            break

        # Retrieve omega values
        omega = andes.get_partial_variable("GENROU", "omega", all_generators)
        omega_log.append((new_time, omega))
        t = new_time

    print("[Test] Simulation completed.")
    return omega_log


### Run test ###
if __name__ == "__main__":
    omega_log = main()

    import matplotlib
    matplotlib.use('TkAgg')  

    import matplotlib.pyplot as plt
    
    # Unpack data
    times = [t for t, _ in omega_log]
    omegas = list(zip(*[omega for _, omega in omega_log]))  # Transpose to per-generator

    # Plot
    plt.figure()
    for i, omega_series in enumerate(omegas):
        plt.plot(times, omega_series, label=f"Gen {i}")
    plt.xlabel("Time [s]")
    plt.ylabel("Omega")
    plt.title("Generator Speeds")
    plt.legend()
    plt.grid()
    plt.savefig("tests/test_plots/test_flask_andes_omega.png")
    plt.show()