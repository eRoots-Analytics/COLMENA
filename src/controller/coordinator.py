"""
This class contains the logic of the coordinator which is responsible for the communication between agents and for the execution of the simulation.
"""

import traceback

from src.config.config import Config
from src.controller.admm import ADMM
from src.controller.mpc_agent import MPCAgent
from src.simulator.andes_wrapper import AndesWrapper

class Coordinator:
    
    def __init__(self, andes: AndesWrapper, agents: list):
        # Constants
        self.tstep = Config.tstep
        self.tf =    Config.tf
        self.dt =    Config.dt
        self.K =     Config.K
        self.tdmpc = Config.tdmpc

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
            for t in range(self.K + 1)
            }
        
        self.dual_vars = {
            (i, j, t): 0.0 #NOTE: could be initialized differently
            for i in self.agents
            for j in self.agents
            for t in range(self.K + 1)
            }
        
        self.dual_history = {
            (i, j, t): []
            for i in self.agents
            for j in self.agents
            for t in range(self.K + 1)
            }

        self.error_save = [] # to store error
        self.omega_log = []  # to store (time, omega_values_dict)

        # Initilailzed ADMM algorithm 
        self.admm = ADMM(self)

        print("[Main] Coordinator initialized.")

        # Run simulation
        try:
            self.terminated = self.run()
        except Exception as e:
            print(f"[Exception] Error during simulation run: {e}")
            traceback.print_exc()


    def run_admm(self):
        return self.admm.solve()
    
    def run(self):

        self.k = 0
        self.t = 0.0

        print(f"[Init] Starting MPC loop at t = {self.t}, final time = {self.tf}")

        try:
            i = 0 # Counter for DMPC activation
            while self.k < int(self.tf/self.tstep): 
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

                # 2. Run DMPC - ADMM algorithm
                if self.k >= i * int(self.tdmpc/self.tstep):
                    i += 1
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
                    print(f"[Error] Simulation step failed at simulation time {new_time}.")
                    break

                # 5. Update time step and time 
                self.k += 1
                self.t += self.tstep
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
    

            
        


        



