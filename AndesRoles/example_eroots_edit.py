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
            
    class SecondaryPowerResponse(Role):
        @Metric('frequency')
        @Requirements('GENERATOR')
        @KPI('(mean(abs(deriv(frequency)))< 0.001 && mean(frequency)[1]')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            with open('data.json', 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.device_dict = {'model_name': self.model_name, 'idx': self.idx}
            controller_dict =  {'dt':0.1, 'Kp':0.1, 'Ki':2, 'Uref':1, 'idx':self.idx}
            self.PIcontroller = aux.PIcontroller(**controller_dict)

        @Persistent(it = 10)    
        def behavior(self):
            set_points = self.PIcontroller.get_set_point(input)
            roleChangeDict = set_points.update(self.device_dict)
            responseAndes = requests.get(andes_url + '/device_role_change', params = roleChangeDict)
            return responseAndes
    
    class GridFormingRole(Role):
        @Metric('frequency')
        @KPI('mean(frequency)[1]')
        @Requirements('GFM')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            with open('data.json', 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.device_dict = {'model_name': self.model_name, 'idx': self.idx}
            self.kpi_exist = False

        @Persistent(it = 20)    
        def behavior(self):
            responseTimeSync = requests.get(andes_url + '/device_sync')
            responseDict = responseTimeSync.json()
            if responseDict['time'] < 10 and not self.kpi_exist:
                return
            roleChangeDict = self.device_dict
            roleChangeDict['param'] = 'is_GFM'
            roleChangeDict['value'] = 1
            responseAndes = requests.get(andes_url + '/device_role_change', params = roleChangeDict)
            return responseAndes
        
    class EstimationRole(Role):
        @Metric('frequency')
        @KPI('mean(frequency)[1]')
        @Channel('estimationChannel')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            with open('data.json', 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.device_dict = {'model_name': self.model_name, 'idx': self.idx}

            #We initialize the initial estimation
            self.neighbours = requests.get(andes_url + '/neighbours', params = self.device_dict)
            self.second_neighbours = requests.get(andes_url + '/second_neighbours', params = self.device_dict)
            

        #function that updates the estimation 
        def update_data(new_data):
            return

        @Async(new_data ='estimationChannel')
        def behavior(self, new_data):
            return
        
    

        