import os
import numpy as np
import json
import time

try:
    import requests
    from colmenasrc.controller.mpc_agent import MPCAgent
    from colmenasrc.controller.coordinator import Coordinator
    from colmenasrc.simulator.andes_wrapper import AndesWrapper
    from colmenasrc.config.config import Config
except ModuleNotFoundError: # Dintre de building tool amagar
    #print("colmenasrc not imported.")
    pass

import logging

from colmena import (
    Context,
    Service,
    Role,
    Requirements,
    Metric,
    Persistent,
    KPI,
    Data,
    Dependencies,
    Version,
    BaseImage
)

def filter_global_error(input_dict: dict, target_iter: int) -> dict:
    """
    Filters a dictionary, keeping entries where the key is in 'X_Y' format
    and 'Y' matches target_iter OR (target_iter - 1). Non-'X_Y' keys are also preserved.

    Args:
        input_dict (dict): The dictionary to filter.
        target_iter (int): The integer representing the current 'y' value.
                           The function will keep keys with 'y' equal to target_iter
                           or (target_iter - 1).

    Returns:
        dict: A new dictionary containing only the desired entries.
    """
    filtered_dict = {}
    target_iter_str = str(target_iter)

    # Calculate the previous iteration and convert to string for comparison
    prev_iter_str = str(max(target_iter - 1,0))

    for key, value in input_dict.items():
        # Regex to match keys like 'area_0', 'foo_123' and capture the number
        match = re.match(r'^[^_]+_(\d+)$', key)
        if match:
            y_str = match.group(1)  # Extract the 'y' part as a string

            # Check if y_str matches target_iter OR (target_iter - 1)
            if y_str == target_iter_str or y_str == prev_iter_str:
                filtered_dict[key] = value
        else:
            # If the key doesn't match the 'X_Y' format, preserve it
            filtered_dict[key] = value
    return filtered_dict

class GridAreas(Context):
    @Version("0.1")
    @Dependencies(*["pyomo", "requests"])
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def locate(self, device):
        num_area = os.getenv('AGENT_ID')[-1]
        id = {'id': f"area_{num_area}"}
        print(json.dumps(id))

class GlobalError(Context):
    @Version("0.1")
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
    @Data(name = 'dual_vars', scope = 'grid_areas/id = .')
    @Data(name = 'state', scope = 'all_global/id = .')
    @Data(name='start_dict', scope = 'all_global/id = .')
    @Data(name = 'global_error', scope = 'all_global/id = .')
    @Metric('frequency')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class Distributed_MPC(Role):
        @Version("0.0")
        @BaseImage("xaviercasasbsc/agent_src")
        @Requirements('AREA')
        @Metric('frequency')
        @Data(name = 'dual_vars', scope = 'grid_areas/id = .')
        @KPI('abs(avg(avg_over_time(agentcontrol_frequency[1m])) - 1) < 0.001') # Intentar bajarlo a 15 segundos.
        @Context(class_ref = GlobalError, name='all_global')
        @Context(class_ref = GridAreas, name='grid_areas')
        @Dependencies(*["pyomo", "requests"])
        @Data(name = 'state')
        @Data(name='start_dict', scope= 'all_global/id = .')
        @Data(name = 'global_error', scope = 'all_global/id = .')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.andes_url = Config.andes_url
            try:
                self.andes = AndesWrapper(load = False)
            except:
                self.andes = AndesWrapper()
            
            self.n_areas = len(self.andes.get_complete_variable("Area", "idx"))
            self.agent_id = os.getenv('AGENT_ID')
            self.area = int(self.agent_id[-1])
            self.neighbors = requests.get(self.andes_url + '/neighbour_area', params={'area':self.area}).json()['value']
            self.iter = 0
            self.max_iter = 50

            self.data_read_scope = f"grid_areas/id = {str(self.area)}"
            self.data_write_scope = f"grid_areas/id = {str(self.area+1 if self.area < self.n_areas else 1)}"

            Config.agent = True
            Config.colmena = False
            self.agent = MPCAgent(self.area, self.andes)
            self.coordinator = Coordinator(self.andes)
            self.admm = self.coordinator.admm
            self.model = self.agent.setup_dmpc(self.coordinator)
            self.agent.setup = False
            self.initialized_decorators = False
            self.online_step = 0

        @Persistent()
        def behavior(self):
            self.logger.info('Running')
            self.iter = 0
            self.agent.initialize_variables_values()
            self.agent.first_warm_start()
            time.sleep(0.1)
            if not self.initialized_decorators:
                self.error = 1
                self.global_error.publish({
                    'agent': 1,
                    'error': self.error,
                    'to_publish': 1
                })
                self.state_horizon_jsonlike = {f"{a}_{b}_{c}_{d}": val for (a,b,c,d), val in self.coordinator.variables_horizon_values.items()}
                self.state.publish(self.state_horizon_jsonlike, scope=self.data_write_scope)
                self.state.publish(self.state_horizon_jsonlike, scope=self.data_read_scope)
                self.initialized_decorators = True
                #self.wait_for_all()
                time.sleep(0.1)
            else:
                time.sleep(0.1)

            # Stop Flask logs
            time_start = time.time()
            while self.error > self.admm.tol and self.iter < self.max_iter + 1.5*(self.iter==0)*(self.max_iter):
                self.logger.info(f'Iteration {self.iter}')
                initial_state_horizon_jsonlike = self.state.get(scope=self.data_read_scope)
                if not isinstance(initial_state_horizon_jsonlike, dict):
                    initial_state_horizon_jsonlike = json.loads(initial_state_horizon_jsonlike)
                if self.agent.generators: 
                    if self.iter ==0: 
                        # Initialize the model for the first iteration
                        self.agent.initialize_variables_values()

                    if self.admm.controlled:
                        self.admm._solve_agent(self.agent, self.iter)

                    # Residual computation
                    self.logger.info(f"Iteration {self.iter}, Primal Residual: is undefinided")

                self.admm._update_duals()
                self.admm._update_pyomo_params(self.agent) 

                self.variables_horizon_values_json = {f"{a}_{b}_{c}_{d}": val for (a,b,c,d), val in self.coordinator.variables_horizon_values.items()}
                self.state.publish(self.variables_horizon_values_json, scope=self.data_write_scope)

                mse_error = self.admm._compute_primal_residual_mse()

                #We read the global_error data channel and wait to publish our error when its the agent's turn
                global_error_dict = self.global_error.get()
                if not isinstance(global_error_dict, dict):
                    global_error_dict = json.loads(global_error_dict)

                while global_error_dict['to_publish'] != self.area:
                    global_error_dict = self.global_error.get()
                    if not isinstance(global_error_dict, dict):
                        global_error_dict = json.loads(global_error_dict)
                    print(f'waiting for areas to publish errors {global_error_dict} in {self.area}')
                    time.sleep(0.001)
                global_error_dict[f'{self.area}_{self.iter}'] = mse_error
                global_error_dict['to_publish'] = self.area + 1 if self.area < self.n_areas else 1
                self.global_error.publish(global_error_dict)

                #Once all agents have updated the error, we compute the global error from the previous iteration (!)
                new_error = 0
                if self.iter >= 1:
                    for i in range(1,self.n_areas+1):
                        try:
                            new_error = max(new_error, global_error_dict[f'{i}_{self.iter-1}'])
                        except KeyError:
                            self.logger.info("No error value found.")
                else:
                    new_error = 1
                if self.area == self.n_areas:
                    global_error_dict = filter_global_error(global_error_dict, self.iter)
                    global_error_dict['to_publish'] = 1
                    self.global_error.publish(global_error_dict)
                self.error = new_error
                print('f[Main] Current mse error is {self.error}')

                #We wait until we have received a new message from the other area
                changed_horizon = False
                change_time_start = time.time()
                while not changed_horizon:
                    state_horizon_jsonlike = json.loads(self.state.get(scope=self.data_read_scope))
                    self.logger.info(f'Waiting 3 for iter {self.iter} and online step {self.online_step}')
                    if state_horizon_jsonlike != initial_state_horizon_jsonlike:
                        self.logger.info(f'Horizon changed')
                        changed_horizon = True
                        state_horizon_read = {tuple(map(int, key.split("_"))): val for key, val in state_horizon_jsonlike.items()}
                        self.coordinator.variables_horizon_values.update(state_horizon_read)
                        time.sleep(0.005)
                        break 
                    if time.time() - change_time_start > 2:
                        self.logger.info(f'Wait broken')
                        break
                self.iter += 1
                        
            role_change_list = self.coordinator.collect_role_changes(specific_agent = self.agent)
            for role_change in role_change_list:
                if not role_change:
                    pass
                    self.logger.info("[Warning] Empty role change detected.")
                self.logger.info(f'Role change is {role_change}')
                self.andes.set_value(role_change)
            time_spent = time.time() - time_start
            self.online_step += 1
            time.sleep(max(0,self.agent.dt - time_spent))

            return 1
    
    class MonitoringRole(Role):
        @Version("0.0")
        @BaseImage("xaviercasasbsc/agent_src")
        @Requirements('AREA')
        @Metric('frequency')
        @Dependencies(*['pyomo', 'requests'])
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.andes_url = Config.andes_url
            Config.colmena = False
            self.area = int(os.getenv('AGENT_ID')[-1])
            try:
                self.andes = AndesWrapper(load = False)
            except:
                self.andes = AndesWrapper()
            self.n_areas = len(self.andes.get_complete_variable("Area", "idx"))

        @Persistent(period=1)
        def behavior(self):
            area_frequency_1 = self.andes.get_area_variable(model='GENROU', var='omega', area = self.area)
            if area_frequency_1:
                area_M_1 = self.andes.get_area_variable(model='GENROU', var='M', area = self.area)
                mean_freq_1 = np.dot(area_frequency_1, area_M_1) / np.sum(area_M_1)

            area_frequency_2 = self.andes.get_area_variable(model='GENCLS', var='omega', area = self.area)
            if area_frequency_2:
                area_M_2 = self.andes.get_area_variable(model='GENCLS', var='M', area = self.area)
                mean_freq_2 = np.dot(area_frequency_2, area_M_2) / np.sum(area_M_2)

            mean_freq = 0
            if (not area_frequency_1) and area_frequency_2:
                mean_freq = mean_freq_2
            elif area_frequency_1 and (not area_frequency_2):
                mean_freq = mean_freq_1
            elif area_frequency_1 and area_frequency_2:
                mean_freq = (mean_freq_1 + mean_freq_2) / 2

            self.frequency.publish(mean_freq)
            return 1

    class SimulationManager(Role):
        @Version("0.0")
        @BaseImage("xaviercasasbsc/agent_src")
        @Requirements('SIMULATOR')
        @Dependencies(*['pyomo', 'requests'])
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.andes_url = Config.andes_url
            Config.colmena = True
            try:
                self.andes = AndesWrapper(load = False)
            except:
                self.andes = AndesWrapper()

        @Persistent()
        def behavior(self):
            self.andes.run_step()
            time.sleep(Config.tstep*Config.sim_ratio)
