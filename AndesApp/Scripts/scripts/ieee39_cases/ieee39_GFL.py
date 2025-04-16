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

if n_genrou == 0:
    system.Toggle.alter(src='model', idx = 'Toggler_1', value = new_model_name)
    system.Toggle.alter(src='u', idx = 'Toggler_1', value = '1')

n_redual = 4
system = aux.build_new_system_legacy(system_ieee, new_model_name='REDUAL', n_redual = n_redual)
for i in range(n_redual):
    idx = system.REDUAL.idx.v[i]
    system.REDUAL.set(src='is_GFM', attr = 'v', idx=idx, value=0)
    system.REDUAL.set(src='D', attr = 'v', idx=idx, value=10)
    system.REDUAL.set(src='M', attr = 'v', idx=idx, value=10)
    system.REDUAL.set(src='kw', attr = 'v', idx=idx, value=0.1)
system.REDUAL.set(src='is_GFM', attr = 'v', idx='GENROU_1', value=0)
system.REDUAL.set(src='is_GFM', attr = 'v', idx='GENROU_3', value=0)
system.REDUAL.prepare()
for i in range(system.IEEEST.n):
    idx = system.IEEEST.idx.v[i]
    system.IEEEST.set(src='u', attr = 'v', idx=idx, value=0)
system.find_devices()
system.setup()
new_model = getattr(system, 'REDUAL')
system.REDUAL.prepare()
system.find_devices()
system.setup()
system.Toggle.set(src='u', attr = 'v', idx='Toggler_1', value=0)
system.PQ.config.p2p = 1
system.PQ.config.p2z = 0
system.PQ.config.p2i = 0
system.PFlow.run()
system.TDS.config.tf = 20
system.TDS_stepwise.config.criteria = 0
set_point_dict = []
#set_point_dict += [{'model':'REDUAL', 'param':'gammap', 'value':0.8, 'add':False, 'idx':'GENROU_1', 't': 5}]
#set_point_dict += [{'model':'REDUAL', 'param':'gammap', 'value':0.8, 'add':False, 'idx':'GENROU_2', 't': 5}]
#set_point_dict += [{'model':'REDUAL', 'param':'Pref', 'value':pref_ini_1, 'add':False, 'idx':'GENROU_1', 't': 5}]
#set_point_dict += [{'model':'REDUAL', 'param':'Pref', 'value':pref_ini_2, 'add':False, 'idx':'GENROU_2', 't': 5}]
p0 = system.PQ.p0.v[0]*1.05
uid_1 = system.PQ.idx2uid('PQ_18')
uid_2 = system.PQ.idx2uid('PQ_19')
Ppf1 = system.PQ.Ppf.v[uid_1]*1
Ppf2 = system.PQ.Ppf.v[uid_2]*1
req0 = system.PQ.Req.v[0]*1
xeq0 = system.PQ.Xeq.v[0]*1
charge_setpoints = setpoints.variable_charge_setpoints(Ppf1, Ppf2)
mode_setpoints = setpoints.mode_setpoints()
set_point_dict += charge_setpoints
#set_point_dict += charge_setpoints + mode_setpoints

#system.TDS_stepwise.config.tol = 0.005
#system.TDS_stepwise.config.g_scale = 0
#system.TDS_stepwise.run_set_points(set_points_dict = set_point_dict,  t_change = 4, t_max =7.1)    
model_controller = system.TGOV1N
model_controller = system.REDUAL
system.TDS_stepwise.run_secondary_response(models = [], model_input =system.GENROU, set_points_dict = set_point_dict, 
                                           t_max = 15, batch_size = 0.1)    
system.TDS_stepwise.load_plotter()
matplotlib.use('TkAgg')
n_tuple = tuple(range(n_redual))
ngenrou_tuple = tuple(range(10-n_redual))
#fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Qe, a = n_tuple)
fig, ax = system.TDS_stepwise.plt.plot(system.Bus.v)
fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a = ngenrou_tuple)
fig, ax = system.TDS_stepwise.plt.plot(system.Bus.a)
_ = 0