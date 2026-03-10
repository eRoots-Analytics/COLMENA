"""
This class contains the logic of the ADMM algorithm.
"""

import numpy as np
import pyomo.environ as pyo
from colmenasrc.config.config import Config

class ADMM:
    def __init__(self, coordinator):
        """
        Initialize ADMM parameters and link to the main coordinator object.
            
        Args:
            coordinator: An instance of the Coordinator class that manages agents and system state.
        """
        self.controlled = Config.controlled
        
        self.alpha =    Config.alpha
        self.max_iter = Config.max_iter
        self.tol =      Config.tol

        self.rho =          Config.rho
        self.rho_diff =     Config.rho_diff
        self.rho_scaled =   Config.rho_scaled
        self.coordinator = coordinator

    def solve(self):
        """
        Execute the ADMM algorithm to coordinate agent MPCs.

        Returns:
            success (bool): Whether convergence was achieved.
            role_changes (list): Role change instructions for the system actuators.
        """
        agents = self.coordinator.agents.values()

        i = 0
        for i in range(self.max_iter):
            for agent in agents:   
                if agent.generators: 
                    if i==0: 
                        # Initialize the model for the first iteration
                        agent.initialize_variables_values()

                    if self.controlled:
                        self._solve_agent(agent, i)

                    # Residual computation
                    primal_residual = self._compute_primal_residual_inf()
                    self.coordinator.error_save.append(primal_residual) 

                    print(f"Iteration {i}, Primal Residual: {primal_residual}")

                    if primal_residual < self.tol:
                        print("Distributed MPC converged (via primal residual)")
                        return True, self.coordinator.collect_role_changes()

            self._update_duals()
            self._update_pyomo_params() 

        return False, self.coordinator.collect_role_changes()

    def _solve_agent(self, agent, i, colmena = False):
        """
        Solve the local MPC problem for an agent at ADMM iteration i.

        Args:
            agent: The MPC agent.
            i (int): Current ADMM iteration.
        """
        # 0. Setup
        if agent.setup:
            model = agent.setup_dmpc(self.coordinator)
            agent.setup = False 
        else:
            model = agent.model
        
        if i == 0:
            agent.first_warm_start() 
        else:
            agent.warm_start() 

        # 1. Solve
        solver = pyo.SolverFactory('ipopt')
        result = solver.solve(model, tee=False)

        if result.solver.termination_condition != pyo.TerminationCondition.optimal:
            print(f"Infeasible or max iterations for agent {agent.area}")
            raise RuntimeError(f"Agent {agent.area} MPC failure at iteration {i}.")
        
        ########### FOR PLOTTING #############
        omega_coi_pred = [pyo.value(model.omega[k]) for k in model.TimeHorizon]
        if not Config.agent:
            self.coordinator.omega_coi_prediction_log.append(
                (self.coordinator.t, {str(agent.area): omega_coi_pred})
            )
        ######################################

        # 2. Save
        for k in model.TimeInput:
            if not Config.angles:
                for nbr in self.coordinator.neighbours[agent.area]:
                    self.coordinator.variables_horizon_values[agent.area, nbr, k, agent.area] = model.P_exchange[k, nbr].value  
                    self.coordinator.variables_horizon_values[nbr, agent.area, k, agent.area] = model.P_exchange_areas[k, nbr].value
            else:
                for nbr in self.coordinator.neighbours[agent.area]:
                    self.coordinator.variables_horizon_values_P[agent.area, nbr, k, agent.area] = model.P_exchange[k, nbr].value  
                    self.coordinator.variables_horizon_values[nbr, agent.area, k] = model.delta[k].value  
                    self.coordinator.variables_horizon_values[agent.area, nbr, k] = model.delta_areas[nbr, k].value  

        agent.save_warm_start()
                  
    def _update_duals(self, agent = None):
        """
        Update dual variables based on current power exchange disagreement.
        """
        alpha = self.alpha
        vars_dict = self.coordinator.variables_horizon_values
        if Config.angles:
            vars_dict_P = self.coordinator.variables_horizon_values_P

        for (area, nbrs) in self.coordinator.neighbours.items():
            for nbr in nbrs:
                for k in range(self.coordinator.K):
                    # Get local and neighbor values
                    if not Config.angles and k != self.coordinator.K:
                        theta_ii = vars_dict[area, nbr, k, area]
                        theta_ij = vars_dict[area, nbr, k, nbr]

                        # Update the dual variable
                        key = (area, nbr, k)
                        lambda_old = self.coordinator.dual_vars[key]
                        lambda_new = lambda_old + alpha * (theta_ii - theta_ij)
                        self.coordinator.dual_vars[key] = lambda_new
                    else:
                        # Update the dual variable P
                        alpha = self.rho
                        P_ij = vars_dict_P[area, nbr, k]
                        P_ji = vars_dict_P[nbr, area, k]
                        key = (area, nbr, k)
                        lambda_old = self.coordinator.dual_vars_P[key]
                        lambda_new = lambda_old + alpha * (P_ij + P_ji)
                        self.coordinator.dual_vars_P[key] = lambda_new

                        # Update the dual variable for angles
                        alpha = self.rho*self.rho_scaled[k]
                        theta_ii = vars_dict[area, area, k]
                        theta_ij = vars_dict[nbr, area, k]
                        key = (area, nbr, k)
                        lambda_old = self.coordinator.dual_vars[key]
                        lambda_new = lambda_old + alpha * (theta_ii - theta_ij)
                        self.coordinator.dual_vars[key] = lambda_new
                        
                        # Update the dual variable for angles diff 
                        if k == self.coordinator.K:
                            continue
                        alpha = self.rho*self.rho_diff
                        theta_iik = vars_dict[area, area, k]
                        theta_ijk = vars_dict[nbr, area, k]
                        theta_iikone = vars_dict[area, area, k+1]
                        theta_ijkone = vars_dict[nbr, area, k+1]
                        key = (area, nbr, k)
                        lambda_old = self.coordinator.dual_vars_diff[key]
                        lambda_new = lambda_old + alpha * (theta_iikone - theta_iik - (theta_ijkone - theta_ijk))
                        self.coordinator.dual_vars_diff[key] = lambda_new
    
    def _update_pyomo_params(self, agent_a = None):
        """
        Synchronize shared variables and duals in Pyomo models across agents.
        """
        vars_dict = self.coordinator.variables_horizon_values

        for agent in self.coordinator.agents.values():
            if agent_a is not None:
                agent = agent_a
            if agent.generators:
                model = agent.model
                area = agent.area
                for nbr in self.coordinator.neighbours[area]:
                    for k in range(self.coordinator.K):
                        if not Config.angles:
                            model.variables_horizon_values[area, nbr, k, area].value = vars_dict[area, nbr, k, area]
                            model.variables_horizon_values[area, nbr, k, nbr].value = vars_dict[area, nbr, k, nbr]
                            model.dual_vars[area, nbr, k].value         = self.coordinator.dual_vars[area, nbr, k]
                        else:
                            vars_dict_P = self.coordinator.variables_horizon_values_P

                            model.variables_horizon_values[area, nbr, k].value = vars_dict[area, nbr, k]
                            model.variables_horizon_values[nbr, area, k].value = vars_dict[nbr, area, k]
                            model.variables_horizon_values_P[area, nbr, k].value = vars_dict_P[area, nbr, k]
                            model.variables_horizon_values_P[nbr, area, k].value = vars_dict_P[nbr, area, k]

                            model.dual_vars[area, nbr, k].value         = self.coordinator.dual_vars[area, nbr, k]
                            model.dual_vars_P[area, nbr, k].value       = self.coordinator.dual_vars_P[area, nbr, k]
                            model.dual_vars_diff[area, nbr, k].value    = self.coordinator.dual_vars_diff[area, nbr, k]

    def _compute_primal_residual_mse(self):
        """
        Compute the Mean Squared Error (MSE) of primal residuals over all agents.

        Returns:
            float: The root mean squared primal residual.
        """
        residual_sum = 0.0
        count = 0
        vars_dict = self.coordinator.variables_horizon_values

        for (area, nbrs) in self.coordinator.neighbours.items():
            for nbr in nbrs:
                for k in range(self.coordinator.K):
                    if not Config.angles:
                        theta_ii = vars_dict[area, nbr, k, area]
                        theta_ij = vars_dict[area, nbr, k, nbr]
                    else:
                        theta_ii = vars_dict[area, nbr, k]
                        theta_ij = vars_dict[nbr, area, k]

                    residual_sum += (theta_ii - theta_ij)**2
                    count += 2

        return np.sqrt(residual_sum / count) if count else 0.0
    
    def _compute_primal_residual_inf(self):
        """
        Compute the infinity norm (max absolute) of primal residuals.

        Returns:
            float: Maximum absolute difference between shared variables.
        """
        max_residual = 0.0
        vars_dict = self.coordinator.variables_horizon_values

        for (area, nbrs) in self.coordinator.neighbours.items():
            for nbr in nbrs:
                for k in range(self.coordinator.K):
                    if not Config.angles:
                        theta_ii = vars_dict[area, nbr, k, area]
                        theta_ij = vars_dict[area, nbr, k, nbr]
                    else:
                        theta_ii = vars_dict[area, nbr, k]
                        theta_ij = vars_dict[nbr, area, k]
                    residual = abs(theta_ii - theta_ij)

                    max_residual = max(max_residual, residual)

        return max_residual