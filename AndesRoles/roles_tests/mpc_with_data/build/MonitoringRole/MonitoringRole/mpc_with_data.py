import time, os
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
    Data,
    Dependencies
)

#Service to deploy a one layer control
url = 'http://192.168.68.67:5000' + "/print_app"

class GridAreas(Context):
    @Dependencies("requests")
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def locate(self, device):
        agent_id = os.getenv('AGENT_ID')
        if agent_id in ['area_a', 'device_a', 'device_b']:
            location = {'id' : 'area_a'}
        if agent_id in ['area_b', 'device_c', 'device_d']:
            location = {'id' : 'area_b'}
        print(json.dumps(location))

class Device(Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def locate(self, device):
        agent_id = os.getenv('AGENT_ID')
        id = {'id':agent_id}
        print(json.dumps(id))

class FirstLayer(Context):
    @Dependencies("requests")
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def locate(self, device):
        agent_id = os.getenv('AGENT_ID')
        if agent_id in ['area_a', 'area_b']:
            location = {'id' : 'firstlayer'}
        else:
            location = {'id': 'secondlayer'}
        print(json.dumps(location))

class AgentControl(Service):
    @Context(class_ref= GridAreas, name = 'grid_area')
    @Context(class_ref= FirstLayer, name = 'first_layer')
    @Data(name = 'state_horizon', scope = 'first_layer/id = .')
    @Data(name = 'device_data', scope = 'grid_area/id = .')
    @Metric('deviation')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class LayerOne(Role):
        @Context(class_ref= GridAreas, name="grid_area")
        @Data(name = 'state_horizon', scope = 'first_layer/id = .')
        @Data(name = 'device_data', scope = 'grid_area/id = .')
        @Requirements('AREA')
        @Dependencies('requests')
        @Metric('deviation')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            n_areas = 2
            self.states = np.ones(n_areas)
            self.value = np.random.rand(1)
            self.agent_id = os.getenv('AGENT_ID')
            self.T = 10
            self.first = True

        @Persistent()
        def behavior(self):
            p_mean = 0
            a_mean = 0

            if self.first:
                device_data = {}
                state_horizon = {}
                self.first = False
                n = 1
            else:
                device_data = json.loads(self.device_data.get().decode('utf-8'))
                state_horizon = json.loads(self.device_data.get().decode('utf-8'))
                n = len(device_data.keys())

            for key, val in device_data.items():
                p_mean += val['P']/n
                a_mean += val['a']/n
            
            area_state = [p_mean, a_mean]
            area_state_horizon = np.tile(area_state, (self.T, 1))
            
            state_horizon[self.agent_id] = area_state_horizon
            self.state_horizon.publish(self.agent_id)

            print(f"state horizon if {state_horizon}")
            area_state = [p_mean, a_mean]
            area_state_constant = np.tile(area_state, (self.T, 1))

            deviation = np.norm(area_state_horizon - area_state_constant)
            self.deviation.publish(deviation)
            time.sleep(0.2)
            return 1

    class MonitoringRole(Role):
        @Context(class_ref= GridAreas, name ="grid_area")
        @Data(name = 'device_data', scope = 'grid_area/id = .')
        @Requirements('DEVICE')
        @Dependencies("requests")
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            n_areas = 2
            self.states = np.ones(n_areas)
            self.value = np.random.rand(1)
            self.agent_id = os.getenv('AGENT_ID')
            self.first = True


        @Persistent()
        def behavior(self):

            if self.first:
                device_data = {}
                self.first = False
            else:
                device_data = json.loads(self.device_data.get().decode('utf-8'))
                
            print(device_data)
            
            p_value = 1 + 0.1*np.random.rand()
            a_value = 1 + 0.1*np.random.rand()
            device_data[self.agent_id] ={'P':p_value, 'a':a_value}
            self.device_data.publish(device_data)
            time.sleep(0.2)
            return 1
