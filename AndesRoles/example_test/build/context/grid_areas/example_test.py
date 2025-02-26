import time
import numpy as np
import requests
import time
import sys
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
        @Channel('behaviorChange')
        @Requirements('GENERATOR')
        #@KPI('erootsusecase/frequency[1s]>1')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS
            HOST_IP = "192.168.68.60" 
            PORT = 5000
            self.andes_url = f"http://{HOST_IP}:{PORT}"
            #responseAndes = requests.get(self.andes_url + '/assign_device')
            #self.device_dict = responseAndes.json()
            self.device_dict = {'model':'REDUAL', 'idx':'GENROU_1'}
            self.t_start = time.time()
        
          
        def sync2Andes(self):
            responseAndes = requests.get(self.andes_url + '/device_sync', params=self.device_dict)
            self.variables = responseAndes.json()
            return responseAndes
        
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

            roleChangeOut = self.device_dict
            roleChangeOut['role'] = self.__class__.__name__
            responseAndes = requests.get(self.andes_url + '/assign_out', params = roleChangeOut)
            return
    
    class GridFormingRole(Role):
        @Metric('frequency')
        @KPI('erootsusecase/frequency[1s]>1')
        @Requirements('GENERATOR')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            HOST_IP = "192.168.68.60" 
            PORT = 5000
            self.andes_url = f"http://{HOST_IP}:{PORT}"
            self.device_dict = {'model':'REDUAL', 'idx':'GENROU_1'}
            self.t_start = time.time()

        def behavior(self):
            responseTimeSync = requests.get(self.andes_url + '/device_sync')
            responseDict = responseTimeSync.json()
            if responseDict['time'] < 10 and not self.kpi_exist:
                return
            roleChangeDict = self.device_dict
            roleChangeDict['param'] = 'is_GFM'
            roleChangeDict['value'] = 1
            responseAndes = requests.get(self.andes_url + '/device_role_change', params = roleChangeDict)

            roleChangeOut = self.device_dict
            roleChangeOut['role'] = self.__class__.__name__
            responseAndes = requests.get(self.andes_url + '/assign_out', params = roleChangeOut)
            return responseAndes

