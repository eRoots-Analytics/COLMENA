import os, sys
import matplotlib 
current_directory = os.path.dirname(os.path.abspath(__file__))
one_levels_up = os.path.dirname(current_directory)
sys.path.insert(0, one_levels_up)
import numpy as np
from andes.utils.paths import get_case, cases_root, list_cases
import andes as ad
import time 
npcc_file = get_case('npcc/npcc_converters.xlsx')
ad.config_logger(stream_level=10)
system = ad.load(npcc_file, setup = False)

system.setup()
system.REDUAL.prepare()
system.TDS.config.tf = 20
system.PQ.config.p2p = 1
system.PQ.config.p2z = 0
system.PQ.config.p2i = 0
system.PFlow.run()
print(system.REDUAL.is_GFM.v)
time.sleep(1)
system.TDS.config.tf = 5
system.TDS.run()

system.TDS.load_plotter()
matplotlib.use('TkAgg')
#fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Qe, a = n_tuple)
fig, ax = system.TDS.plt.plot(system.Bus.v)
fig, ax = system.TDS.plt.plot(system.GENROU.omega)
fig, ax = system.TDS.plt.plot(system.REDUAL.delta)
fig, ax = system.TDS.plt.plot(system.REDUAL.a)
fig, ax = system.TDS.plt.plot(system.REDUAL.v)
fig, ax = system.TDS.plt.plot(system.Bus.a)
print(system.REDUAL.is_GFM.v)

_ = 0