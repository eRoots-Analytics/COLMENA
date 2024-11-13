import time
import numpy as np
import flask
import json
import requests
import time
import traceback
import cvxpy as cp
import traceback
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

andes_url = 'http://127.0.0.1:5000'
current_directory = os.path.dirname(__file__)
json_path = os.path.join(current_directory, 'data.json')

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

class ErootsUseCase(Service):
    @Metric('frequency')
    @Context(class_ref=GridAreas, name="grid_areas")
    @Channel('behaviorChange', scope= ' ')
    @Channel('referenceValue', scope = ' ')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.t_start = time.time()
    
    class AndesTimeSync(Role):
        @Metric('frequency')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.andes_url = andes_url
            self.t_start = time.time()
            self.t_andes = 0
            self.t_run = 0.1
            self.t_max = 20
            
        @Persistent()
        def behavior(self):
            try:
                insync = False
                t_role = time.time() - self.t_start
                if insync:
                    responseRun = requests.get(andes_url + '/run', params = {'t_run':self.t_run})
                    self.t_andes = responseRun.json()['Time']
                    print('Andes is running code:', responseRun.status_code)
                elif self.t_andes + self.t_run <= t_role and self.t_andes < self.t_max:
                    responseRun = requests.get(andes_url + '/run', params = {'t_run':self.t_run})
                    self.t_andes = responseRun.json()['Time']
                    print('Andes is running code:', responseRun.status_code)
                else:
                    print('Andes is not running')
            except Exception as e:
                print(e)
                traceback.print_exc()
                
                
    class BasicRole(Role):
        @Metric('frequency')
        @Channel('behaviorChange')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS 
            with open(json_path, 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.device_dict = {'model_name': self.model_name, 'idx': self.idx}
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
            value = self.publish_metric('omega')
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
                
    
    class BehaviorChangeRole(Role):
        @Channel('behaviorChange')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS 
            with open(json_path, 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.device_dict = {'model_name': self.model_name, 'device_idx': self.idx}
            self.t_start = time.time()
            
        def change2Andes(self, param, value):
            roleChangeDict = self.device_dict
            roleChangeDict['param'] = param
            roleChangeDict['value'] = value
            responseAndes = requests.post(andes_url + '/device_role_change', json = roleChangeDict)
            print(f'Role Change performed at {time.time() - self.t_start} COLMENA time')
            return responseAndes
        
        @Async(new_behavior = 'behaviorChange')
        def behavior(self, new_behavior):
            print(f"new_behavior is {new_behavior}")
            param = new_behavior['param']
            value = new_behavior['value']
            self.change2Andes(param, value)
           
              
            