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
                            'Pg': {(g, k): 0.0 for g in self.generators for k in range(self.K)},
                            'P_exchange': {(area, k): 0.0 for area in self.other_areas for k in range(self.K)},
                            'P_exchange_areas': {(area, k): 0.0 for area in self.other_areas for k in range(self.K)},
                            }
        
        ### Set up individial optimization model ###
        self.model =                    pyo.ConcreteModel()

        # Set for indexing
        self.model.generators =         pyo.Set(initialize=self.generators)
        self.model.loads =              pyo.Set(initialize=self.loads) 
        self.model.areas =              pyo.Set(initialize=self.areas)
        self.model.other_areas =        pyo.Set(initialize=self.other_areas)

        # Range Set for time indexing
        self.model.TimeHorizon =        pyo.RangeSet(0, self.K)     
        self.model.TimeInput =          pyo.RangeSet(0, self.K - 1) 
        self.model.TimeConstraints =    pyo.RangeSet(0, self.K - 2) 
 
        # Params: tuning cost function
        self.model.q =                  pyo.Param(initialize=self.q)
        self.model.rho =                pyo.Param(initialize=self.rho)

        # Params: system parameters
        self.model.M =                  pyo.Param(initialize=self.M_coi)  # System inertia

        # Params: initial conditions
        self.model.omega0 =             pyo.Param(mutable=True)
        self.model.P0 =                 pyo.Param(mutable=True)
        self.model.Pd =                 pyo.Param(initialize=0, mutable=True)
        self.model.u_GENROU_values =    pyo.Param(self.model.generators, mutable=True)

        # Decision variables
        def _get_power_bounds(model, k, i):
            # Otherwise, assign bounds based on generator bus type
            gen_bus = self.gen_location[i]
            if gen_bus in self.PV_bus:
                j = self.PV_bus.index(gen_bus)
                return (self.pmin_pv[j] - 0.1, self.pmax_pv[j] + 0.2)
            elif gen_bus in self.slack_bus:
                j = self.slack_bus.index(gen_bus)
                return (self.pmin_slack[j] - 0.1, self.pmax_slack[j] + 0.2)
            else:
                raise ValueError(f"Generator at bus {gen_bus} not found in PV or slack bus lists.")

        self.model.omega =               pyo.Var(self.model.TimeHorizon, bounds=(0.85, 1.15))
        self.model.P =                   pyo.Var(self.model.TimeInput)
        self.model.Pg =                  pyo.Var(self.model.TimeInput, self.model.generators, bounds=_get_power_bounds)
        self.model.P_exchange =          pyo.Var(self.model.TimeInput, self.model.other_areas)
        self.model.P_exchange_areas =    pyo.Var(self.model.TimeInput, self.model.other_areas)

        ### Constraints ### 
        # Frequency
        self.model.initial_freq =        pyo.Constraint(expr=self.model.omega[0] == self.model.omega0)
        self.model.terminal_freq =       pyo.Constraint(expr=self.model.omega[self.K] == self.omega_ref)

        # Power transmission
        def _tripping_constraint(model, k, i):
            # Get the upper bound of Pg[i]
            lb, ub = _get_power_bounds(model, k, i)
            return model.Pg[k, i] <= model.u_GENROU_values[i] * ub

        self.model.trip_constr =          pyo.Constraint(self.model.TimeInput, self.model.generators, rule=_tripping_constraint)
        self.model.balance_constr_area =  pyo.Constraint(self.model.TimeInput, rule=lambda model, k: model.P[k] == sum(model.u_GENROU_values[gen] * model.Pg[k, gen] for gen in model.generators))
        self.model.power_exchang_constr = pyo.Constraint(self.model.TimeInput, self.model.other_areas, rule=lambda model, k, nbr: model.P_exchange_areas[k, nbr] == -model.P_exchange[k, nbr])
        
        # Steady-state
        self.model.ss_constr_freq =       pyo.Constraint(self.model.TimeInput, rule=lambda model, k: model.M * (model.omega[k + 1] - model.omega[k]) / self.dt == model.P[k] - model.Pd - sum(model.P_exchange[k, nbr] for nbr in model.other_areas)) #- model.P_offset[k] - model.D * (model.omega[k] - self.omega_ref)

    def setup_dmpc(self, coordinator):
        ### Set up distirbuted optimization model ###
        self.model.dual_vars =                  pyo.Param(self.model.areas, self.model.areas, self.model.TimeInput,
                                                              initialize=coordinator.dual_vars, mutable=True)
        self.model.variables_horizon_values =   pyo.Param(self.model.areas, self.model.areas, self.model.TimeInput, self.model.areas,
                                                              initialize=coordinator.variables_horizon_values, mutable=True)
        ### Cost ###
        def _freq_cost(model):
            return model.q * sum((model.omega[k] - self.omega_ref)**2 for k in model.TimeHorizon)

        def _lagrangian_term(model):
            return sum(
                model.dual_vars[self.area, nbr, k] * (model.P_exchange[k, nbr] - model.variables_horizon_values[self.area, nbr, k, nbr]) +   
                model.dual_vars[nbr, self.area, k] * (model.variables_horizon_values[nbr, self.area, k, nbr] - model.P_exchange_areas[k, nbr])
                for nbr in model.other_areas for k in model.TimeInput
                )

        def _convex_term(model):
            return model.rho * sum(
                (model.P_exchange[k, nbr] - model.variables_horizon_values[self.area, nbr, k, nbr])**2 +
                (model.variables_horizon_values[nbr, self.area, k, nbr] - model.P_exchange_areas[k, nbr])**2
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
        self.governors =     self.andes.get_area_variable("TGOV1N", "idx", self.area)
        self.loads =         self.andes.get_area_variable("PQ", "idx", self.area)
        self.buses =         self.andes.get_area_variable("Bus", "idx", self.area)
        self.PV_bus =        self.andes.get_area_variable("PV", "bus", self.area)
        self.generator_bus = self.andes.get_area_variable("GENROU", "bus", self.area)
        self.loads_bus =     self.andes.get_area_variable("PQ", "bus", self.area)
        self.slack_bus =     self.andes.get_complete_variable("Slack", "bus", self.area)
        self.areas =         self.andes.get_complete_variable("Area", "idx")

        self.gen_location = {gen: self.generator_bus[i] for i, gen in enumerate(self.generators)} #NOTE: necessary?
        self.bus2idgen = {self.generator_bus[i]: gen for i, gen in enumerate(self.generators)} #NOTE: necessary?

        # List of neighbour areas, interface buses and susceptance
        self.other_areas = self.andes.get_neighbour_areas(self.area)
        self.interface_buses = self.andes.get_interface_buses(self.area, self.other_areas)
        # self.b_areas = self.andes.get_system_susceptance(self.area, self.other_areas)

        self.pmax_slack = self.andes.get_complete_variable("Slack", "pmax", self.area)
        self.pmin_slack = self.andes.get_complete_variable("Slack", "pmin", self.area)
        self.pmax_pv =    self.andes.get_area_variable("PV", "pmax", self.area)
        self.pmin_pv =    self.andes.get_area_variable("PV", "pmin", self.area)

        self.pref0 = self.andes.get_partial_variable("TGOV1N", "pref0", self.governors)

        self.Sn_values = self.andes.get_partial_variable("GENROU", "Sn", self.generators)
        self.M_values = np.array(self.andes.get_partial_variable("GENROU", "M", self.generators))

        for i in range(len(self.generators)):
            self.M_values[i] = self.M_values[i] / self.Sn_values[i] * 100  # Normalize M values by Sn values 
        
        self.S_coi = sum(self.Sn_values)
        # self.M_coi =  sum(self.M_values)
        self.M_coi = 0.0 
        if self.generators:
            for i in range(len(self.generators)):
                self.M_coi += self.M_values[i] * self.Sn_values[i] # Normalize M values by Sn values 
            self.M_coi /= self.S_coi  # Normalize M_coi by S_coi

    def initialize_variables_values(self): 
        # Frequency
        omega_values = self.andes.get_partial_variable("GENROU", "omega", self.generators)
        weight = np.array(self.M_values) * np.array(self.Sn_values)
        self.omega0 = np.dot(weight, np.array(omega_values)) / np.sum(weight)
        self.model.omega0.set_value(self.omega0)

        # Mechanical power
        self.P0 = 0.0
        self.tm_values = self.andes.get_partial_variable("GENROU", "tm", self.generators)
        self.u_GENROU_values = self.andes.get_partial_variable("GENROU", "u", self.generators)
        for i, (gen, val) in enumerate(zip(self.generators, self.u_GENROU_values)):
            self.model.u_GENROU_values[gen] = val
            self.P0 += self.tm_values[i] * self.u_GENROU_values[i]
        self.model.P0 = self.P0
        
        # Demand
        self.Pd = 0.0
        self.u_PQ_values = self.andes.get_partial_variable("PQ", "u", self.loads)
        self.Ppf_values = self.andes.get_partial_variable("PQ", "Ppf", self.loads)
        for i, bus in enumerate(self.loads_bus):
            if bus in self.buses:
                self.Pd += self.Ppf_values[i] * self.u_PQ_values[i]
        self.model.Pd = self.Pd
        
        # Power exchange
        self.power_exchange = self.andes.get_exact_power_transfer(self.area, self.interface_buses)
        for nbr, val in self.power_exchange.items():
            for k in range(self.K):
                self.model.P_exchange[k, int(nbr)] = val

    def first_warm_start(self): 
        """
        Initialize the model with the first values of the variables.
        """
        for k in range(self.K + 1):
            self.vars_saved['omega'][k] = self.model.omega0.value

        for k in range(self.K):  
            self.vars_saved['P'][k] = sum(self.tm_values)
            
            for i, gen in enumerate(self.generators):
                self.vars_saved['Pg'][(gen, k)] = self.tm_values[i] 
                
            for nbr in self.other_areas:
                self.vars_saved['P_exchange'][(nbr, k)] = self.model.P_exchange[k, nbr].value                   #self.model.P_exchange[nbr].value
                self.vars_saved['P_exchange_areas'][(nbr, k)] = -self.model.P_exchange[k, nbr].value

                self.model.variables_horizon_values[self.area, nbr, k, nbr] = self.model.P_exchange[k, nbr].value
                self.model.variables_horizon_values[nbr, self.area, k, nbr] = -self.model.P_exchange[k, nbr].value

        self.warm_start()
        
    def warm_start(self):
        """
        Warm start the optimization model with saved variable values.
        """
        for k in range(self.K + 1):
            self.model.omega[k].value = self.vars_saved['omega'][k]
        
        for k in range(self.K):
            self.model.P.value = self.vars_saved['P'][k]
            
            for nbr in self.other_areas:
                self.model.P_exchange[k, nbr].value = self.vars_saved['P_exchange'][(nbr, k)]
                self.model.P_exchange_areas[k, nbr].value = self.vars_saved['P_exchange_areas'][(nbr, k)]
        
            for gen in self.generators:
                self.model.Pg[k, gen].value = self.vars_saved['Pg'][(gen, k)]
    
    def save_warm_start(self):
        """
        Save the current values of the variables for warm start.
        """
        for k in range(self.K + 1):
            self.vars_saved['omega'][k] = self.model.omega[k].value
        
        for k in range(self.K):
            self.vars_saved['P'][k] = self.model.P[k].value
            
            for gen in self.generators:
                self.vars_saved['Pg'][(gen, k)] = self.model.Pg[k, gen].value
                
            for nbr in self.other_areas:
                self.vars_saved['P_exchange'][(nbr, k)] = self.model.P_exchange[k, nbr].value
                self.vars_saved['P_exchange_areas'][(nbr, k)] = self.model.P_exchange_areas[k, nbr].value

    