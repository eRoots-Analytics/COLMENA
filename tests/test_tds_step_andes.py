"""
This script is used to compare the tds.run() and tds.itm_step() functions of andes. 
NOTE: a notebook would be much better and interactive!
"""
import sys
import matplotlib
import matplotlib.pyplot as plt
from pathlib import Path

# Move to one level up, i.e. project root folder (COLMENA). 
sys.path.append(str(Path(__file__).resolve().parents[1]))
import andes as ad
from andes.routines.tds import TDS

# Set plotter use
matplotlib.use("TkAgg") 

# Load system
system = ad.load(ad.get_case("ieee39/ieee39_full.xlsx"))
system.files.no_output = True
system.PFlow.run()

# TDS setup
tds = TDS(system)
tds.config.fixt = 1
tds.config.shrinkt = 0
tds.config.tstep = 0.01
tds.config.tf = 1.0
tds.t = 0.0
tds.init()

# Logging
time_history = []
omega_history = [[] for _ in range(len(system.GENROU))]

system.GENROU.tm0.v[0] = 0.5  # increase Pm of first generator

###################### TDS_step test ######################
""""
1. Uncomment this section to test the tds.run() function.
2. Comment the TDS_step test section.
3. Check plots.
"""
# Step-by-step simulation
while tds.t < tds.config.tf:

    # Log current state
    time_history.append(tds.t)
    for i in range(len(system.GENROU)):
        omega_history[i].append(system.GENROU.omega.v[i])

    # Advance one time step
    tds.itm_step()
    tds.t += tds.config.tstep

print("Simulation finished.")

# Plot
plt.figure(figsize=(10, 6))
for i, omega in enumerate(omega_history):
    plt.plot(time_history, omega, label=f'Gen {i+1}')
plt.xlabel("Time [s]")
plt.ylabel("Speed [pu]")
plt.title("Generator Speed ω vs Time")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig("tests/test_plots/test_tds_step_omega.png")
plt.show()
print("Plot saved to tests/test_plots/test_tds_step_omega.png")


###################### TDS test ######################
""""
1. Uncomment this section to test the tds.run() function.
2. Comment the TDS_step test section.
3. Check plots.
"""
# tds.run()
# system.TDS.load_plotter()
# fig, ax = system.TDS.plt.plot(system.GENROU.omega)
# fig.savefig("tests/test_plots/test_tds_omega.png")
# print("Plot saved to tests/test_plots/test_tds_omega.png")