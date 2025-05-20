import numpy as np
import pyomo.environ as pyo
from pyomo.environ import value, Constraint

class ADMM:
    def __init__(self, coordinator):
        self.coordinator = coordinator

    def solve(self):
        agents = list(self.coordinator.agents.values())
        others = self.coordinator.neighbours

        for i in range(self.coordinator.max_iter):
            for agent in agents:
                
                self._solve_agent(agent, others[agent.area], i)

            primal_residual = self._compute_primal_residual()
            self.coordinator.error_save.append(primal_residual) 

            print(f"Iteration {i}, Primal Residual: {primal_residual:.6f}")

            if primal_residual < self.coordinator.tol:
                print("Distributed MPC converged (via primal residual)")
                return True, self._collect_role_changes(), self.coordinator
            
            self._update_duals()

        return False, self._collect_role_changes(), self.coordinator

    def _solve_agent(self, agent, other_agent, i):
        if i==0: #NOTE: in online setup needs to changed
            agent.first_warm_start()
            model = agent.setup_mpc(self.coordinator) #NOTE: mpc agent construction should happen once and never again 
        else:
            model = agent.model
            agent.warm_start()

            #NOTE: is this necessary?
            for k, v in self.coordinator.variables_horizon_values.items():
                model.variables_horizon_values[k].value = v
            for k, v in self.coordinator.dual_vars.items():
                model.dual_vars[k].value = v

        solver = pyo.SolverFactory('ipopt')
        result = solver.solve(model, tee=False) #NOTE: cost vector necessary? How do you access results? 

        if result.solver.termination_condition != pyo.TerminationCondition.optimal:
            print(f"Infeasible or max iterations for agent {agent.area}")
            self._check_constraint_violations(model) #NOTE: place in utils
            raise RuntimeError(f"Agent {agent.area} MPC failure at iteration {i}.")

        agent.save_warm_start()

        # Save delta values
        agent.theta_primal.append({t: model.theta[t].value for t in model.TimeHorizon})
        agent.theta_areas_primal.append({(nbr, t): model.theta_areas[nbr, t].value for nbr in agent.model.other_areas for t in model.TimeHorizon})

        for t in model.TimeHorizon:
            for other_agent in self.coordinator.agents.values():
                if other_agent.area == agent.area:
                    continue
                self.coordinator.variables_horizon_values[agent.area, agent.area, t] = model.theta[t].value
                self.coordinator.variables_horizon_values[other_agent.area, agent.area, t] = model.theta_areas[other_agent.area, t].value

    def _update_duals(self):
        alpha = self.coordinator.alpha

        for (area, nbrs) in self.coordinator.neighbours.items():
            for nbr in nbrs:
                for t in range(self.coordinator.T + 1):
                    # Get local and neighbor values
                    theta_i = self.coordinator.variables_horizon_values[area, area, t]
                    theta_j = self.coordinator.variables_horizon_values[area, nbr, t]

                    # Update the dual variable
                    key = (area, nbr, t)
                    lambda_old = self.coordinator.dual_vars[key]
                    lambda_new = lambda_old + alpha * (theta_i - theta_j)
                    self.coordinator.dual_vars[key] = lambda_new

    def _compute_primal_residual(self):
        residual_sum = 0.0
        count = 0
        vars_dict = self.coordinator.variables_horizon_values

        for (area, nbrs) in self.coordinator.neighbours.items():
            for nbr in nbrs:
                for t in range(self.coordinator.T + 1):
                    theta_ii = vars_dict[area, area, t]
                    theta_ji = vars_dict[nbr, area, t]

                    theta_jj = vars_dict[nbr, nbr, t]
                    theta_ij = vars_dict[area, nbr, t]

                    residual_sum += (theta_ii - theta_ji)**2 + (theta_jj - theta_ij)**2
                    count += 2
        return np.sqrt(residual_sum / count) if count else 0.0

    def _collect_role_changes(self):
        andes_role_changes = []
        agents = list(self.coordinator.agents.values())
        
        # Sync time (assuming all agents return the same)
        time_start = self.coordinator.andes.sync_time()

        for agent in agents:
            for gen_id in agent.generators:
                kundur = not isinstance(gen_id, str)
                id_number = gen_id if kundur else (gen_id[-2:] if gen_id[-2] != '_' else gen_id[-1])
                for t in range(1, agent.T + 1):
                    for param in ['p_direct', 'b']:  # Adjust this list if needed

                        role_change = {'var': param,
                                       't': time_start + agent.dt * t}
                        
                        if param == 'tm0':
                            role_change['model'] = 'GENROU'
                            role_change['idx'] = 'GENROU_' + id_number
                        else:
                            role_change['model'] = 'TGOV1' if kundur else 'TGOV1N'
                            role_change['idx'] = id_number if kundur else 'TGOV1_' + id_number
                        
                        if param == 'paux0':
                            role_change['value'] = agent.model.Pg[gen_id, t].value - agent.model.Pg[gen_id, 0].value
                        elif param == 'b':
                            role_change['value'] = 1
                        else:
                            role_change['value'] = agent.model.Pg[gen_id, t].value

                        # Send to Andes
                        self.coordinator.andes.send_setpoint(role_change)
                        andes_role_changes.append(role_change.copy())
        
        return andes_role_changes


    def _check_constraint_violations(self, model):
        print("\nConstraint violations (abs residual > {:.1e}):".format(self.coordinator.tol))
        for constr in model.component_objects(Constraint, active=True):
            for index in constr:
                c = constr[index]
                expr = c.body
                val = value(expr)

                violated = False
                msg = f"{c.name}[{index}]: {expr} = {val:.4e}"

                lb = value(c.lower) if c.has_lb() else None
                ub = value(c.upper) if c.has_ub() else None

                if lb is not None and ub is not None and abs(lb - ub) < 1e-8:
                    # Equality constraint
                    if abs(val - lb) > self.coordinator.tol:
                        msg += f" ≠ EQ({lb:.4e}) "
                        violated = True
                else:
                    if lb is not None and val < lb - self.coordinator.tol:
                        msg += f" < LB({lb:.4e}) "
                        violated = True
                    if ub is not None and val > ub + self.coordinator.tol:
                        msg += f" > UB({ub:.4e}) "
                        violated = True

                if violated:
                    print(constr.pprint())
                    print(msg)