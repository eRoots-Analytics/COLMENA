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
import os, sys
from andes.utils.paths import get_case, cases_root, list_cases
import andes as ad
from copy import deepcopy



ieee_file = get_case('kundur/kundur_full.xlsx')
ieee_file = get_case('ieee39/ieee39_full.xlsx')

ad.config_logger(stream_level=10)
system = ad.load(ieee_file, setup = False)
system.setup()
system.PFlow.run()
system.TDS.init()
initial_delta = []
initial_a = []
for i in system.GENROU.delta.v:
    initial_delta.append(deepcopy(i))
    print(f"initial angle is {i}")
for i in system.Bus.a.v:
    initial_a.append(deepcopy(i))
    print(f"initial bus angle is {i}")

system.TDS.run()

lines = [7,17,20,31,21]
for i, line_id in enumerate(system.Line.idx.v):
    print(i)
    if i+1 in lines:
        bus_1 = system.Line.bus1.v[i]
        bus_2 = system.Line.bus2.v[i]
        bus_1 = system.Bus.idx2uid(bus_1)
        bus_2 = system.Bus.idx2uid(bus_2)
        print(system.Bus.a.v[bus_1] - system.Bus.a.v[bus_2])

for i, delta in enumerate(system.GENROU.delta.v):
    print(f"delta diff a is {delta - initial_delta[i]}")
for i, delta in enumerate(system.Bus.a.v):
    print(f"delta diff b is {delta - initial_a[i]}")

system.TDS_stepwise.run()

exit()
system.TDS_stepwise.load_plotter()


matplotlib.use('TkAgg')
#fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Qe, a = n_tuple)
fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.delta)
fig, ax = system.TDS_stepwise.plt.plot(system.Bus.a, a = (0,1,2,3))
_ = 0
