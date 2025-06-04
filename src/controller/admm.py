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
            self._update_pyomo_params() # NOTE: convergence can be improved by updating only the changed agents

        return False, self.coordinator.collect_role_changes()

    def _solve_agent(self, agent, i):
        if agent.setup: #NOTE: in online setup needs to changed
            model = agent.setup_dmpc(self.coordinator) 
            agent.first_warm_start() 
        else:
            model = agent.model
        agent.setup = False #NOTE realiability check

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

        agent.save_warm_start()

        # Save results in the coordinator map NOTE: this could be converted into a function for readibility
        for k in model.TimeStates:
            self.coordinator.variables_horizon_values[agent.area, agent.area, k] = model.theta[k + 1].value                                    
            for nbr in self.coordinator.neighbours[agent.area]:
                self.coordinator.variables_horizon_values[nbr, agent.area, k] = model.theta_areas[nbr, k].value   
                  
    def _update_duals(self, i):
        alpha = self.alpha
        vars_dict = self.coordinator.variables_horizon_values

        for (area, nbrs) in self.coordinator.neighbours.items():
            for nbr in nbrs:
                for k in range(self.coordinator.K):
                    # Get local and neighbor values
                    theta_ii = vars_dict[area, area, k]
                    theta_ij = vars_dict[area, nbr, k]

                    # Update the dual variable
                    key = (area, nbr, k)
                    lambda_old = self.coordinator.dual_vars[key]
                    lambda_new = lambda_old + alpha * (theta_ii - theta_ij)
                    self.coordinator.dual_vars[key] = lambda_new

                    ########### FOR PLOTTING #############
                    self.primal_log.append({
                        "iteration": i,
                        "k": k,
                        "area": area,
                        "nbr": nbr,
                        "theta_ii": theta_ii,
                        "theta_ij": theta_ij,
                        "residual": abs(theta_ii - theta_ij),
                        "dual": lambda_new
                    })
                    ######################################
    
    def _update_pyomo_params(self):
        for agent in self.coordinator.agents.values():
            model = agent.model
            area = agent.area
            for nbr in self.coordinator.neighbours[area]:
                for k in range(self.coordinator.K):
                    model.variables_horizon_values[area, nbr, k].value = self.coordinator.variables_horizon_values[area, nbr, k]
                    model.dual_vars[area, nbr, k].value = self.coordinator.dual_vars[area, nbr, k]

    def _compute_primal_residual_mse(self):
        residual_sum = 0.0
        count = 0
        vars_dict = self.coordinator.variables_horizon_values

        for (area, nbrs) in self.coordinator.neighbours.items():
            for nbr in nbrs:
                for k in range(self.coordinator.K):
                    theta_ii = vars_dict[area, area, k]
                    theta_ij = vars_dict[area, nbr, k]

                    residual_sum += (theta_ii - theta_ij)**2
                    count += 2

        return np.sqrt(residual_sum / count) if count else 0.0
    
    def _compute_primal_residual_inf(self):
        max_residual = 0.0
        vars_dict = self.coordinator.variables_horizon_values

        for (area, nbrs) in self.coordinator.neighbours.items():
            for nbr in nbrs:
                for k in range(self.coordinator.K):
                    theta_ii = vars_dict[area, area, k]
                    theta_ij = vars_dict[area, nbr, k]

                    residual = abs(theta_ii - theta_ij)

                    max_residual = max(max_residual, residual)

        return max_residual