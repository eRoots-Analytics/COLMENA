import os, sys
import matplotlib 
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
import numpy as np
import matplotlib.pyplot as plt
import andes_methods as ad_methods
import aux_function as aux
import os, sys
from andes.utils.paths import get_case, cases_root, list_cases
import andes as ad
import colmena_test as Colmena


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


for model, param_dict in system_dict.items():
    #if n_genrou is 0 we just change all generators for 
    if model == gen_model and n_genrou == 0:
        model = new_model_name
    elif model in gen_dependencies and n_genrou == 0:
        continue
    
    elif model == gen_model and n_genrou > 0:
        _ = 0
        
    elif model in gen_dependencies and n_genrou > 0:
        for i in range(n_genrou):
            new_dict = {key: value[i] for key, value in param_dict.items()}
            system_to.add(model, new_dict)
        continue

    for i in range(len(param_dict['u'])):        
        new_dict = {key: value[i] for key, value in param_dict.items() if isinstance(value, list) or isinstance(value, np.ndarray)}
        new_dict_ = 0
        generator_like = ['GENROU', 'REGCV1', 'REGCA1']
        if i < n_genrou and model in generator_like:
            model = 'GENROU'
        elif i < n_genrou + n_GFM and model in generator_like:
            model = 'REGCV1'
        elif i >= n_genrou + n_GFM and model in generator_like:
            model = 'REGCA1'
        system_to.add(model, new_dict)

system_ieee = system        
system = system_to
if n_genrou == 0:
    system.Toggle.alter(src='model', idx = 'Toggler_1', value = new_model_name)
    system.Toggle.alter(src='name', idx = 'Toggler_1', value = 'GENROU_1')
    system.Toggle.alter(src='u', idx = 'Toggler_1', value = '1')

redual = True
if redual:
    system = aux.build_new_system_legacy(system_ieee, new_model_name='REDUAL')
    system.REDUAL.set(src='is_GFM', attr = 'v', idx='GENROU_10', value=1)
    system.REDUAL.set(src='D', attr = 'v', idx='GENROU_10', value=10)
    system.REDUAL.set(src='kv', attr = 'v', idx='GENROU_10', value=0.005)
    system.REDUAL.set(src='kw', attr = 'v', idx='GENROU_10', value=0.1)
    system.REDUAL.set(src='M', attr = 'v', idx='GENROU_10', value=10)

    system.Toggle.set(src='u', attr = 'v', idx='Toggler_1', value=1)
    system.Toggle.set(src='t', attr = 'v', idx='Toggler_1', value=2)

    system.REDUAL.prepare()
    system.find_devices()
    system.setup()
    new_model = getattr(system, 'REDUAL')
    system.PFlow.run()
    system.TDS.config.tf = 20
    system.TDS_stepwise.config.criteria = 0
    system.TDS_stepwise.run_set_points(set_points='REDUAL', t_max = 50, t_change = 35)
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')

    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Qe, a=0)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.omega, a=0)
    #fig, ax = system.TDS.plt.plot(system.REDUAL.dw, a=0)

    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Pe, a=0)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.v, a=0)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.a, a=0)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.S0_y, a=0)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.S1_y, a=0)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.S2_y, a=0)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Ipcmd, a=0)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Iqcmd, a=0)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Ipout, a=0)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Iqout_y, a=0)
    vq = system.dae.ts.y[:, system.REDUAL.vq.a]
    t = system.dae.ts.t
    #system.TDS.plt.plot_data(t, vq * Id,xlabel='Time [s]',ylabel='Ipcmd [pu]')

    fig, ax = system.TDS_stepwise.plt.plot(system.Bus.v, a=tuple(range(39)))
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=tuple(range(8)))

double_model = True
if double_model:
    system = aux.build_new_system(system_ieee, model_swap={'REDUAL':['REGCV1', 'REGCP1']})
    system.find_devices()
    system.setup()
    system.PFlow.run()
    system.TDS.config.tf = 20
    system.TDS_stepwise.config.criteria = 0
    set_point_dict = [{'model':'REGCV1', 'src':'u', 'value':1, 'add':False, 'idx':'GENROU_10'}]
    set_point_dict.append({'model':'REGCP1', 'src':'u', 'value':0, 'add':False, 'idx':'GENROU_10'})
    system.TDS_stepwise.run_set_points(set_points_dict=set_point_dict)
    system.TDS_stepwise.load_plotter()