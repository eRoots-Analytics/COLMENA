import numpy as np
import time
import requests
from copy import deepcopy
import matplotlib.pyplot as plt
import matplotlib
from andes.utils.paths import get_case, cases_root, list_cases
import andes as ad
import pyomo.environ as pyo
import pyomo

#Service to deploy a one layer control

url = 'http://192.168.68.74:5000' + "/print_app"
andes_url = 'http://192.168.68.74:5000'

from pyomo.core.expr.visitor import identify_variables
from pyomo.environ import value, Constraint

def print_all_variables(model):
    """
    Prints all variables of a Pyomo or similar optimization model before solving.
    Prints name, value, lower bound, upper bound.
    
    Args:
        model: The optimization model instance.
    """
    print("\n==== VARIABLES BEFORE SOLVING ====")

    # If model has a 'component_objects' method (Pyomo style)
    try:
        for var in model.component_objects(pyo.Var, active=True):
            var_object = getattr(model, var.name)
            print(f"\nVariable: {var.name}")
            var_object.pprint()

    # If model variables are accessible via a dictionary (e.g., CasADi, custom frameworks)
    except AttributeError:
        try:
            for name, var in model.variables.items():
                print(f"Variable: {name}")
                print(f"  Value: {var.value}")
                print(f"  Lower Bound: {var.lb}")
                print(f"  Upper Bound: {var.ub}")
        except AttributeError:
            print("Could not find a method to access variables. Please adapt this function to your model structure.")

    print("==== END OF VARIABLES ====")

def check_constraint_violations(model, tolerance=23e-4):
    print("\nConstraint violations (abs residual > {:.1e}):".format(tolerance))
    for constr in model.component_objects(Constraint, active=True):
        for index in constr:
            c = constr[index]
            expr = c.body
            val = value(expr)

            violated = False
            msg = f"{c.name}[{index}]: {expr} = {val:.4e}"

            lb = value(c.lower) if c.has_lb() else None
            ub = value(c.upper) if c.has_ub() else None

            if lb is not None and ub is not None and abs(lb - ub) < 1e-8:
                # Equality constraint
                if abs(val - lb) > tolerance:
                    msg += f" ≠ EQ({lb:.4e}) "
                    violated = True
            else:
                if lb is not None and val < lb - tolerance:
                    msg += f" < LB({lb:.4e}) "
                    violated = True
                if ub is not None and val > ub + tolerance:
                    msg += f" > UB({ub:.4e}) "
                    violated = True

            if violated:
                print(constr.pprint())
                print(msg)

def add_area_mpc(self, model):
    buses = requests.post(andes_url + '/area_variable_sync', json={'model':'Bus', 'var':'idx', 'area':self.area}).json()['value']
    generators = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'idx', 'area':self.area}).json()['value']
    loads = requests.post(andes_url + '/area_variable_sync', json={'model':'PQ', 'var':'idx', 'area':self.area}).json()['value']
    b_lines = requests.post(andes_url + '/lines_susceptance', json={'area':self.area}).json()['value']
    PQ_bus = requests.post(andes_url + '/area_variable_sync', json={'model':'PQ', 'var':'bus', 'area':self.area}).json()['value']

    #We initialize the variables
    model.area_buses = pyo.Set(initialize = buses)
    model.P_bus = pyo.Var(model.area_buses, model.TimeHorizon)
    model.delta_bus = pyo.Var(model.area_buses, model.TimeHorizon, bounds=(-10, 10))
    model.freq_gen = pyo.Var(model.generator_bus, model.TimeHorizon, bounds=(0.8, 1.2))
    model.P_line = pyo.Var(model.area_buses, model.area_buses, model.TimeHorizon)

    responseAndes = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'M', 'idx':generators})
    M_values = responseAndes.json()['value']
    responseAndes = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'D', 'idx':generators})
    D_values = responseAndes.json()['value']
    responseAndes = requests.post(andes_url + '/partial_variable_sync', json={'model':'PQ', 'var':'p0', 'idx':loads})
    p0_values = responseAndes.json()['values']
    p0_values = {bus:p0_values[i] for i, bus in enumerate(PQ_bus)}
    M_values = {gen_bus:M_values[i] for i, gen_bus in enumerate(model.generator_bus)}
    D_values = {gen_bus:D_values[i] for i, gen_bus in enumerate(model.generator_bus)}
    for i, bus in enumerate(model.area_buses):
        if bus in loads:
            p0_values[bus] = p0_values[i] 
        else:
            p0_values[bus] = 0
    model.M_values = pyo.Param(model.generator_bus, initialize = M_values)
    model.D_values = pyo.Param(model.generator_bus, initialize = D_values)
    model.p0_values = pyo.Param(model.area_buses, initialize = p0_values)

    #Coupling Constraints
    model.coupling_constraint_angle = pyo.Constraint(
        model.TimeDynamics, 
        rule=lambda model, t: sum(model.M)*model.delta[t] == sum(model.delta_bus[gen, t]*model.M_values[gen] for gen in model.generator_bus) )

    fn = 60
    #we define the generator dynamics
    model.constraint_area1 = pyo.Constraint(
        model.generator_bus, 
        model.TimeDynamics, 
        rule=lambda model, i, t: model.delta_bus[i, t+1] - model.delta_bus[i, t] ==  self.dt*2*np.pi*fn*(model.freq[t]-1))
    model.constraint_area2 = pyo.Constraint(
        model.generator_bus, 
        model.TimeDynamics, 
        rule=lambda model, i, t: 
        model.M_values[i]*(model.freq_gen[i, t+1] - model.freq_gen[i, t])/self.dt == (-model.D_values[i](model.freq_gen[i,t]-1) + model.Pg[i, t] - model.P_bus[i,t]))

    #We define the grid dynamics
    model.constraint_line = pyo.Constraint(
        model.area_buses, 
        model.area_buses, 
        rule=lambda model, bus1, bus2, t: 
        model.P_line[bus1, bus2, t] == b_lines[bus1, bus2]*(model.delta_bus[bus1] - model.delta_bus[bus2]))
    model.constraint_bus = pyo.Constraint(
        model.area_buses, 
        rule=lambda model, bus, t: 
        model.P_bus[bus, t] + model.Pg[self.bus2idgen[bus], t] + sum(model.P_line[bus, other_bus, t] for other_bus in model.area_bus) + model.P_demand[bus,t] == 0)


def setup_mpc(self, mpc_problem, dt = 0.5, controllable_redual = False):
    area = self.area
    #STEP 1: Data Collection

    #We query Andes the idxs of the different types of models in the agent's area aas a list
    generators = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'idx', 'area':self.area}).json()['value']
    loads = requests.post(andes_url + '/area_variable_sync', json={'model':'PQ', 'var':'idx', 'area':self.area}).json()['value']
    areas = requests.get(andes_url + '/complete_variable_sync', params={'model':'Area', 'var':'idx'}).json()['value']
    buses = requests.post(andes_url + '/area_variable_sync', json={'model':'Bus', 'var':'idx', 'area':self.area}).json()['value']

    #We get the buses where the devices are located
    PV_bus = requests.post(andes_url + '/area_variable_sync', json={'model':'PV', 'var':'bus', 'area':self.area}).json()['value']
    generator_bus = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'bus', 'area':self.area}).json()['value']
    other_areas = [i for i in areas if i != self.area]
    responseAndes = requests.get(andes_url + '/neighbour_area', params = {'area': str(area)})    
    other_areas = responseAndes.json()['value']


    gen_location = {gen:generator_bus[i] for i, gen in enumerate(generators)}
    bus2idgen = {generator_bus[i]:gen for i, gen in enumerate(generators)}
    self.bus2idgen = bus2idgen

    M_coi = 0
    D_coi = 0
    fn_coi = 0
    S_area = 0
    P_demand = 0
    S_base = []
    #We get the values for specific device parameters
    responseAndes = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'Sn', 'idx':generators})
    Sn_values = responseAndes.json()['value']
    responseAndes = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'Pe', 'idx':generators})
    Pe_values = responseAndes.json()['value']
    responseAndes = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'tm', 'idx':generators})
    tm_values = responseAndes.json()['value']
    responseAndes = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'M', 'idx':generators})
    M_values = responseAndes.json()['value']
    responseAndes = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'D', 'idx':generators})
    D_values = responseAndes.json()['value']
    responseAndes = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'fn', 'idx':generators})
    fn_values = responseAndes.json()['value']
    responseAndes = requests.get(andes_url + '/complete_variable_sync', params={'model':'PV', 'var':'p0'})
    p0_values = responseAndes.json()['value']
    responseAndes = requests.post(andes_url + '/area_variable_sync', json={'model':'PQ', 'var':'p0', 'area':self.area})
    PQ_values = responseAndes.json()['value']
    for i, bus in enumerate(PQ_values):
        p0 = PQ_values[i]
        P_demand += p0   
    #We compute the Center of Inertia and other values using the previous parameters
    for i, bus in enumerate(generator_bus):
        if bus in buses:
            S_area += Sn_values[i]
    for i, bus in enumerate(generator_bus):
        if bus in buses:
            Sn = Sn_values[i]
            fn = fn_values[i]
            M = M_values[i]
            D = D_values[i]
            M_coi += M
            D_coi += D
            fn_coi += Sn*fn
            S_base.append(Sn)
    M_coi = M_coi
    D_coi = D_coi/S_area
    fn_coi = fn_coi/S_area
    fn_coi = 60

    #We define the model and the first sets over which the variables are defined 
    model = pyo.ConcreteModel()
    model.M = pyo.Param(initialize= M_coi)
    model.D = pyo.Param(initialize= D_coi)
    model.fn = pyo.Param(initialize= fn_coi)
    model.generators = pyo.Set(initialize = generators)
    model.loads = pyo.Set(initialize = loads)
    pe_base = {i:Pe_values for i,Pe in list(zip(model.generators, Pe_values))}
    model.Sn = pyo.Param(model.generators, initialize = pe_base)
    model.other_areas = pyo.Set(initialize = other_areas)
    model.areas = pyo.Set(initialize = areas)
    model.TimeHorizon = pyo.RangeSet(0, self.T)
    model.TimeDynamics = pyo.RangeSet(0, self.T-1)
    model.TimeSecondDynamics = pyo.RangeSet(0, self.T-2)
    model.dual_vars = pyo.Param(model.areas, model.areas, model.TimeHorizon, initialize = mpc_problem.dual_vars, mutable = True)

    #We query Andes for the pmax and pmin values of the generators
    slack_bus = requests.get(andes_url + '/complete_variable_sync', params={'model':'Slack', 'var':'bus', 'area':self.area}).json()['value']
    pmax_slack_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'Slack', 'var':'pmax', 'area':self.area}).json()['value']
    pmin_slack_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'Slack', 'var':'pmin', 'area':self.area}).json()['value']
    Sn_slack_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'Slack', 'var':'Sn', 'area':self.area}).json()['value']
    pmax_pv_values = requests.post(andes_url + '/area_variable_sync', json={'model':'PV', 'var':'pmax', 'area':self.area}).json()['value']
    pmin_pv_values = requests.post(andes_url + '/area_variable_sync', json={'model':'PV', 'var':'pmin', 'area':self.area}).json()['value']

    def power_bounds(model, gen, t):
        gen_bus = gen_location[gen]
        if gen_bus in PV_bus:
            index = PV_bus.index(gen_bus) 
            pmax = (pmax_pv_values[index])
            pmin = (pmin_pv_values[index])
        elif gen_bus in slack_bus:
            index = slack_bus.index(gen_bus)
            pmax = (pmax_slack_values[index])
            pmin = (pmin_slack_values[index])
        else:
            pmax = 11
            pmin = 0
        return (pmin, pmax+1)
    
    #We define the decision variable of the problem:
        #delta (size T) the angle of the area
        #freq  (size T) the frequency of the area in pu
        #Pg    (size #generators*T) the power generation of the generators in the area
        #P     (size T) the sum of the total power in the area 
        #delta_areas (size other_ares*T) the angle of the other areas

    model.delta = pyo.Var(model.TimeHorizon, bounds=(-50, 50))
    model.delta_areas = pyo.Var(model.other_areas, model.TimeHorizon, initialize = 0.0, bounds=(-50, 50))
    model.freq = pyo.Var(model.TimeHorizon, bounds = (0.99, 1.01))
    model.Pg = pyo.Var(model.generators, model.TimeHorizon, bounds=power_bounds)
    model.P = pyo.Var(model.TimeHorizon, initialize = 0.0)
    model.P_exchange = pyo.Var(model.TimeHorizon, initialize = 0.0)

    #We define parameters of the problem:
        #b (size areas*areas) the susceptance in pu between 2 areas
        #Pd (size T) the power demand in the area at time t 
        #state_horizon_values (size T) the power demand in the area at time t 

    b_areas = requests.get(andes_url + '/system_susceptance', params={'area':self.area}).json()
    b_areas = {int(k): v for k, v in b_areas.items()}
    delta_previous = {t:0 for t in model.TimeHorizon}
    delta_areas_previous = delta_areas_previous = {(area, t): 0.0 for area in model.other_areas for t in model.TimeHorizon}
    model.Pd = pyo.Param(model.TimeHorizon, initialize = P_demand)
    model.b = pyo.Param(model.other_areas, initialize = b_areas)
    model.delta_previous = pyo.Param(model.TimeHorizon, initialize= delta_previous, mutable = True)
    model.delta_areas_previous = pyo.Param(model.other_areas, model.TimeHorizon, initialize= delta_areas_previous, mutable = True)
    model.state_horizon_values = pyo.Param(model.areas, model.areas, model.TimeHorizon, initialize = self.state_horizon_values, mutable=True)

    #We define the initial conditions:
    # delta0 : the initial area angle initialized as the weighted mean od sum (M_i*delta_i)/sum(M_i)
    # freq0  : the initial area frequency 
    delta_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'delta', 'idx':generators}).json()['value']
    delta_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'Bus', 'var':'a', 'idx':buses}).json()['value']
    freq_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'omega', 'idx':generators}).json()['value']
    M_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'M', 'idx':generators}).json()['value']
    response_delta_equivalent = requests.get(andes_url + '/delta_equivalent', params={'area':1})
    delta_equivalent = response_delta_equivalent.json()['value']
    response_delta_equivalent = requests.get(andes_url + '/delta_equivalent', params={'area':self.area})
    p_losses = response_delta_equivalent.json()['losses']
    p_losses *= 1
    delta0 = np.mean(delta_values)
    freq0 = np.dot(M_values, freq_values) / np.sum(M_values)
    model.delta[0].value = delta0
    model.freq[0].value = freq0
    print(f"freq0 is {freq0} for area {self.area}")
    delta_equivalent['1'] = 0
    if self.area == 1:
        delta0 = 0
        delta_areas0 = delta_equivalent['2']
    else:
        delta0 = delta_equivalent[str(self.area)]
        delta_areas0 = 0

    print(f"delta0 is {delta0}, Ddelta is {delta_areas0}")
    initial_area_values = {}
    for x_area in model.other_areas:
        delta_area = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'delta', 'area':x_area}).json()['value']
        delta_area = requests.post(andes_url + '/area_variable_sync', json={'model':'Bus', 'var':'a', 'area':x_area}).json()['value']
        M_area = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'M', 'area':x_area}).json()['value']
        #initial_area_values[x_area] = (np.dot(M_area, delta_area) / np.sum(M_area))
        initial_area_values[x_area] = np.mean(delta_area)

    tm0 = {generator:tm_values[i] for i,generator in enumerate(model.generators)}
    delta_areas0_dict = {area:delta for area, delta in zip(model.other_areas, [delta_areas0])}
    model.delta0 = pyo.Param(initialize = delta0, mutable=True)
    model.freq0 = pyo.Param(initialize = freq0, mutable=True)
    model.p_losses = pyo.Param(initialize = p_losses, mutable=True)
    model.delta_areas0 = pyo.Param(model.other_areas, initialize = delta_areas0_dict, mutable=True)
    model.tm0 = pyo.Param(model.generators, initialize = tm0, mutable=True)
    self.ramp_up = 0.005

    def initial_p(model, i):
        return (model.tm0[i] - self.ramp_up, model.Pg[i,0], model.tm0[i] + self.ramp_up)
    
    def initial_delta_areas(model, i):
        #return (initial_area_values[i], model.delta_areas[i, 0], initial_area_values[i])    
        return (model.delta_areas0[i], model.delta_areas[i, 0], model.delta_areas0[i])
    
    #We define the problem constraints
    #C1: initial area angle initial value
    #C2: initial area frequency initial value 
    #C3: initial area's angle value for the neighboring areas
    #C4: initial power injected by the generators in p.u.
    model.constraint_initial_conditions = pyo.Constraint(expr = model.delta[0] == model.delta0)
    model.constraint_initial_conditions2 = pyo.Constraint(expr = model.freq[0] == model.freq0)
    model.constraint_initial_conditions3 = pyo.Constraint(model.other_areas, rule = initial_delta_areas)
    model.constraint_initial_conditions4 = pyo.Constraint(model.generators, rule= initial_p)

    #We define the dynamics of the system as constraints
    #C1: the current area angle derivative
    #C2: the current frequency angle derivative
    #C3: the generator maximum ramp up
    #C4: the generator minimum ramp up
    model.constrains_dynamics1 = pyo.Constraint(model.TimeDynamics, rule=lambda model, t: (model.delta[t+1] - model.delta[t])==  self.dt*2*np.pi*fn*(model.freq[t]-1))
    model.constrains_dynamics2 = pyo.Constraint(model.TimeDynamics, rule=lambda model, t: model.M*(model.freq[t+1] - model.freq[t])/dt == ((-model.D(model.freq[t]-1) + model.P[t] - model.Pd[t] - model.P_exchange[t] + model.p_losses)))
    model.constrains_dynamics3 = pyo.Constraint(model.generators, model.TimeDynamics, rule=lambda model, i, t: (model.Pg[i, t+1] - model.Pg[i, t]) <= self.dt*self.ramp_up)
    model.constrains_dynamics4 = pyo.Constraint(model.generators, model.TimeDynamics, rule=lambda model, i, t: -self.ramp_up*self.dt <= (model.Pg[i, t+1] - model.Pg[i, t]))

    #We define the Inter Area constraints:
    #C1: constraint defining the power exchanged between areas P_exchange = sum(P_i,j) for j in the other areas
    #C2: constraint defining the total power generated P = sum(P_gen) for gen in current area generators
    #gamma the losses in the generators
    def power_inter_area(model, t):
        return model.P_exchange[t] == sum(model.b[area]*(model.delta[t] - model.delta_areas[area, t]) for area in model.other_areas)
    model.constrains_area = pyo.Constraint(model.TimeHorizon, rule = power_inter_area)
    def power_balance_rule(model, t):
        return model.P[t] == sum(model.Pg[gen, t] for gen in model.generators)
    model.constraints_balance = pyo.Constraint(model.TimeHorizon, rule = power_balance_rule)

    #We define a condition for the final states To ensure feasability.
    area_sign = 1 if self.area == 1 else -1
    #model.final_condition = pyo.Constraint(expr = model.delta[0] == model.delta[self.T])
    #model.final_condition_others = pyo.Constraint(model.other_areas,rule = lambda model, i: model.delta_areas[i, 0] == model.delta_areas[i,self.T])
    #model.convex_condition = pyo.Constraint(model.TimeSecondDynamics, rule =lambda model, t: (area_sign)*(model.delta[t] - 2*model.delta[t+1] + model.delta[t+2]) >= 0)
    #model.convex_condition_other = pyo.Constraint(model.TimeSecondDynamics, model.other_areas, rule =lambda model, t, i: (-area_sign)*(model.delta_areas[i,t] - 2*model.delta_areas[i,t+1] + model.delta_areas[i,t+2]) >= 0)
    #model.final_condition = pyo.Constraint(expr = model.freq[self.T] == 1)
    #model.final_condition = pyo.Constraint(expr = model.freq[self.T] == 1)

    #We define the cost function
    #COST 1: Linear cost related to each generator power
    #COST 2: Cost term related to losses of active power
    #COST 3: Frequency correction term where cost = norm(frequency - frequency_nominal)
    #COST 4: Lagrangian multipliers of the problem  
    # a is the error term associated with the error of what the current area thinks of the state values of the neighboring areas 
    # b is the error term associated with the error of what the neighboring areas think of the state values of current area 
    #COST 5: Penalty Term
    n = len(generators)
    model.rho = pyo.Param(initialize = mpc_problem.rho, mutable=True)
    cost = np.ones(n) + np.random.rand(n)
    cost_dict = {generator:cost[i] for i,generator in enumerate(generators)}
    model.c = pyo.Param(model.generators, initialize=cost_dict)
    def p_cost(model):
        return sum(model.c[i] * (model.Pg[i,t]) for i in model.generators for t in model.TimeHorizon)
    def p_exchange_cost(model):
        return sum((model.P_exchange[t])**2 for t in model.TimeHorizon)
    def freq_cost(model):
        return sum((model.freq[t]-1)**2 for t in model.TimeHorizon)
    def lagrangian_term(model):
        a = 0
        b = 0
        for other_area in model.other_areas:
            for t in model.TimeHorizon:
                a += model.dual_vars[self.area, other_area, t]*(model.state_horizon_values[other_area, other_area, t] - model.delta_areas[other_area, t])
                b += model.dual_vars[other_area, self.area, t]*(model.delta[t] - model.state_horizon_values[other_area, self.area, t]) 
        return (a + b)
    def penalty_term(model):
        a = 0
        exp = 0
        a += sum( sum(((self.T+1-t)**exp)*(model.delta_areas[i,t] - model.state_horizon_values[i, i, t])**2 for i in model.other_areas) for t in model.TimeHorizon)
        a += sum( sum(((self.T+1-t)**exp)*(model.delta[t]         - model.state_horizon_values[i, self.area, t])**2 for i in model.other_areas) for t in model.TimeHorizon)
        norm = (a) 
        return (model.rho/2)*norm
    def damping_term(model):
        a = 0
        a += sum((model.delta[t] - model.delta_previous[t])**2  for t in model.TimeHorizon)
        a += sum( sum((model.delta_areas[i,t] - model.delta_areas_previous[i, t])**2 for i in model.other_areas) for t in model.TimeHorizon)
        #a = a + (self.dt-0.1)*40*a + (self.T-10)*1.0*a +  (self.T-16)*(self.T-10)*1.6*a
        a = 50*a
        a = 60*a
        a = 1*a
        return a
    def terminal_cost(model):
        a = 0
        a += self.T*(model.freq[self.T]-1)**2
        return 1*a 
    def steady_state_condition(model):
        a = 0
        a += 2*(model.P[self.T]-model.Pd[self.T] - model.P_exchange[self.T])**2
        return a 
    def power_normalization(model):
        a = 0
        a += sum((model.Pg[gen, t+1] - model.Pg[gen, t])**2 for gen in model.generators for t in model.TimeDynamics)
        return a
    def smoothing_term(model):
        a = 0
        a += sum((model.delta[t+1] - model.delta[t])**2 for t in model.TimeDynamics)
        a += 0*sum((model.delta_areas[i,t+1] - model.delta_areas[i,t])**2 for i in model.other_areas for t in model.TimeDynamics)
        return a
    model.cost = pyo.Objective(rule=lambda model: 3e3*freq_cost(model) + 1*lagrangian_term(model) + 0*steady_state_condition(model)
                       + penalty_term(model) + 1e2*damping_term(model) + 0*terminal_cost(model) + 5e6*smoothing_term(model), sense=pyo.minimize)
    return model

class mpc_agent:
    def __init__(self, agent_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.n_areas = 2
        self.alpha0 = 0.01
        self.dt = 0.1
        self.tol = 2.4e-4
        self.andes_url = andes_url 
        self.agent_id = agent_name
        self.area = int(self.agent_id[-1])
        responseAndes = requests.get(self.andes_url + '/assign_device', params = {'agent': self.agent_id})
        self.device_dict = responseAndes.json()
        self.t_start = time.time()
        self.T = 15          #number of timesteps when performing the MPC
        
        self.areas = requests.get(andes_url + '/complete_variable_sync', params={'model':'Area', 'var':'idx'}).json()['value']
        self.other_areas = [i for i in self.areas if i != self.area]
        self.first = True
        self.state_horizon_values = {}
        self.state_saved_values = {}
        self.reset_starting_points = False
        self.alpha = 0.3
        self.rho = 0.1
        self.delta_primal_vars = []
        self.delta_areas_primal_vars = []
        for area_local in self.areas:
            for area_out in self.areas:
                for t in range(self.T+1):
                    self.state_horizon_values[area_local, area_out, t] = 0
    
    def first_warm_start(self):
        generators = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'idx', 'area':self.area}).json()['value']
        response_delta_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'delta', 'idx':generators}).json()
        print(f"response is {response_delta_values}")
        delta_values = response_delta_values['value']
        M_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'M', 'idx':generators}).json()['value']
        delta0 = np.dot(M_values, delta_values) / np.sum(M_values)

        responseAndes = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'Pe', 'area':self.area})
        Pe_values = responseAndes.json()['value']
        responseAndes = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'tm', 'area':self.area})
        tm_values = responseAndes.json()['value']

        areas = requests.get(andes_url + '/complete_variable_sync', params={'model':'Area', 'var':'idx'}).json()['value']
        other_areas = [i for i in areas if i != self.area]

        for t in range(self.T+1):
            self.state_horizon_values[self.area, self.area, t] = delta0
            self.state_saved_values['f', t] = 1.0
            self.state_saved_values['P', t] = np.sum(tm_values)
            self.state_saved_values['P_exchange', t] = 0.0
            for i, gen in enumerate(generators):
                self.state_saved_values['Pg', gen, t] = tm_values[i]
            for area in other_areas:
                self.state_saved_values['delta_areas', t] = 0.0
        return 1

    def warm_start(self):
        for t in self.model.TimeHorizon:
            for area in self.model.other_areas:
                self.model.delta_areas_previous[area, t].value = self.model.delta_areas[area,t].value
                if t != 0:
                    self.model.delta_areas[area, t].value = self.state_horizon_values[area, area, t]
                    self.model.delta[t].value = self.state_horizon_values[area, self.area, t]
            
            if t+1 > self.T:
                continue
            self.model.freq[t].value = max(self.state_saved_values['f', t+1], 0.85001)
            self.model.P[t].value =  self.state_saved_values['P', t+1]
            self.model.P_exchange[t].value =  self.state_saved_values['P_exchange', t+1]
            for gen in self.model.generators:
                self.model.Pg[gen, t].value = self.state_saved_values['Pg', gen, t+1]

            if self.area == 2:
                self.model.delta[t].value = 0.016069
            self.model.delta_previous[t].value = self.model.delta[t].value
        return 1
    
    def save_warm_start(self):
        for t in self.model.TimeHorizon:
            self.state_saved_values['f', t] = self.model.freq[t].value
            self.state_saved_values['P', t] = self.model.P[t].value
            self.state_saved_values['P_exchange', t] = self.model.P_exchange[t].value
            for gen in self.model.generators:
                self.state_saved_values['Pg', gen, t] = self.model.Pg[gen, t].value 
            for area in self.model.other_areas:
                self.state_saved_values['delta_areas', t] = self.model.delta_areas[area, t]
        return 1
    
    def reset_starting_points_method(self):
        #We reset the starting points delta0, freq0, Pg0, delta_areas0
        model = self.model
        generators = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'idx', 'area':self.area}).json()['value']
        freq_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'omega', 'idx':generators}).json()['value']
        M_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'M', 'idx':generators}).json()['value']
        tm_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'tm', 'idx':generators}).json()['value']
        response = requests.get(andes_url + '/delta_equivalent', params={'area':1}).json()
        delta_equivalent = response['value']
        response_areas = requests.get(andes_url + '/delta_equivalent', params={'area':self.area}).json()
        p_losses = response_areas['losses']
        tm0 = {generator:tm_values[i] for i,generator in enumerate(model.generators)}
        delta_equivalent['1'] = 0
        if self.area == 1:
            delta0 = 0
            delta_areas0 = delta_equivalent['2']
        else:
            delta0 = delta_equivalent[str(self.area)]
            delta_areas0 = 0

        freq0 = np.dot(M_values, freq_values) / np.sum(M_values)
        model.delta0.value = delta0 
        model.freq0.value = freq0
        model.p_losses = p_losses
        for area in model.other_areas:
            model.delta_areas0[area].value = delta_areas0
        for gen in model.generators:
            model.tm0[gen].value = tm0[gen]
            
    def setup_mpc(self, mpc_problem):
        self.model = setup_mpc(self, mpc_problem, self.dt, self.T)
        return self.model

class mpc:
    def __init__(self, agents, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.n_areas = 2
        self.areas = list(range(1, self.n_areas +1))
        self.alpha = {}
        self.alpha0 = 0.001
        self.T = agents[0].T
        self.agents = {agent.area:agent for agent in agents}
        self.dual_vars = {}
        self.areas = {}
        self.error = 100
        self.error_save = []
        self.Ki = 2e-4
        self.Kd = 7e-7
        self.rho = 0.05
        self.alpha =  0.015
        self.T_send = 5
        self.second_stage = False
        for area in range(1, self.n_areas+1):
            responseAndes = requests.get(andes_url + '/neighbour_area', params = {'area': str(area)})
            self.areas[area] = responseAndes.json()['value']
        for area_local, neighbors in self.areas.items():
            for area_to in neighbors:
                for t in range(self.T+1):
                    self.dual_vars[area_local, area_to, t] = 0.0
        
        self.delta_dual = {key: 0 for key in self.dual_vars}
        self.delta_dual = {key: 0 for key in self.dual_vars}
        self.delta_dual_vars = {k: 0 for k in self.dual_vars}
        self.integral_term = {key: 0 for key in self.dual_vars}
        self.derivative_term = {key: 0 for key in self.dual_vars}
        self.dual_history = {key: [] for key in self.dual_vars}
        self.delta_dual_history = {key: [] for key in self.dual_vars}


def solve_mpc(mpc_problem, verbose = False):
    agents = [agent for agent in mpc_problem.agents.values()]
    agent_1 = mpc_problem.agents[1]
    agent_2 = mpc_problem.agents[2]
    other = {"area_1": agent_2, "area_2": agent_1}
    mpc_problem.iter = 300
    mpc_problem.rho = 15
    mpc_problem.T_send = 8
    for i in range(mpc_problem.iter):
        responseAndes = requests.get(agent_1.andes_url + '/sync_time')
        for agent in agents:
            other_agent = other[agent.agent_id]

            if agent.first:
                agent.first_warm_start()
                other_agent.first_warm_start()
                model = agent.setup_mpc(mpc_problem)
                agent.first = False
            else:
                model = agent.model
                for key, val in agent.state_horizon_values.items():
                    model.state_horizon_values[key].value = val
                for key, val in mpc_problem.dual_vars.items():
                    model.dual_vars[key].value = val

            if agent.reset_starting_points:
                #We reset the starting points delta0, freq0, Pg0, delta_areas0
                agent.reset_starting_points = False
                agent.reset_starting_points_method()

            agent.warm_start()
            solver = pyo.SolverFactory('ipopt')
            #print_all_variables(model)
            tee = False
            solver.options["halt_on_ampl_error"] = "yes"
            result = solver.solve(model, tee=tee)
            print("Solver status:", result.solver.status)
            agent.save_warm_start()
            #we update the dual variables
            termination = result.solver.termination_condition

            if termination == pyomo.opt.TerminationCondition.infeasible:
                print(f"[{agent.agent_id}] Solver reported infeasibility ")
                print_all_variables(model)

                # Optional: break or handle accordingly
                check_constraint_violations(agent.model)
                raise RuntimeError(f"[{agent.agent_id}] MPC problem is infeasible")
        
            elif termination == pyomo.opt.TerminationCondition.maxIterations:
                print(f"[{agent.agent_id}] Solver hit max iterations.")
                print_all_variables(model)
                # Optional: check constraint violations or log dual residuals
                raise RuntimeError(f"[{agent.agent_id}] MPC problem did not converge (max iterations)")

            delta_dict = {t:model.delta[t].value for t in agent.model.TimeHorizon}
            delta_areas_dict = {t:model.delta_areas[area, t].value for t in model.TimeHorizon for area in agent.model.other_areas}
            agent.delta_primal_vars.append(delta_dict)
            agent.delta_areas_primal_vars.append(delta_areas_dict)
            #We get the current state_horizon and updated it with the solution for the agent's area
            for t in model.TimeHorizon:
                for other_agent in agents:
                    other_area = other_agent.area
                    if other_area == agent.area:
                        continue
                    other_agent.state_horizon_values[agent.area, agent.area, t] = model.delta[t].value
                    other_agent.state_horizon_values[agent.area, other_area, t] = model.delta_areas[other_area, t].value

        for t in range(mpc_problem.T+1):
            for agent in mpc_problem.agents.values():
                for neighbor_area in agent.model.other_areas:
                    neighbor_agent = mpc_problem.agents[neighbor_area]
                    mpc_problem.delta_dual_vars[neighbor_area, agent.area, t] = (agent.model.delta[t].value - neighbor_agent.model.delta_areas[agent.area, t].value)
                    mpc_problem.delta_dual_history[neighbor_area, agent.area, t].append(mpc_problem.delta_dual_vars[agent.area, neighbor_area , t])
        
        #We update the dual variables
        for t in range(mpc_problem.T+1):
            for agent in mpc_problem.agents.values():
                for neighbor_area in agent.model.other_areas:
                    neighbor_agent = mpc_problem.agents[neighbor_area]
                    alpha = mpc_problem.rho
                    if mpc_problem.second_stage:
                        gamma = 0.8*mpc_problem.rho/2
                        current_residual = mpc_problem.delta_dual_vars[agent.area, neighbor_area , t]
                        previous_residual = mpc_problem.delta_dual_history[agent.area, neighbor_area , t][-2]
                        mpc_problem.integral_term[agent.area, neighbor_area , t] += mpc_problem.delta_dual_vars[agent.area, neighbor_area , t]
                        mpc_problem.derivative_term[agent.area, neighbor_area , t] = current_residual - previous_residual
                        mpc_problem.dual_vars[agent.area, neighbor_area , t] += gamma*mpc_problem.delta_dual_vars[agent.area, neighbor_area , t]
                        mpc_problem.dual_vars[agent.area, neighbor_area , t] += gamma*mpc_problem.Ki*mpc_problem.integral_term[agent.area, neighbor_area , t]
                        mpc_problem.dual_vars[agent.area, neighbor_area , t] += gamma*mpc_problem.Kd*mpc_problem.derivative_term[agent.area, neighbor_area , t]
                    else:
                        mpc_problem.dual_vars[agent.area, neighbor_area , t] += alpha*mpc_problem.delta_dual_vars[agent.area, neighbor_area , t]
                    mpc_problem.dual_history[agent.area, neighbor_area , t].append(mpc_problem.dual_vars[agent.area, neighbor_area , t])
                    
        #Now update the alpha
        error = max(abs(v) for v in mpc_problem.delta_dual_vars.values())
        norm2_error = np.sqrt(sum(v**2 for v in mpc_problem.delta_dual_vars.values()))
        norm2_dual_error = 0
        for agent in agents:  # assuming all_agents is a list of agents
            if len(agent.delta_primal_vars) >= 2:
                last_dict = agent.delta_primal_vars[-1]
                second_last_dict = agent.delta_primal_vars[-2]

                # Sum the values at each timestep if they match
                norm2_dual_error += sum((last_dict[t] - second_last_dict[t])**2 for t in last_dict if t in second_last_dict)
            if len(agent.delta_areas_primal_vars) >= 2:
                last_dict = agent.delta_areas_primal_vars[-1]
                second_last_dict = agent.delta_areas_primal_vars[-2]

                # Sum the values at each timestep if they match
                norm2_dual_error += sum((last_dict[t] - second_last_dict[t])**2 for t in last_dict if t in second_last_dict)
            else:
                print(f"Agent {agent} does not have enough delta entries.")
                norm2_dual_error = 0
        mpc_problem.error_save.append([error, mpc_problem.rho, norm2_error, norm2_dual_error])

        if not mpc_problem.second_stage and i<100:
            mu = 15
            rho_max = 1e9
            if norm2_error > mu*norm2_dual_error:
                mpc_problem.rho = min(rho_max, mpc_problem.rho*1.3)
            elif mu*norm2_error < norm2_dual_error and (not mpc_problem.second_stage):
                mpc_problem.rho *= 0.8

        for agent in agents:
            _ = 0
            agent.model.rho.value = mpc_problem.rho 
        andes_role_changes = []
        converged = False
        print(f"error is {error} in iteration {i}")
        print("rho is ", mpc_problem.rho)
        if np.abs(error) < agent.tol:
            print(f"dist MPC converged")
            converged = True

        agent.first = False
    
        #If Converged we send all the new setpoints to the generator's governors
        #All the new set points are sent to andes and not just the first one
        if converged or i >= mpc_problem.iter-1:
            mpc_problem.iter_converge = i            
            responseAndes = requests.get(agent.andes_url + '/sync_time')
            time_start = responseAndes.json()['time']
            for x_agent in agents:
                generators = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'idx', 'area':x_agent.area}).json()['value']
                params = ['pref0', 'p_goal', 'paux0', 'tm0']
                params = ['p_direct', 'b']
                for gen_id in generators:
                    for param in params:
                        for t in range(1, mpc_problem.T_send):
                            if type(gen_id) == str:
                                kundur = False
                                id_number = gen_id[-1]
                                if gen_id[-2] != '_':
                                    id_number = gen_id[-2:]
                            else:
                                kundur = True
                                id_number = gen_id
                            roleChangeDict = {}
                            roleChangeDict['var'] = param
                            if roleChangeDict['var'] == 'tm0':
                                roleChangeDict['model'] = 'GENROU'
                                roleChangeDict['idx'] = 'GENROU_' + id_number
                            else:    
                                if not kundur:
                                    roleChangeDict['model'] = 'TGOV1N'
                                    roleChangeDict['idx'] = 'TGOV1_' + id_number
                                else:
                                    roleChangeDict['model'] = 'TGOV1'
                                    roleChangeDict['idx'] = id_number

                            if roleChangeDict['var'] == 'paux0':
                                roleChangeDict['value'] = x_agent.model.Pg[gen_id, t].value - x_agent.model.Pg[gen_id, 0].value 
                            elif roleChangeDict['var'] == 'b':
                                roleChangeDict['value'] = 1
                            else:
                                roleChangeDict['value'] = x_agent.model.Pg[gen_id, t].value
                            roleChangeDict['t'] = time_start + x_agent.dt*t
                            a = deepcopy(roleChangeDict)
                            andes_role_changes.append(a)
                            responseAndes = requests.get(x_agent.andes_url + '/add_set_point', params = roleChangeDict)
                            #print(f"change is {roleChangeDict['value']} at time {roleChangeDict['t']}")
            
            responseAndes = requests.get(x_agent.andes_url + '/set_last_control_time', params = {'t':roleChangeDict['t']})
            return converged, andes_role_changes, mpc_problem
        print(f"error is {error}")
    return converged, andes_role_changes, mpc_problem

def online_mpc():
    #We initialize the mpc problem
    #We first initialize the agents
    simulation_stopped = False
    agent_1 = mpc_agent("area_1")
    agent_2 = mpc_agent("area_2")
    responseAndes = requests.get(agent_1.andes_url + '/stop_simulation')
    agents = [agent_1, agent_2]
    mpc_problem = mpc(agents)
    mpc_problem.iter = 200
    mpc_problem.alpha = 15
    mpc_problem.rho = 15
    other = {"area_1": agent_2, "area_2": agent_1}
    converged, andes_role_changes, mpc_problem = solve_mpc(mpc_problem)
    agent = mpc_problem.agents[1]
    dt = agent.dt
    t_max = 1
    print('hi')
    last_time = -1
    for i in range(t_max):
        time_start = time.time()
        synced_time = requests.get(agent.andes_url + '/sync_time').json()['time']
        simulation_stopped = (last_time >= synced_time)
        last_time = synced_time
        if simulation_stopped:
            break
        responseAndes = requests.get(agent_1.andes_url + '/stop_simulation')
        for agent in mpc_problem.agents.values():
            agent.reset_starting_points = True
        solve_mpc(mpc_problem)
        print(f"convergence in {mpc_problem.iter_converge}")
        print(f"delta0 is {agent_1.model.freq[0].value}")
        time_spent = time.time() - time_start
        print(f"time_spent is {time_spent}")
        time.sleep(max(0,dt - time_spent))
    return converged, andes_role_changes, mpc_problem

andes_url = 'http://192.168.68.74:5000'

responseLoad = requests.post(andes_url + '/start_simulation')
delta_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'GENROU', 'var':'delta'}).json()['value']

time.sleep(9)
#We run the first iteration of the MPC

converged, andes_role_changes, mpc_problem = online_mpc()
agents = list(mpc_problem.agents.values())
print(f"converged is {converged}")
print(f"alpha is {mpc_problem.alpha}")
print(mpc_problem.dual_vars)
model = agents[0].model
other_model = agents[1].model
agent = agents[0]
agent2 = agents[1]
for t in model.TimeHorizon:
    print(f"delta self [{t}, area1] = {model.delta[t].value}")
    print(f"delta self [{t}, area1] = {model.delta_areas[2,t].value}")
    print(f"delta self [{t}, area2] = {other_model.delta[t].value}")

for t in model.TimeHorizon:
    print(f"delta self [{t}, area2] = {other_model.delta_areas[1,t].value}")
    print(f"delta self [{t}, area1] = {model.delta[t].value}")

for t in model.TimeHorizon:
    print(f"freq self [{t}, area1] = {model.freq[t].value}")
    print(f"freq self [{t}, area2] = {other_model.freq[t].value}")

for t in model.TimeHorizon:
    print(f"P_exchange self [{t}, area1] = {model.P_exchange[t].value}")
    print(f"delta model 2 self [{t}, area2] = {model.delta[t].value}")
    print(f"delta model 2 self [{t}, area1] = {model.delta_areas[2,t].value}")
    print(f"P_exchange self [{t}, area2] = {other_model.P_exchange[t].value}")
    print(f"delta model 2 self [{t}, area2] = {other_model.delta[t].value}")
    print(f"delta model 2 self [{t}, area1] = {other_model.delta_areas[1,t].value}")


def plot_dual_history(dual_history, title=None):
    plt.figure(figsize=(12, 6))
    for key, history in dual_history.items():
        plt.plot(history, label=f"{key}")
    plt.xlabel('Iteration')
    plt.ylabel('Dual Variable Value')
    if title is None:
        plt.title('Dual Variable History Over Iterations')
    else:
        plt.title('title')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def plot_freq_and_angle(model, other_model):
    """
    Plot the frequency and angle (delta) trajectories for model (Area 1)
    and frequency trajectory for other_model (Area 2).

    Assumes:
    - model.delta[t] and model.freq[t] exist for Area 1
    - other_model.freq[t] exists for Area 2
    """
    time = sorted(model.TimeHorizon)

    # Extract trajectories
    delta_area1 = [model.delta[t].value for t in time]
    delta_area2 = [other_model.delta[t].value for t in time]
    freq_area1 = [model.freq[t].value for t in time]
    freq_area2 = [other_model.freq[t].value for t in time]  # relies on other_model in scope

    # Plot angle trajectory
    plt.figure()
    plt.plot(time, delta_area1, label="Angle (delta) - Area 1")
    plt.plot(time, delta_area2, label="Angle (delta) - Area 2", linestyle="--")
    plt.xlabel("Time")
    plt.ylabel("Angle (rad)")
    plt.title("Angle Trajectory (Area 1)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

    # Plot frequency trajectories
    plt.figure()
    plt.plot(time, freq_area1, label="Frequency - Area 1")
    plt.plot(time, freq_area2, label="Frequency - Area 2", linestyle="--")
    plt.xlabel("Time")
    plt.ylabel("Frequency (Hz)")
    plt.title("Frequency Trajectories")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

def plot_primal_history(primal_history, title="Delta Primal Variable History"):
    """
    Plot the history of a multivalued primal variable across ADMM iterations.

    Parameters:
    - primal_history: List[Dict[t, value]] — one dict per ADMM iteration
    - title: str — plot title
    """
    if not primal_history:
        print("No primal variable history to plot.")
        return

    # Extract time indices from the first iteration
    time_steps = sorted(primal_history[0].keys())
    iterations = list(range(len(primal_history)))

    # Create a figure
    plt.figure(figsize=(10, 6))

    # For each time step t, collect its value over all iterations
    for t in time_steps:
        values = [iteration_dict[t] for iteration_dict in primal_history]
        plt.plot(iterations, values, label=f"t={t}")

    plt.xlabel("ADMM Iteration")
    plt.ylabel("Delta Value")
    plt.title(title)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

matplotlib.use('TkAgg')
plot_dual_history(mpc_problem.dual_history, title = 'Dual History')
plot_dual_history(mpc_problem.delta_dual_history, title = 'Delta Dual History')
plot_primal_history(agent.delta_primal_vars, title = 'Angle primal vars 1')
plot_primal_history(agent2.delta_areas_primal_vars, title = 'Angle Others primal vars 2')
plot_primal_history(agent.delta_areas_primal_vars, title = 'Angle primal vars 1')
plot_primal_history(agent2.delta_primal_vars, title = 'Angle Others primal vars 2')


# Assuming model and other_model are already defined and solved
plot_freq_and_angle(agent.model, agent2.model)

for i in range(3):
    plt.plot([row[i] for row in mpc_problem.error_save[:]])
    plt.yscale("log")   
    plt.grid(True)    
    plt.tight_layout()
    # Plot column 1 (second value of each entry) for the first 80 entries
    plt.show()