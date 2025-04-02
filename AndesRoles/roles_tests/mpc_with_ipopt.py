import time, os
import numpy as np
import json
import time
import traceback
import queue
import requests 
import logging
import pyomo as pyo
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
andes_url = 'http://192.168.68.67:5000'
def setup_mpc(system, area, dt = 0.5, T = 20):
    generators = requests.get(andes_url + '/complete_variable_sync', params={'model':'GENROU', 'var':'idx'}).json()['value']
    loads = requests.get(andes_url + '/complete_variable_sync', params={'model':'PQ', 'var':'idx'}).json()['value']
    areas = requests.get(andes_url + '/complete_variable_sync', params={'model':'Area', 'var':'idx'}).json()['value']
    buses = requests.get(andes_url + '/complete_variable_sync', params={'model':'Area', 'var':'idx'}).json()['value']

    bus_area = requests.get(andes_url + '/complete_variable_sync', params={'model':'Bus', 'var':'area'}).json()['value']
    PQ_bus = requests.get(andes_url + '/complete_variable_sync', params={'model':'PQ', 'var':'bus'}).json()['value']
    PV_bus = requests.get(andes_url + '/complete_variable_sync', params={'model':'PV', 'var':'bus'}).json()['value']
    generator_bus = requests.get(andes_url + '/complete_variable_sync', params={'model':'GENROU', 'var':'bus'}).json()['value']
    other_areas = [i for i in areas if i !=area]

    buses = [bus for i, bus in enumerate(buses) if bus_area[i] == 1]
    loads = [loads[i] for i, bus in enumerate(PQ_bus) if bus in buses]
    generators = [generators[i] for i, bus in enumerate(PV_bus) if bus in buses]

    M_coi = 0
    D_coi = 0
    S_area = 0
    P_demand = 0
    S_base = []
    Sn_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'GENROU', 'var':'Sn'}).json()['value']
    Pe_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'GENROU', 'var':'Pe'}).json()['value']
    M_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'GENROU', 'var':'M'}).json()['value']
    D_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'GENROU', 'var':'D'}).json()['value']
    p0_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'PV', 'var':'p0'}).json()['value']
    for i, bus in enumerate(generator_bus):
        if bus in buses:
            S_area += Sn_values[i]
    for i, bus in enumerate(generator_bus):
        if bus in buses:
            Sn = Sn_values[i]
            p0 = Pe_values[i]
            M = M_values[i]
            D = D_values[i]
            M_coi = Sn*M/S_area
            M_coi = Sn*D/S_area
            P_demand += Sn*p0
            S_base.append(Sn)

    model = pyo.ConcreteModel()
    model.M = pyo.Param(initialize= M_coi)
    model.D = pyo.Param(initialize= D_coi)
    model.generators = pyo.Set(initialize =generators)
    model.loads = pyo.Set(initialize = loads)
    S_base = {i:Sn for i,Sn in list(zip(model.generators, S_base))}
    model.Sn = pyo.Param(model.generators, initialize= S_base)
    model.other_areas = pyo.Set(initialize = other_areas)
    model.TimeHorizon = pyo.RangeSet(0, T)
    model.TimeDynamics = pyo.RangeSet(0, T-1)

    #We define the variables
    slack_bus = requests.get(andes_url + '/complete_variable_sync', params={'model':'Slack', 'var':'bus'}).json()['value']
    pmax_slack_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'Slack', 'var':'pmax'}).json()['value']
    pmin_slack_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'Slack', 'var':'pmin'}).json()['value']
    Sn_slack_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'Slack', 'var':'Sn'}).json()['value']

    pmax_pv_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'PV', 'var':'pmax'}).json()['value']
    pmin_pv_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'PV', 'var':'pmin'}).json()['value']
    def power_bounds(model, gen, t):
        if gen in PV_bus:
            index = PV_bus.index(gen)
            Sn = Sn_values[index]     
            pmax = (pmax_pv_values[index])*Sn
            pmin = (pmin_pv_values[index])*Sn
        elif gen in slack_bus:
            Sn = Sn_slack_values[index]     
            pmax = (pmax_slack_values[index])*Sn
            pmin = (pmin_slack_values[index])*Sn
        else:
            pmax = 100
            pmin = 0
        return (pmin, pmax)
    
    model.delta = pyo.Var(model.TimeHorizon)
    model.delta_areas = pyo.Var(model.TimeHorizon, model.other_areas)
    model.freq = pyo.Var(model.TimeHorizon)
    model.Pg = pyo.Var(model.generators, model.TimeHorizon, bounds=power_bounds)
    model.P = pyo.Var(model.TimeHorizon)
    model.P_exchange = pyo.Var(model.TimeHorizon)

    b_areas = np.random.rand(system.Area.n-1)*0.10
    b_areas = {area:b_areas[i] for i, area in enumerate(model.other_areas)}


    #we define the parameters
    model.Pd = pyo.Param(model.TimeHorizon, initialize = P_demand)
    model.b = pyo.Param(model.other_areas, initialize = b_areas)

    #We define the initial conditions 
    gen_delta0 = requests.get(andes_url + '/complete_variable_sync', params={'model':'GENROU', 'var':'delta0'}).json()['value']
    gen_omega = requests.get(andes_url + '/complete_variable_sync', params={'model':'GENROU', 'var':'omega'}).json()['value']
    delta0 = 0
    freq0 = 0
    for i, bus in enumerate(generator_bus):
        if bus in buses:
            delta0 += (gen_delta0[i])
    for i, bus in enumerate(generator_bus):
        if bus in buses:
            freq0 += (gen_omega[i]-1)
    
    def initial_p(model, i):
        try:
            index = generator_bus.index(i)
            Sn = Sn_values[index]
            Pe = Pe_values[index]*Sn
        except:
            index = PV_bus.index(i)
            Sn = Sn_values[index]
            Pe = p0_values[index]*Sn
        return model.Pg[i,0] == Pe
    
    model.constraint_initial_conditions = pyo.Constraint(expr = model.delta[0] == delta0)
    model.constraint_initial_conditions2 = pyo.Constraint(expr = model.freq[0] == freq0)
    model.constraint_initial_conditions3 = pyo.Constraint(model.generators, rule= initial_p)

    #We define the dynamics of the system
    model.constrains_dynamics1 = pyo.Constraint(model.TimeDynamics, rule=lambda model, t: model.delta[t+1] == model.delta[t] + dt*2*np.pi*model.freq[t])
    model.constrains_dynamics2 = pyo.Constraint(model.TimeDynamics, rule=lambda model, t: model.M*(model.freq[t+1] - model.freq[t])/dt == (-model.freq[t] + model.P[t] - model.Pd[t] + (model.P_exchange[t])/(2*np.pi)))
    model.constrains_dynamics3 = pyo.Constraint(model.generators, model.TimeDynamics, rule=lambda model, i, t: (model.Pg[i, t+1] - model.Pg[i, t]) <= 10)
    model.constrains_dynamics4 = pyo.Constraint(model.generators, model.TimeDynamics, rule=lambda model, i, t: -10 <= (model.Pg[i, t+1] - model.Pg[i, t]))

    #We define the Inter Area constraints:
    model.constrains_freq = pyo.Constraint(model.TimeDynamics, rule=lambda model, t:(model.freq[t]) >= -0.03)
    def power_inter_area(model, t):
        return model.P_exchange[t] == sum(model.b[area] *(model.delta[t] - model.delta_areas[t, area]) for area in model.other_areas)
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
        return sum(model.c[i] * (model.Pg[i,t])**2 for i in model.generators for t in model.TimeHorizon)
    def p_exchange_cost(model):
        return sum((model.P_exchange[t] - model.P_exchange[0])**2 for t in model.TimeHorizon)
    def freq_cost(model):
        return sum(100*model.freq[t]**2 for t in model.TimeHorizon)
    model.cost = pyo.Objective(rule=lambda model: p_cost(model) + p_exchange_cost(model) + freq_cost(model), sense=pyo.minimize)
    solver = pyo.SolverFactory('ipopt')
    return model, solver

class GridAreas(Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def locate(self, device):
        agent_id = os.getenv('AGENT_ID')
        if agent_id in ['area1', 'device1', 'device2']:
            location = {'id' : 'area1'}
        if agent_id in ['area2', 'device3', 'device4']:
            location = {'id' : 'area2'}
        print(json.dumps(location))

class Device(Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def locate(self, device):
        agent_id = os.getenv('AGENT_ID')
        id = {'id':agent_id}
        print(json.dumps(id))

class FirstLayer(Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def locate(self, device):
        agent_id = os.getenv('AGENT_ID')
        if agent_id in ['area1', 'area2']:
            location = {'id' : 'firstlayer'}
        print(json.dumps(location))

class AgentControl(Service):
    @Context(class_ref= GridAreas, name = 'grid_area')
    @Context(class_ref= FirstLayer, name = 'first_layer')
    @Data(name = 'state_horizon', scope = 'first_layer/id = .')
    @Data(name = 'device_data', scope = 'grid_area/id = .')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class LayerOneMPC(Role):
        @Context(class_ref= GridAreas, name="grid_area")
        @Data(name = 'state_horizon', scope = 'first_layer/id = .')
        @Data(name = 'device_data', scope = 'grid_area/id = .')
        @Requirements('Area')
        @Dependencies('requests')
        @Dependencies('pyomo')
        @Metric('deviation')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.areas = 2
            self.states = np.ones(2)
            self.value = np.random.rand(1)
            self.agent_id = os.getenv('AGENT_ID')
            responseAndes = self.get_system_data(self.andes_url + '/get_system_data')
            self.system_data = responseAndes.json()
        
        def behavior(self):
            device_data = json.loads(self.device_data.get().decode('utf-8'))
            p_mean = 0
            a_mean = 0
            n = len(device_data.keys())
            for key, val in device_data.item():
                p_mean += val['P']/n
                a_mean += val['a']/n
            
            area_state = [p_mean, a_mean]
            area_state_horizon = np.tile(area_state, (self.T, 1))
            
            state_horizon = json.loads(self.device_data.get().decode('utf-8'))
            state_horizon[self.agent_id] = area_state_horizon
            self.state_horizon.publish(state_horizon)
            print(state_horizon)

            time.sleep(0.2)
            return 1

    class DeviationMonitoring(Role):
        @Context(class_ref= GridAreas, name="grid_area")
        @Data(name = 'state_horizon', scope = 'first_layer/id = .')
        @Data(name = 'device_data', scope = 'grid_area/id = .')
        @Requirements('Area')
        @Dependencies('requests')
        @Metric('deviation')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            n_areas = 2
            self.agent_id = os.getenv('AGENT_ID')

        @Persistent()
        def behavior(self):
            device_data = json.loads(self.device_data.get().decode('utf-8'))
            p_mean = 0
            a_mean = 0
            n = len(device_data.keys())

            for key, val in device_data.item():
                p_mean += val['P']/n
                a_mean += val['a']/n
            
            state_horizon = json.loads(self.state_horizon.get().decode('utf-8'))
            area_state_horizon = getattr(state_horizon, self.agent_id, None) 
            
            if area_state_horizon is None:
                return 1
            T = len(area_state_horizon) 

            area_state = [p_mean, a_mean]
            area_state_constant = np.tile(area_state, (self.T, 1))

            deviation = np.norm(area_state_horizon - area_state_constant)
            self.deviation.publish(deviation)
            time.sleep(0.1)
            return 1

    class MonitoringRole(Role):
        @Context(class_ref= GridAreas, name="grid_area")
        @Data(name = 'device_data', scope = 'grid_area/id = .')
        @Requirements('Device')
        @Dependencies("requests")
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            n_areas = 2
            self.states = np.ones(n_areas)
            self.value = np.random.rand(1)
            self.agent_id = os.getenv('AGENT_ID')

        @Persistent()
        def behavior(self):
            data = json.loads(self.device_data.get().decode('utf-8'))
            p_value = 1 + np.random.rand()
            a_value = 1 + np.random.rand()
            data[self.agent_id] ={'P':p_value, 'a':a_value}
            self.device_data.publish(data)
            print(data)
            time.sleep(0.1)
            return 1
