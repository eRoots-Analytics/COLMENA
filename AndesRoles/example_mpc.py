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

HOST_IP = "192.168.68.67"
andes_url = 'http://127.0.0.1:5000'
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
    
class ErootsMPC(Service):
    @Channel('estimationChannel', scope ='')
    @Channel('simulationChannel', scope ='')
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
            PORT = 5000
            self.andes_url = f"http://{HOST_IP}:{PORT}"            
            responseAndes = requests.get(self.andes_url + '/assign_area', params={'role':self.__class__.__name__})
            self.area = responseAndes.json()['area']
            self.areas = requests.get(self.andes_url + '/assign_area', params={'role':self.__class__.__name__})
     
        @Async(new_data ='estimationChannel')
        def behavior(self, new_data):
            self.update_data(new_data)
        
    class performMPC(Role):
        @Metric('frequency')
        @Channel('estimationChannel')
        @KPI('erootsmpc/frequency[1s]> 10')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            PORT = 5000
            self.andes_url = f"http://{HOST_IP}:{PORT}"            
            responseAndes = requests.get(self.andes_url + '/assign_area', params={'role':self.__class__.__name__})
            self.area = responseAndes.json()['area']
    
        @Persistent()
        def behavior(self, new_data):
            t0 = time.sleep()
            mpc = self.perform_mpc(new_data)
            #when i send a message through a channel only one agent can read it?
            for area in self.areas:
                self.estimationChannel.publish({self.area: mpc.horizon}, to=area)
            self.change_set_points(mpc.value)