import numpy as np
import tensorly as tl
import matplotlib
import matplotlib.pyplot as plt
import andes_methods as ad
from scipy.integrate import odeint
from scipy.optimize import root
#import tensorflow as tf

from scipy.optimize import approx_fprime

if __name__ == '__main__':
    import andes
    from andes.utils.paths import get_case, cases_root, list_cases

andes.config_logger(30)
list_cases()
base_case = True
individual_case = False
kundur_modified_case_a = True
kundur_modified_case_b = False


#We run the normal simulation
if base_case:
    matplotlib.use('TkAgg') 
    ss = andes.run(get_case('kundur/kundur_full.xlsx'))
    ss.PFlow.run()
    ss.TDS_colmena.run()
    bus_param = ss.Bus.as_dict()
    gen_param = ss.GENROU.as_dict()
    line_param = ss.Line.as_dict()
    PQ_param = ss.PQ.as_dict()
    matplotlib.use('TkAgg') 
    ss.TDS_colmena.load_plotter()
    fig, ax = ss.TDS_colmena.plt.plot(ss.GENROU.omega, a=(3))
    #plt.show()

#We define a simple 2-bus sstem
if individual_case:
    ss = andes.System()
    bus_params = {key: value[0] for key, value in bus_param.items()}
    gen_params = {key: value[0] for key, value in gen_param.items()}
    PQ_params = {key: value[0] for key, value in gen_param.items()}
    line_params = {key: value[0] for key, value in gen_param.items()}
    gen_params["bus"] = 1
    PQ_params["bus"] = 2
    line_params["bus1"] = 1
    line_params["bus2"] = 2
    
    ss.add("Bus", param_dict = bus_params)
    bus_params["idx"] = 2
    ss.add("Bus", param_dict = bus_params)
    
    ss.add("GENROU_bimode", param_dict = gen_params)
    ss.add("PQ", param_dict = PQ_params)
    ss.add("Line", param_dict = line_params)
    
    ss.PFlow.run()
    ss.TDS.config.tf = 2
    ss.TDS.run()

    ss.TDS.load_plotter()
    plt.show()

if kundur_modified_case_a:
    #grid setup
    #we disconnect the existing synchronous generator
    #and then connect 
    ss = andes.load('kundur_modified.xlsx')
    ad.initialize_system_data(ss, ss.GENROU_bimode)
    ss.TDS.config.tf = 10
    original_M = ss.GENROU_bimode.Mb.v[0]
    syn_idx = ss.GENROU_bimode.idx.v[0]
    ss.GENROU_bimode.alter("Ma", idx = syn_idx, value=100*original_M)
    ss.GENROU_bimode.alter("bus", idx = syn_idx, value=1)
    val = ss.GENROU_bimode.get(src = "e2d0a", idx=syn_idx)
    ss.PFlow.run()
    ss.TDS.run()
    matplotlib.use('TkAgg') 
    ss.TDS.load_plotter()
    fig, ax = ss.TDS.plt.plot(ss.GENROU_bimode.omega, a=0)

if kundur_modified_case_b:
    #grid setup
    #we disconnect the existing synchronous generator
    #and then connect 
    ss = andes.load('kundur_modified.xlsx')
    ad.initialize_system_data(ss, ss.GENROU_bimode)
    ss.TDS.config.tf = 10
    original_M = ss.GENROU_bimode.Mb.v[0]
    ss.GENROU.alter("u", idx = 1, value=0)
    syn_idx = ss.GENROU_bimode.idx.v[0]
    ss.TGOV1.alter("syn", idx = 1, value=syn_idx)
    ss.EXDC2.alter("syn", idx = 1, value=syn_idx)
    ss.GENROU_bimode.alter("Mb", idx = syn_idx, value=1*original_M)
    ss.GENROU_bimode.alter("vf0a", idx = syn_idx, value=1.5)
    ss.GENROU_bimode.alter("vf0b", idx = syn_idx, value=1.5)
    
    ss.PFlow.run()
    ss.TDS.run()
    matplotlib.use('TkAgg') 
    ss.TDS.load_plotter()
    fig, ax = ss.TDS.plt.plot(ss.GENROU_bimode.omega, a=0)
    fig, ax = ss.TDS.plt.plot(ss.GENROU_bimode.vlim.zi, a=0)


           
