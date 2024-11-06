import numpy as np
import tensorly as tl
import matplotlib
import matplotlib.pyplot as plt
import andes_methods as ad
import time 
from scipy.integrate import odeint
from scipy.optimize import root
from matplotlib2tikz import save as tikz_save
#import tensorflow as tf

from scipy.optimize import approx_fprime

if __name__ == '__main__':
    import andes
    from andes.utils.paths import get_case, cases_root, list_cases

import andes
andes.config_logger(30)
base_case = True
individual_case = False
time.sleep(10)
#We set up an R-L-C setup
case1 = True
case2 = True

if case1:
    ss = andes.System()
    ss.add("Bus")
    ss.add("Bus")

    AC_dict = {"bus1": 1, "bus2": 1, "V":1, "a":2}
    RLC_dict = {"bus1": 1, "bus2": 1, "R":0.5, "L":0.3, "C":0.2}

    ss.add("V_Source_AC", param_dict= AC_dict)
    ss.add("RLC_AC", param_dict= RLC_dict)
    ss.PFlow.run()
    ss.TDS.run()

if case2:
    ss2 = andes.System()
    ss2.add("Bus")
    ss2.add("Node")
    ss2.add("Node")

    VSC_dict = {"bus":1, "node1":1, "node2":2, "Sn":1, "fn":60,  "busf": "Bus_Freq1", "pqflag": 1, "qmx": 0.33, "qmn":-0.33,
                'v0':0.8, 'v1':1.1, 'dqdv':-1, 'fdbd':-0.017, 'ddn':5, 'ialim':1.1, 'vt0':0.88, 'vt1':0.9, 'vt2':1.1, 'vt3':1.2,
                'vrflag':0, 'ft0':59.5, 'ft1':59.7, 'ft2':60.3, 'ft3':60.5, 'frflag':0, 'tip':0.02, 'tiq':0.02,'gammap':0.1,'gammaq':0.1}
    R_dict = {"bus1": 1, "bus2": 1, "R":0.5}
    busf_dict= {"bus":1, 'Tf':0.02, 'Tw':0.02, 'fn':60}
    
    ss2.add("VSC", param_dict= VSC_dict)
    ss2.add("BusFreq", param_dict= busf_dict)
    ss2.PFlow.run()
    ss2.TDS.run()
