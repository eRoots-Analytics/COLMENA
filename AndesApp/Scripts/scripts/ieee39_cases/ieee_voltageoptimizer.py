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


ieee_file = get_case('ieee39/ieee39_full.xlsx')
ad.config_logger(stream_level=10)
system = ad.load(ieee_file, setup = False)

#We Substitute the synchronous generators for renewables generators with converters
system_to = ad.System()
system_dict = system.as_dict()
new_model_name = 'REGCV1'
gen_model = 'GENROU'
gen_dependencies = ['IEEEST', 'TGOV1N', 'IEEEX1']
n_GFM = 1
n_GFL = 1
n_genrou = system.GENROU.n - n_GFL - n_GFM

system_ieee = system
system_ieee.Toggle.set(src='u', attr = 'v', idx='Toggler_1', value=1)
system_ieee.Toggle.set(src='t', attr = 'v', idx='Toggler_1', value=2)
system_ieee.Toggle.set(src='dev', attr = 'v', idx = 'Toggler_1', value = 'GENROU_9')
system_ieee.Toggle.set(src='dev', attr = 'v', idx = 'Toggler_1', value = 'Line_28')
system_ieee.Toggle.set(src='model', attr = 'v', idx = 'Toggler_1', value = 'Line')
system_ieee.Toggle.set(src='u', attr = 'v', idx = 'Toggler_1', value = 0)


n_redual = 4
system = aux.build_new_system_legacy(system_ieee, n_redual =n_redual)
system.find_devices()
system.REDUAL.prepare()

for i in range(n_redual):
    idx = system.REDUAL.idx.v[i]
    system.REDUAL.set(src='is_GFM', attr = 'v', idx=idx, value=1)
  
system.setup()
system.PFlow.run()
system.TDS_stepwise.config.criteria = 0

p0 = system.PQ.p0.v[0]*1.05

system.PQ.config.p2p = 1
system.PQ.config.p2z = 0
system.PQ.config.p2i = 0
uid_1 = system.PQ.idx2uid('PQ_18')
uid_2 = system.PQ.idx2uid('PQ_19')
Ppf1 = system.PQ.Ppf.v[uid_1]*1
Ppf2 = system.PQ.Ppf.v[uid_2]*1
req0 = system.PQ.Req.v[0]*1
xeq0 = system.PQ.Xeq.v[0]*1
set_point_dict = []
charge_setpoints = setpoints.variable_charge_setpoints(Ppf1, Ppf2)
mode_setpoints = setpoints.mode_setpoints(value = 1)
set_point_dict += charge_setpoints 
system.TDS_stepwise.run_secondary_response(models = [system.REDUAL], model_input = system.REDUAL, set_points_dict=charge_setpoints, t_max = 20)    
system.TDS_stepwise.load_plotter()

matplotlib.use('TkAgg')
n_tuple = tuple(range(n_redual))
ngenrou_tuple = tuple(range(10-n_redual))
fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Qe, a = n_tuple)
fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Pe, a = n_tuple)
fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.v, a = n_tuple)
fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.delta, a = n_tuple)
fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.a, a = n_tuple)
fig, ax = system.TDS_stepwise.plt.plot(system.PQ.v, a = n_tuple)
fig, ax = system.TDS_stepwise.plt.plot(system.Bus.v)
fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a = ngenrou_tuple)
retu_ = 0