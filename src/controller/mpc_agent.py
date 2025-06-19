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
                            'P': 0.0,
                            'Pg': {(g): 0.0 for g in self.generators},
                            'P_exchange': {(area): 0.0 for area in self.other_areas},
                            'P_exchange_areas': {(area): 0.0 for area in self.other_areas},
                            }
        
        ### Set up individial optimization model ###
        self.model =                    pyo.ConcreteModel()

        # Set for indexing
        self.model.generators =         pyo.Set(initialize=self.generators)
        self.model.loads =              pyo.Set(initialize=self.loads) 
        self.model.areas =              pyo.Set(initialize=self.areas)
        self.model.other_areas =        pyo.Set(initialize=self.other_areas)

        # Params: scalar and multidimensional
        # self.model.b =                  pyo.Param(initialize=self.b_areas)
 
        # Params: tuning cost function
        self.model.q =                  pyo.Param(initialize=self.q)
        self.model.rho =                pyo.Param(initialize=self.rho)

        # Params: initial conditions
        self.model.P0 =                 pyo.Param(mutable=True)
        self.model.Pd =                 pyo.Param(initialize=0, mutable=True)
        self.model.u_GENROU_values =    pyo.Param(self.model.generators, mutable=True)

        # Decision variables
        def _get_power_bounds(model, i):
            gen_bus = self.gen_location[i]
            if gen_bus in self.PV_bus:
                j = self.PV_bus.index(gen_bus)
                return (self.pmin_pv[j], self.pmax_pv[j] + 0.2) 
            elif gen_bus in self.slack_bus:
                j = self.slack_bus.index(gen_bus)
                return (self.pmin_slack[j], self.pmax_slack[j] + 0.2)

        self.model.P =                   pyo.Var()
        self.model.Pg =                  pyo.Var(self.model.generators, bounds=_get_power_bounds)
        self.model.P_exchange =          pyo.Var(self.model.other_areas)
        self.model.P_exchange_areas =    pyo.Var(self.model.other_areas)

        ### Constraints ### 
        # Power transmission
        self.model.balance_constr_area =  pyo.Constraint(rule=lambda model: model.P == sum(model.u_GENROU_values[gen] * model.Pg[gen] for gen in model.generators))
        self.model.power_exchang_constr = pyo.Constraint(self.model.other_areas, rule=lambda model, nbr: model.P_exchange_areas[nbr] == -model.P_exchange[nbr])
        
        # Steady-state
        self.model.ss_constr_freq =       pyo.Constraint(rule=lambda model: 0 == model.P - model.Pd - sum(model.P_exchange[nbr] for nbr in model.other_areas)) #- model.P_offset[k] - model.D * (model.omega[k] - self.omega_ref)

    def setup_dmpc(self, coordinator):
        ### Set up distirbuted optimization model ###
        self.model.dual_vars =                  pyo.Param(self.model.areas, self.model.areas, 
                                                              initialize=coordinator.dual_vars, mutable=True)
        self.model.variables_horizon_values =   pyo.Param(self.model.areas, self.model.areas,
                                                              initialize=coordinator.variables_horizon_values, mutable=True)
        ### Cost ###
        def _freq_cost(model):
            return model.q * (model.P - self.model.P0)**2

        def _lagrangian_term(model):
            return sum(
                model.dual_vars[self.area, nbr] * (model.P_exchange[nbr] - model.variables_horizon_values[self.area, nbr]) +   
                model.dual_vars[nbr, self.area] * (model.variables_horizon_values[nbr, self.area] - model.P_exchange_areas[nbr])
                for nbr in model.other_areas
                )

        def _convex_term(model):
            return model.rho * sum(
                (model.P_exchange[nbr] - model.variables_horizon_values[self.area, nbr])**2 +
                (model.variables_horizon_values[nbr, self.area] - model.P_exchange_areas[nbr])**2
                for nbr in model.other_areas
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
        self.b_areas = self.andes.get_system_susceptance(self.area, self.other_areas)

        self.pmax_slack = self.andes.get_complete_variable("Slack", "pmax", self.area)
        self.pmin_slack = self.andes.get_complete_variable("Slack", "pmin", self.area)
        self.pmax_pv =    self.andes.get_area_variable("PV", "pmax", self.area)
        self.pmin_pv =    self.andes.get_area_variable("PV", "pmin", self.area)

        self.pref0 = self.andes.get_partial_variable("TGOV1", "pref0", self.generators)
    

    def initialize_variables_values(self): 
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
            self.model.P_exchange[int(nbr)] = val

    def first_warm_start(self): 
        """
        Initialize the model with the first values of the variables.
        """
        self.vars_saved['P'] = sum(self.tm_values)
        
        for i, gen in enumerate(self.generators):
            self.vars_saved['Pg'][(gen)] = self.tm_values[i] 
            
        for nbr in self.other_areas:
            self.vars_saved['P_exchange'][(nbr)] = self.model.P_exchange[nbr].value                   #self.model.P_exchange[nbr].value
            self.vars_saved['P_exchange_areas'][(nbr)] = -self.model.P_exchange[nbr].value

            self.model.variables_horizon_values[self.area, nbr] = self.model.P_exchange[nbr].value
            self.model.variables_horizon_values[nbr, self.area] = -self.model.P_exchange[nbr].value

        self.warm_start()
        
    def warm_start(self):
        """
        Warm start the optimization model with saved variable values.
        """
        self.model.P.value = self.vars_saved['P']
        
        for nbr in self.other_areas:
            self.model.P_exchange[nbr].value = self.vars_saved['P_exchange'][(nbr)]
            self.model.P_exchange_areas[nbr].value = self.vars_saved['P_exchange_areas'][(nbr)]
    
        for gen in self.generators:
            self.model.Pg[gen].value = self.vars_saved['Pg'][(gen)]
    
    def save_warm_start(self):
        """
        Save the current values of the variables for warm start.
        """
        self.vars_saved['P'] = self.model.P.value

        for nbr in self.other_areas:
            self.vars_saved['P_exchange'][(nbr)] = self.model.P_exchange[nbr].value
            self.vars_saved['P_exchange_areas'][(nbr)] = self.model.P_exchange_areas[nbr].value

        for gen in self.generators:
            self.vars_saved['Pg'][(gen)] = self.model.Pg[gen].value    

    