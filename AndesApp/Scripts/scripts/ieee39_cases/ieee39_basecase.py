import os, sys
import matplotlib 
current_directory = os.path.dirname(os.path.abspath(__file__))
one_levels_up = os.path.dirname(current_directory)
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
three_levels_up = os.path.dirname(os.path.dirname(os.path.dirname(current_directory)))
sys.path.insert(0, one_levels_up)
sys.path.insert(0, three_levels_up)
import numpy as np
import matplotlib.pyplot as plt
import aux_function as aux
import os, sys
from andes.utils.paths import get_case, cases_root, list_cases
import andes as ad
import colmena_test as Colmena
import ieee_setpoints as setpoints


ieee_file = get_case('kundur/kundur_full.xlsx')
ad.config_logger(stream_level=10)
system = ad.load(ieee_file, setup = False)
system.setup()
system.PFlow.run()
system.TDS_stepwise.run()

system.TDS_stepwise.load_plotter()
matplotlib.use('TkAgg')
#fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Qe, a = n_tuple)
fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.delta)
fig, ax = system.TDS_stepwise.plt.plot(system.Bus.a, a = (0,1,2,3))
_ = 0