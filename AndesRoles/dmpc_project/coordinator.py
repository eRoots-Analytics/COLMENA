from admm import ADMM
from config import Config
from mpc_agent import MPCAgent
from andes_interface import AndesInterface

class Coordinator:
    
    def __init__(self, agents, andes_interface):
        self.agents = {agent.area: agent for agent in agents}
        self.n_areas = len(self.agents)
        self.andes = andes_interface

        self.T =        Config.T
        self.q =        Config.q
        self.alpha =    Config.alpha
        self.rho =      Config.rho
        self.max_iter = Config.max_iter
        self.tol =      Config.tol

        self.neighbours = {}

        self.dual_vars = {}
        self.dual_history = {}
        self.dual_vars = {}
        self.dual_history = {}

        self.variables_horizon_values = {
                                         (i, j, t): 0.0
                                         for i in self.agents
                                         for j in self.agents
                                         for t in range(self.T + 1)
                                        }

        self.error_save = []

        self._build_neighbours() #NOTE: again build neighbours..
        self._initialize_duals()

        self.admm = ADMM(self)

    def run(self):
        return self.admm.solve()

    def _build_neighbours(self):
        for area in self.agents.keys():
            self.neighbours[area] = self.andes.get_neighbour_areas(area) #NOTE: check if area is int or str

    def _initialize_duals(self): #NOTE: is this consistent? 
        for a1 in self.agents.keys():
            for a2 in self.agents.keys():
                for t in range(self.T + 1):
                    self.dual_vars[a1, a2, t] = 0.0
                    self.dual_history[a1, a2, t] = []
