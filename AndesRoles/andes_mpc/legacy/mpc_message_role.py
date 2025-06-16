import time, os
import numpy as np
import json
import time
import traceback
import queue
import requests 
import pyomo.environ as pyo
import logging
from mpc_agent import MPC_agent
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

class GridAreas(Context):
    @Dependencies(*["pyomo", "requests"])
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def locate(self, device):
        agent_id = os.getenv('AGENT_ID', type =int)[-1]
        id = {'id':agent_id}
        print(json.dumps(id))

class Pair(Context):
    @Dependencies(*["pyomo", "requests"])
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.n_areas = 2
    
    def locate(self, device):
        agent_id = os.getenv('AGENT_ID', type =int)[-1]
        agent_id_next = str((int(agent_id%self.n_areas) + 1) )
        id = {'id_forward':agent_id + '_' + agent_id_next, 'id_backward':agent_id_next + '_' +agent_id}
        print(json.dumps(id))


class MPCControl(Service):
    @Data(name = 'dual_vars_data', scope = 'GridAreas/id = .')
    @Data(name = 'primal_vars')
    @Channel('theta')
    @Metric('frequency')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class LayerOne(Role):
        @Requirements('AREA')
        @Metric('MPCControl/frequency[10s] < 0')
        @Dependencies(*["pyomo", "requests"])
        @Data(name = 'dual_vars_data', scope = 'GridAreas/id = .')
        @Data(name = 'primal_vars_data')
        @Channel(name = 'theta_channel')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.agent_id = os.getenv('AGENT_ID')
            self.area = self.agent_id[-1]
            self.neighbors = requests.get(andes_url + '/neighbor_area', params={'area':self.area}).json()['value']
            self.iter = 0
            self.max_iter = 100

            MPC_agent.__init__(self, **kwargs)
            self.setup_mpc()
            requests.get(self.andes_url + '/start_simulation')

        @Persistent()
        def behavior(self):
            self.error = 100
            self.iter = 0
            self.get_initial_values()
            self.initialize_dual_vars()
            self.initialize_horizon()
            self.dual_vars_data.publish(self.dual_vars)

            time.sleep(0.1)
            while self.error > self.tol and self.iter < self.max_iter:
                self.warm_start()
                self.state_horizon = json.loads(self.primal_vars.get().decode('utf-8')) 
                solver = pyo.SolverFactory('ipopt')
                tee = False
                solver.options["halt_on_ampl_error"] = "yes"
                result = solver.solve(self.model, tee=tee)

                #We publish the new state_horizon on the line channel
                state_horizon = {self.area:{}}
                for t in self.model.TimeHorizon:
                    state_horizon[self.area][self.area, t] = self.model.delta[t].value
                    for area_i in self.model.other_areas:
                        state_horizon[self.area][area_i, t]  = self.model.delta_areas[area_i, t].value
                self.theta_channel.publish(state_horizon)

                #Agent i updates the dual variables lambda_{j,i}
                dual_vars = json.loads(self.dual_vars_data.get().decode('utf-8')) 
                for t in self.model.TimeHorizon:
                    for area_i in self.model.other_areas:
                        dual_vars[area_i, t] += self.rho*(self.model.delta[t].value - state_horizon[area_i, self.area, t])
                self.dual_vars_data.publish(dual_vars) 

            self.frequency.publish(1)
            self.error = 100
            self.change_set_points()
            return 1
    
    class SaveRole(Role):
        @Requirements('AREA')
        @Metric('MPCControl/frequency[10s] < 0')
        @Dependencies(*["pyomo", "requests"])
        @Data(name = 'primal_vars_data')
        @Channel(name = 'theta_channel')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        @Async(new_theta = 'theta_channel')
        def behavior(self, new_theta):
            all_vars = json.loads(self.primal_vars_data.get().decode('utf-8')) 
            for key,val in new_theta.items():
                all_vars[key] = val
            self.primal_vars_data.publish(all_vars)
            return