import time, os
import numpy as np
import json
import time
import requests 
import copy
import pyomo.environ as pyo
import logging
import sys
sys.path.append('/home/pablo/Desktop/eroots/COLMENA')
from colmenasrc.controller.mpc_agent import MPCAgent
from colmenasrc.controller.coordinator import Coordinator
from colmenasrc.controller.admm import ADMM
from colmenasrc.simulator.andes_wrapper import AndesWrapper
from colmenasrc.config.config import Config

from copy import deepcopy
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
andes_url = 'http://127.0.0.1:5000'

class GridAll(Context):
    @Dependencies(*["pyomo", "requests"])
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def locate(self, device):
        id = {'id':1}
        print(json.dumps(id))

class AgentControl(Service):
    @Context(class_ref = GridAll, name='all_global')
    @Data(name = 'dual_vars', scope = 'all_global/id = .')
    @Data(name = 'primal_vars', scope = 'all_global/id = .')
    @Data(name = 'global_error', scope = 'all_global/id = .')
    @Channel(name= 'to_coordinator', scope = 'all_global/id = .')
    @Metric('frequency')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class Distributed_MPC(Role):
        @Requirements('AREA')
        @Metric('frequency')
        @Dependencies(*["pyomo", "requests"])
        @Context(class_ref = GridAll, name='all_global')
        @Data(name = 'dual_vars', scope = 'all_global/id = .')
        @Data(name = 'primal_vars', scope = 'all_global/id = .')
        @Data(name = 'global_error', scope = 'all_global/id = .')
        @Channel(name= 'to_coordinator', scope = 'all_global/id = .')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.andes_url = andes_url
            self.andes = AndesWrapper()
            self.n_areas = len(self.andes.get_complete_variable("Area", "idx"))
            self.agent_id = os.getenv('AGENT_ID')
            self.area = int(self.agent_id[-1])
            self.neighbors = requests.get(andes_url + '/neighbour_area', params={'area':self.area}).json()['value']
            self.iter = 0
            self.max_iter = 500
            self.data_read = self.primal_vars
            self.data_write = self.to_coordinator

            Config.agent = True
            self.agent = MPCAgent(self.area, self.andes)
            self.coordinator = Coordinator(self.andes)
            self.admm = self.coordinator.admm
            self.model = self.agent.setup_dmpc(self.coordinator)
            self.agent.setup = False
            self.initialized_decorators = False
            self.online_step = 0
            time.sleep(0.1)

        @Persistent()
        def behavior(self):
            print('running')
            self.error = 100
            self.iter = 0
            self.agent.initialize_variables_values()
            self.agent.first_warm_start()
            if not self.initialized_decorators:
                self.global_error.publish({'agent':1, 'error':self.error})
                self.state_horizon_jsonlike = {f"{a}_{b}_{c}_{d}": val for (a,b,c,d), val in self.coordinator.variables_horizon_values.items()}
                self.data_read.publish(self.state_horizon_jsonlike)
                state_horizon_message = self.state_horizon_jsonlike
                state_horizon_message['type'] = 'error'
                self.data_write.publish(state_horizon_message)
                self.initialized_decorators = True
            else:
                time.sleep(0.1)

            # Stop Flask logs
            time_start = time.time()
            while self.error > self.admm.tol and self.iter < self.max_iter + 1.5*(self.iter==0)*(self.max_iter):
                print(f'Iteration {self.iter}')
                initial_state_horizon_jsonlike = json.loads(self.data_read.get()) 
                if self.agent.generators: 
                    if self.iter ==0: 
                        # Initialize the model for the first iteration
                        self.agent.initialize_variables_values()

                    if self.admm.controlled:
                        self.admm._solve_agent(self.agent, self.iter)

                    # Residual computation
                    print(f"Iteration {self.iter}, Primal Residual: is undefinided")

                self.admm._update_duals()
                self.admm._update_pyomo_params(self.agent) 
                self.variables_horizon_values_json = {
                    f"{a}_{b}_{c}_{self.area}": val
                    for (a, b, c, d), val in self.coordinator.variables_horizon_values.items()
                    if d == self.area  # <--- This is the new condition
                }
                self.variables_horizon_values_json['type'] = 'primal' 
                self.data_write.publish(self.variables_horizon_values_json)
                
                #We publish the error and then get it back
                inf_error = self.admm._compute_primal_residual_inf()
                self.data_write.publish({self.area: inf_error, 'type':'error'})
                new_error = 0
                error_dict = json.loads(self.global_error.get())
                for i in range(1, self.n_areas+1):
                    try:
                        new_error = max(new_error, error_dict[i])
                    except:
                        new_error = 1
                        break
                self.error = new_error

                #We wait until we have received a new message from the other area
                changed_horizon = False
                change_time_start = time.time()
                while not changed_horizon: 
                    state_horizon_jsonlike = json.loads(self.data_read.get()) 
                    print(f'Waiting 3 for iter {self.iter} and online step {self.online_step}')
                    if state_horizon_jsonlike != initial_state_horizon_jsonlike:
                        changed_horizon = True
                        state_horizon_read = {tuple(map(int, key.split("_"))): val for key, val in state_horizon_jsonlike.items()}
                        self.coordinator.variables_horizon_values.update(state_horizon_read)
                        time.sleep(0.005)
                        break 
                    if time.time() - change_time_start > 2:
                        print(f'Wait broken')
                        break
                self.iter += 1
                        
            role_change_list = self.coordinator.collect_role_changes(specific_agent = self.agent)
            for role_change in role_change_list:
                if not role_change: 
                    print("[Warning] Empty role change detected.")
                print(f'Role change is {role_change}')
                self.andes.set_value(role_change)
            time_spent = time.time() - time_start
            self.online_step += 1
            time.sleep(max(0,self.agent.dt - time_spent))

            if self.agent.area == self.n_areas:
                time.sleep(0.01)
                for i in range(50):
                    success, new_time = self.andes.run_step()
                    time.sleep(0.1)
                    print(f"Step was {success} and time is {new_time}")
            return 1
    
    class CoordinatorAgent(Role):
        @Metric('frequency')
        @Context(class_ref = GridAll, name='all_global')
        @Requirements('AREA')
        @Data(name = 'dual_vars', scope = 'all_global/id = .')
        @Data(name = 'primal_vars', scope = 'all_global/id = .')
        @Data(name = 'global_error', scope = 'all_global/id = .')
        @Channel(name= 'to_coordinator', scope = 'all_global/id = .')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.andes_url = andes_url
            self.andes = AndesWrapper()
            self.n_areas = len(self.andes.get_complete_variable("Area", "idx"))
            self.online_step = 0
            self.initialize = 0
            time.sleep(0.1)

        @Async(msg="to_coordinator")
        def behavior(self, msg):
            print('Received incoming data')
            data = json.loads(msg)
            if data['type'] == 'primal':
                data.pop('type')
                primal_data = json.loads(self.primal_vars.get())
                primal_data = {f"{a}_{b}_{c}_{d}": val for (a,b,c,d), val in primal_data.items()}
                primal_data.update(data)
                self.primal_vars.publish(primal_data)
            elif data['type'] == 'error':
                data.pop('type')
                global_error = json.loads(self.global_error.get())
                global_error = {f"{a}": val for (a), val in global_error.items()}
                global_error.update(data)
                self.global_error.publish(global_error)
            else:
                raise Exception('Data type sent not recognized')
            return (1)