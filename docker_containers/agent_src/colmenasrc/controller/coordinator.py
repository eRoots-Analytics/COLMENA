"""
This class contains the logic of the coordinator which is responsible for the communication between agents and for the execution of the simulation.
"""

import traceback
import time
import numpy as np
from colmenasrc.config.config import Config
from colmenasrc.controller.admm import ADMM
from colmenasrc.controller.mpc_agent import MPCAgent, MPCAgentv2
from colmenasrc.simulator.andes_wrapper import AndesWrapper

class Coordinator:
    """
    Central coordinator for running a distributed MPC simulation using ADMM.

    This class manages agent initialization, logging, disturbance handling,
    and coordination of decentralized control via ADMM.

    Attributes:
        tstep (float): Time step of the simulation.
        tf (float): Final simulation time.
        dt (float): Discretization time step for MPC.
        K (int): Prediction horizon length.
        tdmpc (float): Time delay between DMPC activations.
        td (float): Time of disturbance.
        controlled (bool): Flag indicating if control actions should be applied.
        disturbance (bool): Flag indicating if a disturbance has occurred.
        andes (AndesWrapper): Interface to the power system simulator.
        areas (list): List of area identifiers.
        agents (dict): Mapping of area IDs to their respective MPC agents.
        neighbours (dict): Neighbourhood graph between areas.
        variables_horizon_values (dict): Horizon-wide shared variable values.
        dual_vars (dict): ADMM dual variables (Lagrangian multipliers).
        logs (...): Time-series logs for various system states.
        admm (ADMM): ADMM solver instance.
        terminated (bool): Simulation termination status.
    """

    def __init__(self, andes: AndesWrapper):
        """
        Initialize the Coordinator with configuration and simulation interface and run the simulation.

        Args:
            andes (AndesWrapper): Simulator interface for power system model.
        """
        # Constants
        self.tstep =      Config.tstep
        self.tf =         Config.tf
        self.dt =         Config.dt
        self.K =          Config.K
        self.tdmpc =      Config.tdmpc
        self.td =         Config.td
        self.T_send =     Config.T_send
        self.angles =     Config.angles
        self.controlled = Config.controlled

        self.disturbance = False

        # Andes interface
        self.andes = andes

        # Areas
        self.areas = self.andes.get_complete_variable("Area", "idx")

        # System agents and cache 
        if self.angles:
            self.agents = {agent: MPCAgentv2(agent, andes) for agent in self.areas}
        else:
            self.agents = {agent: MPCAgent(agent, andes) for agent in self.areas}

        self.neighbours = {
            area: self.andes.get_neighbour_areas(area)
            for area in self.agents
        }

        if not Config.angles:
            self.variables_horizon_values = {
                (i, j, t, w): 0.0 
                for i in self.agents
                for j in self.agents
                for t in range(self.K)
                for w in self.agents
                }

            self.dual_vars = {
                (i, j, t): 0.0
                for i in self.agents
                for j in self.agents
                for t in range(self.K)
                }
        else:
            self.variables_horizon_values = {
                (i, j, t): 0.0 
                for i in self.agents
                for j in self.agents
                for t in range(self.K)
                }

            self.dual_vars = {
                (i, j, t): 0.0
                for i in self.agents
                for j in self.agents
                for t in range(self.K)
                }
            
            self.dual_vars_P = {
                (i, j, t): 0.0
                for i in self.agents
                for j in self.agents
                for t in range(self.K)
                }
            
            self.dual_vars_diff = {
                (i, j, t): 0.0
                for i in self.agents
                for j in self.agents
                for t in range(self.K)
                }

        # Logs
        self.error_save = [] 
        self.omega_log = []  
        self.omega_coi_prediction_log = []
        self.omega_coi_log = []
        self.bus_v_log = []
        self.bus_a_log = []
        self.redual_v_log = []
        self.redual_a_log = []

        # Initilailzed ADMM algorithm 
        self.admm = ADMM(self)
        self.colmena = True
        print("[Main] Coordinator initialized.")
        if Config.agent:
            return 
        try:
            if Config.colmena:
                self.terminated = self.run_colmena()
            else:
                self.terminated = self.run()
            return         

        except Exception as e:
            print(f"[Exception] Error during simulation run: {e}")
            traceback.print_exc()

    def run_admm(self):
        """
        Execute one iteration of the ADMM algorithm.

        Returns:
            tuple: (success flag, list of role changes to apply)
        """
        return self.admm.solve()
    
    def run(self, colmena_run = False):
        """
        Main simulation loop handling:
        - disturbance injection
        - control execution
        - system evolution

        Returns:
            bool: True if simulation completed successfully, False otherwise.
        """
        self.k = 0
        self.t = 0.0

        print(f"[Init] Starting MPC loop at t = {self.t}, final time = {self.tf}")

        try:
            j = 0 # Counter for DMPC activation
            while self.k < int(self.tf/self.tstep): 
                print(f"[Loop] Time {self.t:.2f}")

                # === Log omega for plotting ===
                # Omega
                omega_snapshot = {}
                for agent_id, agent in self.agents.items():
                    omega = self.andes.get_partial_variable("GENROU", "omega", agent.generators)
                    omega_snapshot[agent_id] = omega
                self.omega_log.append((self.t, omega_snapshot))
                # Omegas COI
                for agent in self.agents.values():
                    omega_values = self.andes.get_partial_variable("GENROU", "omega", agent.generators)
                    weight = np.array(agent.M_values) * np.array(agent.Sn_values)
                    omega_coi = np.dot(weight, np.array(omega_values)) / np.sum(weight)

                    self.omega_coi_log.append(
                    (self.t, {str(agent.area): omega_coi})
                    )
                if 'converters' in Config.case_name:
                    value_snapshot = {}
                    for agent_id, agent in self.agents.items():
                        omega = self.andes.get_partial_variable("Bus", "v", agent.generators)
                        omega_snapshot[agent_id] = omega
                    self.bus_v_log.append((self.t, value_snapshot))

                    value_snapshot = {}
                    for agent_id, agent in self.agents.items():
                        omega = self.andes.get_partial_variable("Bus", "a", agent.generators)
                        omega_snapshot[agent_id] = omega
                    self.bus_a_log.append((self.t, value_snapshot))

                    value_snapshot = {}
                    for agent_id, agent in self.agents.items():
                        omega = self.andes.get_partial_variable("REDUAL", "a", agent.generators)
                        omega_snapshot[agent_id] = omega
                    self.redual_a_log.append((self.t, value_snapshot))

                    value_snapshot = {}
                    for agent_id, agent in self.agents.items():
                        omega = self.andes.get_partial_variable("REDUAL", "a", agent.generators)
                        omega_snapshot[agent_id] = omega
                    self.redual_v_log.append((self.t, value_snapshot))

                # === Disturbance injection ===
                if self.k == int(self.td/self.tstep):
                    self.disturbance = True
                    print("[Loop] Disturbance acting")

                    if self.andes.failure == 'line':
                        self.andes.set_value({'model': 'Line',
                                          'idx': 'Line_1',
                                          'src': 'u',
                                          'attr': 'v',
                                          'value': 0})
                    elif self.andes.failure == 'generator':
                        self.andes.set_value({'model': 'GENROU',
                                          'idx': 'GENROU_1',
                                          'src': 'u',
                                          'attr': 'v',
                                          'value': 0})
                    else:
                        self.andes.set_value({'model': 'PQ',
                                              'idx': 'PQ_1',
                                              'src': 'Ppf',
                                              'attr': 'v',
                                              'value': 0.0})
                        self.andes.set_value({'model': 'PQ',
                                              'idx': 'PQ_2',
                                              'src': 'Ppf',
                                              'attr': 'v',
                                              'value': 0.0})
                        for i in range(1, 11):
                            if i == 5:
                                continue
                            self.andes.set_value({'model': 'PQ',
                                              'idx': f'PQ_{i*3}',
                                              'src': 'Ppf',
                                              'attr': 'v',
                                              'value': 0.0})
                        
                for i,failure in enumerate(self.andes.additional_failures):
                    sync_time = self.andes.get_dae_time()
                    if failure['t'] >= sync_time:
                        failure.pop('t')
                        self.andes.set_value(failure)
                        self.andes.additional_failures.pop(i) 

                # === Execute control ===
                sync_time = self.andes.get_dae_time()
                if sync_time < 10:
                    _ = 0
                elif self.k >= j * int(self.tdmpc/self.tstep):
                    j += 1
                    success, role_change_list = self.run_admm()
                    if not success:
                        print("[Error] ADMM failed.")
                        # break

                    # Send set pointscollect_role_changes
                    if self.controlled and self.disturbance:
                        for role_change in role_change_list:
                            if not role_change: 
                                print("[Warning] Empty role change detected.")
                            self.andes.set_value(role_change)

                # === Simulate system forward ===
                success, new_time = self.andes.run_step()
                if not success:
                    print(f"[Error] Simulation step failed at simulation time {new_time}.")
                    break
                
                self.k += 1
                self.t += self.tstep

            return True
        except Exception as e:
            print(f"[Exception] Error during loop: {e}")
            traceback.print_exc()
        return False
    
    def run_colmena(self, colmena_run = False):
        """
        Main simulation loop handling:
        - disturbance injection
        - control execution
        - system evolution

        Returns:
            bool: True if simulation completed successfully, False otherwise.
        """
        self.k = 0
        self.t = 0.0

        print(f"[Init] Starting MPC loop at t = {self.t}, final time = {self.tf}")
        success, new_time = self.andes.run_step()

        try:
            j = 0 # Counter for DMPC activation
            while self.k < int(self.tf/self.tstep): 
                print(f"[Loop] Time {self.t:.2f}")
                initial_time = self.andes.get_dae_time()

                # === Log omega for plotting ===
                # Omega
                omega_snapshot = {}
                for agent_id, agent in self.agents.items():
                    omega = self.andes.get_partial_variable("GENROU", "omega", agent.generators)
                    omega_snapshot[agent_id] = omega
                self.omega_log.append((self.t, omega_snapshot))
                # Omegas COI
                for agent in self.agents.values():
                    omega_values = self.andes.get_partial_variable("GENROU", "omega", agent.generators)
                    weight = np.array(agent.M_values) * np.array(agent.Sn_values)
                    omega_coi = np.dot(weight, np.array(omega_values)) / np.sum(weight)

                    self.omega_coi_log.append(
                    (self.t, {str(agent.area): omega_coi})
                    )
                
                if 'converters' in Config.case_name:
                    value_snapshot = {}
                    for agent_id, agent in self.agents.items():
                        omega = self.andes.get_partial_variable("Bus", "v", agent.generators)
                        omega_snapshot[agent_id] = omega
                    self.bus_v_log.append((self.t, value_snapshot))

                    value_snapshot = {}
                    for agent_id, agent in self.agents.items():
                        omega = self.andes.get_partial_variable("Bus", "a", agent.generators)
                        omega_snapshot[agent_id] = omega
                    self.bus_a_log.append((self.t, value_snapshot))

                    value_snapshot = {}
                    for agent_id, agent in self.agents.items():
                        omega = self.andes.get_partial_variable("REDUAL", "v", agent.generators)
                        omega_snapshot[agent_id] = omega
                    self.redual_v_log.append((self.t, value_snapshot))

                    value_snapshot = {}
                    for agent_id, agent in self.agents.items():
                        omega = self.andes.get_partial_variable("REDUAL", "a", agent.generators)
                        omega_snapshot[agent_id] = omega
                    self.redual_a_log.append((self.t, value_snapshot))
                    
                # === Disturbance injection ===
                if self.k == int(self.td/self.tstep):
                    self.disturbance = True
                    print("[Loop] Disturbance acting")

                # === Disturbance injection ===
                if self.k == int(self.td/self.tstep):
                    self.disturbance = True
                    print("[Loop] Disturbance acting")

                    if self.andes.failure == 'line':
                        self.andes.set_value({'model': 'Line',
                                          'idx': 'Line_1',
                                          'src': 'u',
                                          'attr': 'v',
                                          'value': 0})
                    elif self.andes.failure == 'generator':
                        self.andes.set_value({'model': 'GENROU',
                                          'idx': 'GENROU_1',
                                          'src': 'u',
                                          'attr': 'v',
                                          'value': 0})
                    else:
                        self.andes.set_value({'model': 'PQ',
                                              'idx': 'PQ_1',
                                              'src': 'Ppf',
                                              'attr': 'v',
                                              'value': 0.0})
                        self.andes.set_value({'model': 'PQ',
                                              'idx': 'PQ_2',
                                              'src': 'Ppf',
                                              'attr': 'v',
                                              'value': 0.0})
                        for i in range(1, 11):
                            if i == 5:
                                continue
                            self.andes.set_value({'model': 'PQ',
                                              'idx': f'PQ_{i*3}',
                                              'src': 'Ppf',
                                              'attr': 'v',
                                              'value': 0.0})

                for i,failure in enumerate(self.andes.additional_failures):
                    sync_time = self.andes.get_dae_time()
                    if failure['t'] >= sync_time:
                        failure.pop('t')
                        self.andes.set_value(failure)
                        self.andes.additional_failures.pop(i) 
                        
                # === Simulate system forward ===
                sync_time = self.andes.get_dae_time()
                if self.t < 6:
                    success, new_time = self.andes.run_step()
                    self.k += 1
                    self.t += self.tstep
                    time.sleep(self.tstep)
                else:
                    while sync_time == initial_time and sync_time < self.tf:
                        sync_time = self.andes.get_dae_time()
                        time.sleep(0.001)
                        print(f'[Run] Waiting, initial_time is {initial_time}, sync_time is {sync_time}')
                    self.t += self.tstep
                    self.k += 1
                    
                if sync_time > self.tf:
                    return True
            return True
        except Exception as e:
            print(f"[Exception] Error during loop: {e}")
            traceback.print_exc()
        return False
    
    def run_colmena_step(self):
        success, new_time = self.andes.run_step()
        omega_snapshot = {}
        for agent_id, agent in self.agents.items():
            omega = self.andes.get_partial_variable("GENROU", "omega", agent.generators)
            omega_snapshot[agent_id] = omega
        self.omega_log.append((self.t, omega_snapshot))
        # Omegas COI
        for agent in self.agents.values():
            omega_values = self.andes.get_partial_variable("GENROU", "omega", agent.generators)
            weight = np.array(agent.M_values) * np.array(agent.Sn_values)
            omega_coi = np.dot(weight, np.array(omega_values)) / np.sum(weight)
            self.omega_coi_log.append(
            (self.t, {str(agent.area): omega_coi})
            )
        self.t += self.tstep
        self.k += 1
        return True

    def collect_role_changes(self, specific_agent = None):
        """
        Collect role changes (i.e., setpoints) from all agents to apply via ANDES.

        Returns:
            list: A list of role change dictionaries suitable for `andes.set_value()`.
        """
        andes_role_changes = []
        agents = list(self.agents.values())
        if specific_agent is not None:
            agents = [specific_agent]
        if self.controlled:
            for agent in agents:
                for i, (gen_id, gov_id) in enumerate(zip(agent.generators, agent.governors)):
                    if not Config.angles:
                        role_change = {
                            'model': 'TGOV1N',
                            'src': 'paux0',
                            'idx': gov_id,
                            'attr': 'v',
                            'value': agent.model.Pg[0, gen_id].value - agent.pref0[i]
                        }
                        andes_role_changes.append(role_change.copy())

                    else:
                        for t in range(self.T_send):
                            sync_time = self.andes.get_dae_time()
                            role_change = {
                                'model': 'TGOV1N',
                                'src': 'paux0',
                                'idx': gov_id,
                                'attr': 'v',
                                'value': agent.model.Pg[t, gen_id].value - agent.pref0[i],
                                'time': sync_time + t*Config.dt
                            }
                        andes_role_changes.append(role_change.copy())

        return andes_role_changes
