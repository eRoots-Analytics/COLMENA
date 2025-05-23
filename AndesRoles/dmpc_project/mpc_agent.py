import numpy as np
import pyomo.environ as pyo
from config import Config
from andes_interface import AndesInterface
import pdb  

class MPCAgent:
    def __init__(self, agent_id: str, andes_interface: AndesInterface):

        self.dt =        Config.dt
        self.T =         Config.T
        self.ramp_up =   Config.ramp_up
        self.ramp_down = Config.ramp_down
        self.freq_ref =  Config.freq_ref 

        self.agent_id = 'Agent_' + str(agent_id)
        self.area = agent_id
        self.andes = andes_interface  

        self.setup = True

        # self.variables_horizon_values = {} 
        self.variables_saved_values = {}
        self.gen_location = {}
        self.bus2idgen = {}

        # Get system data and state values
        self._get_system_data()
        # self.get_state_values() #NOTE: could be useless

        self.model = pyo.ConcreteModel()

        self.vars_saved = {
                            'freq': np.ones(self.T + 1),
                            'P': np.zeros(self.T + 1),
                            'P_exchange': np.zeros(self.T + 1),
                            'Pg': {(g, t): 0.0 for g in self.generators for t in range(self.T + 1)},
                            'theta': np.zeros(self.T + 1),
                            'theta_areas': {(area, t): 0.0 for area in self.other_areas for t in range(self.T + 1)},
                            }

    def setup_mpc(self, coordinator):

        ### Set up optimization model ###
        # Set for indexing
        self.model.generators =     pyo.Set(initialize=self.generators)
        self.model.loads =          pyo.Set(initialize=self.loads) 
        self.model.areas =          pyo.Set(initialize=self.areas)
        self.model.other_areas =    pyo.Set(initialize=self.other_areas)

        # Range Set for time indexing
        self.model.TimeHorizon =    pyo.RangeSet(0, self.T)
        self.model.TimeDynamics =   pyo.RangeSet(0, self.T - 1) #NOTE: to check if it is needed

        # Params: scalar and multidimensional
        self.model.M =                          pyo.Param(initialize=self.M_coi)
        self.model.D =                          pyo.Param(initialize=self.D_coi)
        self.model.fn =                         pyo.Param(initialize=self.fn_coi)
        self.model.Pd =                         pyo.Param(self.model.TimeHorizon, initialize=self.Pd)
        self.model.b =                          pyo.Param(self.model.other_areas, initialize=self.b_areas)
        self.model.Sn =                         pyo.Param(self.model.generators, initialize=self.Pe_base) #NOTE: useless because we don't consider generators individually
        self.model.dual_vars =                  pyo.Param(self.model.areas, self.model.areas, self.model.TimeHorizon, 
                                                          initialize=coordinator.dual_vars, mutable=True)
        self.model.variables_horizon_values =   pyo.Param(self.model.areas, self.model.areas, self.model.TimeHorizon,
                                                          initialize=coordinator.variables_horizon_values, mutable=True)
        self.model.freq0 =  pyo.Param(mutable=True)
        self.model.theta0 = pyo.Param(mutable=True)
        
        # Params: tuning 
        self.model.q =   pyo.Param(initialize=coordinator.q, mutable=True)
        self.model.rho = pyo.Param(initialize=coordinator.rho, mutable=True)
        
        # Decision variables
        def _get_power_bounds(model, i, t):
            gen_bus = self.gen_location[i]
            if gen_bus in self.PV_bus:
                j = self.PV_bus.index(gen_bus)
                return (self.pmin_pv[j], self.pmax_pv[j] + 0.2)
            elif gen_bus in self.slack_bus:
                j = self.slack_bus.index(gen_bus)
                return (self.pmin_slack[j], self.pmax_slack[j] + 0.2)
            else:
                return (0, 11) # NOTE: can be ereased theoretically 
            
        self.model.freq =           pyo.Var(self.model.TimeHorizon, bounds=(0.85, 1.15))
        self.model.P =              pyo.Var(self.model.TimeHorizon)
        self.model.P_exchange =     pyo.Var(self.model.TimeHorizon)
        self.model.Pg =             pyo.Var(self.model.generators, self.model.TimeHorizon, bounds=_get_power_bounds)
        self.model.theta =          pyo.Var(self.model.TimeHorizon, bounds=(-50, 50))
        self.model.theta_areas =    pyo.Var(self.model.other_areas, self.model.TimeHorizon, bounds=(-50, 50))

        ### Constraints ### 
        # Initial conditions
        def _initial_angle_areas(model, i): #NOTE: Hard coded, neeeds to be changed
            return model.theta_areas[i, 0] == coordinator.agents[i].theta0
        
        def _initial_p(model, i):
            idx = self.generators.index(i)
            return model.Pg[i, 0] == self.tm_values[idx]

        self.model.terminal_constraint1 = pyo.Constraint(expr=self.model.freq[self.T] == self.freq_ref)
        self.model.constraint_initial_conditions2 = pyo.Constraint(expr=self.model.freq[0] == self.model.freq0)
        self.model.constraint_initial_conditions1 = pyo.Constraint(expr=self.model.theta[0] == self.model.theta0)
        self.model.constraint_initial_conditions3 = pyo.Constraint(self.model.other_areas, rule=_initial_angle_areas)
        self.model.constraint_initial_conditions4 = pyo.Constraint(self.model.generators, rule=_initial_p)

        # Dynamics and ramp up/down
        self.model.constrains_dynamics2 = pyo.Constraint(self.model.TimeDynamics, rule=lambda model, t: model.M * (model.freq[t + 1] - model.freq[t]) / self.dt == model.P[t] - model.Pd[t] - model.P_exchange[t] - model.D * (model.freq[t] - 1))
        self.model.constrains_dynamics3 = pyo.Constraint(self.model.generators, self.model.TimeDynamics, rule=lambda model, i, t: (model.Pg[i, t + 1] - model.Pg[i, t]) <= self.dt * self.ramp_up)
        self.model.constrains_dynamics4 = pyo.Constraint(self.model.generators, self.model.TimeDynamics, rule=lambda model, i, t: -self.dt * self.ramp_down <= (model.Pg[i, t + 1] - model.Pg[i, t]))

        # Power transmission
        def _power_inter_area(model, t): # NOTE: add constraint on power exchange
            return model.P_exchange[t] == sum(model.b[nbr] * (model.theta[t] - model.theta_areas[nbr, t]) for nbr in model.other_areas)
        
        self.model.constraints_balance =  pyo.Constraint(self.model.TimeHorizon, rule=lambda model, t: model.P[t] == sum(model.Pg[gen, t] for gen in model.generators))
        self.model.constraints_area =     pyo.Constraint(self.model.TimeHorizon, rule=_power_inter_area)

        ### Cost ###
        def _freq_cost(model):
            return model.q * sum((model.freq[t] - 1)**2 for t in model.TimeHorizon)

        def _lagrangian_term(model):
            return sum(
                model.dual_vars[nbr, self.area, t] * (model.theta[t] - model.variables_horizon_values[nbr, self.area, t]) + # NOTE: model.variables_horizon_values[self.area, nbr, t] is actually useless
                model.dual_vars[nbr, nbr, t] * (model.variables_horizon_values[nbr, nbr, t] - model.theta_areas[nbr, t])    # NOTE: model.variables_horizon_values[nbr, nbr, t] is actually useless
                for nbr in model.other_areas for t in model.TimeHorizon
                )

        def _convex_term(model):
            eps = 1e-4
            return model.rho * sum(
                (model.theta[t] - model.variables_horizon_values[nbr, self.area, t])**2 +
                (model.variables_horizon_values[nbr, nbr, t] - model.theta_areas[nbr, t])**2
                for nbr in model.other_areas for t in model.TimeHorizon
            ) + eps
        
        self.model.cost = pyo.Objective(rule=lambda model: _freq_cost(model) + _lagrangian_term(model) + _convex_term(model), sense=pyo.minimize)
        
        return self.model
    
    def _get_area_devices(self):
        """
        Get the devices list in area from Andes.
        """
        self.generators = self.andes.get_area_variable("GENROU", "idx", self.area)
        self.loads = self.andes.get_area_variable("PQ", "idx", self.area)
        self.areas = self.andes.get_complete_variable("Area", "idx")
        self.buses = self.andes.get_area_variable("Bus", "idx", self.area)
        self.PV_bus = self.andes.get_area_variable("PV", "bus", self.area)
        self.generator_bus = self.andes.get_area_variable("GENROU", "bus", self.area)
        self.slack_bus = self.andes.get_complete_variable("Slack", "bus", self.area)

        self.gen_location = {gen: self.generator_bus[i] for i, gen in enumerate(self.generators)}
        self.bus2idgen = {self.generator_bus[i]: gen for i, gen in enumerate(self.generators)}
    
    def _get_neighbour_areas(self):
        """
        Get the neighbour areas from Andes.
        """
        self.other_areas = self.andes.get_neighbour_areas(self.area)    
    
    def _get_area_device_params(self):
        """
        Get the parameters in area from Andes.
        """
        self.Sn_values = self.andes.get_partial_variable("GENROU", "Sn", self.generators)
        self.Pe_values = self.andes.get_partial_variable("GENROU", "Pe", self.generators)
        self.tm_values = self.andes.get_partial_variable("GENROU", "tm", self.generators)
        self.M_values =  self.andes.get_partial_variable("GENROU", "M", self.generators)
        self.D_values =  self.andes.get_partial_variable("GENROU", "D", self.generators)
        self.fn_values = self.andes.get_partial_variable("GENROU", "fn", self.generators)
        self.p0_values = self.andes.get_complete_variable("PV", "p0")

        self._compute_coi_parameters()

        self.pmax_slack = self.andes.get_complete_variable("Slack", "pmax", self.area)
        self.pmin_slack = self.andes.get_complete_variable("Slack", "pmin", self.area)
        self.pmax_pv = self.andes.get_area_variable("PV", "pmax", self.area)
        self.pmin_pv = self.andes.get_area_variable("PV", "pmin", self.area)
    
    def _get_system_susceptance(self):
        self.b_areas = self.andes.get_system_susceptance(self.area)
    
    def _compute_coi_parameters(self): #NOTE to move
        """
        Compute the COI model parameters for the area.
        """
        self.S_area = 0.0
        self.M_coi = 0.0 
        self.Pd = 0.0
        self.D_coi = 0.0
        self.fn_coi = 0.0  
        self.P_demand = 0.0

        for i, bus in enumerate(self.generator_bus):
            if bus in self.buses:
                Sn = self.Sn_values[i]
                self.S_area += Sn
                self.M_coi += self.M_values[i]
                self.Pd += self.Pe_values[i]
                self.D_coi += Sn * self.D_values[i]
                self.fn_coi += Sn * self.fn_values[i]
                self.P_demand += self.Pe_values[i]

        if self.S_area > 0:
            self.D_coi /= self.S_area
            self.fn_coi = 60.0  # Set nominal frequency explicitly

        self.Pe_base = {gen: self.Pe_values[i] for i, gen in enumerate(self.generators)} 

    def _get_system_data(self):
        self._get_area_devices()
        self._get_neighbour_areas() 
        self._get_area_device_params()
        self._get_system_susceptance()
    
    def _get_theta_equivalent(self): #NOTE: change the name
        self.delta_theta = self.andes.get_theta_equivalent(self.area)

    def get_state_values(self):
        if self.area == 1:
            self.model.theta0.set_value(0.0)
        else:
            self._get_theta_equivalent()
            self.model.theta0.set_value(self.delta_theta)                     #NOTE: this is a hard coded value, needs to be changed

        freq_values = self.andes.get_partial_variable("GENROU", "omega", self.generators)
        weight = np.array(self.M_values) * np.array(self.Sn_values)
        freq0 = np.dot(weight, np.array(freq_values)) / np.sum(weight)
        self.model.freq0.set_value(freq0) 
        

    def first_warm_start(self): #NOTE: can be improved
        for t in range(self.T + 1):
            self.vars_saved['freq'][t] = self.freq0
            self.vars_saved['P'][t] = sum(self.tm_values)
            self.vars_saved['P_exchange'][t] = 0.0 #NOTE: can be initilaied differently 
            self.vars_saved['theta'][t] = self.theta0 

            for area in self.other_areas:
                self.vars_saved['theta_areas'][(area, t)] = 0.0 #NOTE: can be initilaied differently 

            for i, gen in enumerate(self.generators):
                self.vars_saved['Pg'][(gen, t)] = self.tm_values[i]
        
        self.warm_start()
        
    def warm_start(self):
        for t in range(self.T + 1):
            self.model.freq[t].value = self.vars_saved['freq'][t] #max(self.vars_saved['freq'][t], 0.85)
            self.model.P[t].value = self.vars_saved['P'][t]
            self.model.P_exchange[t].value = self.vars_saved['P_exchange'][t]
            self.model.theta[t].value = self.vars_saved['theta'][t]

            for nbr in self.other_areas:
                self.model.theta_areas[nbr, t].value = self.vars_saved['theta_areas'][(nbr, t)]

            for gen in self.generators:
                self.model.Pg[gen, t].value = self.vars_saved['Pg'][(gen, t)]
    
    def save_warm_start(self):
        for t in range(self.T + 1):
            self.vars_saved['freq'][t] = self.model.freq[t].value
            self.vars_saved['P'][t] = self.model.P[t].value
            self.vars_saved['P_exchange'][t] = self.model.P_exchange[t].value
            self.vars_saved['theta'][t] = self.model.theta[t].value

            for nbr in self.other_areas:
                self.vars_saved['theta_areas'][(nbr, t)] = self.model.theta_areas[nbr, t].value

            for gen in self.generators:
                self.vars_saved['Pg'][(gen, t)] = self.model.Pg[gen, t].value



    