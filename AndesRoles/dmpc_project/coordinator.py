from admm import ADMM
from config import Config

class Coordinator:
    
    def __init__(self, agents, andes_interface):
        # Constants
        self.T =        Config.T
        self.q =        Config.q
        self.alpha =    Config.alpha
        self.rho =      Config.rho
        self.max_iter = Config.max_iter
        self.tol =      Config.tol

        # Andes interface
        self.andes = andes_interface

        # System agents and cache 
        self.agents = {agent.area: agent for agent in agents}

        self.neighbours = {
            area: self.andes.get_neighbour_areas(area)
            for area in self.agents
        }

        self.variables_horizon_values = {
            (i, j, t): 0.0 #NOTE: could be initialized differently
            for i in self.agents
            for j in self.agents
            for t in range(self.T + 1)
            }
        
        self.dual_vars = {
            (i, j, t): 0.0 #NOTE: could be initialized differently
            for i in self.agents
            for j in self.agents
            for t in range(self.T + 1)
            }
        
        self.dual_history = {
            (i, j, t): []
            for i in self.agents
            for j in self.agents
            for t in range(self.T + 1)
            }

        self.error_save = []

        self.admm = ADMM(self)

    def run_admm(self):
        return self.admm.solve()
    
    def run_simulation(self):
        t = 0
        while t < self.T:

            converged, role_changes, problem_state = self.run_admm()
            
            t += 1