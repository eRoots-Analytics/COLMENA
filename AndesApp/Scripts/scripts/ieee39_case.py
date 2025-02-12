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
system_ieee.Toggle.set(src='u', attr = 'v', idx='Toggler_1', value=1)
system_ieee.Toggle.set(src='t', attr = 'v', idx='Toggler_1', value=2)
system_ieee.Toggle.set(src='dev', attr = 'v', idx = 'Toggler_1', value = 'GENROU_9')

system_ieee.Toggle.set(src='dev', attr = 'v', idx = 'Toggler_1', value = 'Line_28')
system_ieee.Toggle.set(src='model', attr = 'v', idx = 'Toggler_1', value = 'Line')
system_ieee.Toggle.set(src='u', attr = 'v', idx = 'Toggler_1', value = 0)

if n_genrou == 0:
    system.Toggle.alter(src='model', idx = 'Toggler_1', value = new_model_name)
    system.Toggle.alter(src='u', idx = 'Toggler_1', value = '1')

redual = False
if redual:
    system = aux.build_new_system_legacy(system_ieee, new_model_name='REDUAL', n_redual = 2)

    system.REDUAL.set(src='is_GFM', attr = 'v', idx='GENROU_1', value=1)
    system.REDUAL.set(src='D', attr = 'v', idx='GENROU_1', value=5)
    system.REDUAL.set(src='M', attr = 'v', idx='GENROU_1', value=10)
    system.REDUAL.set(src='is_GFM', attr = 'v', idx='GENROU_2', value=1)
    system.REDUAL.set(src='kv', attr = 'v', idx='GENROU_1', value=0.005)
    system.REDUAL.set(src='kw', attr = 'v', idx='GENROU_1', value=0.1)

    system.REDUAL.prepare()
    system.find_devices()
    system.setup()
    new_model = getattr(system, 'REDUAL')
    system.PFlow.run()
    system.TDS.config.tf = 20
    system.TDS_stepwise.config.criteria = 0
    system.TDS_stepwise.run_set_points(set_points='REDUAL', t_change = 10, t_max = 20)
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

double_model = False
if double_model:
    n_redual = 3
    system_pre = aux.build_new_system_legacy(system_ieee, n_redual =n_redual)
    system = aux.build_new_system(system_pre, model_swap={'REDUAL':['REGCV1', 'REGCP1']})

    system.find_devices()
    system.REDUAL.prepare()
    system.setup()
    system.PFlow.run()
    system.TDS_stepwise.config.criteria = 0
    set_point_dict = [{'model':'REGCV1', 'param':'u', 'value':0, 'add':False, 'idx':'GENROU_1', 't':5}]
    set_point_dict.append({'model':'REGCP1', 'param':'u', 'value':1, 'add':False, 'idx':'GENROU_1', 't':5})
    set_point_dict = [{'model':'REGCV1', 'param':'u', 'value':1, 'add':False, 'idx':'GENROU_1', 't':5}]
    set_point_dict.append({'model':'REGCP1', 'param':'u', 'value':0, 'add':False, 'idx':'GENROU_1', 't':5})

    p0 = system.PQ.p0.v[0]*1.05
    Ppf1 = system.PQ.Ppf.v[0]*1
    Ppf2 = system.PQ.Ppf.v[1]*1
    req0 = system.PQ.Req.v[0]*1
    xeq0 = system.PQ.Xeq.v[0]*1
    system.PQ.config.p2p = 1
    system.PQ.config.p2z = 0
    system.PQ.config.p2i = 0
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.7*Ppf1, 'add':False, 'idx':'PQ_1', 't': 5}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.9*Ppf2, 'add':False, 'idx':'PQ_2', 't': 5}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.1*Ppf1, 'add':False, 'idx':'PQ_1', 't': 20}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.9*Ppf2, 'add':False, 'idx':'PQ_2', 't': 20}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.9*Ppf1, 'add':False, 'idx':'PQ_1', 't': 40}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.1*Ppf2, 'add':False, 'idx':'PQ_2', 't': 40}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.05*Ppf1, 'add':False, 'idx':'PQ_1', 't': 90}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.95*Ppf2, 'add':False, 'idx':'PQ_2', 't': 90}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.7*Ppf1, 'add':False, 'idx':'PQ_1', 't': 120}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.3*Ppf2, 'add':False, 'idx':'PQ_2', 't': 120}]
    system.TDS_stepwise.run_set_points(set_points_dict=set_point_dict,  t_change = 10, t_max = 50)    
    system.TDS_stepwise.load_plotter()
    
    matplotlib.use('TkAgg')
    n_tuple = tuple(range(n_redual))
    ngenrou_tuple = tuple(range(10-n_redual))
    fig, ax = system.TDS_stepwise.plt.plot(system.REGCP1.Qe, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REGCP1.v, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REGCP1.Pe, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REGCP1.v, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REGCP1.a, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REGCV1.Qe, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REGCV1.omega, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REGCV1.Pe, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REGCV1.v, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REGCV1.a, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.PQ.v, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.Bus.v)
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a = ngenrou_tuple)
    _ = 0

multiple_devices = True
if multiple_devices:
    n_redual = 4
    system = aux.build_new_system_legacy(system_ieee, new_model_name='REDUAL', n_redual = n_redual)
    for i in range(n_redual):
        idx = system.REDUAL.idx.v[i]
        system.REDUAL.set(src='is_GFM', attr = 'v', idx=idx, value=0)
        system.REDUAL.set(src='D', attr = 'v', idx=idx, value=10)
        system.REDUAL.set(src='M', attr = 'v', idx=idx, value=10)
        system.REDUAL.set(src='kw', attr = 'v', idx=idx, value=0.1)

    system.REDUAL.set(src='is_GFM', attr = 'v', idx='GENROU_1', value=1)
    system.REDUAL.set(src='is_GFM', attr = 'v', idx='GENROU_3', value=1)
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

    new_model = getattr(system, 'REDUAL')
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
    Ppf1 = system.PQ.Ppf.v[0]*1
    Ppf2 = system.PQ.Ppf.v[1]*1
    req0 = system.PQ.Req.v[0]*1
    xeq0 = system.PQ.Xeq.v[0]*1

    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1*Ppf1, 'add':False, 'idx':'PQ_18', 't': 2}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1*Ppf2, 'add':False, 'idx':'PQ_19', 't': 2.5}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.9*Ppf1, 'add':False, 'idx':'PQ_18', 't': 30}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.1*Ppf2, 'add':False, 'idx':'PQ_19', 't': 30}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.9*Ppf1, 'add':False, 'idx':'PQ_18', 't': 60}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.3*Ppf2, 'add':False, 'idx':'PQ_19', 't': 60}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.05*Ppf1, 'add':False, 'idx':'PQ_18', 't': 90}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.95*Ppf2, 'add':False, 'idx':'PQ_19', 't': 90}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.7*Ppf1, 'add':False, 'idx':'PQ_18', 't': 120}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.3*Ppf2, 'add':False, 'idx':'PQ_19', 't': 120}]

    #set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':0, 'add':False, 'idx':'GENROU_1', 't': 10}]
    #set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':1, 'add':False, 'idx':'GENROU_2', 't': 10}]
    #set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':0, 'add':False, 'idx':'GENROU_2', 't': 30}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':1, 'add':False, 'idx':'GENROU_3', 't': 30}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':0, 'add':False, 'idx':'GENROU_3', 't': 50}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':1, 'add':False, 'idx':'GENROU_4', 't': 50}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':0, 'add':False, 'idx':'GENROU_4', 't': 70}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':1, 'add':False, 'idx':'GENROU_1', 't': 70}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':0, 'add':False, 'idx':'GENROU_1', 't': 90}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':1, 'add':False, 'idx':'GENROU_2', 't': 90}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':0, 'add':False, 'idx':'GENROU_2', 't': 110}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':1, 'add':False, 'idx':'GENROU_4', 't': 110}]

    #system.TDS_stepwise.config.tol = 0.005
    #system.TDS_stepwise.config.g_scale = 0
    #system.TDS_stepwise.run_set_points(set_points_dict = set_point_dict,  t_change = 4, t_max =7.1)    

    model_controller = system.TGOV1N
    model_controller = system.REDUAL
    system.TDS_stepwise.run_secondary_response(models = [], model_input =system.GENROU, set_points_dict = set_point_dict, 
                                               t_max = 1, batch_size = 0.1)    
    system.TDS_stepwise.load_plotter()

    matplotlib.use('TkAgg')
    n_tuple = tuple(range(n_redual))
    ngenrou_tuple = tuple(range(10-n_redual))
    #fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Qe, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.omega, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.delta, a = n_tuple)
    #fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.vref2, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Pe, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Id, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Iq, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.v, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.a, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.PQ.v, a = n_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.TGOV1N.paux, a = ngenrou_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.TGOV1N.pout, a = ngenrou_tuple)
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a = ngenrou_tuple)

    _ = 0

    plt.clf()
    for controller in model_controller.PIcontroller:
        values = controller.history  # Assuming this is a list of numeric values

        # Generate a time axis (you might need to adjust this)
        time = list(range(len(values)))

        if not time or not values or len(time) != len(values): # Check if the data is valid
            print(f"Warning: Invalid data for controller: {controller}")
            continue
        plt.plot(time, values, label=f"Controller {controller.idx}") # Add a label to each plot
        
    plt.xlabel("Time")  # X-axis label
    plt.ylabel("Values")  # Y-axis label
    plt.title("Controller History")  # Plot title
    plt.legend()  # Show the legend (to differentiate controllers)
    plt.grid(True)  # Add a grid for better readability
    plt.tight_layout() # Adjust layout to prevent labels from overlapping
    plt.show()
    _ = 0