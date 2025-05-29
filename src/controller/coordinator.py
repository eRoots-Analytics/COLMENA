import traceback

from src.config.config import Config
from src.controller.admm import ADMM
from src.controller.mpc_agent import MPCAgent

class Coordinator:
    
    def __init__(self, andes, agents):
        # Constants
        self.tstep = Config.tstep
        self.tf =    Config.tf
        self.dt =    Config.dt
        self.T =     Config.T

        # Andes interface
        self.andes = andes

        # System agents and cache 
        self.agents = {agent: MPCAgent(agent, andes) for agent in agents}
        self.thetas = {}

        self.neighbours = {
            area: self.andes.get_neighbour_areas(area)
            for area in self.agents
        }

        self.variables_horizon_values = {
            (i, j, t): 0.0 #NOTE: could be initialized differently
            for i in self.agents
            for j in self.agents
            for t in range(self.T + 1)
            }
        
        self.dual_vars = {
            (i, j, t): 0.0 #NOTE: could be initialized differently
            for i in self.agents
            for j in self.agents
            for t in range(self.T + 1)
            }
        
        self.dual_history = {
            (i, j, t): []
            for i in self.agents
            for j in self.agents
            for t in range(self.T + 1)
            }

        self.error_save = []

        self.admm = ADMM(self)

        self.omega_log = []  # to store (time, omega_values_dict)

        self.terminated = self.run()

    def run_admm(self):
        return self.admm.solve()
    
    def run(self):
        self.t = self.andes.start_time
        print(f"[Init] Starting MPC loop at t = {self.t}, final time = {self.tf}")

        try:
            while self.t < self.tf: #TODO to adjust
                print(f"[Loop] Time {self.t:.2f}")

                # 1. Get values
                self._initialize_theta_values()

                ######################################################
                # HORRIBLE Retrieve omega values from each agent ###
                omega_snapshot = {}
                for agent_id, agent in self.agents.items():
                    omega = self.andes.get_partial_variable("GENROU", "omega", agent.generators)
                    omega_snapshot[agent_id] = omega
                # Log time and omega values
                self.omega_log.append((self.t, omega_snapshot))
                ######################################################

                # 2. Run ADMM algorithm
                success, role_change_list = self.run_admm()
                if not success:
                    print("[Error] ADMM failed.")
                    break

                # 3. Post results
                for role_change in role_change_list:
                    self.andes.send_setpoint(role_change)

                # 4. Run one ANDES simulation step
                success, new_time = self.andes.run_step()
                if not success:
                    print("[Error] Simulation step failed.")
                    break

                # 5. Update time 
                # NOTE: in the future simulation time step can be different from MPC time step!
                self.t = new_time

            print(f"[Done] MPC run loop finished at t = {self.t}")
            return True
        except Exception as e:
            print(f"[Exception] Error during loop: {e}")
            traceback.print_exc()
        return False

    def _initialize_theta_values(self): #NOTE hardcoded, needs to be changed
        # Theta 
        for agent in self.agents:
            if agent == 1:
                self.thetas[agent] = 0.0
            else:
                self.thetas[agent] = self.andes.get_theta_equivalent(agent)[0] #NOTE: get_theta_equivalent needs to be modified 

        for agent in self.agents.values(): 
            agent.model.theta0.set_value(self.thetas[agent.area])
            for nbr in self.neighbours[agent.area]:
                agent.model.theta0_areas[nbr].set_value(self.thetas[nbr])

    def collect_role_changes(self):
        andes_role_changes = []
        agents = list(self.agents.values())

        for agent in agents:
            for gen_id in agent.generators:
                
                id_number = gen_id.split('_')[-1]

                role_change = {
                    'var': 'tm0',
                    'model': 'GENROU',
                    'idx': f"GENROU_{id_number}",
                    'value': agent.model.Pg[gen_id, 0].value
                }

                self.andes.send_setpoint(role_change)
                andes_role_changes.append(role_change.copy())

        return andes_role_changes

    # def collect_role_changes(self):
    #     andes_role_changes = []
    #     agents = list(self.agents.values())
        
    #     # Sync time (assuming all agents return the same)
    #     time_start = self.andes.sync_time()

    #     for agent in agents:
    #         for gen_id in agent.generators:
    #             kundur = not isinstance(gen_id, str)
    #             id_number = gen_id if kundur else (gen_id[-2:] if gen_id[-2] != '_' else gen_id[-1])
    #             for t in range(1, agent.T + 1):
    #                 if t != 1:
    #                     continue
    #                 for param in ['p_direct', 'b']:  # Adjust this list if needed

    #                     role_change = {'var': param,
    #                                    't': time_start + agent.dt * t}
                        
    #                     if param == 'tm0':
    #                         role_change['model'] = 'GENROU'
    #                         role_change['idx'] = 'GENROU_' + id_number
    #                     else:
    #                         role_change['model'] = 'TGOV1' if kundur else 'TGOV1N'
    #                         role_change['idx'] = id_number if kundur else 'TGOV1_' + id_number
                        
    #                     if param == 'paux0':
    #                         role_change['value'] = agent.model.Pg[gen_id, t].value - agent.model.Pg[gen_id, 0].value
    #                     elif param == 'b':
    #                         role_change['value'] = 1
    #                     else:
    #                         role_change['value'] = agent.model.Pg[gen_id, t].value

    #                     # Send to Andes
    #                     self.andes.send_setpoint(role_change)
    #                     andes_role_changes.append(role_change.copy())
        
    #     return andes_role_changes

    

            
        


        



