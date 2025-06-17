"""
This class contains the logic of the coordinator which is responsible for the communication between agents and for the execution of the simulation.
"""

import traceback

import pyomo.environ as pyo
from src.config.config import Config
from src.controller.admm import ADMM
from src.controller.mpc_agent import MPCAgent
from src.simulator.andes_wrapper import AndesWrapper

import pdb

class Coordinator:
    
    def __init__(self, andes: AndesWrapper, agents: list):
        # Constants
        self.tstep =      Config.tstep
        self.tf =         Config.tf
        self.dt =         Config.dt
        self.K =          Config.K
        self.tdmpc =      Config.tdmpc
        self.td =         Config.td

        self.controlled = Config.controlled

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
            for t in range(self.K)
            }
        
        self.dual_vars = {
            (i, j, t): 0.0 #NOTE: could be initialized differently
            for i in self.agents
            for j in self.agents
            for t in range(self.K)
            }

        self.error_save = [] # to store error
        self.omega_log = []  # to store (time, omega_values_dict)
        self.pg_log = []
        self.delta_log = []
        self.theta_log = []

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

        self.theta_mpc_log = {agent.agent_id: [] for agent in self.agents.values()}
        self.theta_sim_log = {agent.agent_id: [] for agent in self.agents.values()}
        self.theta_pred_horizon = {agent.agent_id: [] for agent in self.agents.values()}

        print(f"[Init] Starting MPC loop at t = {self.t}, final time = {self.tf}")

        try:
            j = 0 # Counter for DMPC activation
            while self.k < int(self.tf/self.tstep): 
                print(f"[Loop] Time {self.t:.2f}")

                # 3. Check for disturbances/events
                if self.k == int(self.td/self.tstep):
                    print("[Loop] Disturbance acting")

                    self.andes.change_parameter_value({'param': 'u', 
                                                       'model': 'Line', 
                                                       'idx': 'Line_0', 
                                                       'value': 0})

                #################FOR PLOTTING#####################
                # HORRIBLE Retrieve omega values from each agent ###
                omega_snapshot = {}
                for agent_id, agent in self.agents.items():
                    omega = self.andes.get_partial_variable("GENROU", "omega", agent.generators)
                    omega_snapshot[agent_id] = omega
                # Log time and omega values
                self.omega_log.append((self.t, omega_snapshot))

                theta_snapshot = {}
                for agent_id, agent in self.agents.items():
                    theta = self.andes.get_partial_variable("Bus", "a", agent.loads_bus)
                    theta_snapshot[agent_id] = theta
                # Log time and omega values
                self.theta_log.append((self.t, theta_snapshot))

                delta_snapshot = {}
                for agent_id, agent in self.agents.items():
                    delta = self.andes.get_partial_variable("GENROU", "delta", agent.generators)
                    delta_snapshot[agent_id] = delta
                # Log time and omega values
                self.delta_log.append((self.t, delta_snapshot))
                ######################################################

                # 1. Run DMPC - ADMM algorithm
                if self.controlled:
                    if self.k >= j * int(self.tdmpc/self.tstep):
                        j += 1
                        success, role_change_list = self.run_admm()
                        if not success:
                            print("[Error] ADMM failed.")
                            # break

                        # Send set points
                        for role_change in role_change_list:
                            self.andes.send_setpoint(role_change)

                #################FOR PLOTTING#####################
                pg_snapshot = {}
                for agent_id, agent in self.agents.items():
                    pg_vals = {gen_id: agent.model.Pg[gen_id, 1].value for gen_id in agent.generators}
                    pg_snapshot[agent_id] = pg_vals
                self.pg_log.append((self.t, pg_snapshot))

                for agent in self.agents.values():
                    theta_horizon = [pyo.value(agent.model.theta[k]) for k in range(agent.K + 1)]
                    self.theta_pred_horizon[agent.agent_id].append(theta_horizon)
                ######################################################

                # 2. Run one ANDES simulation step
                success, new_time = self.andes.run_step()
                if not success:
                    print(f"[Error] Simulation step failed at simulation time {new_time}.")
                    break

                #################FOR PLOTTING#####################
                for agent in self.agents.values():
                    theta_sim = agent.andes.get_partial_variable("Bus", "a", agent.interface_buses[agent.area])  # <- usa il metodo corretto
                    self.theta_sim_log[agent.agent_id].append(theta_sim)
                ######################################################
                
                self.k += 1
                self.t += self.tstep

            return True
        except Exception as e:
            print(f"[Exception] Error during loop: {e}")
            traceback.print_exc()
        return False

    def collect_role_changes(self):
        andes_role_changes = []
        agents = list(self.agents.values())

        for agent in agents:
            for i, gen_id in enumerate(agent.generators):

                role_change = {
                    'var': 'paux0',
                    'model': 'TGVO1',
                    'idx': gen_id,
                    'value': agent.model.Pg[gen_id, 0].value - agent.pref[i]
                }

                self.andes.send_setpoint(role_change)
                andes_role_changes.append(role_change.copy())

        return andes_role_changes
    

            
        


        



