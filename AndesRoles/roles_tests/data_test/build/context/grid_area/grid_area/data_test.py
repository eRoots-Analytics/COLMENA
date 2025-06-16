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
            self.model = self.setup_mpc()

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
                
            
            print('Checking Ipopt availability through Pyomo...')
            if not solver.available(exception_flag=False):
                print('Ipopt is NOT available to Pyomo according to solver.available().')
            try:
                exe_path = solver.executable()
                print(f'Pyomo\'s expected executable path for Ipopt: {exe_path if exe_path else "Not found or not set"}')
            except Exception as e_path:
                print(f'Error obtaining executable path from Pyomo: {e_path}')
                print('Ensure Ipopt is installed correctly and in the system PATH.')
                sys.exit(1)

            print(f'Ipopt found by Pyomo. Executable: {solver.executable()}')
            print(f'Ipopt version (if available through solver): {solver.version()}')

            # 6. Solve the model
            print('Attempting to solve the NLP problem with Ipopt...')
            try:
                # tee=True will show Ipopt's console output during the solve process.
                results = solver.solve(model, tee=True)
            except Exception as e:
                print(f'An error occurred during solver.solve(): {e}')
                print('This could be an issue with the model, solver, or their interaction.')
                sys.exit(1)
            device_id = self.agent_i                    #agent_get = self.state_horizon.get()
            self.state_horizon.publish(device_id)
            print("running")
            a = self.state_horizon.get()
            time.sleep(0.1)
