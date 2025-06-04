import time, os
import numpy as np
import json
import time
import traceback
import queue
import sys
import requests 
import logging
import pyomo.environ as pyo
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
url = 'http://192.168.68.74:5000' + "/print_app"

class GridAreas(Context):
    @Dependencies(*["pyomo", "requests"])
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
        @Dependencies(*["pyomo", "requests"])
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            n_areas = 2
            self.agent_id = os.getenv("AGENT_ID")
            self.states = np.ones(n_areas)
            self.value = np.random.rand(1)
            self.area = 1

        @Persistent()
        def behavior(self):
            model = pyo.ConcreteModel(name='Simple NLP Test')

            # 2. Define variables with bounds and initial values
            #    Initial values can help the solver.
            model.x = pyo.Var(bounds=(1.0, 5.0), initialize=2.0)
            model.y = pyo.Var(bounds=(1.0, 5.0), initialize=2.0)

            # 3. Define the objective function to minimize
            #    Objective: (x - 3.5)^2 + (y - 2.5)^2
            #    The unconstrained minimum is at x=3.5, y=2.5.
            #    With the given bounds [1,5] for x and y, this point is feasible.
            #    The optimal objective value should be 0.
            model.obj = pyo.Objective(expr=(model.x - 3.5)**2 + (model.y - 2.5)**2)

            # 4. Create a solver instance for Ipopt
            #    Pyomo should find 'ipopt' if it's in the PATH (installed by coinor-ipopt package).
            print('Creating Ipopt solver instance...')
            try:
                solver = pyo.SolverFactory('ipopt')
            except Exception as e:
                print(f'Error creating SolverFactory for Ipopt: {e}')
                print('This might indicate a problem with Pyomo or the environment.')
                sys.exit(1)
                device_id = self.agent_i                    #agent_get = self.state_horizon.get()
                self.state_horizon.publish(device_id)
            print("running")
            a = self.state_horizon.get()
            time.sleep(0.1)
