import time
import numpy as np
import requests
import time
import sys
import json
import uuid
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
    Data
)

HOST_IP = '192.168.68.67'
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

class DeviceName(Context):

    def whateveryouwant(self, device):
        return uuid.uuid4()

class ErootsUseCase(Service):
    @Metric('frequency')
    @Context(class_ref=GridAreas, name="grid_areas")
    @Context(class_ref=GridAreas, name="grid_areas")
    @Channel('behaviorChange', scope= ' ')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.t_start = time.time()                
                
    class MonitoringRole(Role):
        @Metric('frequency')
        @Channel('frequency_monitor')
        @Requirements('GENERATOR')
        @Data(name = 'monitoring_data', scope = 'erootsusecase/device_name')
        #@KPI('erootsusecase/frequency[1s]>1')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS
            PORT = 5000
            self.andes_url = f"http://{HOST_IP}:{PORT}"
            responseAndes = requests.get(self.andes_url + '/assign_device')
            self.device_dict = responseAndes.json()
            self.t_start = time.time()
        
        def change2Andes(self, param, value):
            roleChangeDict = self.device_dict
            roleChangeDict['param'] = param
            roleChangeDict['value'] = value
            responseAndes = requests.get(self.andes_url + '/device_role_change', params = self.roleChangeDict)
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
        @Requirements('TRANSFORMER')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            PORT = 5000
            self.andes_url = f"http://{HOST_IP}:{PORT}"
            responseAndes = requests.get(self.andes_url + '/assign_device', params = {'role':self.__class__.__name__})
            self.device_dict = responseAndes.json()
            self.t_start = time.time()

        def behavior(self):
            print('Grid Forming Mode Changed 1')
            requests.post(self.andes_url + '/print_var', json = {'keys':['v','is_GFM']})
            roleChangeDict = self.device_dict
            roleChangeDict['var'] = 'is_GFM'
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
        @Requirements('GENERATOR')
        @KPI('erootsusecase/frequency[1s]>1.0001')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS
            PORT = 5000
            self.andes_url = f"http://{HOST_IP}:{PORT}"
            #responseAndes = requests.get(self.andes_url + '/assign_device')
            #self.device_dict = responseAndes.json()
            self.device_dict = {'model':'GENROU', 'idx':'GENROU_5'}
            PI_params = self.device_dict.get('PI_params', {})
            self.t_start = time.time()
            self.t_last = time.time()
            self.reference = PI_params.get('reference', 1)
            self.Ki = PI_params.get('Ki', 10)
            self.Kp = PI_params.get('Kp', -10)
            self.ctrl_input = PI_params.get('ctrl_input', 1)
            self.x = 0
            self.first = True
        
        @Persistent()
        def behavior(self):
            query_dict = self.device_dict
            query_dict['var'] = 'omega'
            responseAndes = requests.get(self.andes_url + '/specific_device_sync', params=self.device_dict)
            print("Dict is", responseAndes.json())
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
            roleChangeDict = {}
            roleChangeDict['model'] = 'TGOV1N'
            roleChangeDict['idx'] = 'TGOV1_5'
            roleChangeDict['var'] = 'paux0'
            roleChangeDict['value'] = 10
            #time.sleep(0.2)
            responseAndes = requests.post(self.andes_url + '/device_role_change', json = roleChangeDict)
            return responseAndes
