import os, sys
import matplotlib as pyplot
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

#
#ad.prepare()
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
print(sys.path)
# Now you can import your package
if __name__ == '__main__':
    _ = 0
    import andes as ad
    from andes.utils.paths import get_case, cases_root, list_cases

import warnings
#warnings.simplefilter("error")
ad.config_logger(30)
list_cases()
line_activate = True
print(andes.__file__)

#We run the normal simulation
matplotlib.use('TkAgg')
system = ad.load(get_case('kundur/kundur_full.xlsx'), setup = False)
"""system.PQ.config.p2p = 1
system.PQ.config.p2i = 0
system.PQ.config.p2z = 0
system.PQ.config.q2q = 1
system.PQ.config.q2i = 0
system.PQ.config.q2z = 0"""

base_case = False
if base_case:
    #system.Toggle.alter(src='u', idx=1, value=0)
    system.setup()
    system.PFlow.run()
    system.TDS_stepwise.config.refresh_event = 1   
    system.TDS_stepwise.run_secondary_response(tmax = 35)
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2,3))
    fig, ax = system.TDS_stepwise.plt.plot(system.TGOV1.paux, a=(0,1,2,3))
    fig, ax = system.TDS_stepwise.plt.plot(system.TGOV1.pout, a=(0,1,2,3))
    fig, ax = system.TDS_stepwise.plt.plot(system.TGOV1.tm, a=(0,1,2,3))
    #pyplot.plot()

controller_case = True
if controller_case:
    system.setup()
    system.PFlow.run()
    system.TDS_stepwise.config.refresh_event = 1   
    system.TDS_stepwise.run_secondary_response(tmax = 40, controller_control=True)
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2,3))
    fig, ax = system.TDS_stepwise.plt.plot(system.EXDC2.vi, a=(0,1,2,3), linestyles=['-.'])
    _= 0
    #pyplot.plot()

stabilizer_case = True
if stabilizer_case:
    system = ad.load(get_case('kundur/kundur_full.xlsx'), setup = False)
    system.TGOV1.prepare()
    system.setup()
    system.PFlow.run()
    system.TDS_stepwise.config.refresh_event = 1   
    system.TDS_stepwise.run_stabilizer_response(tmax = 35, Ks= 500, batch_size = 0.5)
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    #fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2,3))
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2,3), linestyles=['-.'])
    fig, ax = system.TDS_stepwise.plt.plot(system.EXDC2.vi, a=(0,1,2,3), linestyles=['-.'])
    fig, ax = system.TDS_stepwise.plt.plot(system.EXDC2.vout, a=(0,1,2,3), linestyles=['-.'])
    fig, ax = system.TDS_stepwise.plt.plot(system.EXDC2.vp, a=(0,1,2,3), linestyles=['-.'])
    _= 0

    system = ad.load(get_case('kundur/kundur_full.xlsx'), setup = False)
    #system.EXDC2.set(src='busf', idx=1, value='BusFreq_1', attr='v')
    system.add('IEEEST', avr=1, MODE=5, idx=1)
    system.add('BusFreq', bus=1)
    system.IEEEST.alter(src='busf', idx=1, value='BusFreq_1')
    #system.IEEEST.alter(src='busr', idx=1, value=1)
    system.setup()
    system.PFlow.run()
    system.TDS_stepwise.config.refresh_event = 1   
    system.TDS.run()
    system.TDS_stepwise.run_set_points(set_points = None, batch_size = 0.3)
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    df = system.TDS_stepwise.plt.data_to_df()
    v1_data = df["v"]  
    v2_data = df["v2"]
    #fig, ax = system.TDS_stepwise.plt.plot(system.IEEEST.vss, a=(0), linestyles=['-.'])
    _= 0
    #pyplot.plot()
    #pyplot.plot()

