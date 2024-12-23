import os, sys
import matplotlib 
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
import numpy as np
import matplotlib.pyplot as plt
import andes_methods as ad_methods
import os, sys
from andes.utils.paths import get_case, cases_root, list_cases
import andes as ad
import colmena_test as Colmena
plt.rcParams['pgf.texsystem'] = 'pdflatex'

inverter_model = False
if inverter_model:
    system = ad.load(get_case('ieee14/ieee14_pvd1.xlsx'), setup =False)
    system.Toggler.alter(src = 'u', idx = 2, value = 0)
    system.setup()
    system.TDS.config.refresh_event = 0   
    system.find_devices()
    system.PFlow.run()
    system.TDS_stepwise.run_set_points(tmax = 35, set_points = None, batch_size = 0.1)
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2,3))
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2,3), linestyles=['-.'])

inverter_model_bis = True
if inverter_model_bis:
    system = ad.load(get_case('kundur/kundur_reg.xlsx'), setup = False)
    system_original = ad.load(get_case('kundur/kundur_reg.xlsx'), setup = False)
    system_to = ad.System()
    system_dict = system.as_dict()
    new_model = 'REGCA1'
    new_model = 'REGCV1'
    
    for model, param_dict in system_dict.items():
        if model == 'REGCA1':
            model = new_model 
        if model in ['REECA1', 'REPCA1']:
            continue
        for i in range(len(param_dict['u'])):        
            new_dict = {key: value[i] for key, value in param_dict.items() if isinstance(value, list) or isinstance(value, np.ndarray)}
            new_dict_ = 0
            system_to.add(model, new_dict)
    
    system_to.REGCV1.alter(src='D', idx = 1, value =100)
    system_to.REGCV1.alter(src='M', idx = 1, value =100)
    system_to.find_devices()
    system_to.setup()
    system_original.setup()
    system_to.PFlow.run()
    system_original.PFlow.run()

    print('P1 is', system_original.REGCA1.p0)
    print('P1 is', system_to.REGCV1.Pref)
    print('Q1 is', system_original.REGCA1.q0)
    print('Q1 is', system_to.REGCV1.Qref)

    system = system_to
    system.TDS_stepwise.config.refresh_event = 1   
    system.TDS_stepwise.run_secondary_response(tmax = 30, model = system.REGCV1, batch_size = 0.2)
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2))
    fig, ax = system.TDS_stepwise.plt.plot(getattr(system, new_model).omega, a=0, linestyles=['-.'])
    fig, ax = system.TDS_stepwise.plt.plot(getattr(system, new_model).v, a=0, linestyles=['-.'])
    fig, ax = system.TDS_stepwise.plt.plot(getattr(system, new_model).a, a=0, linestyles=['-.'])
    fig, ax = system.TDS_stepwise.plt.plot(getattr(system, new_model).Pref2, a=0, linestyles=['-.'])
    _= 0

gfm_gfl_combined = False
if gfm_gfl_combined:
    system = ad.load(get_case('ieee/ieee14_pvd1.xlsx'), setup = False)
    system_original = ad.load(get_case('ieee/ieee14_pvd1.xlsx'), setup = False)
    system_to = ad.System()
    system_dict = system.as_dict()

    
    for model, param_dict in system_dict.items():
        for i in range(len(param_dict['u'])):        
            if model == 'GENROU' and i==0:
                continue
            new_dict = {key: value[i] for key, value in param_dict.items() if isinstance(value, list) or isinstance(value, np.ndarray)}
            new_dict_ = 0
            system_to.add(model, new_dict)
    system_to.add('REGCV1', idx = 1, gen = 1)
    system_to.find_devices()
    system_to.setup()
    system_to.PFlow.run()

    system = system_to
    system.TDS_stepwise.config.refresh_event = 1   
    system.TDS_stepwise.run_secondary_response(tmax = 30, model = system.REGCV1, batch_size = 0.2)
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2))
    fig, ax = system.TDS_stepwise.plt.plot(getattr(system, new_model).omega, a=0, linestyles=['-.'])