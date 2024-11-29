import os, sys
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)

import numpy as np
import tensorly as tl
import matplotlib
import matplotlib.pyplot as plt
import andes_methods as ad
import time 
from scipy.integrate import odeint
from scipy.optimize import root
import os
import aux_function as aux
#from tikzplotlib import save as tikz_save

#import tensorflow as tf

from scipy.optimize import approx_fprime

if __name__ == '__main__':
    import andes
    from andes.utils.paths import get_case, cases_root, list_cases

import andes
andes.config_logger(30)
base_case = True
individual_case = False

ss = andes.run(get_case("ieee14/ieee14_pvd1.xlsx"))
aux.set_config(ss, setup =2)
andes.prepare()
ss.PFlow.run()
ss.TDS_colmena.run()
matplotlib.use('TkAgg') 
ss.TDS_colmena.load_plotter()
fig, ax = ss.TDS_colmena.plt.plot(ss.PVD1.Pref, a=0)
fig, ax = ss.TDS_colmena.plt.plot(ss.PVD1.f, a=0)
output_dir = os.path.join('plots', 'plots_cspv')
os.makedirs(output_dir, exist_ok=True)

for a in ss.PVD1._all_vars():
    fig, ax = ss.TDS_colmena.plt.plot(getattr(ss.PVD1, a), a=0)
    output_path1 = os.path.join(output_dir, f'{a}.pgf')
    output_path2 = os.path.join(output_dir, f'{a}.pnf')
    fig.savefig(output_path1)
    fig.savefig(output_path2)
    matplotlib.pyplot.close()

ss2 = andes.System()