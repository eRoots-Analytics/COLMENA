import numpy as np
import tensorly as tl
import matplotlib
import matplotlib.pyplot as plt
import andes_methods as ad
import time 
from scipy.integrate import odeint
from scipy.optimize import root
import os
from matplotlib2tikz import save as tikz_save

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
ss.PFlow.run()
ss.TDS_colmena.run()
matplotlib.use('TkAgg') 
ss.TDS_colmena.load_plotter()
fig, ax = ss.TDS_colmena.plt.plot(ss.PVD1.Pref, a=0)
fig, ax = ss.TDS_colmena.plt.plot(ss.PVD1.f, a=0)
output_dir = os.path.join('plots', 'plots_cs3')
os.makedirs(output_dir, exist_ok=True)

for a in ss.PVD1._all_vars():
    fig, ax = ss.TDS_colmena.plt.plot(getattr(ss.PVD1, a), a=0)
    output_path = os.path.join(output_dir, f'{a}.pgf')
    fig.savefig(output_path)
    matplotlib.pyplot.close()
