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
        location = {"id": os.getenv("AGENT_ID")}
        print(json.dumps(location))

class AgentControl(Service):
    @Context(class_ref= GridAreas, name = "grid_area")
    @Data(name = "state_horizon", scope = "grid_area/id = .")
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class LayerOne(Role):
        @Context(class_ref= GridAreas, name="grid_area")
        @Data(name = "state_horizon", scope = "grid_area/id = .")
        @Dependencies("requests")
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            n_areas = 2
            self.agent_id = os.getenv("AGENT_ID")
            self.states = np.ones(n_areas)
            self.value = np.random.rand(1)
            self.area = 1

        @Persistent()
        def behavior(self):
            device_id = self.agent_id
            #agent_get = self.state_horizon.get()
            self.state_horizon.publish(device_id)
            print("running")
            a = self.state_horizon.get()
            time.sleep(0.1)
