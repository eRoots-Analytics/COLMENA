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
    Data,
    Dependencies
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

class ErootsUseCase(Service):
    @Metric('frequency')
    @Context(class_ref=GridAreas, name="grid_areas")
    @Channel('behaviorChange', scope= ' ')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.t_start = time.time()                
                
    class MonitoringRole(Role):
        @Metric('frequency')
        @Metric('monitored')
        @Requirements('GENERATOR')
        @KPI('erootsusecase/monitored[1s] < 0.5')
        @Dependencies("requests")
        @Requirements('GENERATOR')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS
            PORT = 5000
            self.andes_url = f"http://{HOST_IP}:{PORT}"            
            self.agent_id = os.getenv('AGENT_ID')
            responseAndes = requests.get(self.andes_url + '/assign_device', params = {'agent': self.agent_id})
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
        
        @Persistent(period = 0.1)
        def behavior(self):
            responseAndes = self.change2Andes()
            print(f"role 1 synced at {time.time() - self.t_start}")
            value = self.publish_metric('omega')
            self.monitored.publish(1)
            return 1
    
    
    class GridFormingRole(Role):
        @Metric('frequency')
        @KPI('erootsusecase/frequency[1s] > 0.998')
        @Dependencies("requests")
        @Requirements('TRANSFORMER')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            PORT = 5000
            self.andes_url = f"http://{HOST_IP}:{PORT}"
            self.agent_id = os.getenv('AGENT_ID')
            responseAndes = requests.get(self.andes_url + '/assign_device', params = {'agent': self.agent_id})
            self.device_dict = responseAndes.json()
            self.t_start = time.time()

        @Persistent(period = 0.1)
        def behavior(self):
            query_dict = self.device_dict
            query_dict['var'] = 'is_GFM'
            responseAndes = requests.get(self.andes_url + '/specific_device_sync', params=query_dict)
            is_GFM = responseAndes.json()['value']

            query_dict['var'] = 'Pe'
            responseAndes = requests.get(self.andes_url + '/specific_device_sync', params=query_dict)
            Pe = responseAndes.json()['value']
            if is_GFM:
                Paux = self.Paux_init - Pe
            else:
                self.Paux_init = Pe
                Paux = 0
            requests.post(self.andes_url + '/print_var', json = {'keys':['v','is_GFM']})
            roleChangeDict = self.device_dict
            roleChangeDict['var'] = 'is_GFM'
            roleChangeDict['value'] = 1
            roleChangeDict['agent'] = self.agent_id
            responseAndes = requests.post(self.andes_url + '/device_role_change', json = roleChangeDict)
            requests.post(self.andes_url + '/print_var', json = {'keys':['v','is_GFM']})

            roleChangeDict['var'] = 'Paux'
            roleChangeDict['value'] = Paux*0.5
            #responseAndes = requests.post(self.andes_url + '/device_role_change', json = roleChangeDict)

            print('Grid Forming Mode Changed 2')
            return responseAndes
        
    class AutomaticGenerationControl(Role):
        @Metric('frequency')
        @Requirements('GENERATOR')
        @KPI('erootsusecase/frequency[1s] > 0.998')
        @Dependencies("requests")
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS
            PORT = 5000
            self.andes_url = f"http://{HOST_IP}:{PORT}"
            self.agent_id = os.getenv('AGENT_ID')
            responseAndes = requests.get(self.andes_url + '/assign_device', params = {'agent': self.agent_id})
            self.device_dict = responseAndes.json()
            PI_params = self.device_dict.get('PI_params', {})
            self.t_start = time.time()
            self.t_last = time.time()
            self.reference = PI_params.get('reference', 1)
            self.Ki = PI_params.get('Ki', -40)
            self.Kp = PI_params.get('Kp', -20)
            self.ctrl_input = PI_params.get('ctrl_input', 1)
            self.x = 0
            self.first = True
        
        @Persistent()
        def behavior(self):
            query_dict = self.device_dict
            query_dict['var'] = 'omega'
            responseAndes = requests.get(self.andes_url + '/specific_device_sync', params=query_dict)
            u_input = responseAndes.json()['value']

            query_dict['var'] = 'paux0'
            query_dict['model'] = 'TGOV1N'
            query_dict['idx'] = 'TGOV1_' + self.device_dict['idx'][-1]
            responseAndes = requests.get(self.andes_url + '/specific_device_sync', params=query_dict)
            print("Dict is", responseAndes.json())
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
            roleChangeDict['idx'] = 'TGOV1_' + self.device_dict['idx'][-1]
            roleChangeDict['var'] = 'paux0'
            roleChangeDict['value'] = y
            roleChangeDict['agent'] = self.agent_id
            responseAndes = requests.post(self.andes_url + '/device_role_change', json = roleChangeDict)
            roleChangeDict['var'] = 'paux'
            responseAndes = requests.post(self.andes_url + '/device_role_change', json = roleChangeDict)
            time.sleep(0.1)
            return responseAndes
