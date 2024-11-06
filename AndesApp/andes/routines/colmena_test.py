import numpy as np
import tensorly as tl
import matplotlib
import os, sys
import time
import random
import multiprocessing
from collections import OrderedDict

class Edge:
    def __init__(self, system, collection_uid =-1, adresses = None, collection_name = 'Areac', measurement = 'omega'):
        if adresses is None:
            model = getattr(system, collection_name)
            first_model_name = list(model.service_ref.keys())[0] 
            first_value = model.service_ref[first_model_name]
            self.model_name = first_model_name
            self.adresses = first_value[collection_uid]
            
        else:
            self.model_name = "GENROU_bimode"
            self.adresses = adresses
        self.log_measurement = measurement
        self.log = OrderedDict()
    
    def publish_measurement(self, system, t):
        for uid in self.device_address:
            self.log[(uid, t)] = getattr(system, self.model_name)[uid]
    
    def update_log(self, tnow, tforget):
        t_min = tnow - tforget
        filtered_map = OrderedDict({key: value for key, value in self.log.items() if key[1] > t_min})
        self.log_measurement = filtered_map

    def computeKPI(self, f_kpi = np.mean, f_filter = (lambda x: True)):
        filtered_log = [i for i in self.log.values() if f_filter(i)]
        self.kpi = f_kpi(filtered_log) 
        return
    
    def publish_KPI(self, directory = None):
        self.kpi_directory = directory
        if directory is None:
            return
        with open(directory, 'w') as file:
        # Write the single value to the file
            file.write( str(self.kpi))

class Colmena():
    def __init__(self, system, edges):
        #we construct the needed
        self.system = system
        self.edges = edges
        self.agents = []
        
        for model in system.models:
            if model.role != True:
                continue        
            for idx in model.idx.v:
                self.agents.pushback((model.name, idx))
        
    def define_new_roles(self, t=0):
        dict_results = {}
        for model_name, idx in self.agents:
            model = getattr(self, model_name)
            colmena_binary_parameters = model.colmena_binaries
            if random.random() < 0.2:
                param = random.choice(colmena_binary_parameters)
                dict_results[(model_name, idx)] = param
            for edge in self.edges:
                if idx in edge.adresses:
                    if edge.kpi < 0.997 or edge.kpi > 1.997:
                        dict_results[('GENROU',idx)] = 'A'
        return dict_results
    
    def update_kpi(self):
        for edge in self.edges:
            with open(edge.directory, 'r') as file:
            # Read the value from the file (it will be read as a string)
                kpi = float(file.read())
            
    def run_simulation(self, t_batch = 0.5, tf =20):
        #we run the simulation
        t = 0
        while t < tf:
            self.system.TDS_stepwise.run()
            t = t + 0.5
        return

    def run_batch(self, t=0):
        self.update_kpi()
        self.define_new_roles(t=t)
    
    def run_colmena_sync(self, queue, t=0, tf = 20):
        while t < tf:
            # Wait for a message from Program B (blocking)
            msg_from_edges = queue.get()
            t_dae = queue.get()
            t = t_dae
            if msg_from_edges == "exit":
                print("COLMENA Program exiting loop.")
                break
            
            new_roles = self.define_new_roles(msg_from_edges)
            queue.put(new_roles)

                            
    
            