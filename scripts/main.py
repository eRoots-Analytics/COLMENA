import threading
import time
import requests
import sys
import logging
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
    plt.ylim(0.95, 1.05)
    plt.title("Generator Speeds")
    plt.legend()
    plt.grid()
    plt.savefig("plots/first_test_omega.png")
    plt.show()

    # ==== PLOT PRIMAL VARIABLE EVOLUTION ====
    df_primal = pd.DataFrame(sim.admm.primal_log)
    pairs = df_primal[["area", "nbr"]].drop_duplicates()
    colors = plt.cm.get_cmap('tab10', len(pairs))
    pair_to_color = {
        (row.area, row.nbr): colors(i) for i, row in pairs.reset_index(drop=True).iterrows()
    }

    plt.figure(figsize=(12, 7))
    for (area, nbr), group in df_primal.groupby(["area", "nbr"]):
        color = pair_to_color[(area, nbr)]
        plt.plot(group["iteration"], group["theta_ii"], color=color, label=f"θ_{area}{area} (original)")
        plt.plot(group["iteration"], group["theta_ij"], linestyle='--', color=color, label=f"θ_{area}{nbr} (copy)")

    plt.xlabel("ADMM Iteration")
    plt.ylabel("θ Values")
    plt.title("Primal Variables Across ADMM Iterations")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

    # ==== PLOT COST FUNCTION COMPONENTS ====
    df_cost = pd.DataFrame(sim.admm.cost_log)

    plt.figure(figsize=(10, 6))
    plt.plot(df_cost["iteration"], df_cost["freq_val"], label="Frequency Cost")
    plt.plot(df_cost["iteration"], df_cost["lagrangian_val"], label="Lagrangian Term")
    plt.plot(df_cost["iteration"], df_cost["convex_val"], label="Convex Term")
    plt.plot(df_cost["iteration"], df_cost["total_cost"], label="Total Cost", linewidth=2, color="black")

    plt.xlabel("ADMM Iteration")
    plt.ylabel("Cost Value")
    plt.title("Cost Function")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


    # ==== PLOT RESIDUAL ====
    iterations = list(range(len(sim.error_save)))
    plt.figure(figsize=(10, 6))
    plt.plot(iterations, sim.error_save, label='Primal Residual (∞-norm)')
    plt.xlabel('ADMM Iteration')
    plt.ylabel('Residual')
    plt.title('Primal Residual')
    plt.grid(True)
    plt.yscale('log')  # logarithmic scale helps see slow convergence
    plt.legend()
    plt.tight_layout()
    plt.show()

    # ==== PLOT MPC HORIZON VARIABLES OF LAST ITERATION - FREQ ====
    plt.figure(figsize=(14, 6))
    for agent_id, agent in sim.agents.items():
        time_horizon = list(range(agent.K + 1))
        plt.plot(time_horizon, agent.vars_saved['freq'], label=f"{agent_id} - Frequency")

    plt.xlabel("MPC Horizon Step")
    plt.ylabel("Frequency [pu]")
    plt.title("MPC Horizon Frequency After Final ADMM Iteration")
    plt.ylim(0.95, 1.05)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

    # ==== PLOT MPC HORIZON VARIABLES OF LAST ITERATION - P_EXCHANGE====
    plt.figure(figsize=(14, 6))
    for agent_id, agent in sim.agents.items():
        time_horizon = list(range(agent.K + 1))
        plt.plot(time_horizon, agent.vars_saved['P_exchange'], label=f"{agent_id} - P_exchange")

    plt.xlabel("MPC Horizon Step")
    plt.ylabel("P_exchange [pu]")
    plt.title("MPC Horizon Frequency After Final ADMM Iteration")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

    print('Ok')