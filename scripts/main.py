import threading
import time
import requests
import sys
import logging
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
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
    coordinator = Coordinator(andes, agents=[1, 2]) #TODO: to automitize 
    print(f"[Main] Coordinator run loop finished at t = {coordinator.t}")
    
    return coordinator

if __name__ == '__main__':
    sim = main()

    if sim.terminated:
        print("[Main] Simulation completed succesfully.")
    else: 
        print("[Main] Simulation failed.")

    # ==== PLOT OMEGA ====
    matplotlib.use('TkAgg')  
    omega_log = sim.omega_log
    times = []
    gen_series = defaultdict(list)

    for time, omega_by_agent in omega_log:
        times.append(time)
        for agent_id, omega_list in omega_by_agent.items():
            for local_gen_index, omega_val in enumerate(omega_list):
                gen_name = f"A{agent_id}_G{local_gen_index}"
                gen_series[gen_name].append(omega_val)

    plt.figure()
    for gen_name, omega_vals in gen_series.items():
        plt.plot(times, omega_vals, label=gen_name)

    plt.xlabel("Time [s]")
    plt.ylabel("Omega")
    plt.xlim(0, Config.tf)
    plt.ylim(0.995, 1.005)
    plt.title("Generator Speeds")
    plt.legend()
    plt.grid()
    plt.savefig("plots/first_test_omega.png")
    plt.show()

    #
    matplotlib.use('TkAgg')  
    delta_log = sim.delta_log
    times = []
    gen_series = defaultdict(list)

    for time, delta_by_agent in delta_log:
        times.append(time)
        for agent_id, delta_list in delta_by_agent.items():
            for local_gen_index, delta_val in enumerate(delta_list):
                gen_name = f"A{agent_id}_G{local_gen_index}"
                gen_series[gen_name].append(delta_val)

    plt.figure()
    for gen_name, delta_vals in gen_series.items():
        plt.plot(times, delta_vals, label=gen_name)

    plt.xlabel("Time [s]")
    plt.ylabel("Delta")
    plt.xlim(0, Config.tf)
    # plt.ylim(0.95, 1.05)
    plt.title("Generator Delta")
    plt.legend()
    plt.grid()
    # plt.savefig("plots/first_test_omega.png")
    plt.show()

    #
    matplotlib.use('TkAgg')  
    theta_log = sim.theta_log
    times = []
    bus_series = defaultdict(list)

    for time, theta_by_agent in theta_log:
        times.append(time)
        for agent_id, theta_list in theta_by_agent.items():
            for local_bus_index, theta_val in enumerate(theta_list):
                bus_name = f"A{agent_id}_B{local_bus_index}"
                bus_series[bus_name].append(theta_val)

    plt.figure()
    for bus_name, delta_vals in bus_series.items():
        plt.plot(times, delta_vals, label=bus_name)  # fixed line

    plt.xlabel("Time [s]")
    plt.ylabel("Theta")
    plt.xlim(0, Config.tf)
    # plt.ylim(0.95, 1.05)
    plt.title("Bus Angle")
    plt.legend()
    plt.grid()
    # plt.savefig("plots/first_test_omega.png")
    plt.show()

    # ==== PLOT GEN POWER PROFILES ====
    pg_log = sim.pg_log
    times = []
    gen_pg_series = defaultdict(list)

    for time, pg_by_agent in pg_log:
        times.append(time)
        for agent_id, pg_dict in pg_by_agent.items():
            for local_gen_index, (gen_id, pg_val) in enumerate(pg_dict.items()):
                gen_name = f"A{agent_id}_G{local_gen_index}"
                gen_pg_series[gen_name].append(pg_val)

    plt.figure()
    for gen_name, pg_vals in gen_pg_series.items():
        plt.plot(times, pg_vals, label=gen_name)

    plt.xlabel("Time [s]")
    plt.ylabel("Pg [pu]")
    plt.title("Generator Active Power Setpoints")
    plt.grid()
    plt.legend()
    plt.savefig("plots/first_test_pg.png")
    plt.show()

    # ==== PLOT COST ====
    cost_log = sim.admm.cost_log

    iterations = [entry["iteration"] for entry in cost_log]
    freq_vals = [entry["freq_val"] for entry in cost_log]
    lagrangian_vals = [entry["lagrangian_val"] for entry in cost_log]
    convex_vals = [entry["convex_val"] for entry in cost_log]
    total_costs = [entry["total_cost"] for entry in cost_log]

    plt.figure(figsize=(10, 6))
    plt.plot(iterations, freq_vals, label="Frequency Cost")
    plt.plot(iterations, lagrangian_vals, label="Lagrangian Term")
    plt.plot(iterations, convex_vals, label="Convex Term")
    plt.plot(iterations, total_costs, label="Total Cost", linewidth=2)

    plt.xlabel("ADMM Iteration")
    plt.ylabel("Cost Value")
    plt.title("Cost Terms During ADMM Iterations")
    plt.grid()
    plt.legend()
    plt.savefig("plots/first_test_costs.png")
    plt.show()


    # ========== Horizon prediction vs simulation ==========
    t_plot = 26  # scegli un tempo in cui l’MPC ha fatto almeno K iterazioni

    agent_id = 'Agent_1'
    pred = sim.theta_pred_horizon[agent_id][t_plot]  # predizione da t_plot a t_plot+K
    simu = sim.theta_sim_log[agent_id][t_plot:t_plot + len(pred)]  # realtà nei successivi K passi

    time_pred = np.arange(len(pred)) * Config.dt + t_plot * Config.dt

    plt.figure()
    plt.plot(time_pred, pred, '--', label='Predicted θ')
    plt.plot(time_pred, simu, '-', label='Simulated θ')
    plt.xlabel("Time [s]")
    plt.ylabel("Theta [rad]")
    plt.title(f"Horizon prediction vs simulation (t={t_plot}) - {agent_id}")
    plt.legend()
    plt.grid(True)
    plt.show()


