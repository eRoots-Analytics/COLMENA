import time
import numpy as np
import json
import time
import traceback
import queue
import requests 
import pyomo.environ as pyo
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
url = 'http://192.168.10.137:5000'
class GridAreas(Context):
    @Dependencies(*["pyomo", "requests"])
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
    @Context(class_ref = GridAreas, name='context')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class LayerOne(Role):
        @Dependencies(*["pyomo", "requests"])
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.states = 1
                
        @Persistent()
        def behavior(self):
            print(requests.__version__)
            a = pyo.ConcreteModel()
            print("import workings")
            return 1