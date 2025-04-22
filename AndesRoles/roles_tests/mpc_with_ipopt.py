import time, os
import numpy as np
import json
import time
import traceback
import queue
import requests 
import pyomo.environ as pyo
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

from pyomo.core.expr.visitor import identify_variables
from pyomo.environ import value, Constraint

def check_constraint_violations(model, tolerance=1e-4):
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


def setup_mpc(self, area, dt = 0.5, T = 20, controllable_redual = False):
    generators = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'idx', 'area':self.area}).json()['value']
    loads = requests.post(andes_url + '/area_variable_sync', json={'model':'PQ', 'var':'idx', 'area':self.area}).json()['value']
    areas = requests.get(andes_url + '/complete_variable_sync', params={'model':'Area', 'var':'idx'}).json()['value']
    buses = requests.post(andes_url + '/area_variable_sync', json={'model':'Bus', 'var':'idx', 'area':self.area}).json()['value']

    bus_area = requests.get(andes_url + '/complete_variable_sync', params={'model':'Bus', 'var':'area'}).json()['value']
    PQ_bus = requests.post(andes_url + '/area_variable_sync', json={'model':'PQ', 'var':'bus', 'area':self.area}).json()['value']
    PV_bus = requests.post(andes_url + '/area_variable_sync', json={'model':'PV', 'var':'bus', 'area':self.area}).json()['value']
    generator_bus = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'bus', 'area':self.area}).json()['value']
    other_areas = [i for i in areas if i != area]

    print(f"generators are {generators}")
    print(f"generator_bus are {generator_bus}")
    print(f"buses are {buses}")
    print(f"bus_area are {bus_area}")
    gen_location = {gen:generator_bus[i] for i, gen in enumerate(generators)}

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

    model = pyo.ConcreteModel()
    model.M = pyo.Param(initialize= M_coi)
    model.D = pyo.Param(initialize= D_coi)
    model.generators = pyo.Set(initialize = generators)
    model.loads = pyo.Set(initialize = loads)
    S_base = {i:Sn for i,Sn in list(zip(model.generators, S_base))}
    model.Sn = pyo.Param(model.generators, initialize= S_base)
    model.other_areas = pyo.Set(initialize = other_areas)
    model.TimeHorizon = pyo.RangeSet(0, T)
    model.TimeDynamics = pyo.RangeSet(0, T-1)
    model.dual_lambda = pyo.Param(model.other_areas, model.TimeHorizon, initialize = self.dual_vars)

    #We define the variables
    slack_bus = requests.get(andes_url + '/complete_variable_sync', params={'model':'Slack', 'var':'bus', 'area':self.area}).json()['value']
    pmax_slack_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'Slack', 'var':'pmax', 'area':self.area}).json()['value']
    pmin_slack_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'Slack', 'var':'pmin', 'area':self.area}).json()['value']
    Sn_slack_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'Slack', 'var':'Sn', 'area':self.area}).json()['value']

    pmax_pv_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'PV', 'var':'pmax'}).json()['value']
    pmin_pv_values = requests.get(andes_url + '/complete_variable_sync', params={'model':'PV', 'var':'pmin'}).json()['value']

    print("Sn_values ", Sn_values)
    print(f"PV_bus {PV_bus}")

    def power_bounds(model, gen, t):
        gen_bus = gen_location[gen]
        if gen_bus in PV_bus:
            index = PV_bus.index(gen_bus) 
            Sn = Sn_values[index]     
            pmax = (pmax_pv_values[index])*Sn
            pmin = (pmin_pv_values[index])*Sn
        elif gen_bus in slack_bus:
            index = slack_bus.index(gen_bus)
            Sn = Sn_slack_values[index]     
            pmax = (pmax_slack_values[index])*Sn
            pmin = (pmin_slack_values[index])*Sn
        else:
            pmax = 8000
            pmin = 0
        return (pmin, pmax)
    
    model.delta = pyo.Var(model.TimeHorizon, bounds=(-3, 3))
    model.delta_areas = pyo.Var(model.other_areas, model.TimeHorizon, initialize = self.delta_mean, bounds=(-3, 3))
    model.freq = pyo.Var(model.TimeHorizon, bounds = (0.9, 1.1))
    model.Pg = pyo.Var(model.generators, model.TimeHorizon, bounds=power_bounds)
    model.P = pyo.Var(model.TimeHorizon, initialize = 0.0)
    model.P_exchange = pyo.Var(model.TimeHorizon, initialize = 0.0)


    #we define the parameters
    b_areas = requests.get(andes_url + '/system_susceptance', params={'area':self.area}).json()
    b_areas = {int(k): v for k, v in b_areas.items()}
    model.Pd = pyo.Param(model.TimeHorizon, initialize = P_demand)
    model.b = pyo.Param(model.other_areas, initialize = b_areas)

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
    
    print("delta_area ", delta_area)
    print("M_area ", M_area)
    print("initial_area_values ", initial_area_values)
    def initial_p(model, i):
        try:
            index = generators.index(i)
            Sn = Sn_values[index]
            Pe = Pe_values[index]*Sn
        except:
            generator_bus = gen_location[i]
            index = PV_bus.index(generator_bus)
            Sn = Sn_values[index]
            Pe = p0_values[index]*Sn
        return model.Pg[i,0] == Pe
    
    def initial_delta_areas(model, i):
        return (initial_area_values[i], model.delta_areas[i, 0], initial_area_values[i])
    
    model.constraint_initial_conditions = pyo.Constraint(expr = model.delta[0] == delta0)
    model.constraint_initial_conditions2 = pyo.Constraint(expr = model.freq[0] == freq0)
    model.constraint_initial_conditions3 = pyo.Constraint(model.other_areas, rule = initial_delta_areas)
    model.constraint_initial_conditions4 = pyo.Constraint(model.generators, rule= initial_p)

    #We define the dynamics of the system
    model.constrains_dynamics1 = pyo.Constraint(model.TimeDynamics, rule=lambda model, t: model.delta[t+1] == model.delta[t] + dt*2*np.pi*(model.freq[t]-1))
    model.constrains_dynamics2 = pyo.Constraint(model.TimeDynamics, rule=lambda model, t: model.M*(model.freq[t+1] - model.freq[t])/dt == (-model.D(model.freq[t]-1) + model.P[t] - model.Pd[t] + model.P_exchange[t]))
    model.constrains_dynamics3 = pyo.Constraint(model.generators, model.TimeDynamics, rule=lambda model, i, t: (model.Pg[i, t+1] - model.Pg[i, t]) <= 100*self.dt)
    model.constrains_dynamics4 = pyo.Constraint(model.generators, model.TimeDynamics, rule=lambda model, i, t: -100*self.dt <= (model.Pg[i, t+1] - model.Pg[i, t]))

    #We define the Inter Area constraints:
    model.constrains_freq = pyo.Constraint(model.TimeDynamics, rule=lambda model, t:(model.freq[t]) >= -0.03)
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
        return sum(100*(model.freq[t]-1)**2 for t in model.TimeHorizon)
    def lagrangian_term(model):
        return sum( sum(model.dual_lambda[i, t]*(model.delta_areas[i,t] - self.state_horizon_values[i,t]) for i in model.other_areas) for t in model.TimeHorizon)
    def penalty_term(model):
        return sum( sum((model.delta_areas[i,t] - self.state_horizon_values[i,t])**2 for i in model.other_areas) for t in model.TimeHorizon)
        
        
    model.cost = pyo.Objective(rule=lambda model: freq_cost(model) + lagrangian_term(model) + penalty_term(model), sense=pyo.minimize)
    return model


class FirstLayer(Context):
    @Dependencies(*["pyomo", "requests"])
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def locate(self, device):
        agent_id = os.getenv('AGENT_ID')
        if agent_id in ['area_a', 'area_b']:
            location = {'id' : 'firstlayer'}
        else:
            location = {'id': 'secondlayer'}
        print(json.dumps(location))

class DistributedMPC(Service):
    #@Context(class_ref= GridAreas, name = 'grid_area')
    @Context(class_ref= FirstLayer, name = 'first_layer')
    @Data(name = 'state_horizon', scope = 'first_layer/id = .')
    #@Data(name = 'device_data', scope = 'grid_area/id = .')
    @Metric('error')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class LayerOne(Role):
        @Context(class_ref= FirstLayer, name = 'first_layer')
        @Data(name = 'state_horizon', scope = 'first_layer/id = .')
        @Dependencies(*["pyomo", "requests"])
        @KPI("distributedmpc/error[1s] < 0.01")
        @Metric('error')
        @Requirements('AREA')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.n_areas = 2
            self.alpha = 0.8
            self.dt = 0.1
            self.tol = 1e-3
            self.andes_url = andes_url 
            self.agent_id = os.getenv('AGENT_ID', 'area_1')
            self.area = self.agent_id[-1]
            responseAndes = requests.get(self.andes_url + '/assign_device', params = {'agent': self.agent_id})
            self.device_dict = responseAndes.json()
            self.t_start = time.time()
            self.T = 20                            #number of timesteps when performing the MPC
            
            areas = requests.get(andes_url + '/complete_variable_sync', params={'model':'Area', 'var':'idx'}).json()['value']
            self.other_areas = [i for i in areas if i != self.area]
            self.first = True
            self.state_horizon_values = None
            self.dual_vars = {}
            self.state_saved_values = {}
            for i in self.other_areas:
                for t in range(self.T+1):
                    self.dual_vars[i, t] = 0.0

        def first_warm_start(self, model):
            responseAndes = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'Pe', 'area':self.area})
            Pe_values = responseAndes.json()['value']
            responseAndes = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'Sn', 'area':self.area})
            Sn_values = responseAndes.json()['value']

            for t in model.TimeHorizon:
                self.state_horizon_values[self.area, t] = 0.0
                self.state_saved_values['f', t] = 1.0
                self.state_saved_values['P', t] = np.dot(Pe_values,Sn_values)
                self.state_saved_values['P_exchange', t] = 0.0

                for i, gen in enumerate(model.generators):
                    self.state_saved_values['Pg', gen, t] = Pe_values[i]*Sn_values[i] 
                for area in model.other_areas:
                    self.state_saved_values['delta_areas', t] = 0.0

            return 1

        def warm_start(self, model):
            for t in model.TimeHorizon:
                if t+1 > self.T:
                    continue 
                model.delta[t].value = self.state_horizon_values[self.area, t+1]
                model.freq[t].value = self.state_saved_values['f', t+1]
                model.P[t].value =  self.state_saved_values['P', t+1]
                model.P_exchange[t].value =  self.state_saved_values['P_exchange', t+1]

                for gen in model.generators:
                    model.Pg[gen, t].value = self.state_saved_values['Pg', gen, t+1]
                for area in model.other_areas:
                    model.delta_areas[area, t] = self.state_saved_values['delta_areas', t+1]
            return 1
        
        def save_warm_start(self, model):
            for t in model.TimeHorizon:
                self.state_horizon_values[self.area, t] = model.delta[t].value
                self.state_saved_values['f', t] = model.freq[t].value
                self.state_saved_values['P', t] = model.P[t].value
                self.state_saved_values['P_exchange', t] = model.P_exchange[t].value

                for gen in model.generators:
                    self.state_saved_values['Pg', gen, t] = model.Pg[gen, t].value 
                for area in model.other_areas:
                    self.state_saved_values['delta_areas', t] = model.delta_areas[area, t]

            return 1

        def setup_mpc(self):
            return setup_mpc(self, self.area, self.dt, self.T)
            
        @Persistent()
        def behavior(self):
            self.p_mean = 1
            self.delta_mean = 0

            #We initialize/read the @Data decorators 
            if self.first:
                device_data = {}
                self.state_horizon_values = {}
                for t in range(self.T + 1):
                    for i in self.other_areas:
                        self.state_horizon_values[i, t] = 0
            else:
                state_horizon_values = json.loads(self.device_data.get().decode('utf-8'))
                _ = 0


            #We setup the single area MPC as an optimzation problem and solve it
            model = self.setup_mpc()
            if self.first:
                self.first_warm_start(model)
                print("hi1")
            self.warm_start(model)
            solver = pyo.SolverFactory('ipopt')
            print("hi2")
            result = solver.solve(model, tee=True)
            self.save_warm_start(model)
            check_constraint_violations(model)

            #we update the dual variables
            delta_dual_vars = {k: 0 for k in self.dual_vars}
            for t in range(self.T+1):
                for area in model.other_areas:
                    delta_dual_vars[area, t] = self.alpha*(model.delta_areas[area, t].value - self.state_horizon_values[area, t])
                    self.dual_vars[area, t] += delta_dual_vars[area, t]

            #We get the current state_horizon and updated it with the solution for the agent's area
            self.state_horizon_values = json.loads(self.device_data.get().decode('utf-8'))
            for t in model.TimeHorizon:
                self.state_horizon_values[self.area, t] = model.delta[t].value
            self.state_horizon.publish(self.state_horizon_values)
        
            error = max(delta_dual_vars.values())
            self.error.publish(error)

            if error < self.tol:
                roleChangeDict = {'model' :'GENROU', 'var':'pref0'}
                for gen in model.generators:
                    roleChangeDict = self.device_dict
                    roleChangeDict['value'] = model.Pg[gen, 0].value 
                    responseAndes = requests.post(self.andes_url + '/device_role_change', json = roleChangeDict)
            print(self.dual_vars)
            self.first = False
            time.sleep(3)
            return 1

    """class MonitoringRole(Role):
        #@Context(class_ref= GridAreas, name ="grid_area")
        #@Data(name = 'device_data', scope = 'grid_area/id = .')
        @Requirements('DEVICE')
        @Dependencies("requests")
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.n_areas = 2
            self.andes_url = andes_url 
            self.agent_id = os.getenv('AGENT_ID', 'agent_a')
            responseAndes = requests.get(self.andes_url + '/assign_device', params = {'agent': self.agent_id})
            self.device_dict = responseAndes.json()
            self.t_start = time.time()
            self.first = True
            self.param_to_monitor = ['a', 'v', 'Pe']


        @Persistent()
        def behavior(self):
            #We initalize the initial @Data decorator values
            self.first = True
            print("Start Monitoring behavior")
            if self.first:
                device_data = {}
                self.first = False
            else:
                device_data = json.loads(self.device_data.get().decode('utf-8'))
                _ = 0
            
            #We send the value query to ANDES
            param_dict = {}
            for param in self.param_to_monitor:
                query_dict = self.device_dict
                query_dict['var'] = param
                responseAndes = requests.get(self.andes_url + '/specific_device_sync', params=query_dict)
                value = responseAndes.json()['value']
                param_dict[param] = value
            
            #We publish the new data 
            param_dict['model'] = self.device_dict['model']
            device_data[self.agent_id] = param_dict
            #self.device_data.publish(device_data)

            time.sleep(1.0)
            return 1
"""