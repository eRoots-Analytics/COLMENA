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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def locate(self, device):
        agent_id = os.getenv('AGENT_ID')
        if agent_id in ['area1', 'device1', 'device2']:
            location = {'id' : 'area1'}
        if agent_id in ['area2', 'device3', 'device4']:
            location = {'id' : 'area2'}
        print(json.dumps(location))

class Device(Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def locate(self, device):
        agent_id = os.getenv('AGENT_ID')
        id = {'id':agent_id}
        print(json.dumps(id))

class FirstLayer(Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def locate(self, device):
        agent_id = os.getenv('AGENT_ID')
        if agent_id in ['area1', 'area2']:
            location = {'id' : 'firstlayer'}
        print(json.dumps(location))

class AgentControl(Service):
    @Context(class_ref= GridAreas, name = 'grid_area')
    @Context(class_ref= FirstLayer, name = 'first_layer')
    @Data(name = 'state_horizon', scope = 'first_layer/id = .')
    @Data(name = 'device_data', scope = 'grid_area/id = .')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class LayerOne(Role):
        @Context(class_ref= GridAreas, name="grid_area")
        @Data(name = 'state_horizon', scope = 'first_layer/id = .')
        @Data(name = 'device_data', scope = 'grid_area/id = .')
        @Requirements('Area')
        @Dependencies('requests')
        @Metric('deviation')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            n_areas = 2
            self.states = np.ones(n_areas)
            self.value = np.random.rand(1)
            self.agent_id = os.getenv('AGENT_ID')
            self.T = 10

        def behavior(self):
            device_data = json.loads(self.device_data.get().decode('utf-8'))
            p_mean = 0
            a_mean = 0
            n = len(device_data.keys())

            for key, val in device_data.item():
                p_mean += val['P']/n
                a_mean += val['a']/n
            
            area_state = [p_mean, a_mean]
            area_state_horizon = np.tile(area_state, (self.T, 1))
            
            state_horizon = json.loads(self.device_data.get().decode('utf-8'))
            state_horizon[self.agent_id] = area_state_horizon
            self.state_horizon.publish(self.agent_id)
            print(state_horizon)

            time.sleep(0.1)
            return 1

    class MonitoringRole(Role):
        @Context(class_ref= GridAreas, name="grid_area")
        @Data(name = 'device_data', scope = 'grid_area/id = .')
        @Requirements('Device')
        @Dependencies("requests")
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            n_areas = 2
            self.states = np.ones(n_areas)
            self.value = np.random.rand(1)
            self.agent_id = os.getenv('AGENT_ID')

        @Persistent()
        def behavior(self):
            data = json.loads(self.device_data.get().decode('utf-8'))
            data[self.agent_id] = self.value
            self.device_data.publish(data)
            print(data)
            time.sleep(0.1)
            return 1
