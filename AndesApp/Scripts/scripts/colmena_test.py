import numpy as np
import tensorly as tl
import matplotlib
import os, sys
import time
import random
import multiprocessing
from collections import OrderedDict

class Agent:
    def __init__(self, characteristics, edges):
        self.characteristics = characteristics
        self.edges = edges
        
    def execute_role(self):
        return

class Edge:
    def __init__(self, system, id, info_area = None, info_dict = None):
        self.log = {}
        self.addresses = []
        self.model_names = []
        self.measurements = []
        self.kpi = 0
        self.id = id
        
        #in general we will have info_area = (uid, 'Areac')
        if info_dict is None:
            collection_uid, collection_name, measurement = info_area
            model = getattr(system, collection_name)
            first_model_name = list(model.service_ref.keys())[0] 
            first_value = model.service_ref[first_model_name]
            self.model_name = first_model_name
            self.adresses += first_value[collection_uid]
            self.log_measurement = measurement
            
        else:
            for value in info_dict.values():
                address, target_model, measurement = value
                self.measurements.append(measurement)
                self.model_names.append(target_model)
                self.addresses.append(address)
                self.log_measurement = measurement
                self.model_name = target_model
                
    def publish_measurement(self, system, t=0):
        for idx in self.addresses:
            model = getattr(system, self.model_name)
            uid = model.idx2uid(idx)
            value = getattr(model, self.log_measurement).v[uid]
            self.log[(uid, self.model_name, float(t))] = value
    
    def update_log(self, tnow, tforget):
        t_min = tnow - tforget
        filtered_map = OrderedDict({key: value for key, value in self.log.items() if key[2] > t_min})
        self.log = filtered_map

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
        self.KPIs = {}
        
        for model_name in system.models:
            model = getattr(system, model_name)
            if model not in ['GENROU', 'GENROU_bimode']:
                continue        
            for idx in model.idx.v:
                self.agents.pushback((model.name, idx))
        
        edges_id = []
        for i, edge in enumerate(edges):
            edges_id += [i]
            edge.id = i
            for i, address in enumerate(edge.addresses):
                model_name = edge.model_names[i] 
                measurement = edge.measurements[i]
                self.agents.append((address, model_name))                
        self.edges_id = edges
        
    def define_new_roles(self, t=0):
        dict_results = {}
        for idx, model_name in self.agents:
            model = getattr(self.system, model_name)
            for edge in self.edges:
                if (idx) in edge.addresses:
                    if edge.kpi < 0.997 or edge.kpi > 1.003:
                        dict_results[(idx, edge.model_name)] = 'A'
                    else:
                        dict_results[(idx, edge.model_name)] = 'B'
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

                            