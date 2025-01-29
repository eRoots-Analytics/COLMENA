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
    @Metric('power')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.t_start = time.time()
        self.h = 0.03
    
    class updateEstimation(Role):
        @Metric('frequency')
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

            #we read the estimator
            with open('estimator.json', 'r') as json_file:
                self.estimator = json.load(json_file)

            
        #function that updates the estimation 
        def update_data(self, new_data):
            for key, val in new_data.items():
                a = val.a
                v = val.v
                estimator_model = getattr(self.estimator, key)
                estimator_a = estimator_model.a
                estimator_v = estimator_model.v
                estimator_model.v += estimator_v + self.alpha*(estimator_v - v)
                estimator_model.a += estimator_a + self.alpha*(estimator_a - a)
            return

        @Async(new_data ='estimationChannel')
        def behavior(self, new_data):
            self.update_data(new_data)
            # Write back the updated data
            with open('estimator.json', 'w') as json_file:
                json.dump(self.estimator, json_file, indent=4)
            return
        
    class shareEstimation(Role):
        @Metric('frequency')
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
            
            self.estimator = {}
            for key in self.neighbours:
                name = key['name']
                responseAndes = requests.get(andes_url + '/specific_sync_device', params = self.device_dict)
                bus_data = responseAndes.json()
                self.estimator[name] = {'a':0, 'v':1}

            # Write back the updated data
            with open('estimator.json', 'w') as json_file:
                json.dump(self.estimator, json_file, indent=4)


        @Persistent()
        def behavior(self):
            with open('estimator.json', 'r') as json_file:
                estimator = json.load(json_file)
            #for loop not needed
            for neighbour in self.neighbours:
                self.estimationChannel.publish(estimator, neighbour)  
            return
        
    class performLocalMPC(Role):
        @Metric('frequency')
        @Channel('estimationChannel')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            with open('data.json', 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.device_dict = {'model_name': self.model_name, 'idx': self.idx}
        
        def define_mpc(self):
            f_problem = 0
            return f_problem

        @Persistent()
        def behavior(self):

            #We read the estimation data needed
            with open('estimator.json', 'r') as json_file:
                estimator_data = json.load(json_file)
            

            return