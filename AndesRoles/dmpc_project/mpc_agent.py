import numpy as np
import pyomo.environ as pyo
from config import Config
from andes_interface import AndesInterface
from itertools import product
import pdb  

class MPCAgent:
    def __init__(self, agent_id: str, andes_interface: AndesInterface):

        self.agent_id = 'Agent_' + str(agent_id)
        self.area = agent_id
        self.andes = andes_interface

        self.dt =        Config.dt
        self.T =         Config.T
        self.ramp_up =   Config.ramp_up
        self.ramp_down = Config.ramp_down

        self.theta_primal = []
        self.theta_areas_primal = []    

        # self.variables_horizon_values = {} 
        self.variables_saved_values = {}
        self.gen_location = {}
        self.bus2idgen = {}

        # Get everything from Andes
        self._get_area_devices()
        self._get_neighbour_areas() #NOTE: again build neighbours..
        self._get_area_device_params()
        self._get_system_susceptance()

        self.model = pyo.ConcreteModel()

        # self.variables_horizon_values = {(area, nbr, t): 0
                                        #  for area, nbr, t in product(self.areas, self.other_areas, range(self.T + 1))}
        self.omega_previous = {t: 0
                               for t in range(self.T + 1)}
        
        # self.delta_previous = {t: 0 
                            #    for t in range(self.T + 1)}

        self.saved_states = {
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
        self.model.other_areas =    pyo.Set(initialize=self.other_areas)
        self.model.areas =          pyo.Set(initialize=self.areas)

        # Range Set for time indexing
        self.model.TimeHorizon =    pyo.RangeSet(0, self.T)
        self.model.TimeDynamics =   pyo.RangeSet(0, self.T - 1)

        # Params: scalar and multidimensional
        self.model.M =                          pyo.Param(initialize=self.M_coi)
        self.model.D =                          pyo.Param(initialize=self.D_coi)
        self.model.fn =                         pyo.Param(initialize=self.fn_coi)
        self.model.Pd =                         pyo.Param(self.model.TimeHorizon, initialize=self.Pd) #NOTE: self.Pd is a scalar so no need to use a set
        self.model.b =                          pyo.Param(self.model.other_areas, initialize=self.b_areas)
        self.model.Sn =                         pyo.Param(self.model.generators, initialize=self.Pe_base) #NOTE: useless because we don't consider generators individually
        self.model.dual_vars =                  pyo.Param(self.model.areas, self.model.areas, self.model.TimeHorizon, initialize=coordinator.dual_vars, mutable=True) #NOTE: works becuase they are all connected
        self.model.theta_previous =             pyo.Param(self.model.TimeHorizon, initialize=self.omega_previous, mutable=True)
        # self.model.delta_previous =             pyo.Param(self.model.TimeHorizon, initialize=self.delta_previous, mutable=True)
        self.model.variables_horizon_values =   pyo.Param(self.model.areas, self.model.areas, self.model.TimeHorizon,
                                                          initialize=coordinator.variables_horizon_values, mutable=True) #NOTE: works becuase they are all connected
        
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
                return (0, 11)
            
        self.model.freq =           pyo.Var(self.model.TimeHorizon, bounds=(0.85, 1.15))
        self.model.P =              pyo.Var(self.model.TimeHorizon, initialize=0.0)
        self.model.P_exchange =     pyo.Var(self.model.TimeHorizon, initialize=0.0)
        self.model.Pg =             pyo.Var(self.model.generators, self.model.TimeHorizon, bounds=_get_power_bounds)
        self.model.theta =          pyo.Var(self.model.TimeHorizon, bounds=(-50, 50))
        self.model.theta_areas =    pyo.Var(self.model.other_areas, self.model.TimeHorizon, bounds=(-50, 50), initialize=0.0)
        # self.model.delta =          pyo.Var(self.model.TimeHorizon, bounds=(-50, 50))
        # self.model.delta_areas =    pyo.Var(self.model.other_areas, self.model.TimeHorizon, bounds=(-50, 50), initialize=0.0)
        
        # Tuning parameters
        self.model.q =   pyo.Param(initialize=coordinator.q, mutable=True)
        self.model.rho = pyo.Param(initialize=coordinator.rho, mutable=True)

        ### Constraints ### 
        # Initial conditions
        self.delta0, self.freq0 = self._get_initial_states()

        # self.model.constraint_initial_conditions1 = pyo.Constraint(expr=self.model.delta[0] == self.delta0)

        def _initial_angle_areas(model, i): #NOTE Pablo implemented something different 
            return model.theta_areas[i, 0] == 0.0
        
        def _initial_p(model, i):
            try:
                idx = self.generators.index(i)
                return model.Pg[i, 0] == self.tm_values[idx]
            except Exception:
                return model.Pg[i, 0] == self.p0_values[self.PV_bus.index(self.gen_location[i])]

        self.model.constraint_initial_conditions2 = pyo.Constraint(expr=self.model.freq[0] == self.freq0)
        self.model.constraint_initial_conditions3 = pyo.Constraint(self.model.other_areas, rule=_initial_angle_areas)
        self.model.constraint_initial_conditions4 = pyo.Constraint(self.model.generators, rule=_initial_p)

        # Dynamics
        # self.model.constrains_dynamics1 = pyo.Constraint(self.model.TimeDynamics, rule=lambda model, t: (model.delta[t + 1] - model.delta[t]) == self.dt * 2 * np.pi * fn * (model.freq[t] - 1))
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
                model.dual_vars[self.area, nbr, t] * (model.theta[t] - model.variables_horizon_values[self.area, nbr, t]) +
                model.dual_vars[nbr, nbr, t] * (model.theta_areas[nbr, t] - model.variables_horizon_values[nbr, nbr, t])
                for nbr in model.other_areas for t in model.TimeHorizon
                )

        def _convex_term(model):
            eps = 1e-4
            return model.rho * sum(
                (model.theta[t] - model.variables_horizon_values[self.area, nbr, t])**2 +
                (model.theta_areas[nbr, t] - model.variables_horizon_values[nbr, nbr, t])**2
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

    def _get_initial_states(self):
        delta_values = self.andes.get_partial_variable("Bus", "a", self.buses)
        freq_values = self.andes.get_partial_variable("GENROU", "omega", self.generators)

        weight = np.array(self.M_values) * np.array(self.Sn_values)

        delta0 = np.mean(delta_values)  # or weighted mean if needed
        freq0 = np.dot(weight, np.array(freq_values)) / np.sum(weight)

        return delta0, freq0

    def _compute_coi_parameters(self):
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

    def first_warm_start(self): #NOTE: can be improved
        _, freq0 = self._get_initial_states()  # makes sure self.freq0 and self.delta0 are set

        for t in range(self.T + 1):
            self.saved_states['freq'][t] = freq0
            self.saved_states['P'][t] = sum(self.tm_values)
            self.saved_states['P_exchange'][t] = 0.0
            # self.saved_states['theta'][t] = self.delta0
            for area in self.other_areas:
                self.saved_states['theta_areas'][(area, t)] = 0.0
            for i, gen in enumerate(self.generators):
                self.saved_states['Pg'][(gen, t)] = self.tm_values[i]
        
    def warm_start(self):
        model = self.model
        for t in model.TimeHorizon:
            model.freq[t].value = max(self.saved_states['freq'][t], 0.85)
            model.P[t].value = self.saved_states['P'][t]
            model.P_exchange[t].value = self.saved_states['P_exchange'][t]
            model.theta[t].value = self.saved_states['theta'][t]

            for area in self.other_areas:
                model.theta_areas[area, t].value = self.saved_states['theta_areas'][(area, t)]

            for gen in self.generators:
                model.Pg[gen, t].value = self.saved_states['Pg'][(gen, t)]
    
    def save_warm_start(self):
        model = self.model
        for t in model.TimeHorizon:
            self.saved_states['freq'][t] = model.freq[t].value
            self.saved_states['P'][t] = model.P[t].value
            self.saved_states['P_exchange'][t] = model.P_exchange[t].value
            self.saved_states['theta'][t] = model.theta[t].value

            for area in self.other_areas:
                self.saved_states['theta_areas'][(area, t)] = model.theta_areas[area, t].value

            for gen in self.generators:
                self.saved_states['Pg'][(gen, t)] = model.Pg[gen, t].value



    