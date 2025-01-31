import time
import numpy as np
import json
import requests
import time
import traceback
import cvxpy as cp
import traceback
import sys
sys.path.append('/home/pablo/Desktop/eroots/COLMENA/AndesApp/Scripts/scripts')
import aux_function as aux
import queue
import os
from colmena import (
    Context,
    Service,
    Role,
    Channel,
    Requirements,
    Metric,
    Persistent,
    Async,
    KPI,
)

andes_url = 'http://localhost:5000'
current_directory = os.path.dirname(__file__)
json_path = os.path.join(current_directory, 'data.json')
data = {'model_name':'REDUAL', 'idx':"GENROU_1"}
class GridAreas(Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.structure = {
            "Area1": {"GENROU":[1,2], "bus": [1,2,7,5,6] },
            "Area2": {"GENROU":[3,4], "bus": [3,4,8,9,10]},
        }

    def locate(self, device):
        model_name = device.model
        idx = device.idx
        for area in self.structure.keys():
            area_info = self.structure[area]
            if model_name in area_info.keys():
                if idx in area_info[model_name]:
                    return area
        return False
    
class GridLines(Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        responseAndesLines = requests.get(andes_url + '/line_pairings')
        responseAndesArea = requests.get(andes_url + '/area_structure')
        self.line_pairings = responseAndesLines.json()
        self.areas = responseAndesArea.json()
        self.structure = {}

    def locate(self, device):
        device_bus = device.Bus
        res = []
        for bus_from, bus_to in self.line_pairings.items():
            if bus_from == device_bus or bus_to == device_bus:
                res.append(bus_from + 'to' + bus_to)
        return res

class ErootsUseCase(Service):
    @Metric('frequency')
    @Context(class_ref=GridAreas, name="grid_areas")
    @Channel('behaviorChange', scope= ' ')
    @Channel('estimationChannel', scope = ' ')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.t_start = time.time()                
                
    class MonitoringRole(Role):
        @Metric('frequency')
        @Channel('behaviorChange')
        @Requirements('GENERATOR')
        @KPI('mean(frequency)[1]')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS 
            data = {'model_name':'REDUAL', 'idx':"GENROU_1"}
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('idx', None)
            self.model_name = data.get('model_name', None)
            self.device_dict = {'model_name': self.model_name, 'idx': self.idx}
            print(self.device_dict)
            self.t_start = time.time()
            self.M_value = 1
            
            #We initialize the variables once
            responseAndes = requests.get(andes_url + '/device_sync', params=self.device_dict)
            self.variables = responseAndes.json()
        
        def sync2Andes(self):
            responseAndes = requests.get(andes_url + '/device_sync', params=self.device_dict)
            self.variables = responseAndes.json()
            return responseAndes
        
        def change2Andes(self, param, value):
            roleChangeDict = self.device_dict
            roleChangeDict['param'] = param
            roleChangeDict['value'] = value
            responseAndes = requests.get(andes_url + '/device_role_change', params = self.roleChangeDict)
            return responseAndes
        
        def publish_metric(self, param):
            value = self.variables[param]
            self.frequency.publish(value)
            return value
        
        @Persistent()
        def behavior(self):
            verbose = True
            responseAndes = self.sync2Andes()
            print(f"role 1 synced at {time.time() - self.t_start}")
            value = self.publish_metric('frequency')
            change = False
            if value > 1.003:
                print(f'here the frequency is {value}')
                self.M_value = 10
                self.behaviorChange.publish({'param':'M', 'value':self.M_value})
                change = True 
            if value < 1.003:
                self.M_value = 1.5
                self.behaviorChange.publish({'param':'M', 'value':self.M_value})
                change = True 
            if change and not verbose:
                print('Parameter M is =', self.M_value)
                print('Omega is', value)
            