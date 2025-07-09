import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
import seaborn as sns
import os
from collections import defaultdict
from colmenasrc.config.config import Config

def plot_omegas(coordinator):
    omega_log = coordinator.omega_log
    times = []
    gen_series = defaultdict(list)

    # Actual generator omega logging
    for time, omega_by_agent in omega_log:
        times.append(time)
        for agent_id, omega_list in omega_by_agent.items():
            for local_gen_index, omega_val in enumerate(omega_list):
                gen_name = f"A{agent_id}_G{local_gen_index}"
                gen_series[gen_name].append(omega_val)

    # Plot actual generator omega time series
    plt.figure()
    color_map = {}

    for idx, (gen_name, omega_vals) in enumerate(gen_series.items()):
        line, = plt.plot(times, omega_vals, label=gen_name)
        color_map[gen_name] = line.get_color()

    # Formatting
    plt.xlabel("Time [s]", fontsize=12)
    plt.ylabel("Frequency [Hz]", fontsize=12)
    plt.title("Generator Frequency Time Series", fontsize=14)
    plt.grid(True, alpha=0.3)

    # Move legend outside
    plt.legend(title="Generators", bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)
    plt.tight_layout(rect=[0, 0, 0.85, 1])  # leave space on right for legend
    output_dir = './home/output_plots'
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(f'./home/output_plots/omegas_plot1_area_{Config.case_name}_{Config.failure}.png')


    try:
        plt.show()
    except:
        _ = 0

from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

def plot_omega_coi(coordinator):
    # Step 1: Group actual omega_coi by time
    time_grouped = defaultdict(dict)
    for t, area_dict in coordinator.omega_coi_log:
        for area, value in area_dict.items():
            time_grouped[t][str(area)] = value  # Normalize to string

    sorted_times = sorted(time_grouped.keys())
    all_areas = sorted({area for d in time_grouped.values() for area in d})

    print(f"[DEBUG] Actual areas: {all_areas}")
    print("[DEBUG] Predicted areas:", sorted(set(k for _, d in coordinator.omega_coi_prediction_log for k in d.keys())))


    # Assign colors
    palette = sns.color_palette("husl", len(all_areas))
    area_colors = {area: palette[i] for i, area in enumerate(all_areas)}

    # Step 2: Organize actual data
    actual_data = {area: [] for area in all_areas}
    for t in sorted_times:
        data = time_grouped[t]
        for area in all_areas:
            actual_data[area].append(data.get(area, np.nan))

    # Step 3: Plot actual data
    for area in all_areas:
        plt.plot(
            sorted_times,
            actual_data[area],
            label=f"Area {area}",
            color=area_colors[area],
            linewidth=2.5
        )

    # Step 4: Plot predicted trajectories
    if hasattr(coordinator, "omega_coi_prediction_log"):
        for t0, omega_pred_dict in coordinator.omega_coi_prediction_log:
            for area, omega_pred in omega_pred_dict.items():
                area_str = str(area)
                if area_str not in area_colors:
                    print(f"[WARNING] Prediction area {area_str} not in actual data areas!")
                    continue
                t_horizon = [t0 + k * coordinator.tstep for k in range(len(omega_pred))]
                plt.plot(
                    t_horizon,
                    omega_pred,
                    color=area_colors[area_str],
                    alpha=0.3,
                    linewidth=2
                )

    # Formatting
    # Formatting
    plt.xlabel("Time [s]", fontsize=12)
    plt.ylabel("Frequency [Hz]", fontsize=12)
    plt.title("Generator Frequency Time Series", fontsize=14)
    plt.grid(True, alpha=0.3)

    # Move legend outside
    plt.legend(title="Generators", bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)
    plt.tight_layout(rect=[0, 0, 0.85, 1])  # leave space on right for legend

    output_dir = './home/output_plots'
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(f'./home/output_plots/omegas_plot2_area_{Config.case_name}_{Config.failure}.png')

    try:
        plt.show()
    except:
        _ = 0

