import time
import numpy as np
import flask
import json
import requests
import time
import cvxpy as cp
import traceback
import queue
from controllers import Stabilizer
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
        
class ErootsDynamicsDecentralised(Service):
    @Channel('frequency', scope= ' ')
    @Channel('behaviorChange', scope= ' ')
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
            
        @Persistent(0.1)
        def behavior(self):
            insync = True
            if insync:
                responseRun = requests.get(andes_url + '/run', params = {'t_run':self.t_run})
            elif (time.time() - self.t_start ) >= self.t_run:
                responseRun = requests.get(andes_url + '/run', params = {'t_run':self.t_run})
                self.t_start = time.time()
                print(responseRun.status_code)
                
    class BasicRole(Role):
        @Channel('frequency')
        @Channel('behaviorChange')
        @Metric('power')
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
            responseAndes = requests.get(andes_url + '/device_sync', params = self.device_dict)
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
        
    class failureLocation(Role):
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
        
    class overloadProtection(Role):
        @Channel('behaviorChange')
        @Channel('voltage')
        @Requirements('Line')
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
            
        @Persistent()
        def behavior(self):
            params = ['v1', 'a1', 'v2', 'a2']
            values = {}
            for param in params:
                dictionary_info_v1 = self.device_dict
                dictionary_info_v1['param'] = param
                responseParam =  requests.get(andes_url + '/specific_device_sync', params = self.device_dict)
                value = responseParam.json()['value']
                values[params] = value
    
    class islandDetection(Role):
        @Channel('island')
        @Metric('voltage')
        @KPI('')
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
    
    class stabilizerRole(Role):
        @Channel('island')
        @Metric('voltage')
        @KPI('voltage')
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
            self.controller = Stabilizer()

        @Persistent()
        def behavior(self):
            inputs = self.controller.get_input_vars()
            for input in inputs:
                responseAndes = requests.get(andes_url + '/device_sync', params = input)
            input_signal = self.controller.compute_input(responseAndes)
            output_signal = self.controller.apply(input_signal)
            responseAndes = requests.get(andes_url + '/device_sync', params = input)