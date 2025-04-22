import time, os
import numpy as np
import time
import requests
from copy import deepcopy
import datetime
from andes.utils.paths import get_case, cases_root, list_cases
import andes as ad
import pyomo.environ as pyo
from pyomo.opt import SolverFactory
from colmena import (
    Context,
    Service,
    Role,
    Channel,
    Requirements,
    Metric,
    Persistent,
    Async,
    KPI,
    Data,
    Dependencies
)

#Service to deploy a one layer control

url = 'http://192.168.68.67:5000' + "/print_app"
andes_url = 'http://192.168.10.137:5000'

from pyomo.core.expr.visitor import identify_variables
from pyomo.environ import value, Constraint

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

    #we define the generator dynamics
    model.constraint_area1 = pyo.Constraint(
        model.generator_bus, 
        model.TimeDynamics, 
        rule=lambda model, i, t: model.delta_bus[i, t+1] == model.delta_bus[i, t] + self.dt*2*np.pi*(model.freq[t]-1))
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
    model.contraint_bus = pyo.Constraint(
        model.area_buses, 
        rule=lambda model, bus, t: 
        model.P_bus[bus, t] + model.Pg[self.bus2idgen[bus], t] + sum(model.P_line[bus, other_bus, t] for other_bus in model.area_bus) + model.P_demand[bus,t] == 0)


def setup_mpc(self, mpc_problem, dt = 0.5, T = 20, controllable_redual = False):
    area = self.area
    generators = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'idx', 'area':self.area}).json()['value']
    loads = requests.post(andes_url + '/area_variable_sync', json={'model':'PQ', 'var':'idx', 'area':self.area}).json()['value']
    areas = requests.get(andes_url + '/complete_variable_sync', params={'model':'Area', 'var':'idx'}).json()['value']
    buses = requests.post(andes_url + '/area_variable_sync', json={'model':'Bus', 'var':'idx', 'area':self.area}).json()['value']

    bus_area = requests.get(andes_url + '/complete_variable_sync', params={'model':'Bus', 'var':'area'}).json()['value']
    PQ_bus = requests.post(andes_url + '/area_variable_sync', json={'model':'PQ', 'var':'bus', 'area':self.area}).json()['value']
    PV_bus = requests.post(andes_url + '/area_variable_sync', json={'model':'PV', 'var':'bus', 'area':self.area}).json()['value']
    generator_bus = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'bus', 'area':self.area}).json()['value']
    other_areas = [i for i in areas if i != self.area]

    print(f"generators are {generators}")
    print(f"bus_area are {bus_area}")
    gen_location = {gen:generator_bus[i] for i, gen in enumerate(generators)}
    bus2idgen = {generator_bus[i]:gen for i, gen in enumerate(generators)}
    self.bus2idgen = bus2idgen

    if controllable_redual:
        PV_bus = PV_bus[2:]
    M_coi = 0
    D_coi = 0
    S_area = 0
    P_demand = 0
    S_base = []
    responseAndes = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'Sn', 'idx':generators})
    Sn_values = responseAndes.json()['value']
    responseAndes = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'Pe', 'idx':generators})
    Pe_values = responseAndes.json()['value']
    responseAndes = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'M', 'idx':generators})
    M_values = responseAndes.json()['value']
    responseAndes = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'D', 'idx':generators})
    D_values = responseAndes.json()['value']
    responseAndes = requests.get(andes_url + '/complete_variable_sync', params={'model':'PV', 'var':'p0'})
    p0_values = responseAndes.json()['value']

    for i, bus in enumerate(generator_bus):
        if bus in buses:
            S_area += Sn_values[i]
    for i, bus in enumerate(generator_bus):
        if bus in buses:
            Sn = Sn_values[i]
            p0 = Pe_values[i]
            M = M_values[i]
            D = D_values[i]
            M_coi = Sn*M
            D_coi = Sn*D
            P_demand += Sn*p0
            S_base.append(Sn)
    
    M_coi = Sn*M_coi/Sn
    D_coi = Sn*D_coi/Sn
    model = pyo.ConcreteModel()
    model.M = pyo.Param(initialize= M_coi)
    model.D = pyo.Param(initialize= D_coi)
    model.generators = pyo.Set(initialize = generators)
    model.loads = pyo.Set(initialize = loads)
    pe_base = {i:Pe_values for i,Pe in list(zip(model.generators, Pe_values))}
    model.Sn = pyo.Param(model.generators, initialize = pe_base)
    model.other_areas = pyo.Set(initialize = other_areas)
    model.areas = pyo.Set(initialize = areas)
    model.TimeHorizon = pyo.RangeSet(0, T)
    model.TimeDynamics = pyo.RangeSet(0, T-1)


    #model.delta_horizon = pyo.Param(model.other_areas, model.TimeHorizon, initialize = self.state_horizon_values)
    model.dual_vars = pyo.Param(model.areas, model.TimeHorizon, initialize = mpc_problem.dual_vars, mutable = True)

    #We define the variables
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
        return (pmin, pmax)
    
    model.delta = pyo.Var(model.TimeHorizon, bounds=(-50, 50))
    model.delta_areas = pyo.Var(model.other_areas, model.TimeHorizon, initialize = 0.0, bounds=(-50, 50))
    model.freq = pyo.Var(model.TimeHorizon, bounds = (0.85, 1.15))
    model.Pg = pyo.Var(model.generators, model.TimeHorizon, bounds=power_bounds)
    model.P = pyo.Var(model.TimeHorizon, initialize = 0.0)
    model.P_exchange = pyo.Var(model.TimeHorizon, initialize = 0.0)


    #we define the parameters
    b_areas = requests.get(andes_url + '/system_susceptance', params={'area':self.area}).json()
    b_areas = {int(k): v for k, v in b_areas.items()}
    model.Pd = pyo.Param(model.TimeHorizon, initialize = P_demand)
    model.b = pyo.Param(model.other_areas, initialize = b_areas)
    model.state_horizon_values = pyo.Param(model.areas, model.TimeHorizon, initialize = self.state_horizon_values, mutable=True)

    #We define the initial conditions 
    delta_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'delta', 'idx':generators}).json()['value']
    freq_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'omega', 'idx':generators}).json()['value']
    M_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'M', 'idx':generators}).json()['value']

    delta0 = np.dot(M_values, delta_values) / np.sum(M_values)
    freq0 = np.dot(M_values, freq_values) / np.sum(M_values)
    model.delta[0].value = delta0
    model.freq[0].value = freq0

    initial_area_values = {}
    for x_area in model.other_areas:
        delta_area = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'delta', 'area':x_area}).json()['value']
        M_area = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'M', 'area':x_area}).json()['value']
        initial_area_values[x_area] = (np.dot(M_area, delta_area) / np.sum(M_area))
    

    def initial_p(model, i):
        try:
            index = generators.index(i)
            Pe = Pe_values[index]
        except:
            generator_bus = gen_location[i]
            index = PV_bus.index(generator_bus)
            Pe = p0_values[index]
        return model.Pg[i,0] == Pe
    
    def initial_delta_areas(model, i):
        return (initial_area_values[i], model.delta_areas[i, 0], initial_area_values[i])
    
    model.constraint_initial_conditions = pyo.Constraint(expr = model.delta[0] == delta0)
    model.constraint_initial_conditions2 = pyo.Constraint(expr = model.freq[0] == freq0)
    model.constraint_initial_conditions3 = pyo.Constraint(model.other_areas, rule = initial_delta_areas)
    model.constraint_initial_conditions4 = pyo.Constraint(model.generators, rule= initial_p)

    #We define the dynamics of the system
    self.ramp_up = 0.1
    model.constrains_dynamics1 = pyo.Constraint(model.TimeDynamics, rule=lambda model, t: model.delta[t+1] == model.delta[t] + dt*2*np.pi*(model.freq[t]-1))
    model.constrains_dynamics2 = pyo.Constraint(model.TimeDynamics, rule=lambda model, t: model.M*(model.freq[t+1] - model.freq[t])/dt == (-model.D(model.freq[t]-1) + model.P[t] - model.Pd[t] - model.P_exchange[t]))
    model.constrains_dynamics3 = pyo.Constraint(model.generators, model.TimeDynamics, rule=lambda model, i, t: (model.Pg[i, t+1] - model.Pg[i, t]) <= self.dt*self.ramp_up)
    model.constrains_dynamics4 = pyo.Constraint(model.generators, model.TimeDynamics, rule=lambda model, i, t: -self.ramp_up*self.dt <= (model.Pg[i, t+1] - model.Pg[i, t]))

    #We define the Inter Area constraints:
    def power_inter_area(model, t):
        return model.P_exchange[t] == sum(model.b[area] *(model.delta[t] - model.delta_areas[area, t]) for area in model.other_areas)
    model.constrains_area = pyo.Constraint(model.TimeHorizon, rule= power_inter_area)
    #We define the power balance constraint
    def power_balance_rule(model, t):
        return model.P[t] == sum(model.Pg[gen, t] for gen in model.generators)
    model.constraints_balance = pyo.Constraint(model.TimeHorizon, rule=power_balance_rule)


    #We define the cost function
    n = len(generators)
    cost = np.ones(n) + np.random.rand(n)
    cost_dict = {generator:cost[i] for i,generator in enumerate(generators)}
    model.c = pyo.Param(model.generators, initialize=cost_dict)
    def p_cost(model):
        return sum(model.c[i] * (model.Pg[i,t]) for i in model.generators for t in model.TimeHorizon)
    def p_exchange_cost(model):
        return sum((model.P_exchange[t] - model.P_exchange[0])**2 for t in model.TimeHorizon)
    def freq_cost(model):
        return sum((model.freq[t]-1)**2 for t in model.TimeHorizon)
    def lagrangian_term(model):
        sign = 1 if self.area == 1 else -1
        a = sum( sum(mpc_problem.dual_vars[i, t]*sign*(model.delta_areas[i,t] - model.state_horizon_values[i,t]) for i in model.other_areas) for t in model.TimeHorizon)
        b = 0
        for i, area in enumerate(model.areas):
            other_agent = mpc_problem.agents[i]
            b += sum(mpc_problem.dual_vars[area, t]*sign*(model.delta[t] - other_agent.state_horizon_values[area,t])  for t in model.TimeHorizon)
        return a + b
    def penalty_term(model):
        sign = 1 if self.area ==1 else -1
        a = sum( 10*sum((model.delta_areas[i,t] - model.state_horizon_values[i,t])**2 for i in model.other_areas) for t in model.TimeHorizon)
        b = 100*sum((model.delta[t] - model.state_horizon_values[self.area,t])**2  for t in model.TimeHorizon)
        return a+b
        
    model.cost = pyo.Objective(rule=lambda model: freq_cost(model) + lagrangian_term(model) + penalty_term(model), sense=pyo.minimize)
    return model

class mpc_agent:
    def __init__(self, agent_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.n_areas = 2
        self.alpha = 0.8
        self.dt = 0.2
        self.tol = 1e-5
        self.andes_url = andes_url 
        self.agent_id = agent_name
        self.area = int(self.agent_id[-1])
        responseAndes = requests.get(self.andes_url + '/assign_device', params = {'agent': self.agent_id})
        self.device_dict = responseAndes.json()
        self.t_start = time.time()
        self.T = 3                           #number of timesteps when performing the MPC
        
        self.areas = requests.get(andes_url + '/complete_variable_sync', params={'model':'Area', 'var':'idx'}).json()['value']
        self.other_areas = [i for i in self.areas if i != self.area]
        self.first = True
        self.state_horizon_values = {}
        self.state_saved_values = {}
        for area in self.areas:
            for t in range(self.T +1):
                self.state_horizon_values[area, t] = 0

    
    def first_warm_start(self):
        generators = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'idx', 'area':self.area}).json()['value']
        delta_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'delta', 'idx':generators}).json()['value']
        M_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'M', 'idx':generators}).json()['value']
        delta0 = np.dot(M_values, delta_values) / np.sum(M_values)

        responseAndes = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'Pe', 'area':self.area})
        Pe_values = responseAndes.json()['value']

        areas = requests.get(andes_url + '/complete_variable_sync', params={'model':'Area', 'var':'idx'}).json()['value']
        other_areas = [i for i in areas if i != self.area]

        for t in range(self.T+1):
            self.state_horizon_values[self.area, t] = delta0
            self.state_saved_values['f', t] = 1.0
            self.state_saved_values['P', t] = np.sum(Pe_values)
            self.state_saved_values['P_exchange', t] = 0.0
            for i, gen in enumerate(generators):
                self.state_saved_values['Pg', gen, t] = Pe_values[i]
            for area in other_areas:
                self.state_saved_values['delta_areas', t] = 0.0
        return 1

    def warm_start(self):
        for t in self.model.TimeHorizon:
            if t+1 > self.T:
                continue 
            self.model.delta[t].value = self.state_horizon_values[self.area, t+1]
            self.model.freq[t].value = max(self.state_saved_values['f', t+1], 0.9)
            self.model.P[t].value =  self.state_saved_values['P', t+1]
            self.model.P_exchange[t].value =  self.state_saved_values['P_exchange', t+1]
            for gen in self.model.generators:
                self.model.Pg[gen, t].value = self.state_saved_values['Pg', gen, t+1]
            for area in self.model.other_areas:
                self.model.delta_areas[area, t] = self.state_saved_values['delta_areas', t+1]
        return 1
    
    def save_warm_start(self):
        for t in self.model.TimeHorizon:
            self.state_horizon_values[self.area, t] = self.model.delta[t].value
            self.state_saved_values['f', t] = self.model.freq[t].value
            self.state_saved_values['P', t] = self.model.P[t].value
            self.state_saved_values['P_exchange', t] = self.model.P_exchange[t].value
            for gen in self.model.generators:
                self.state_saved_values['Pg', gen, t] = self.model.Pg[gen, t].value 
            for area in self.model.other_areas:
                self.state_saved_values['delta_areas', t] = self.model.delta_areas[area, t]
        return 1
    
    def setup_mpc(self, mpc_problem):
        self.model = setup_mpc(self, mpc_problem, self.dt, self.T)
        return self.model

class mpc:
    def __init__(self, agents, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.areas = 2
        self.agents = agents
        self.alpha = 1
        self.T = agents[0].T
        self.dual_vars = {}
        self.areas = [int(agent.area) for agent in self.agents]
        for i in self.areas:
            for t in range(self.T+1):
                self.dual_vars[i, t] = 0.0

def solve_mpc():
    agent_1 = mpc_agent("area_1")
    agent_2 = mpc_agent("area_2")
    agents = [agent_1, agent_2]
    mpc_problem = mpc(agents)
    mpc_problem.alpha = 10
    other = {"area_1": agent_2, "area_2": agent_1}
    for i in range(100):
        responseAndes = requests.get(agent_1.andes_url + '/sync_time')
        time_start = int(responseAndes.json()['time'])
        for agent in agents:
            other_agent = other[agent.agent_id]

            if agent.first:
                agent.first_warm_start()
                other_agent.first_warm_start()
                state_value_other = other_agent.state_horizon_values
                model = agent.setup_mpc(mpc_problem)
            else:
                model = agent.model
                #model = agent.setup_mpc(mpc_problem)
                for key, val in agent.state_horizon_values.items():
                    model.state_horizon_values[key] = val
                for key, val in mpc_problem.dual_vars.items():
                    if key[0] != agent.area:
                        model.dual_vars[key] = val



            agent.warm_start()
            solver = pyo.SolverFactory('ipopt')
            result = solver.solve(model, tee=True)
            agent.save_warm_start()
            #we update the dual variables

            agent.first = False
            #We get the current state_horizon and updated it with the solution for the agent's area
            for t in model.TimeHorizon:
                #agent.state_horizon_values[agent.area, t] = model.delta[t].value
                for other_agent in agents:
                    other_area = other_agent.area
                    if other_area == agent.area:
                        continue
                    #agent.state_horizon_values[other_area, t] = model.delta_areas[other_area, t].value
                    other_agent.state_horizon_values[agent.area, t] = model.delta[t].value
                    other_agent.state_horizon_values[other_area, t] = model.delta_areas[other_area, t].value

        mpc_problem.delta_dual_vars = {k: 0 for k in mpc_problem.dual_vars}
        for t in range(mpc_problem.T+1):
            for area in model.areas:
                mpc_problem.delta_dual_vars[area, t] = mpc_problem.alpha*(mpc_problem.dual_vars[area, t] - agent.state_horizon_values[area, t])
                mpc_problem.dual_vars[area, t] += mpc_problem.delta_dual_vars[area, t]

        error = max(abs(v) for v in mpc_problem.dual_vars.values())
        andes_role_changes = []
        converged = False
        print("error is ", error)
        print(f"delta_dual_vars are {mpc_problem.delta_dual_vars[1,0]}")
        if np.abs(error) < agent.tol:
            print(f"dist MPC converged")
            converged = True

        agent.first = False
        responseAndes = requests.get(agent_1.andes_url + '/sync_time')
        time_start = int(responseAndes.json()['time'])
        if converged:
            responseAndes = requests.get(agent.andes_url + '/sync_time')
            time_start_bis = responseAndes.json()['time']
            for x_agent in agents:
                for gen_id in x_agent.model.generators:
                    id_number = gen_id[-1]
                    if gen_id[-2] != '_':
                        id_number = gen_id[-2:]
                    roleChangeDict = {}
                    roleChangeDict['model'] = 'TGOV1N'
                    roleChangeDict['idx'] = 'TGOV1_' + id_number
                    roleChangeDict['var'] = 'pref0'
                    roleChangeDict['value'] = x_agent.model.Pg[gen_id, 0].value
                    roleChangeDict['agent'] = agent.agent_id
                    responseAndes = requests.post(x_agent.andes_url + '/device_role_change', json = roleChangeDict)
                    responseAndes = requests.get(agent.andes_url + '/sync_time')
                    time_now = responseAndes.json()['time']
                    #print(f"simulation time is {time_now}")
                    for t in range(1, x_agent.T+1):
                        roleChangeDict['value'] = x_agent.model.Pg[gen_id, t].value
                        roleChangeDict['t'] = time_start + x_agent.dt*t
                        #print(f't is {roleChangeDict['t']}, actual time is {time.time()-start_time}')
                        a = deepcopy(roleChangeDict)
                        andes_role_changes.append(a)
                        responseAndes = requests.get(x_agent.andes_url + '/add_set_point', params = roleChangeDict)
            return converged, andes_role_changes, agents
        print(f"error is {error}")
    return converged, andes_role_changes, agents

andes_url = 'http://192.168.10.137:5000'
responseLoad = requests.post(andes_url + '/start_simulation')
time.sleep(1)
converged, andes_role_changes, agents = solve_mpc()
print(f"converged is {converged}")

model = agents[0].model
agent = agents[0]
for t in model.TimeHorizon:
    print(f"delta[{t}] = {model.delta[t].value}")
    print(f"delta other[{t}] = {agent.state_horizon_values[1,t]}")

model = agents[1].model
agent = agents[1]
for t in model.TimeHorizon:
    print(f"delta[{t}] = {model.delta[t].value}")
    print(f"delta other[{t}] = {agent.state_horizon_values[2,t]}")