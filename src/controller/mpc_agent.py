"""
This class contains the agent description and the optimization problem definition.
"""

import numpy as np
import pyomo.environ as pyo
import numpy as np

from src.config.config import Config
from src.simulator.andes_wrapper import AndesWrapper

class MPCAgent:
    def __init__(self, agent_id: str, andes_interface: AndesWrapper):

        self.dt =               Config.dt
        self.K =                Config.K

        self.ramp_up =          Config.ramp_up
        self.ramp_down =        Config.ramp_down

        self.omega_ref =        Config.omega_ref 

        self.q =                Config.q
        self.rho =              Config.rho

        self.fn =               Config.fn

        self.agent_id = 'Agent_' + str(agent_id)
        self.area = agent_id

        self.andes = andes_interface  

        self.setup = True

        self.variables_saved_values = {}
        self.gen_location = {}
        self.bus2idgen = {}

        ### Agent get area params ### NOTE: in case of tripping/distrubance the _init_ should be re-executed.
        self._get_area_params()

        self.vars_saved = {
                            'omega': np.ones(self.K + 1),
                            'P': np.zeros(self.K),
                            'P_exchange': np.zeros(self.K),
                            'Pg': {(g, k): 0.0 for g in self.generators for k in range(self.K)},
                            'theta': np.zeros(self.K + 1),
                            'theta_areas': {(area, k): 0.0 for area in self.other_areas for k in range(self.K)},
                            }
        
        ### Set up individial optimization model ###
        self.model =                 pyo.ConcreteModel()

        # Set for indexing
        self.model.generators =      pyo.Set(initialize=self.generators)
        self.model.loads =           pyo.Set(initialize=self.loads) 
        self.model.areas =           pyo.Set(initialize=self.areas)
        self.model.other_areas =     pyo.Set(initialize=self.other_areas)

        # Range Set for time indexing
        self.model.TimeHorizon =     pyo.RangeSet(0, self.K)     
        self.model.TimeInput =       pyo.RangeSet(0, self.K - 1) 
        self.model.TimeConstraints = pyo.RangeSet(0, self.K - 2) 

        # Params: scalar and multidimensional
        self.model.M =               pyo.Param(initialize=self.M_coi)
        self.model.D =               pyo.Param(initialize=self.D_coi)
        self.model.fn =              pyo.Param(initialize=self.fn_coi)
        self.model.Pd =              pyo.Param(self.model.TimeInput, initialize=0, mutable=True)
        self.model.b =               pyo.Param(self.model.other_areas, initialize=self.b_areas)
        # self.model.P_offset =        pyo.Param(self.model.TimeHorizon, initialize=0, mutable=True)
 
        # Params: tuning cost function
        self.model.q =               pyo.Param(initialize=self.q, mutable=True)
        self.model.rho =             pyo.Param(initialize=self.rho, mutable=True)

        # Params: initial conditions
        self.model.omega0 =          pyo.Param(mutable=True)
        self.model.theta0 =          pyo.Param(mutable=True)
        self.model.theta0_areas =    pyo.Param(self.model.other_areas, mutable=True)
        self.model.tm_values =       pyo.Param(self.model.generators, mutable=True)
        self.model.u_values =        pyo.Param(self.model.generators, mutable=True)

        # Decision variables
        def _get_power_bounds(model, i, k):
            gen_bus = self.gen_location[i]
            if gen_bus in self.PV_bus:
                j = self.PV_bus.index(gen_bus)
                return (self.pmin_pv[j], self.pmax_pv[j] + 0.2) 
            elif gen_bus in self.slack_bus:
                j = self.slack_bus.index(gen_bus)
                return (self.pmin_slack[j], self.pmax_slack[j] + 0.2)
            
        self.model.omega =           pyo.Var(self.model.TimeHorizon, bounds=(0.85, 1.15))
        self.model.P =               pyo.Var(self.model.TimeInput)
        self.model.P_exchange =      pyo.Var(self.model.TimeInput)
        self.model.Pg =              pyo.Var(self.model.generators, self.model.TimeInput, bounds=_get_power_bounds) #
        self.model.theta =           pyo.Var(self.model.TimeHorizon)
        self.model.theta_areas =     pyo.Var(self.model.other_areas, self.model.TimeInput)

        ### Constraints ### 
        # Initial conditions
        # def _initial_P(model, i):
        #     return model.Pg[i, 0] == self.model.tm_values[i]

        # def _initial_theta_areas(model, i):
        #     return model.theta_areas[i, 0] == self.model.theta0_areas[i]
        
        # self.model.initial_constr_P =           pyo.Constraint(self.model.generators, rule=_initial_P)
        # self.model.initial_constr_theta_areas = pyo.Constraint(self.model.other_areas, rule=_initial_theta_areas)
        self.model.initial_constr_freq =        pyo.Constraint(expr=self.model.omega[0] == self.model.omega0)
        self.model.initial_constr_theta =       pyo.Constraint(expr=self.model.theta[0] == self.model.theta0)
        self.model.terminal_constr_freq =       pyo.Constraint(expr=self.model.omega[self.K] == self.omega_ref)
        self.model.terminal_constr_deriv =      pyo.Constraint(expr=self.model.omega[self.K - 1] == self.omega_ref)

        # Dynamics and ramp up/down
        self.model.dynamics_constr_theta =      pyo.Constraint(self.model.TimeInput, rule=lambda model, k: (model.theta[k + 1] - model.theta[k]) / self.dt == 2 * np.pi * self.fn * (model.omega[k] - self.omega_ref)) #  
        self.model.dynamics_constr_ramp_up =    pyo.Constraint(self.model.generators, self.model.TimeConstraints, rule=lambda model, gen, k: model.u_values[gen] * (model.Pg[gen, k + 1] - model.Pg[gen, k]) <= self.dt * self.ramp_up)
        self.model.dynamics_constr_rampo_down = pyo.Constraint(self.model.generators, self.model.TimeConstraints, rule=lambda model, gen, k: -self.dt * self.ramp_down <= (model.Pg[gen, k + 1] - model.Pg[gen, k]) * model.u_values[gen])

        # Power transmission
        def _power_inter_area(model, k):
            return model.P_exchange[k] == sum(model.b[nbr] * (model.theta[k] - model.theta_areas[nbr, k]) for nbr in model.other_areas)
        
        self.model.balance_constr_inter_area =  pyo.Constraint(self.model.TimeInput, rule=_power_inter_area)
        self.model.balance_constr_area =        pyo.Constraint(self.model.TimeInput, rule=lambda model, k: model.P[k] == sum(model.u_values[gen] * model.Pg[gen, k] for gen in model.generators))

    def setup_dmpc(self, coordinator):
        ### Set up distirbuted optimization model ###
        self.model.dual_vars =                  pyo.Param(self.model.areas, self.model.areas, self.model.TimeInput, 
                                                              initialize=coordinator.dual_vars, mutable=True) #NOTE: actually useless.
        self.model.variables_horizon_values =   pyo.Param(self.model.areas, self.model.areas, self.model.TimeInput,
                                                              initialize=coordinator.variables_horizon_values, mutable=True)

        self.model.dynamics_constr_freq =       pyo.Constraint(self.model.TimeInput, rule=lambda model, k: model.M * (model.omega[k + 1] - model.omega[k]) / self.dt == model.P[k] - model.Pd[k] - model.P_exchange[k]) #- model.P_offset[k] - model.D * (model.omega[k] - self.omega_ref)

        ### Cost ###
        def _freq_cost(model):
            return model.q * sum((model.omega[k] - self.omega_ref)**2 for k in model.TimeHorizon)

        def _lagrangian_term(model):
            return sum(
                model.dual_vars[self.area, nbr, k] * (model.theta[k + 1] - model.variables_horizon_values[self.area, nbr, k]) +   
                model.dual_vars[nbr, self.area, k] * (model.variables_horizon_values[nbr, nbr, k] - model.theta_areas[nbr, k])
                for nbr in model.other_areas for k in model.TimeInput
                )

        def _convex_term(model):
            return model.rho * sum(
                (model.theta[k + 1] - model.variables_horizon_values[self.area, nbr, k])**2 +
                (model.variables_horizon_values[nbr, nbr, k] - model.theta_areas[nbr, k])**2
                for nbr in model.other_areas for k in model.TimeInput
            )
 
        # Define expressions for each cost component such that it is possible to extract the values
        self.model.freq_cost =       pyo.Expression(rule=_freq_cost)
        self.model.lagrangian_term = pyo.Expression(rule=_lagrangian_term)
        self.model.convex_term =     pyo.Expression(rule=_convex_term)

        # Define the total objective using these expressions
        self.model.cost = pyo.Objective(expr=self.model.freq_cost + self.model.lagrangian_term + self.model.convex_term, sense=pyo.minimize)

        return self.model
    
    def _get_area_params(self):
        """
        Get the all the parameters of the area from Andes.
        """
        # List of devices 
        self.generators =    self.andes.get_area_variable("GENROU", "idx", self.area)
        self.loads =         self.andes.get_area_variable("PQ", "idx", self.area)
        self.areas =         self.andes.get_complete_variable("Area", "idx")
        self.buses =         self.andes.get_area_variable("Bus", "idx", self.area)
        self.PV_bus =        self.andes.get_area_variable("PV", "bus", self.area)
        self.generator_bus = self.andes.get_area_variable("GENROU", "bus", self.area)
        self.loads_bus =     self.andes.get_area_variable("PQ", "bus", self.area)
        self.slack_bus =     self.andes.get_complete_variable("Slack", "bus", self.area)

        self.gen_location = {gen: self.generator_bus[i] for i, gen in enumerate(self.generators)} #NOTE: necessary?
        self.bus2idgen = {self.generator_bus[i]: gen for i, gen in enumerate(self.generators)} #NOTE: necessary?

        # List of neighbour areas, interface buses and susceptance
        self.other_areas = self.andes.get_neighbour_areas(self.area)
        self.interface_buses = self.andes.get_interface_buses(self.area, self.other_areas)
        self.b_areas = self.andes.get_system_susceptance(self.area, self.other_areas)

        # Synchronous generator paramters 
        self.Sn_values = self.andes.get_partial_variable("GENROU", "Sn", self.generators)
        self.Pe_values = self.andes.get_partial_variable("GENROU", "Pe", self.generators)
        self.M_values =  self.andes.get_partial_variable("GENROU", "M", self.generators)
        self.D_values =  self.andes.get_partial_variable("GENROU", "D", self.generators)
        self.fn_values = self.andes.get_partial_variable("GENROU", "fn", self.generators)

        self._compute_coi_parameters()

        self.pmax_slack = self.andes.get_complete_variable("Slack", "pmax", self.area)
        self.pmin_slack = self.andes.get_complete_variable("Slack", "pmin", self.area)
        self.pmax_pv =    self.andes.get_area_variable("PV", "pmax", self.area)
        self.pmin_pv =    self.andes.get_area_variable("PV", "pmin", self.area)

        self.pref = self.andes.get_partial_variable("TGOV1", "pref", self.generators)
    
    def _compute_coi_parameters(self): #NOTE to move
        """
        Compute the COI model parameters for the area.
        """
        self.S_area = 0.0
        self.M_coi = 0.0 
        self.D_coi = 0.0
        self.fn_coi = 0.0

        for i, bus in enumerate(self.generator_bus):
            if bus in self.buses:
                Sn = self.Sn_values[i]
                self.S_area += Sn
                self.M_coi += self.M_values[i]
                self.D_coi += Sn * self.D_values[i]
                self.fn_coi += Sn * self.fn_values[i]

        if self.S_area > 0:
            self.D_coi /= self.S_area
            self.fn_coi = 60.0  # Set nominal frequency explicitly

        self.Pe_base = {gen: self.Pe_values[i] for i, gen in enumerate(self.generators)} 

    def initialize_variables_values(self): 
        # Frequency
        omega_values = self.andes.get_partial_variable("GENROU", "omega", self.generators)
        weight = np.array(self.M_values) * np.array(self.Sn_values)
        self.omega0 = np.dot(weight, np.array(omega_values)) / np.sum(weight) #NOTE: rename 
        self.model.omega0.set_value(self.omega0) 

        # Angles
        self.theta0 = self.andes.get_partial_variable("Bus", "a", self.interface_buses[self.area])
        self.model.theta0.set_value(self.theta0[0])#NOTE: angle logic needs to be revisited if it works!

        self.theta0_areas = {
            area: self.andes.get_partial_variable("Bus", "a", bus_list)
            for area, bus_list in self.interface_buses.items()
            if area != self.area
        }    
        for area, value in self.theta0_areas.items():
            self.model.theta0_areas[area] = value[0]#NOTE: angle logic needs to be revisited if it works!

        # Mechanical power
        self.tm_values = self.andes.get_partial_variable("GENROU", "tm", self.generators)
        for gen, val in zip(self.generators, self.tm_values): #NOTE: to clean because of consistency 
            self.model.tm_values[gen] = val
        
        # Status
        self.u_values = self.andes.get_partial_variable("GENROU", "u", self.generators)
        for gen, val in zip(self.generators, self.u_values): #NOTE: to clean because of consistency 
            self.model.u_values[gen] = val

    def compute_demand(self):
        # Demand
        self.Pd = 0.0
        self.p0_values = self.andes.get_partial_variable("PQ", "p0", self.loads)
        for i, bus in enumerate(self.loads_bus):
            if bus in self.buses:
                self.Pd += self.p0_values[i]

        for k in self.model.TimeInput:
            self.model.Pd[k] = self.Pd

    def first_warm_start(self): 
        for k in range(self.K + 1):
            self.vars_saved['omega'][k] = self.model.omega0.value
            self.vars_saved['theta'][k] = self.model.theta0.value 
        for k in range(self.K):
            self.vars_saved['P'][k] = sum(self.tm_values)
            self.vars_saved['P_exchange'][k] = self.vars_saved['P'][k] - self.Pd #- self.P_offset #NOTE: possible source of error!   
                
            for nbr in self.other_areas:
                self.vars_saved['theta_areas'][(nbr, k)] = self.model.theta0_areas[nbr].value

                self.model.variables_horizon_values[self.area, nbr, k] = self.model.theta0.value
                self.model.variables_horizon_values[nbr, nbr, k] = self.model.theta0_areas[nbr].value

            for i, gen in enumerate(self.generators):
                self.vars_saved['Pg'][(gen, k)] = self.tm_values[i]    
        
        self.warm_start()
        
    def warm_start(self):
        for k in range(self.K + 1):
            self.model.omega[k].value = self.vars_saved['omega'][k] #max(self.vars_saved['omega'][k], 0.85)
            self.model.theta[k].value = self.vars_saved['theta'][k]
        for k in range(self.K):
            self.model.P[k].value = self.vars_saved['P'][k]
            self.model.P_exchange[k].value = self.vars_saved['P_exchange'][k]
            
            for nbr in self.other_areas:
                self.model.theta_areas[nbr, k].value = self.vars_saved['theta_areas'][(nbr, k)]

            for gen in self.generators:
                self.model.Pg[gen, k].value = self.vars_saved['Pg'][(gen, k)]
    
    def save_warm_start(self):
        for k in range(self.K + 1):
            self.vars_saved['omega'][k] = self.model.omega[k].value
            self.vars_saved['theta'][k] = self.model.theta[k].value
        for k in range(self.K):
            self.vars_saved['P'][k] = self.model.P[k].value
            self.vars_saved['P_exchange'][k] = self.model.P_exchange[k].value

            for nbr in self.other_areas:
                self.vars_saved['theta_areas'][(nbr, k)] = self.model.theta_areas[nbr, k].value

            for gen in self.generators:
                self.vars_saved['Pg'][(gen, k)] = self.model.Pg[gen, k].value    

    