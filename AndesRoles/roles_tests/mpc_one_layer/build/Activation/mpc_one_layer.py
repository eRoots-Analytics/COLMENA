import time
import numpy as np
import json
import time
import traceback
import queue
import requests 
import logging
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

#Service to deploy a one layer control
url = 'http://192.168.10.137:5000'
class GridAreas(Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.structure = {
            "floor1": ["reception"],
            "floor2": ["reception", "open_space"],
            "floor3": ["open_space", "manager_office"],
        }

    def locate(self, device):
        print(self.structure["floor1"][0])

class AgentControl(Service):
    @Channel(name = 'state_horizon', scope=' ')
    @Context(class_ref= GridAreas, name = 'grid_area')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class LayerOne(Role):
        @Channel(name = 'state_horizon')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            n_areas = 2
            self.states = np.ones(n_areas)
            self.value = np.random.rand(1)
            self.area = 1
            self.logger.info("Print")
            print("hi")

        def solve(self):
            return 1
                
        @Async(updated_state = "state_horizon")
        def behavior(self, updated_state):
            payload = {'message':updated_state}
            response = requests.post(url, json=payload)
            try:
                a = updated_state
            except:
                updated_state = np.zeros(2)
            print("we updated the state", updated_state)
            response = requests.post(url, json={'state':updated_state})
            area = updated_state[0]
            value = updated_state[1]
            self.state_horizon.publish([self.area, self.value])
            time.sleep(0.2)
            return 1
        
    class Activation(Role):
        @Channel('state_horizon')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            n_areas = 2
            self.states = np.ones(n_areas)
            self.value = np.random.rand(1)
            self.area = 1
            self.logger.info("Print")
            print("hi")

        def solve(self):
            return 1
        
        @Persistent()
        def behavior(self):
            self.state_horizon.publish([self.area, self.value])
            time.sleep(3)
            print("hi")
            return 2