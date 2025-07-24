"""
ANDES module for Edge Simulation
"""

import importlib
import logging
import os
import sys
import time
import numpy as np
from collections import OrderedDict
from andes.variables import IdxParam

class Edge:
    def __init__(self, uid, model = 'Area', value = 'v'):
        first_model_name = list(model.service_ref.keys())[0] 
        first_value = model.service_ref[first_model_name]
        self.model_name = first_model_name
        
        self.device_address = first_value[uid]
        self.log_measurement = value
        self.log = OrderedDict()
    
    def publish_measurement(self, system, t):
        for uid in self.device_address:
            self.log[(uid, t)] = getattr(system, self.model_name)[uid]
    
    def update_log(self, tnow, tforget):
        t_min = tnow - tforget
        filtered_map = OrderedDict({key: value for key, value in self.log.items() if key[1] > t_min})
        self.log_measurement = filtered_map

    def computeKPI(self, f_kpi = np.mean(), f_filter = (lambda x: True)):
        filtered_log = [i for i in self.log.values() if f_filter(i)]
        self.kpi = f_kpi(filtered_log) 
        return
        