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

    def solve(self):
        agents = self.coordinator.agents.values()

        for i in range(self.max_iter):
            for agent in agents:

                if i==0: 
                    # Initialize the model for the first iteration
                    agent.initialize_variables_values()
                # pdb.set_trace()

                self._solve_agent(agent, i)

            primal_residual = self._compute_primal_residual_inf()
            self.coordinator.error_save.append(primal_residual) 

            print(f"Iteration {i}, Primal Residual: {primal_residual}")

            if primal_residual < self.tol:
                print("Distributed MPC converged (via primal residual)")
                return True, self.coordinator.collect_role_changes()

            self._update_duals()
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

        agent.save_warm_start()

        # Save results in the coordinator map NOTE: this could be converted into a function for readibility
        for t in model.TimeHorizon:
            self.coordinator.variables_horizon_values[agent.area, agent.area, t] = model.theta[t].value                                    
            for nbr in self.coordinator.neighbours[agent.area]:
                self.coordinator.variables_horizon_values[agent.area, nbr, t] = model.theta_areas[nbr, t].value   
                  
    def _update_duals(self):
        alpha = self.alpha
        vars_dict = self.coordinator.variables_horizon_values

        for (area, nbrs) in self.coordinator.neighbours.items():
            for nbr in nbrs:
                for t in range(self.coordinator.K + 1):
                    # Get local and neighbor values
                    theta_ii = vars_dict[area, area, t]
                    theta_ji = vars_dict[nbr, area, t]

                    # Update the dual variable
                    key = (nbr, area, t)
                    lambda_old = self.coordinator.dual_vars[key]
                    lambda_new = lambda_old + alpha * (theta_ii - theta_ji)
                    self.coordinator.dual_vars[key] = lambda_new
    
    def _update_pyomo_params(self):
        for agent in self.coordinator.agents.values():
            model = agent.model
            area = agent.area
            for nbr in self.coordinator.neighbours[area]:
                for t in range(self.coordinator.K + 1):
                    model.variables_horizon_values[area, nbr, t].value = self.coordinator.variables_horizon_values[area, nbr, t]
                    model.dual_vars[area, nbr, t].value = self.coordinator.dual_vars[area, nbr, t]

    def _compute_primal_residual_mse(self):
        residual_sum = 0.0
        count = 0
        vars_dict = self.coordinator.variables_horizon_values

        for (area, nbrs) in self.coordinator.neighbours.items():
            for nbr in nbrs:
                for t in range(self.coordinator.K + 1):
                    theta_ii = vars_dict[area, area, t]
                    theta_ji = vars_dict[nbr, area, t]

                    residual_sum += (theta_ii - theta_ji)**2
                    count += 2

        return np.sqrt(residual_sum / count) if count else 0.0
    
    def _compute_primal_residual_inf(self):
        max_residual = 0.0
        vars_dict = self.coordinator.variables_horizon_values

        for (area, nbrs) in self.coordinator.neighbours.items():
            for nbr in nbrs:
                for t in range(self.coordinator.K + 1):
                    theta_ii = vars_dict[area, area, t]
                    theta_ji = vars_dict[nbr, area, t]

                    residual = abs(theta_ii - theta_ji)

                    max_residual = max(max_residual, residual)

        return max_residual