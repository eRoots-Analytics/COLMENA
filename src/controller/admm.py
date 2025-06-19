"""
This class contains the logic of the ADMM algorithm.
"""

import numpy as np
import pyomo.environ as pyo
from src.config.config import Config

class ADMM:
    def __init__(self, coordinator):
        self.alpha =    Config.alpha
        self.max_iter = Config.max_iter
        self.tol =      Config.tol

        self.coordinator = coordinator

        self.primal_log = []
        self.cost_log = []

    def solve(self):
        agents = self.coordinator.agents.values()

        i = 0
        for i in range(self.max_iter):
            for agent in agents:

                if i==0: 
                    # Initialize the model for the first iteration
                    agent.initialize_variables_values()

                self._solve_agent(agent, i)

            # Residual computation
            primal_residual = self._compute_primal_residual_inf()
            self.coordinator.error_save.append(primal_residual) 

            print(f"Iteration {i}, Primal Residual: {primal_residual}")

            if primal_residual < self.tol:
                print("Distributed MPC converged (via primal residual)")
                return True, self.coordinator.collect_role_changes()

            self._update_duals(i)
            self._update_pyomo_params() 

        return False, self.coordinator.collect_role_changes()

    def _solve_agent(self, agent, i):
        if agent.setup:
            # agent.compute_offset()
            model = agent.setup_dmpc(self.coordinator)
            agent.setup = False #NOTE realiability check
        else:
            model = agent.model
        
        if i == 0:
            agent.first_warm_start() 
        else:
            agent.warm_start() 

        solver = pyo.SolverFactory('ipopt')
        result = solver.solve(model, tee=False)

        if result.solver.termination_condition != pyo.TerminationCondition.optimal:
            print(f"Infeasible or max iterations for agent {agent.area}")
            raise RuntimeError(f"Agent {agent.area} MPC failure at iteration {i}.")
        
        ########### FOR PLOTTING #############
        self.cost_log.append({
            "iteration": i,
            "freq_val" : pyo.value(model.freq_cost),
            "lagrangian_val" : pyo.value(model.lagrangian_term),
            "convex_val" : pyo.value(model.convex_term),
            "total_cost" : pyo.value(model.cost)
        })
        ######################################

        # Save results in the coordinator map
        # NOTE: this could be converted into a function for readibility
        # NOTE: inconsistent!!!!!!
        for nbr in self.coordinator.neighbours[agent.area]:
            self.coordinator.variables_horizon_values[agent.area, agent.area] = model.P_exchange[nbr].value  
            self.coordinator.variables_horizon_values[agent.area, nbr] = model.P_exchange_areas[nbr].value

        agent.save_warm_start()
                  
    def _update_duals(self, i):
        alpha = self.alpha
        vars_dict = self.coordinator.variables_horizon_values

        for (area, nbrs) in self.coordinator.neighbours.items():
            for nbr in nbrs:
                # Get local and neighbor values
                theta_ii = vars_dict[area, area]
                theta_ij = vars_dict[nbr, area]

                # Update the dual variable
                key = (area, nbr)
                lambda_old = self.coordinator.dual_vars[key]
                lambda_new = lambda_old + alpha * (theta_ii - theta_ij)
                self.coordinator.dual_vars[key] = lambda_new

                ########### FOR PLOTTING #############
                self.primal_log.append({
                    "iteration": i,
                    "area": area,
                    "nbr": nbr,
                    "theta_ii": theta_ii,
                    "theta_ij": theta_ij,
                    "residual": abs(theta_ii - theta_ij),
                    "dual": lambda_new
                })
                ######################################
    
    def _update_pyomo_params(self):
        vars_dict = self.coordinator.variables_horizon_values
        for agent in self.coordinator.agents.values():
            model = agent.model
            area = agent.area
            for nbr in self.coordinator.neighbours[area]:
                model.variables_horizon_values[area, area].value = vars_dict[area, area]
                model.variables_horizon_values[area, nbr].value = vars_dict[area, nbr]
                model.dual_vars[area, nbr].value = self.coordinator.dual_vars[area, nbr]

    def _compute_primal_residual_mse(self):
        residual_sum = 0.0
        count = 0
        vars_dict = self.coordinator.variables_horizon_values

        for (area, nbrs) in self.coordinator.neighbours.items():
            for nbr in nbrs:
                theta_ii = vars_dict[area, area]
                theta_ij = vars_dict[nbr, area]

                residual_sum += (theta_ii - theta_ij)**2
                count += 2

        return np.sqrt(residual_sum / count) if count else 0.0
    
    def _compute_primal_residual_inf(self):
        max_residual = 0.0
        vars_dict = self.coordinator.variables_horizon_values

        for (area, nbrs) in self.coordinator.neighbours.items():
            for nbr in nbrs:
                theta_ii = vars_dict[area, area]
                theta_ij = vars_dict[nbr, area]

                residual = abs(theta_ii - theta_ij)

                max_residual = max(max_residual, residual)

        return max_residual