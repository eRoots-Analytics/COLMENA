import numpy as np

class Coordinator:
    def __init__(self, agents, rho, max_iter, tol):
        self.agents = agents
        self.rho = rho
        self.max_iter = max_iter
        self.tol = tol
        self.shared_vars = {}
        self.z = {}
        self.u = {}

    def run_admm_step(self):
        # ADMM loop
        for iteration in range(self.max_iter):
            # Step 1: Each agent solves its local MPC
            all_vars = []
            for agent in self.agents:
                agent_id = agent.agent_id
                agent.update_shared_vars(self.z)
                agent.update_dual_vars(self.u.get(agent_id, {}))
                agent.solve()
                all_vars.append(agent.get_shared_vars())

            # Step 2: Average shared variables
            keys = all_vars[0].keys()
            self.z = {k: np.mean([vars[k] for vars in all_vars]) for k in keys}

            # Step 3: Dual update
            converged = True
            for agent in self.agents:
                uid = agent.agent_id
                if uid not in self.u:
                    self.u[uid] = {k: 0.0 for k in keys}
                for k in keys:
                    prev_u = self.u[uid][k]
                    primal_val = agent.get_shared_vars()[k]
                    self.u[uid][k] += self.rho * (primal_val - self.z[k])
                    if abs(primal_val - self.z[k]) > self.tol:
                        converged = False

            if converged:
                break
