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

class Pair(Context):
    @Dependencies(*["pyomo", "requests"])
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.n_areas = 2
    
    def locate(self, device):
        agent_id = os.getenv('AGENT_ID', type =int)[-1]
        agent_id_next = str((int(agent_id%self.n_areas) + 1) )
        id = {'id_forward':agent_id + '_' + agent_id_next, 'id_backward':agent_id_next + '_' +agent_id}
        area_pairings_fw = ['12', '12', '34','34', '56', '56']
        area_pairings_bw = ['41', '23', '23','41', '45', '56']
        id = {'id_forward': area_pairings_fw[int(agent_id)], 'id_backward':area_pairings_bw[int(agent_id)]}
        print(json.dumps(id))

class AgentControl(Service):
    @Context(Pair, name ='pairs')
    @Data(name = 'dual_vars')
    @Data(name = 'messages_forward', scope= 'agentcontrol/Pair/id_forward = .')
    @Data(name = 'messages_backward', scope= 'agentcontrol/Pair/id_backward = .')
    @Metric('deviation')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class LayerOne(Role):
        @Requirements('AREA')
        @Dependencies(*["pyomo", "requests"])
        @Data(name = 'dual_vars')
        @Data(name = 'messages_forward', scope= 'agentcontrol/Pair/id_forward = .')
        @Data(name = 'messages_backward', scope= 'agentcontrol/Pair/id_backward = .')
        @Metric('frequency')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.agent_id = os.getenv('AGENT_ID')
            self.area = self.agent_id[-1]
            self.neighbors = requests.get(andes_url + '/neibour_area', params={'area':self.area}).json()['value']
            self.iter = 0

            MPC_agent.__init__(self, **kwargs)
            self.setup_mpc()
            if self.area%1:
                self.state_horizon_publish = self.messages_forward
                self.state_horizon_get = self.messages_backward
            else:
                self.state_horizon_get = self.messages_forward
                self.state_horizon_publish = self.messages_backward

        @Persistent()
        def behavior(self):
            self.error = 100
            self.iter = 0
            self.get_initial_values()

            while self.error > self.tol:
                solver = pyo.SolverFactory('ipopt')
                #print_all_variables(model)
                tee = False
                solver.options["halt_on_ampl_error"] = "yes"
                result = solver.solve(self.model, tee=tee)
                
                #We publish the new state
                state_horizon = json.loads(self.state_horizon_get.get().decode('utf-8'))
                for t in self.model.TimeHorizon:
                    state_horizon[self.area, self.area, t] = self.model.delta[t].value
                    for area_i in self.model.other_areas:
                        state_horizon[self.area, area_i, t] = self.model.delta_areas[area_i, t].value
                self.state_horizon_publish.publish(state_horizon)

                #we update the agents iteration number
                self.iter += 1
                iterations = json.loads(self.iterations.get().decode('utf-8')) 
                iterations[self.area] += self.iter 
                self.iterations.publish(iterations) 

                #We wait for all the agents to get to the same iteration 
                iterations = json.loads(self.iterations.get().decode('utf-8'))
                while not all(value == self.iter for value in iterations.values()): 
                    iterations = json.loads(self.iterations.get().decode('utf-8'))
                    time.sleep(0.01)

                #Agent i updates the dual variables lambda_{j,i}
                dual_vars = json.loads(self.dual_vars.get().decode('utf-8')) 
                for t in self.model.TimeHorizon:
                    for area_i in self.model.other_areas:
                        dual_vars[area_i, self.area, t] += self.rho*(self.model.delta[t].value - self.state_horizon[area_i, self.area])
                dual_vars = json.loads(self.dual_vars.get().decode('utf-8')) 

                if self.iter > 200:
                    break
            
            self.change_set_points()
                 