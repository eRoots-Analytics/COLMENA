"""
This class contains the logic of the coordinator which is responsible for the communication between agents and for the execution of the simulation.
"""

import traceback

import numpy as np
from src.config.config import Config
from src.controller.admm import ADMM
from src.controller.mpc_agent import MPCAgent
from src.simulator.andes_wrapper import AndesWrapper

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

        self.controlled = Config.controlled

        self.disturbance = False

        # Andes interface
        self.andes = andes

        # Areas
        self.areas = self.andes.get_complete_variable("Area", "idx")

        # System agents and cache 
        self.agents = {agent: MPCAgent(agent, andes) for agent in self.areas}

        self.neighbours = {
            area: self.andes.get_neighbour_areas(area)
            for area in self.agents
        }

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

        # Logs
        self.error_save = [] 
        self.omega_log = []  
        self.omega_coi_prediction_log = []
        self.omega_coi_log = []

        # Initilailzed ADMM algorithm 
        self.admm = ADMM(self)

        print("[Main] Coordinator initialized.")

        # Start simulation
        try:
            self.terminated = self.run()
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
    
    def run(self):
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

                # === Disturbance injection ===
                if self.k == int(self.td/self.tstep):
                    self.disturbance = True
                    print("[Loop] Disturbance acting")

                    # self.andes.set_value({'model': 'GENROU',
                    #                       'idx': 'GENROU_2',
                    #                       'src': 'tm0',
                    #                       'attr': 'v',
                    #                       'value': 0})
                    # self.andes.set_value({'model': 'GENROU',
                    #                       'idx': 'GENROU_2',
                    #                       'src': 'u',
                    #                       'attr': 'v',
                    #                       'value': 0})

                    self.andes.set_value({'model': 'PQ',
                                          'idx': 'PQ_0',
                                          'src': 'Ppf',
                                          'attr': 'v',
                                          'value': 5.0})

                # === Execute control ===
                if self.k >= j * int(self.tdmpc/self.tstep):
                    j += 1
                    success, role_change_list = self.run_admm()
                    if not success:
                        print("[Error] ADMM failed.")
                        # break

                    # Send set points
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

    def collect_role_changes(self):
        """
        Collect role changes (i.e., setpoints) from all agents to apply via ANDES.

        Returns:
            list: A list of role change dictionaries suitable for `andes.set_value()`.
        """
        andes_role_changes = []
        agents = list(self.agents.values())

        if self.controlled:
            for agent in agents:
                for i, (gen_id, gov_id) in enumerate(zip(agent.generators, agent.governors)):

                    role_change = {
                        'model': 'TGOV1N',
                        'src': 'paux0',
                        'idx': gov_id,
                        'attr': 'v',
                        'value': agent.model.Pg[0, gen_id].value - agent.pref0[i]
                    }

                    andes_role_changes.append(role_change.copy())

        return andes_role_changes
