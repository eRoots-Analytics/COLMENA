import time, os
import numpy as np
import json
import time
import requests 
import pyomo.environ as pyo
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

class GridAreas(Context):
    @Dependencies(*["pyomo", "requests"])
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def locate(self, device):
        agent_id = os.getenv('AGENT_ID')
        id = {'id':agent_id}
        print(json.dumps(id))

class GlobalError(Context):
    @Dependencies(*["pyomo", "requests"])
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def locate(self, device):
        agent_id = os.getenv('AGENT_ID')
        id = {'id':1}
        print(json.dumps(id))

class AgentControl(Service):
    @Context(class_ref = GridAreas, name='grid_areas')
    @Context(class_ref = GlobalError, name='all_global')
    @Data(name = 'dual_vars', scope = 'grid_areas/id =.')
    @Data(name = 'Data_1', scope = 'all_global/id = .')
    @Data(name = 'Data_2', scope = 'all_global/id = .')
    @Data(name = 'Data_3', scope = 'all_global/id = .')
    @Data(name = 'Data_4', scope = 'all_global/id = .')
    @Data(name = 'Data_5', scope = 'all_global/id = .')
    @Data(name = 'Data_6', scope = 'all_global/id = .')
    @Data(name = 'global_error', scope = 'all_global/id = .')
    @Metric('frequency')
    @Metric('always_negative')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class Distributed_MPC(Role):
        @Requirements('AREA')
        @Metric('frequency')
        @Data(name = 'dual_vars', scope = 'grid_areas/id =.')
        @KPI('agentcontrol/frequency < 1.001')
        @Context(class_ref = GlobalError, name='all_global')
        @Context(class_ref = GridAreas, name='grid_areas')
        @Dependencies(*["pyomo", "requests"])
        @Data(name = 'Data_1', scope = 'all_global/id = .')
        @Data(name = 'Data_2', scope = 'all_global/id = .')
        @Data(name = 'Data_3', scope = 'all_global/id = .')
        @Data(name = 'Data_4', scope = 'all_global/id = .')
        @Data(name = 'Data_5', scope = 'all_global/id = .')
        @Data(name = 'Data_6', scope = 'all_global/id = .')
        @Data(name = 'global_error', scope = 'all_global/id = .')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.andes_url = andes_url
            try:
                self.andes = AndesWrapper(load =False)
            except:
                self.andes = AndesWrapper()
            
            self.n_areas = len(self.andes.get_complete_variable("Area", "idx"))
            self.agent_id = os.getenv('AGENT_ID')
            self.area = int(self.agent_id[-1])
            self.neighbors = requests.get(andes_url + '/neighbour_area', params={'area':self.area}).json()['value']
            self.iter = 0
            self.max_iter = 650
            self.data_read = getattr(self, 'Data_' + str(self.area))
            self.data_write = getattr(self, 'Data_' + str(self.area+1 if self.area < self.n_areas else 1))

            Config.agent = True
            self.agent = MPCAgent(self.area, self.andes)
            self.coordinator = Coordinator(self.andes)
            self.admm = self.coordinator.admm
            self.model = self.agent.setup_dmpc(self.coordinator)
            self.agent.setup = False
            self.initialized_decorators = False
            self.online_step = 0
            time.sleep(10)

        @Persistent()
        def behavior(self):
            print('running')
            self.error = 100
            self.iter = 0
            self.agent.initialize_variables_values()
            self.agent.first_warm_start()
            self.global_error.publish({'agent':1, 'error':self.error})
            self.frequency.publish(2)
            if not self.initialized_decorators:
                self.state_horizon_jsonlike = {f"{a}_{b}_{c}_{d}": val for (a,b,c,d), val in self.coordinator.variables_horizon_values.items()}
                self.data_write.publish(self.state_horizon_jsonlike)
                self.data_read.publish(self.state_horizon_jsonlike)
                self.initialized_decorators = True
                time.sleep(1)
            else:
                time.sleep(1)

            # Stop Flask logs
            time_start = time.time()
            while self.error > self.admm.tol and self.iter < self.max_iter + 1.5*(self.iter==0)*(self.max_iter):
                print(f'Iteration {self.iter}')
                initial_state_horizon_jsonlike = self.data_read.get()
                if not isinstance(initial_state_horizon_jsonlike, dict):
                    initial_state_horizon_jsonlike = json.loads(initial_state_horizon_jsonlike)
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

                self.variables_horizon_values_json = {f"{a}_{b}_{c}_{d}": val for (a,b,c,d), val in self.coordinator.variables_horizon_values.items()}
                self.data_write.publish(self.variables_horizon_values_json)
                
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
                for i in range(30):
                    success, new_time = self.andes.run_step()
                    time.sleep(0.1)
                    print(f"Step was {success} and time is {new_time}")
            return 1
    
    class MonitoringRole(Role):
        @Requirements('AREA')
        @Metric('frequency')
        @Dependencies(*["pyomo", "requests"])
        @Metric('always_negative')
        @KPI('agentcontrol/always_negative[3s] > 1')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.andes_url = andes_url
            self.area = os.getenv('AGENT_ID')[-1]
            try:
                self.andes = AndesWrapper(load =False)
            except:
                self.andes = AndesWrapper()

        @Persistent()
        def behavior(self):
            area_frequency = self.andes.get_area_variable(model='GENROU', var='omega', area = self.area)
            area_M = self.andes.get_area_variable(model='GENROU', var='M', area = self.area)
            mean_freq = np.dot(area_frequency, area_M)
            self.frequency.publish(mean_freq)
            self.always_negative.publish(-1)
            return 1