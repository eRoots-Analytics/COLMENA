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
system.add(model='Toggle', param_dict={'model':'Line', 'dev':'Line_8', 't':4, 'idx':2})
system.setup()
base_case = False
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
line_activate = False
if line_activate:
    system_dict = system.as_dict()
    system.PFlow.run()
    ad.config_logger(stream_level=20)        
    system.TDS_stepwise.run_topology_change(remove_changes=[{'model_name':'Bus', 'idx':7}])
    system.TDS_stepwise.load_plotter()

system_intermittent = False
#Chnages mades
#A: changed gamma_p value
#B: changed droop constrant R value
#C: changed turbine pout value
#D: changed turbine pref value 
#E: changed load p2p value
#F: changed load p0 value
set_points = ['intermittent', 'droop', 'turbine', 'pref', 'load', 'load_p0' ]
variables = ['pout', 'pout', 'pout', 'pref', 'v', 'v']
models = ['TGOV1', 'TGOV1', 'TGOV1', 'TGOV1', 'PQ', 'PQ']
initialize = 4
set_points_diff = set_points[initialize:]
if system_intermittent:
    for i, set_point in enumerate(set_points_diff):
        system = ad.load(get_case('kundur/kundur_full.xlsx'), setup = False)
        system.setup()
        system.PFlow.run()
        system.TDS_stepwise.run_set_points(set_points = set_point)
        system.TDS_stepwise.load_plotter()
        matplotlib.use('TkAgg')
        fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2,3))
        fig, ax = system.TDS_stepwise.plt.plot(system.TGOV1.pref, a=(0,1,2,3))
        ax.set_title(set_point)

        model_name = models[initialize + i]
        var_name = variables[initialize + i]
        model = getattr(system, model_name)
        var = getattr(model, var_name)
        fig, ax = system.TDS_stepwise.plt.plot(var, a=(0))
        ax.set_title(set_point)
        #fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(1), fig=fig, ax=ax, linestyles=['-.'])
        #pyplot.plot()

system_converter = False
if system_converter:
    system = ad.run(get_case('ieee14/ieee14_pvd1_bis.xlsx'))
    #system.as_dict()
    ad.config_logger(stream_level=20)  
    system.PFlow.run()      
    system.TDS.run()
    #system.TDS_stepwise.run_set_points(set_points = 'converter')
    system.TDS.load_plotter()
    matplotlib.use('TkAgg')
    fig, ax = system.TDS.plt.plot(system.PVD1.v, a=(0))
    fig, ax = system.TDS.plt.plot(system.PVD1.v, a=(1), fig=fig, ax=ax, linestyles=['-.'])
    #pyplot.plot()

governor_bis = False
if governor_bis:
    system = ad.load(get_case('kundur/kundur_full.xlsx'), setup = False)
    system_dict = system.as_dict()
    system_to = ad.System()
    for i in range(2):
        idx = system.TGOV1.idx.v[i]
        syn = system.TGOV1.syn.v[i]
        system_to.add(model = 'TGOV1_bis', param_dict= {'idx':idx, 'syn':syn, 'p_add':0.1})
    for model, param_dict in system_dict.items():
        for i in range(len(param_dict['u'])):    
            if model == 'TGOV1' and i < 2:
                continue    
            new_dict = {key: value[i] for key, value in param_dict.items() if isinstance(value, list) or isinstance(value, np.ndarray)}
            system_to.add(model, new_dict)
    system =system_to
    system.setup()
    system.PFlow.run()
    system.TDS_stepwise.run_set_points(set_points = 'PQ')
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2,3))
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(1), fig=fig, ax=ax, linestyles=['-.'])
    #pyplot.plot()


dynload = True
if dynload and False:
    system = ad.load(get_case('kundur/kundur_full.xlsx'), setup = False)
    for i in range(1):
        idx = system.PQ.idx.v[i]
        bus = system.PQ.bus.v[i]
        zip_dict = {"idx": i,
        "u": 1.0,
        "name": "ZIP_" + str(i),
        "pq": "PQ_0",
        "kpp": 50.0,
        "kpi": 40.0,
        "kpz": 10.0,
        "kqp": 100.0,
        "kqi": 0.0,
        "kqz": 0.0,
        'bus': bus
        }
        fload_dict = {"idx": i, "pq": "PQ_0", "bus":bus}
        #system.add(model = 'ZIP', param_dict= zip_dict)
        system.add(model = 'FLoad', param_dict= fload_dict)
    system.setup()
    system.PFlow.run()
    system.TDS_stepwise.run_set_points(set_points = 'load_p0')
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0))
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(1), fig=fig, ax=ax, linestyles=['-.'])
    #pyplot.plot()


dynload_pq = True 
if dynload_pq:
    system = ad.load(get_case('kundur/kundur_full.xlsx'), setup = False)
    """system.PQ.config.p2p = 1
    system.PQ.config.p2i = 0
    system.PQ.config.p2z = 0
    system.PQ.config.q2q = 1
    system.PQ.config.q2i = 0
    system.PQ.config.q2z = 0
    system.Toggle.alter(src='u', idx=1, value=0)
"""
    system.setup()
    system.PFlow.run()
    system.TDS_stepwise.run_set_points(set_points = 'load_p0', tmax = 18)
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2,3))
    fig, ax = system.TDS_stepwise.plt.plot(system.PQ.v, a=(0,1), linestyles=['-.'])
    #pyplot.plot()

dynload_fload = False
if dynload_fload:
    system = ad.load(get_case('ieee14/ieee14_fload.json'), setup = False)
    system.FLoad.set(src='busf', idx='FLoad_1', value='BusFreq_3', attr='v')
    system.setup()
    system.PFlow.run()
    system.TDS_stepwise.run_set_points(set_points = 'fload')
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2,3))
    fig, ax = system.TDS_stepwise.plt.plot(system.FLoad.v, a=(0), linestyles=['-.'])
    #pyplot.plot()

dynload_zip = True
if dynload_zip:
    system = ad.load(get_case('ieee14/ieee14_zip.json'), setup = False)
    #system.ZIP.set(src='busf', idx='ZIP_1', value='BusFreq_3', attr='v')
    system.setup()
    system.PFlow.run()
    system.TDS_stepwise.run_set_points(set_points = 'ZIP')
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2,3))
    fig, ax = system.TDS_stepwise.plt.plot(system.ZIP.a, a=(0), linestyles=['-.'])
    #pyplot.plot()

usecase_pq = False
if usecase_pq:
    system = ad.load(get_case('kundur/kundur_full.xlsx'), setup = False)
    system.setup()
    system.PFlow.run()
    system.TDS_stepwise.run_set_points(set_points = 'load_p0')
    #system.TDS_stepwise.run_set_points(set_points = None)
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2,3))
    fig, ax = system.TDS_stepwise.plt.plot(system.PQ.v, a=(0), linestyles=['-.'])
    #pyplot.plot()


usecase_motor = True
if usecase_motor:
    system = ad.load(get_case('kundur/kundur_motor.xlsx'), setup = False)
    system.setup()
    system.PFlow.run()
    system.TDS_stepwise.run_set_points(set_points = 'motor')
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2,3))
    fig, ax = system.TDS_stepwise.plt.plot(system.Motor5.p, a=(0), fig=fig, ax=ax, linestyles=['-.'])
    #pyplot.plot()

usecase_vsc = False
if usecase_vsc:
    system = ad.load(get_case('ieee14/ieee14_regcp1_nopll.json'), setup = False)
    system.setup()
    system.PFlow.run()
    system.TDS_stepwise.run_set_points(set_points = None)
    system.TDS_stepwise.load_plotter()
    matplotlib.use('TkAgg')
    fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega, a=(0,1,2,3))
    fig, ax = system.TDS_stepwise.plt.plot(system.Motor5.p, a=(0), fig=fig, ax=ax, linestyles=['-.'])