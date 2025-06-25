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
    coordinator = Coordinator(andes) #TODO: to automitize 
    print(f"[Main] Coordinator run loop finished at t = {coordinator.t}")
    
    return coordinator

if __name__ == '__main__':
    sim = main()

    if sim.terminated:
        print("[Main] Simulation completed succesfully.")
    else: 
        print("[Main] Simulation failed.")

    matplotlib.use('TkAgg')
    # === Initialize logs ===
    omega_log = sim.omega_log
    pg_log = sim.pg_log
    pd_log = sim.pd_log

    # === Extract time and data ===
    times = []
    gen_series_omega = defaultdict(list)
    gen_series_pg = defaultdict(list)
    load_series_pd = defaultdict(list)

    for t_idx, (time, omega_by_agent) in enumerate(omega_log):
        times.append(time)
        for agent_id, omega_list in omega_by_agent.items():
            for local_gen_index, omega_val in enumerate(omega_list):
                gen_name = f"A{agent_id}_G{local_gen_index}"
                gen_series_omega[gen_name].append(omega_val)

    for t_idx, (time, pg_by_agent) in enumerate(pg_log):
        for agent_id, pg_dict in pg_by_agent.items():
            for local_gen_index, (gen_id, pg_val) in enumerate(pg_dict.items()):
                gen_name = f"A{agent_id}_G{local_gen_index}"
                gen_series_pg[gen_name].append(pg_val)

    for t_idx, (time, pd_by_agent) in enumerate(pd_log):
        for agent_id, pd_list in pd_by_agent.items():
            for local_load_index, pd_val in enumerate(pd_list):
                load_name = f"A{agent_id}_L{local_load_index}"
                load_series_pd[load_name].append(pd_val)

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

    plt.xlabel(r"Time [s]")
    plt.ylabel(r"\omega")
    plt.xlim(0, Config.tf)
    plt.ylim(0.98, 1.02)
    plt.title(r"Generator Frequency Over Time")
    plt.legend()
    plt.grid()
    plt.tight_layout()
    # plt.savefig("plots/Kundur_Frequency_GenFail1_Uncontrolled.png")
    plt.show()

    # # === Create subplots ===
    # fig, axs = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    # # --- Plot Omega ---
    # for gen_name, omega_vals in gen_series_omega.items():
    #     axs[0].plot(times, omega_vals, label=gen_name)
    # axs[0].set_ylabel(r"$\Omega$")
    # axs[0].set_ylim(0.98, 1.02)
    # axs[0].set_title("Generator Frequency Over Time")
    # axs[0].legend()
    # axs[0].grid()

    # # --- Plot Pg ---
    # for gen_name, pg_vals in gen_series_pg.items():
    #     axs[1].plot(times, pg_vals, label=gen_name)
    # axs[1].set_ylabel(r"$P_{\mathrm{mech, ref}}$ [pu]")
    # axs[1].set_title("Generator Active Power Setpoints Over Time")
    # axs[1].legend()
    # axs[1].grid()

    # # # --- Plot Pd ---
    # # for load_name, pd_vals in load_series_pd.items():
    # #     axs[1].plot(times, pd_vals, label=load_name)
    # # axs[1].set_xlabel("Time [s]")
    # # axs[1].set_ylabel(r"$P_{\mathrm{load}}$ [pu]")
    # # axs[1].set_title("Load Active Power Consumption Over Time")
    # # axs[1].legend()
    # # axs[1].grid()

    # # === Finalize and save ===
    # plt.tight_layout()
    # # plt.savefig("plots/Kundur_GenFail1_Controlled.png", dpi=300)
    # plt.show()



