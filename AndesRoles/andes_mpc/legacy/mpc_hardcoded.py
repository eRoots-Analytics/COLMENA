import time, os
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
andes_url = 'http://192.168.68.67:5000'
class MPC_agent():
    def __init__(self, **kwargs):
        self.T = kwargs.get("T", 20)
        self.dt = kwargs.get("dt", 0.1)
        self.rho = kwargs.get("rho", 1)
        self.gamma = kwargs.get("T", 1e3)
        self.error = kwargs.get("error", 1e3)
        self.tol = kwargs.get("tol", 1e-4)

    def setup_mpc(self):
        return
    
    def initialize_admm(self):
        self.dual_vars = {}
        self.dual_vars[area] = 0
        for area in self.neighbors:
            self.dual_vars[area] = 0

    def warm_start(self):
        self.dual_vars = {}

class AgentControl(Service):
    @Data(name = 'state_horizon_1')
    @Data(name = 'state_horizon_2')
    @Data(name = 'dual_vars_1')
    @Data(name = 'dual_vars_2')
    @Data(name = 'iteration_1')
    @Data(name = 'iteration_2')
    @Metric('frequency')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class LayerOne(Role):
        @Requirements('AREA')
        @Dependencies(*["pyomo", "requests"])
        @Data(name = 'state_horizon_1')
        @Data(name = 'state_horizon_2')
        @Data(name = 'dual_vars_1')
        @Data(name = 'dual_vars_2')
        @Data(name = 'iteration_1')
        @Data(name = 'iteration_2')
        @Metric('frequency')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.agent_id = os.getenv('AGENT_ID')
            self.area = self.agent_id[-1]
            self.neighbors = requests.get(andes_url + '/neibour_area', params={'area':self.area}).json()['value']
            self.iter = 0
            self.state_horizon_own = getattr(self,'state_horizon_' + str(self.area))
            self.state_horizon_other = getattr(self,'state_horizon_' + str(2 if self.area == 1 else 1))

            self.iterations_own = getattr(self,'iterations_' + str(self.area))
            self.iterations_other = getattr(self,'iterations_' + str(2 if self.area == 1 else 1))

            self.dual_vars_own = getattr(self,'dual_vars_own' + str(self.area))
            self.dual_vars_other = getattr(self,'dual_vars_other' + str(2 if self.area == 1 else 1))
            
            MPC_agent.__init__(self, **kwargs)
            self.setup_mpc()
            self.initialize_admm()

        @Persistent()
        def behavior(self):
            self.error = 100
            self.iter = 0

            while self.error > self.tol:
                self.initialize_admm()
                solver = pyo.SolverFactory('ipopt')
                #print_all_variables(model)
                tee = False
                solver.options["halt_on_ampl_error"] = "yes"
                result = solver.solve(self.model, tee=tee)
                
                #We publish the new state_horizon on our own channel
                state_horizon = {}
                self.state_horizon_own = self.state_horizon_own.get().decode('utf-8')
                self.state_horizon_other = self.state_horizon_other.get().decode('utf-8')
                for t in self.model.TimeHorizon:
                    state_horizon[self.area, self.area, t] = self.model.delta[t].value
                    for area_i in self.model.other_areas:
                        state_horizon[area_i, self.area, t] = self.model.delta_areas[area_i, t].value
                self.state_horizon_own.publish(state_horizon)

                #we update the agents iteration number
                self.iter += 1
                iterations = json.loads(self.iterations_own.get().decode('utf-8')) 
                iterations[self.area] += self.iter 
                self.iterations_own.publish(iterations) 

                #We wait for all the agents to get to the same iteration 
                iterations = json.loads(self.iterations_other.get().decode('utf-8'))
                while not all(value == self.iter for value in iterations.values()): 
                    iterations = json.loads(self.iterations_other.get().decode('utf-8'))
                    time.sleep(0.01)

                #Agent i updates the dual variables lambda_{j,i}
                dual_vars_own = json.loads(self.dual_vars_own.get().decode('utf-8')) 
                state_horizon_other = json.loads(self.state_horizon_other.get().decode('utf-8'))
                for t in self.model.TimeHorizon:
                    for area_i in self.model.other_areas:
                        dual_vars_own[area_i, t] += self.rho*(self.model.delta[t].value - state_horizon_other[self.area, t])
                self.dual_vars_own.publish(dual_vars_own) 

                if self.iter > 200:
                    break
            
            self.change_roles()