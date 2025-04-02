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
    Data
)

class OneLayerControl(Service):
    @Data('state_projection', scope = '')
    @Data('device_data', scope = 'area')
    @Context('areas')
    @Metric('deviation')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    #Role that executes the control calculations 
    class AreaDistributedControl(Role):
        @KPI('onelayercontrol/deviation[5s] > 1', scope = 'area')
        @Metric('deviation')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            #A way to define to which area the control is associated with
            self.area = locate

        def build_control_problem(self):
            mpc_problem = empty_problem() 
            for device in self.area.devices:
                #we set the parameters for initial conditions as follows
                #by checking the states that we used
                initial_state_device =self.device_data.get(device)
                mpc_problem.initial_conditions.set(device, initial_state_device)

            #We iterate over the Areas Context
            for area in self.areas.get():
                #we set the parameters for the future state projections of the other areas by 
                #checking the data stored
                mpc_problem.future_states.set(self.state_projection.get(area))
            
            return mpc_problem

        def behavior(self):
            problem = self.build_control_problem()
            problem.solve()

            #We publish in the Data the areas internal solution
            #The ideal would be to overwrite older data publications 
            self.state_projection.publish((self.area, problem.sol))

            #We change the devices values by sending a request to ANDES
            for device in self.area:
                self.set_value_device(device, problem.sol(t=0))

            #We publish the area's stimation for the future of its states
            self.state_projection.publish({self.area.name : problem.sol.x})
    
    #Role that monitors how close the control projection is following the real measures
    #Althought it could probably be combined with the previous role 
    class AreaMonitoringControl(Role):
        @Data('state_projection', scope = '')
        @Data('device_data', scope = 'area')
        @Metric('deviation')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #we initialize the are stored in the agent
            self.area = locate

        def behavior(self):
            actual_state = []
            #The role collects the actual states of the device in the are
            for device in self.area:
                actual_state.append(self.device_data.get(device))

            #The role collects the state projection
            state_projection = self.state_projection.get(self.area)

            #The deviation metric is equal to the differenece between power expected and actual power 
            #This metric is published in the area's scope 
            error = np.norm(state_projection[0] - actual_state)
            self.deviation.publish(error, scope = self.area.name)
