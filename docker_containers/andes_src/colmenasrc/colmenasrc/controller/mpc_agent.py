"""
This class contains the agent description and the optimization problem definition.
"""

import numpy as np
import pyomo.environ as pyo
import numpy as np

from colmenasrc.config.config import Config
from colmenasrc.simulator.andes_wrapper import AndesWrapper

class MPCAgent:
    """
    Distributed Model Predictive Control (DMPC) agent for power system area control.

    This agent interfaces with the Andes simulation backend to construct, initialize, and solve
    a Pyomo-based MPC model that incorporates inter-area power exchanges, frequency regulation,
    ramp constraints, and distributed coordination using ADMM.

    Attributes:
        agent_id (str): Identifier for the agent (e.g., 'Agent_1').
        area (str): Area identifier used in Andes for this agent.
        andes (AndesWrapper): Interface to the Andes simulator for data access.
        model (ConcreteModel): Pyomo optimization model.
        K (int): Prediction horizon.
        dt (float): Discretization time step.
        omega_ref (float): Nominal frequency reference.
        ramp_up (float): Maximum ramp-up rate.
        ramp_down (float): Maximum ramp-down rate.
        q (float): Weight on frequency deviation in cost function.
        rho (float): Penalty parameter in ADMM convex term.
        fn (float): Nominal system frequency (e.g., 50 or 60 Hz).
    """

    def __init__(self, agent_id: str, andes_interface: AndesWrapper):
        """
        Initializes the DMPC agent with Andes interface and sets up model structure.

        Args:
            agent_id (str): Identifier for this agent.
            andes_interface (AndesWrapper): Interface to the Andes simulator.
        """
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

        ### Agent get area params
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
        
        # Frequency dynamic 
        self.model.dynamic_constr_freq =  pyo.Constraint(self.model.TimeInput, rule=lambda model, k: model.M * (model.omega[k + 1] - model.omega[k]) / self.dt == model.P[k] - model.Pd - sum(model.P_exchange[k, nbr] for nbr in model.other_areas)) #- model.P_offset[k] - model.D * (model.omega[k] - self.omega_ref)

    def setup_dmpc(self, coordinator):
        """
        Sets up the distributed optimization components including ADMM terms.

        Args:
            coordinator: Coordinator object containing dual variables and variable history.
        """
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

        self.model.freq_cost =       pyo.Expression(rule=_freq_cost)
        self.model.lagrangian_term = pyo.Expression(rule=_lagrangian_term)
        self.model.convex_term =     pyo.Expression(rule=_convex_term)

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
        self.D_values = np.array(self.andes.get_partial_variable("GENROU", "D", self.generators))

        for i in range(len(self.generators)):
            self.M_values[i] = self.M_values[i] / self.Sn_values[i] * 100  # Normalize M values by Sn values 
        
        self.S_coi = sum(self.Sn_values)
        # self.M_coi =  sum(self.M_values)
        self.M_coi = 0.0 
        if self.generators:
            for i in range(len(self.generators)):
                self.M_coi += self.M_values[i]
        if 'npcc' in self.andes.case_path: 
            self.M_values_secondary = self.andes.get_area_variable("GENCLS", "M", self.area)
            self.D_values_secondary = self.andes.get_area_variable("GENCLS", "D", self.area)
            self.D = sum(self.D_values) + sum(self.D_values_secondary)
            for i in range(len(self.M_values_secondary)):
                #self.M_coi += self.M_values_secondary[i]
                _ = 0

    def initialize_variables_values(self): 
        """
        Initializes model variables from Andes snapshot data.
        """
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

class MPCAgentv2:
    """
    Distributed Model Predictive Control (DMPC) agent for power system area control.

    This agent interfaces with the Andes simulation backend to construct, initialize, and solve
    a Pyomo-based MPC model that incorporates inter-area power exchanges, frequency regulation,
    ramp constraints, and distributed coordination using ADMM.

    Attributes:
        agent_id (str): Identifier for the agent (e.g., 'Agent_1').
        area (str): Area identifier used in Andes for this agent.
        andes (AndesWrapper): Interface to the Andes simulator for data access.
        model (ConcreteModel): Pyomo optimization model.
        K (int): Prediction horizon.
        dt (float): Discretization time step.
        omega_ref (float): Nominal frequency reference.
        ramp_up (float): Maximum ramp-up rate.
        ramp_down (float): Maximum ramp-down rate.
        q (float): Weight on frequency deviation in cost function.
        rho (float): Penalty parameter in ADMM convex term.
        fn (float): Nominal system frequency (e.g., 50 or 60 Hz).
    """

    def __init__(self, agent_id: str, andes_interface: AndesWrapper):
        """
        Initializes the DMPC agent with Andes interface and sets up model structure.

        Args:
            agent_id (str): Identifier for this agent.
            andes_interface (AndesWrapper): Interface to the Andes simulator.
        """
        self.dt =               Config.dt
        self.K =                Config.K
        self.T =                Config.T

        self.ramp_up =          Config.ramp_up
        self.ramp_down =        Config.ramp_down

        self.omega_ref =        Config.omega_ref 

        self.q =                Config.q
        self.rho =              Config.rho
        self.rho_diff =         Config.rho_diff
        self.rho_scaled =       Config.rho_scaled
        self.fn =               Config.fn
        self.angles =           Config.angles
        self.agent_id = 'Agent_' + str(agent_id)
        self.area = agent_id

        self.andes = andes_interface  

        self.setup = True

        self.variables_saved_values = {}
        self.gen_location = {}
        self.bus2idgen = {}

        ### Agent get area params
        self._get_area_params()

        self.vars_saved = { 
                            'omega': np.ones(self.K + 1),
                            'P': np.zeros(self.K),
                            'Pg': {(g, k): 0.0 for g in self.generators for k in range(self.K)},
                            'delta': {(area, k): 0.0 for area in self.other_areas for k in range(self.K)},
                            'delta_areas': {(area, k): 0.0 for area in self.other_areas for k in range(self.K)},
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
        self.model.rho_diff =           pyo.Param(initialize=self.rho_diff)
        self.model.rho_scaled =         pyo.Param(initialize=self.rho_scaled)

        # Params: system parameters
        self.model.M =                  pyo.Param(initialize=self.M_coi)  # System inertia
        self.model.D =                  pyo.Param(initialize=self.D)  # System inertia
        self.model.b =                  pyo.Param(self.model.other_areas, initialize = self.b_areas) #Susceptance


        # Params: initial conditions
        self.model.omega0 =             pyo.Param(mutable=True)
        self.model.delta0 =             pyo.Param(mutable=True)
        self.model.P0 =                 pyo.Param(mutable=True)
        self.model.Pd =                 pyo.Param(initialize=0, mutable=True)
        self.model.tm0 =                pyo.Param(self.model.generators, mutable=True)
        self.model.u_generators =       pyo.Param(self.model.generators, mutable=True)
        self.model.delta_ref =          pyo.Param(self.model.areas, self.model.areas, mutable=True) 

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
        self.model.delta =               pyo.Var(self.model.TimeHorizon, bounds=(-1,1))
        self.model.delta_areas =         pyo.Var(self.other_areas, self.model.TimeHorizon, bounds=(-1,1))

        self.model.P =                   pyo.Var(self.model.TimeInput)
        self.model.Pg =                  pyo.Var(self.model.TimeInput, self.model.generators, bounds=_get_power_bounds)
        self.model.P_exchange =          pyo.Var(self.model.TimeInput, self.model.other_areas)

        ### Constraints ### 
        # Initial Values
        def initial_p(model, i):
            return (model.tm0[i]*model.u_generators[i] - self.dt*self.ramp_up*model.u_generators[i], model.Pg[i,0], 
                model.tm0[i]*model.u_generators[i] + self.dt*self.ramp_up*model.u_generators[i])
        self.model.initial_freq  =                  pyo.Constraint(expr=self.model.omega[0] == self.model.omega0)
        self.model.initial_delta =                  pyo.Constraint(expr=self.model.delta[0] == self.model.delta0)
        self.model.constraint_initial_conditions =  pyo.Constraint(self.model.generators, rule= initial_p)

        # Power transmission
        def _tripping_constraint(model, k, i):
            # Get the upper bound of Pg[i]
            lb, ub = _get_power_bounds(model, k, i)
            return model.Pg[k, i] <= model.u_generators[i] * ub
        def power_inter_area(model, area, t):
            return model.P_exchange[t, area] == model.b[area]*(model.delta[t] + model.delta_ref[self.area, area] - model.delta_areas[area, t])
        self.model.constrains_area =      pyo.Constraint(self.model.TimeHorizon, self.other_areas, rule = power_inter_area)
        self.model.trip_constr =          pyo.Constraint(self.model.TimeInput, self.model.generators, rule=_tripping_constraint)
        self.model.balance_constr_area =  pyo.Constraint(self.model.TimeInput, rule=lambda model, k: model.P[k] == sum(model.u_GENROU_values[gen] * model.Pg[k, gen] for gen in model.generators))
        
        # Frequency dynamic 
        #We define the dynamics of the system as constraints
        #C1: the current area angle derivative
        #C2: the current frequency angle derivative
        #C3: the generator maximum ramp up
        #C4: the generator minimum ramp up
        #We define the dynamics of the system as constraints
        self.model.constrains_dynamics1 = pyo.Constraint(self.model.TimeInput, rule=lambda model, t: 
                                        (model.delta[t+1] - model.delta[t])==  self.dt*2*np.pi*self.fn*(model.omega[t]-self.omega_ref))
        self.model.constrains_dynamics2 = pyo.Constraint(self.model.TimeInput, rule=lambda model, t: 
                                        model.M*(model.omega[t+1] - model.omega[t])/self.dt == ((-model.D(model.omega[t]-self.omega_ref) + model.P[t] - model.Pd[t] - sum(model.P_exchange[t, nbr] for nbr in model.other_areas))))
        self.model.constrains_dynamics3 = pyo.Constraint(self.model.generators, self.model.TimeInput, rule=lambda model, i, t: 
                                        (model.Pg[i, t+1] - model.Pg[i, t]) <= self.dt*self.ramp_up)
        self.model.constrains_dynamics4 = pyo.Constraint(self.model.generators, self.model.TimeInput, rule=lambda model, i, t: 
                                        -self.ramp_up*self.dt*model.u_generators[i] <= (model.Pg[i, t+1] - model.Pg[i, t])*model.u_generators[i])
    
    def setup_dmpc(self, coordinator):
        """
        Sets up the distributed optimization components including ADMM terms.

        Args:
            coordinator: Coordinator object containing dual variables and variable history.
        """
        model = self.model 
        ### Set up distributed optimization model ###
        self.model.dual_vars =                  pyo.Param(self.model.areas, self.model.areas, self.model.TimeInput,
                                                              initialize=coordinator.dual_vars, mutable=True)
        self.model.dual_vars_P =                pyo.Param(model.areas, model.areas, model.TimeInput, 
                                                          initialize = coordinator.dual_vars_P, mutable = True)
        self.model.dual_vars_diff =             pyo.Param(model.areas, model.areas, model.TimeInput, 
                                                          initialize = coordinator.dual_vars_diff, mutable = True)

        self.model.variables_horizon_values =   pyo.Param(self.model.areas, self.model.areas, self.model.TimeInput,
                                                              initialize=coordinator.variables_horizon_values, mutable=True)
        self.model.variables_horizon_values_P =   pyo.Param(self.model.areas, self.model.areas, self.model.TimeInput,
                                                              initialize=coordinator.variables_horizon_values, mutable=True)
        ### Cost ###
        def _freq_cost(model):
            return model.q * sum((model.omega[k] - self.omega_ref)**2 for k in model.TimeHorizon)

        def _lagrangian_term(model):
            a = 0
            b = 0
            c = 0
            for other_area in model.other_areas:
                for t in model.TimeInput:
                    a += model.rho_scaled[t]*model.dual_vars[self.area, other_area, t]*(model.variable_horizon_values[other_area, other_area, t] - model.delta_areas[other_area, t])
                    a += model.rho_scaled[t]*model.dual_vars[other_area, self.area, t]*(model.delta[t] - model.variable_horizon_values[other_area, self.area, t]) 
                    if  self.area < other_area:
                        b += model.dual_vars_P[self.area, other_area, t]*(model.P_exchange[other_area, t])
                for t in model.TimeInput:
                    c += model.dual_vars_diff[other_area, self.area, t](model.delta[t+1]-model.delta[t])
                    c += model.dual_vars_diff[self.area, other_area, t](-model.delta_areas[other_area, t+1]+model.delta_areas[other_area, t])
            return (a + b + c)
        def _convex_term(model):
            a = 0
            b = 0
            c = 0
            a += sum( sum(model.rho_scaled[t]*(model.delta_areas[i,t] - model.variable_horizon_values[i, i, t])**2 for i in model.other_areas) for t in model.TimeInput)
            a += sum( sum(model.rho_scaled[t]*(model.delta[t]         - model.variable_horizon_values[i, self.area, t])**2 for i in model.other_areas) for t in model.TimeInput)
            b += sum( sum((model.P_exchange[i, t]  + model.variable_horizon_values_P[i, self.area, t])**2 for i in model.other_areas) for t in model.TimeInput)
            for other_area in model.other_areas:
                for t in model.TimeInput:
                    c += (model.delta[t+1]-model.delta[t] - (model.variable_horizon_values[other_area, self.area, t+1] - model.variable_horizon_values[other_area, self.area, t] ))**2
                    c += (model.variable_horizon_values[self.area, other_area, t+1] - model.variable_horizon_values[other_area, self.area, t] - (model.delta_areas[other_area, t+1]-model.delta_areas[other_area, t]))**2
            c = coordinator.rho_diff*c
            norm = (a + b + c) 
            return (model.rho/2)*norm
        
        def _damping_term(model):
            a = 0
            for t in model.TimeInput:
                a += (self.T-t)*(model.delta[t] - model.delta_previous[t])**2  
                a += 0
            a = 100*a
            return a
        def _terminal_cost(model):
            a = 0
            a += self.T*(model.omega[self.T]-1)**2
            return 1*a 

        def _smoothing_term(model):
            a = 0
            b = 0
            a += sum((model.delta[t+1] - model.delta[t])**2 for t in model.TimeDynamics)
            a += 0*sum((model.delta_areas[i,t+1] - model.delta_areas[i,t])**2 for i in model.other_areas for t in model.TimeDynamics)
            b += 1*sum((model.omega[t+1] - model.omega[t])**2 for t in model.TimeDynamics)
            return a + b 
        
        self.model.freq_cost =       pyo.Expression(rule=_freq_cost)
        self.model.lagrangian_term = pyo.Expression(rule=_lagrangian_term)
        self.model.convex_term =     pyo.Expression(rule=_convex_term)
        self.model.damping_term =    pyo.Expression(rule=_damping_term)
        self.model.terminal_cost =   pyo.Expression(rule=_terminal_cost)
        self.model.smoothing_term =  pyo.Expression(rule=_smoothing_term)

        self.model.cost = pyo.Objective(expr=1e2*self.model.freq_cost + 1e1*self.model.terminal_cost + self.model.lagrangian_term 
                                        + self.model.convex_term + 1e1*self.model.damping_term + 1e1*self.model.smoothing_term, sense=pyo.minimize)

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
        self.other_areas        = self.andes.get_neighbour_areas(self.area)
        self.interface_buses    = self.andes.get_interface_buses(self.area, self.other_areas)
        self.b_areas            = self.andes.get_system_susceptance(self.area, self.other_areas)

        self.pmax_slack = self.andes.get_complete_variable("Slack", "pmax", self.area)
        self.pmin_slack = self.andes.get_complete_variable("Slack", "pmin", self.area)
        self.pmax_pv =    self.andes.get_area_variable("PV", "pmax", self.area)
        self.pmin_pv =    self.andes.get_area_variable("PV", "pmin", self.area)

        self.pref0 = self.andes.get_partial_variable("TGOV1N", "pref0", self.governors)

        self.Sn_values = self.andes.get_partial_variable("GENROU", "Sn", self.generators)
        self.D_values = np.array(self.andes.get_partial_variable("GENROU", "D", self.generators))
        self.M_values = np.array(self.andes.get_partial_variable("GENROU", "M", self.generators))

        for i in range(len(self.generators)):
            self.M_values[i] = self.M_values[i] / self.Sn_values[i] * 100  # Normalize M values by Sn values 
        
        self.S_coi = sum(self.Sn_values)
        # self.M_coi =  sum(self.M_values)
        self.M_coi = 0.0 
        if self.generators:
            for i in range(len(self.generators)):
                self.M_coi += self.M_values[i]
        if 'npcc' in self.andes.case_path: 
            self.M_values_secondary = self.andes.get_area_variable("GENCLS", "M", self.area)
            self.D_values_secondary = self.andes.get_area_variable("GENCLS", "D", self.area)
            self.D = sum(self.D_values) + sum(self.D_values_secondary)
            for i in range(len(self.M_values_secondary)):
                self.M_coi += self.M_values_secondary[i]
                
    def initialize_variables_values(self): 
        """
        Initializes model variables from Andes snapshot data.
        """
        # Frequency
        omega_values = self.andes.get_partial_variable("GENROU", "omega", self.generators)
        weight = np.array(self.M_values) * np.array(self.Sn_values)
        if 'npcc' in self.andes.case_path:
            omega_values_2 = self.andes.get_partial_variable("GENCLS", "omega", self.non_controllable_generators)
            M_values = self.andes.get_partial_variable("GENCLS", "M", self.non_controllable_generators)
            Sn_values = self.andes.get_partial_variable("GENCLS", "Sn", self.non_controllable_generators)
            weights_2 = np.array(M_values) * np.array(Sn_values)
            weight = np.concatenate(weight, weights_2)
            omega_values = np.concatenate(omega_values, omega_values_2)
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
        if 'npcc' in self.andes.case_path:
            tm_values = self.andes.get_partial_variable("GENCLS", "tm", self.non_controllable_generators)
            u_GENROU_values = self.andes.get_partial_variable("GENCLS", "u", self.non_controllable_generators)
            for i, (gen, val) in enumerate(zip(self.non_controllable_generators, u_GENROU_values)):
                P0 += tm_values[i] * u_GENROU_values[i]
        self.model.Pd -= P0
        
        # Power exchange
        self.power_exchange = self.andes.get_exact_power_transfer(self.area, self.interface_buses)
        for nbr, val in self.power_exchange.items():
            for k in range(self.K):
                self.model.P_exchange[k, int(nbr)] = val

        #Angles 
        if not self.angles:
            return
        response = self.andes.get_delta_equivalent()
        self.delta_equivalent   = response['delta_equivalent']
        self.delta_ref          = response['delta_ref']
        self.model.delta0       = self.delta_equivalent[self.area]
        self.model.delta_ref    = self.delta_ref

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
                if not Config.angles:
                    self.vars_saved['P_exchange'][(nbr, k)] = self.model.P_exchange[k, nbr].value                   #self.model.P_exchange[nbr].value
                    self.vars_saved['P_exchange_areas'][(nbr, k)] = -self.model.P_exchange[k, nbr].value

                    self.model.variables_horizon_values[self.area, nbr, k, nbr] = self.model.P_exchange[k, nbr].value
                    self.model.variables_horizon_values[nbr, self.area, k, nbr] = -self.model.P_exchange[k, nbr].value
                else:
                    self.vars_saved['P_exchange'][(nbr, k)] = self.model.P_exchange[k, nbr].value                   
                    self.vars_saved['delta_areas'][(self.area, nbr, k)] = self.model.delta_areas[k, nbr].value                   
                    self.vars_saved['delta'][(k)] = self.model.delta[k].value                   

                    self.model.variables_horizon_values[self.area, nbr, k] = self.model.P_exchange[k, nbr].value

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
                if not Config.angles:
                    self.model.P_exchange_areas[k, nbr].value = self.vars_saved['P_exchange_areas'][(nbr, k)]
                else:
                    self.model.delta_areas[k, nbr].value = self.vars_saved['delta_areas'][(self.area, nbr, k)]                     
                    self.model.delta[k].value = self.vars_saved['delta'][(k)]
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
                if not Config.angles:
                    self.vars_saved['P_exchange'][(nbr, k)] = self.model.P_exchange[k, nbr].value
                    self.vars_saved['P_exchange_areas'][(nbr, k)] = self.model.P_exchange_areas[k, nbr].value