import time
import numpy as np
import flask
import json
import requests
import time
import cvxpy as cp
import traceback
import queue
from test_examples import TestExamples
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
        
class ErootsPowerCaseDecentralised(Service):
    @Channel('frequency', scope= " ")
    @Channel('behaviorChange', scope= " ")
    @Channel('referenceValue', scope = ' ')
    @Channel('timeToBalance', scope = ' ')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.t_start = time.time()
        self.h = 0.03
    
    class AndesTimeSync(Role):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.andes_url = andes_url
            self.t_start = time.time()
            self.t_run = 0.1
            
        @Persistent()
        def behavior(self):
            if (time.time() - self.t_start ) >= self.t_run:
                responseRun = requests.get(andes_url + '/run', params = {'t_run':self.t_run})
                print(responseRun.status_code)
                
    class BasicRole(Role):
        @Channel('frequency')
        @Channel('behaviorChange')
        @Metric('power')
        @Metric('rampUpRate')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS 
            with open('data.json', 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.device_dict = {'model_name': self.model_name, 'idx': self.idx}
            self.t_start = time.time()
            
            #We initialize the variables once
            responseAndes = requests.get(andes_url + '/device_sync', params=self.device_dict)
            self.variables = responseAndes.json()
        
        def sync2Andes(self):
            responseAndes = requests.get(andes_url + '/device_sync', params=self.device_dict)
            self.variables = responseAndes.json()
            print(responseAndes.status_code)
            return responseAndes
        
        def change2Andes(self, param, value):
            roleChangeDict = self.device_dict
            roleChangeDict['param'] = param
            roleChangeDict['value'] = value
            responseAndes = requests.post(andes_url + '/device_role_change', json = self.roleChangeDict)
            print(responseAndes.status_code)
            return responseAndes
        
        def publish_metric(self, param):
            value = self.variables[param]
            self.frequency.publish(value)
        
        @Persistent()
        def behavior(self):
            responseAndes = self.sync2Andes()
            self.publish_metric('omega')
    
    class BehaviorChangeRole(Role):
        @Channel('behaviorChange', scope= " ")
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS 
            with open('data.json', 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.device_dict = {'model_name': self.model_name, 'device_idx': self.idx}
            self.t_start = time.time()
            
        def change2Andes(self, behaviorDict):
            #the role change includes the model_name if not precised
            if behaviorDict['model_name'] is None:
                behaviorDict.uodate(self.device_dict)
            responseAndes = requests.post(andes_url + '/device_role_change', json = behaviorDict)
            print("andes_response is", responseAndes.status_code)
            return responseAndes
        
        @Async(new_behavior = 'behaviorChange')
        def behavior(self, behaviorDict):
            print(f"new_ehavior is {behaviorDict}")
            self.change2Andes(behaviorDict)
        
    class activateSecondaryResponse():
        @Channel('reserveRate')
        @Channel('power')
        @Channel('timeToBalance')
        @KPI('power < 0.05')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS 
            with open('data.json', 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.device_dict = {'model_name': self.model_name, 'device_idx': self.idx}
            self.t_start = time.time()
        
    class EngageSecondaryResponseRole():
        @Channel('timeToBalance')
        @Channel('behaviorChange')
        @KPI('timeToBalance < 100')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS 
            with open('data.json', 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.device_dict = {'model_name': self.model_name, 'device_idx': self.idx}
            self.t_start = time.time()
            self.generator = (self.model_name == 'GENROU')
            self.load = (self.model_name == 'PQ')
        
        def behavior(self):
            behaviorChangeDict = {'param':'u', 'value':1}
            time.sleep(5)
            behaviorChangeDict.update(self.device_dict)
            self.behaviorChange.publish(behaviorChangeDict)
    
    class ControlSecondaryResponseRole():
        @Channel('timeToBalance')
        @Channel('power')
        @Channel('behaviorChange')
        @KPI('-0.05 > power && power < 0.05')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS 
            with open('data.json', 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.device_dict = {'model_name': self.model_name, 'device_idx': self.idx}
            self.t_start = time.time()
            self.h = 0.03
            self.P_change = 0
        
        def get_rate_power(self):
            value = 1
            value = 0.5
            return value
        
        @Async(power = 'power')
        def behavior(self, power):
            power_change_instep = self.get_rate_power()*self.h
            if power > 0:
                power_change = -power_change_instep
            else:
                power_change = power_change_instep
            behaviorChangeDict = {'param':'u', 'value':power_change, 'add':True}
            behaviorChangeDict.update(self.device_dict)
            self.P_change += power_change
            self.behaviorChange.publish(behaviorChangeDict)
    
        
    class OnlineOPF_S1(Role):
        @Channel('OPF_update')
        @Channel('behaviorChange')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS 
            with open('data.json', 'r') as json_file:
                data = json.load(json_file)
            self.grid = data.get('system', None)
            self.t_start = time.time()
            
        
