import time
import numpy as np
import requests
import time
import sys
import deepcopy
import ctrl
import json
sys.path.append('/home/pablo/Desktop/eroots/COLMENA/AndesApp/Scripts/scripts')
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.t_start = time.time()                
                
    class MonitoringRole(Role):
        @Metric('frequency')
        @Channel('frequency_monitor')
        @Requirements('GENERATOR')
        #@KPI('erootsusecase/frequency[1s]>1')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS
            HOST_IP = "192.168.68.61" 
            PORT = 5000
            self.andes_url = f"http://{HOST_IP}:{PORT}"
            responseAndes = requests.get(self.andes_url + '/assign_device')
            self.device_dict = responseAndes.json()
            self.t_start = time.time()
        
          
        def sync2Andes(self):
            responseAndes = requests.get(self.andes_url + '/device_sync', params=self.device_dict)
            self.variables = responseAndes.json()
            return responseAndes
        
        def publish_metric(self, param):
            print("keys are ", self.variables.keys())
            if param not in self.variables.keys():
                requests.post(self.andes_url + '/print_var', json = self.variables)
            value = self.variables[param]
            self.frequency.publish(value)
            return value
        
        @Persistent()
        def behavior(self):
            responseAndes = self.sync2Andes()
            print(f"role 1 synced at {time.time() - self.t_start}")
            value = self.publish_metric('v')
            return
    
    class GridFormingRole(Role):
        @Metric('frequency')
        @KPI('erootsusecase/frequency[1s]>1')
        @Requirements('GENERATOR')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            HOST_IP = "192.168.68.61" 
            PORT = 5000
            self.andes_url = f"http://{HOST_IP}:{PORT}"
            responseAndes = requests.get(self.andes_url + '/assign_device', params = {'role':self.__class__.__name__})
            self.device_dict = responseAndes.json()
            self.t_start = time.time()

        def behavior(self):
            print('Grid Forming Mode Changed 1')
            requests.post(self.andes_url + '/print_var', json = {'keys':['v','is_GFM']})
            roleChangeDict = self.device_dict
            roleChangeDict['param'] = 'is_GFM'
            roleChangeDict['value'] = 1
            responseAndes = requests.post(self.andes_url + '/device_role_change', json = roleChangeDict)
            requests.post(self.andes_url + '/print_var', json = {'keys':['v','is_GFM']})

            roleChangeOut = self.device_dict
            roleChangeOut['role'] = self.__class__.__name__
            responseAndes = requests.post(self.andes_url + '/assign_out', json = roleChangeOut)
            print('Grid Forming Mode Changed 2')
            return responseAndes
    
    class AutomaticGenerationControl(Role):
        @Metric('frequency')
        @Channel('frequency_monitor')
        @Requirements('GENERATOR')
        @KPI('erootsusecase/frequency[1s]>1.01')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS
            HOST_IP = "192.168.68.61" 
            PORT = 5000
            self.andes_url = f"http://{HOST_IP}:{PORT}"
            responseAndes = requests.get(self.andes_url + '/assign_device')
            self.device_dict = responseAndes.json()
            PI_params = getattr(self.device_dict, 'PI_params')
            self.t_start = time.time()
            self.t_last = time.time()
            self.reference = PI_params.get('reference', 1)
            self.Ki = PI_params.get('Ki', 1)
            self.Kp = PI_params.get('Kp', 1)
            self.x = 0
            self.first = True
        
        @Async(u_input="frequency_monitor")
        def behavior(self, u_input):
            if self.first:
                dt=0
                self.first = False
                self.t_last = time.time()
            else:
                dt = time.time()-self.t_last
                self.t_last = time.time()
            self.x += dt*self.Ki*(u_input-self.reference)
            y = self.x + self.Kp*(u_input-self.reference)
            roleChangeDict = self.device_dict
            roleChangeDict['param'] = 'paux0'
            roleChangeDict['value'] = y
            responseAndes = requests.post(self.andes_url + '/device_role_change', json = roleChangeDict)
            return responseAndes
        
    class AutomaticGenerationControl_alt(Role):
        @Metric('frequency')
        @Channel('frequency_monitor')
        @Requirements('GENERATOR')
        @KPI('erootsusecase/frequency[1s]>1.01')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS
            HOST_IP = "192.168.68.61" 
            PORT = 5000
            self.andes_url = f"http://{HOST_IP}:{PORT}"
            responseAndes = requests.get(self.andes_url + '/assign_device')
            self.device_dict = responseAndes.json()
            PI_params = getattr(self.device_dict, 'PI_params')
            self.t_start = time.time()
            self.t_last = time.time()
            self.reference = PI_params.get('reference', 1)
            self.Ki = PI_params.get('Ki', 1)
            self.Kp = PI_params.get('Kp', 1)
            self.ctrl_input = PI_params.get('ctrl_input', 1)
            self.x = 0
            self.first = True
        
        @Persistent()
        def behavior(self):
            responseAndes = requests.get(self.andes_url + '/specific_device_sync', params=self.device_dict)
            u_input = responseAndes.json()['value']
            if self.first:
                dt=0
                self.first = False
                self.t_last = time.time()
            else:
                dt = time.time()-self.t_last
                self.t_last = time.time()
            self.x += dt*self.Ki*(u_input-self.reference)
            y = self.x + self.Kp*(u_input-self.reference)
            roleChangeDict = self.device_dict
            roleChangeDict['param'] = 'TGOV1N'
            roleChangeDict['param'] = 'paux0'
            roleChangeDict['value'] = y
            responseAndes = requests.post(self.andes_url + '/device_role_change', json = roleChangeDict)
            return responseAndes



