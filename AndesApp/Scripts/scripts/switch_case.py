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
base_case = False
line_activate = True
print(andes.__file__)

#We run the normal simulation
matplotlib.use('TkAgg')
system = ad.load(get_case('kundur/kundur_full.xlsx'), setup = False)
system.add(model='Toggle', param_dict={'model':'Line', 'dev':'Line_8', 't':4, 'idx':2})
system.setup()
if base_case:
    system.PFlow.run()
    system.TDS_stepwise.config.refresh_event = 1   
    system.TDS_stepwise.run_set_points()
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    fig, ax = system.TDS_stepwise.plt.plot(system.Line.v1, a=(7))
    fig, ax = system.TDS_stepwise.plt.plot(system.Line.v2, a=(7), fig=fig, ax=ax, linestyles=['-.'])
    #pyplot.plot()

line_dict = {'u':0,'idx': 15, 'bus1':7, 'bus2':9}
if line_activate:
    system_dict = system.as_dict()
    system.PFlow.run()
    system.TDS_stepwise.run_topology_change(remove_changes=[{'model_name':'Bus', 'idx':7}])
    system.TDS_stepwise.load_plotter()
    