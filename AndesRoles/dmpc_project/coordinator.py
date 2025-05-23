from admm import ADMM
from config import Config
import pdb

class Coordinator:
    
    def __init__(self, agents, andes_interface):
        # Constants
        self.dt = Config.dt
        self.T =  Config.T

        # Andes interface
        self.andes = andes_interface

        # System agents and cache 
        self.agents = {agent.area: agent for agent in agents}
        self.thetas = {}

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

        self.run_simulation()

    def run_admm(self):
        return self.admm.solve()
    
    def run_simulation(self):
        self.t = 0
        while self.t <= self.dt * self.T:

            # Get grid global variables (thetas)
            self._initialize_theta_values()

            # Solve ADMM-based optimization
            _, role_change_dict, _ = self.run_admm() #NOTE return necessary?

            # Send updated controls to ANDES
            self.andes.send_setpoint(role_change_dict)

            # Let ANDES continue
            self.andes.set_last_control_time(self.t)

            # Update time
            self.t += self.dt

    def _initialize_theta_values(self): #NOTE hardcoded, needs to be changed
        # Theta 
        for agent in self.agents:
            if agent == 1:
                self.thetas[agent] = 0.0
            else:
                self.thetas[agent] = self.andes.get_theta_equivalent(agent)[0] #NOTE: get_theta_equivalent needs to be modified 

        for agent in self.agents.values(): 
            agent.model.theta0.set_value(self.thetas[agent.area])
            for nbr in self.neighbours[agent.area]:
                agent.model.theta0_areas[nbr].set_value(self.thetas[nbr])


        



