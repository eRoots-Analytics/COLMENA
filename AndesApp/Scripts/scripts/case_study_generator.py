import os, sys

current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
import numpy as np
import tensorly as tl
import matplotlib
import matplotlib.pyplot as plt
import andes_methods as ad_methods
from scipy.integrate import odeint
from scipy.optimize import root
import os, sys
import andes
#import tensorflow as tf
from andes.utils.paths import get_case, cases_root, list_cases
import pandas as pd
import andes as ad
import colmena_test as Colmena
from scipy.optimize import approx_fprime
plt.rcParams['pgf.texsystem'] = 'pdflatex'

current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
print(sys.path)
# Now you can import your package
if __name__ == '__main__':
    _ = 0
    import andes as ad
    from andes.utils.paths import get_case, cases_root, list_cases

ad.config_logger(30)
list_cases()
base_case = False
normal_simulation = False
simulation_environment = False
colmena_environment = True   
kundur_modified_case_a = False
print(andes.__file__)

#We run the normal simulation
matplotlib.use('TkAgg')
ss1 = ad.run(get_case('kundur/kundur_full.xlsx'))
if base_case:
    ss1.PFlow.run()
    ss1.TDS.config.tf = 20
    ss1.TDS.run()
    ss1.TDS.load_plotter()
    old_ss = ss1
    # fig, ax = ss1.TDS.plt.plot(ss1.GENROU.v, a=(0, 3))
    #plt.show()

if normal_simulation:
    #grid setup
    ss = ad.load(get_case('kundur/kundur_full_bimode.xlsx'), setup = False)
    ss.setup()
    ad_methods.initialize_system_data(ss, ss1, ss.GENROU_bimode)
    for uid in range(4):
        idx = uid + 1  
        ss.GENROU_bimode.alter("Mb", idx=idx, value= 0.4)
        ss.GENROU_bimode.alter("Ma", idx=idx, value= 1.5)
    ss.PFlow.run()
    ss.TDS.run()
    ss.TDS.load_plotter()
    df = ss.TDS.plt.data_to_df()
    found1, found2 = ss.TDS.plt.find('omega')
    data = ss.TDS.plt.get_values(found1)
    data = np.array(data)
    data = np.where(data < 1.003, 0, 1)

    x_values = np.linspace(0, ss.TDS.config.tf, data.shape[0])
    fig, axs = plt.subplots(4, 1, figsize=(8, 12))  # 4 plots in 1 column layout

    for i in range(4):
        axs[i].plot(x_values, data[:, i], marker='o', markersize=2)  # Plot each column
        axs[i].set_title(f'Agent {i+1}')
        axs[i].set_ylim([-0.5, 1.5])  # Set y-axis range for binary data
        axs[i].set_ylabel('Role')
        axs[i].grid(True)

    plt.tight_layout()  # Adjust the layout to prevent overlap
    plt.show()
    fig, ax = ss.TDS.plt.plot(ss.GENROU_bimode.omega, a=(0,1,2,3))
    plt.show()

if simulation_environment:
    ss = ad.load(get_case('kundur/kundur_full_bimode.xlsx'), setup = False)
    ss.setup()
    ad_methods.initialize_system_data(ss, ss1, ss.GENROU_bimode)
    ad_methods.setup_system(ss.GENROU_bimode)
    ss.PFlow.run()
    ss.TDS_stepwise.run_batches()
    ss.TDS_stepwise.config.tf = 20
    ss.TDS_stepwise.load_plotter()
    found1, found2 = ss.TDS_stepwise.plt.find('omega')
    data = ss.TDS_stepwise.plt.get_values(found1)
    data = ss.TDS_stepwise.save_roles
    plt.ion()
    ad_methods.plot_roles(data, ss.TDS_stepwise.config.tf, condition=None)
    df = ss.TDS_stepwise.plt.data_to_df()
    fig, ax = ss.TDS_stepwise.plt.plot(ss.GENROU_bimode.omega, a=(0,1,2,3))
    plt.show()

if colmena_environment:
    ss = ad.load(get_case('kundur/kundur_full.xlsx'), setup = False)
    ss.setup()
    ad_methods.initialize_system_data(ss, ss1, ss.GENROU)
    edge1 = Colmena.Edge(ss, adresses = [1,2], model_target = "GENROU", measurement = "omega")
    edge2 = Colmena.Edge(ss, adresses = [3,4], model_target = "GENROU", measurement = "omega")
    edges = [edge1, edge2]
    colmena = Colmena.Colmena(ss, edges)
    ss.edges = edges
    ss.TDS_stepwise.run_batches(colmena)
    

if kundur_modified_case_a:
    #grid setup
    ss = ad.load('kundur_modified_b.xlsx', setup = False)
    ss.TDS.config.tf = 10
    original_M = ss.GENROU_bimode.M.v[0]
    syn_idx = ss.GENROU_bimode.idx.v[0]
    ss.GENROU_bimode.alter("D", idx=syn_idx, value= 0.01)
    ad_methods.initialize_system_data(ss, ss1, ss.GENROU_bimode)
    #ss.GENROU_bimode.alter("M", idx=syn_idx, value= 1)
    ss.GENROU_bimode.alter("Mb", idx=syn_idx, value= 0.6)
    ss.GENROU_bimode.alter("Ma", idx=syn_idx, value= 2)
    ss.setup()
    ss.PFlow.run()
    ss.TDS.run()
    matplotlib.use('TkAgg')
    ss.TDS.load_plotter()
    fig, ax = ss.TDS.plt.plot(ss.GENROU_bimode.omega, a=0)

    output_dir = os.path.join('plots', 'plots_gen_2')
    a = 'omega'
    os.makedirs(output_dir, exist_ok=True)
    output_path1 = os.path.join(output_dir, f'{a}.pgf')
    output_path2 = os.path.join(output_dir, f'{a}.png')
    fig.savefig(output_path1)
    fig.savefig(output_path2)