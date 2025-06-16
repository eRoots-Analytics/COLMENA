import time, os
import numpy as np
import json
import time
import traceback
import queue
import requests 
import pyomo.environ as pyo
from copy import deepcopy
import logging

class MPC_agent():
    def __init__(self, **kwargs):
        self.T = kwargs.get("T", 20)
        self.dt = kwargs.get("dt", 0.1)
        self.rho = kwargs.get("rho", 1)
        self.gamma = kwargs.get("T", 1e3)
        self.error = kwargs.get("error", 1e3)
        self.tol = kwargs.get("tol", 1e-4)
        self.andes_url = andes_url
        
    def setup_mpc(self, mpc_problem, controllable_redual = False):
        andes_url = self.andes_url
        area = self.area
        dt = self.dt
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
            return (pmin, pmax+0.2)

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
            Ddelta0 = delta_equivalent['2']
        else:
            delta0 = delta_equivalent[str(self.area)]
            Ddelta0 = 0
        print(f"delta0 is {delta0}, Ddelta is {Ddelta0}")
        time.sleep(2)
        initial_area_values = {}
        for x_area in model.other_areas:
            delta_area = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'delta', 'area':x_area}).json()['value']
            delta_area = requests.post(andes_url + '/area_variable_sync', json={'model':'Bus', 'var':'a', 'area':x_area}).json()['value']
            M_area = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'M', 'area':x_area}).json()['value']
            #initial_area_values[x_area] = (np.dot(M_area, delta_area) / np.sum(M_area))
            initial_area_values[x_area] = np.mean(delta_area)

        def initial_p(model, i):
            try:
                index = generators.index(i)
                Pe = Pe_values[index]
                tm = tm_values[index]
                print(f"Pe is {Pe}, tm is {tm}")
            except:
                generator_bus = gen_location[i]
                index = PV_bus.index(generator_bus)
                Pe = p0_values[index]
            return model.Pg[i,0] == tm

        def initial_delta_areas(model, i):
            #return (initial_area_values[i], model.delta_areas[i, 0], initial_area_values[i])
            if i == 1:
                return (0, model.delta_areas[i, 0], 0)
            else:
                return (Ddelta0, model.delta_areas[i, 0], Ddelta0)

        #We define the problem constraints
        #C1: initial area angle initial value
        #C2: initial area frequency initial value 
        #C3: initial area's angle value for the neighboring areas
        #C4: initial power injected by the generators in p.u.
        model.constraint_initial_conditions = pyo.Constraint(expr = model.delta[0] == delta0)
        model.constraint_initial_conditions2 = pyo.Constraint(expr = model.freq[0] == freq0)
        model.constraint_initial_conditions3 = pyo.Constraint(model.other_areas, rule = initial_delta_areas)
        model.constraint_initial_conditions4 = pyo.Constraint(model.generators, rule= initial_p)

        #We define the dynamics of the system as constraints
        #C1: the current area angle derivative
        #C2: the current frequency angle derivative
        #C3: the generator maximum ramp up
        #C4: the generator minimum ramp up
        self.ramp_up = 0.05
        model.constrains_dynamics1 = pyo.Constraint(model.TimeDynamics, rule=lambda model, t: (model.delta[t+1] - model.delta[t])==  self.dt*2*np.pi*fn*(model.freq[t]-1))
        model.constrains_dynamics2 = pyo.Constraint(model.TimeDynamics, rule=lambda model, t: model.M*(model.freq[t+1] - model.freq[t])/dt == ((-model.D(model.freq[t]-1) + model.P[t] - model.Pd[t] - model.P_exchange[t] + p_losses)))
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
        model.cost = pyo.Objective(rule=lambda model: 5e2*freq_cost(model) + 1*lagrangian_term(model) + 0*steady_state_condition(model)
                           + penalty_term(model) + 0.0*damping_term(model) + 5e3*terminal_cost(model) + 5e3*smoothing_term(model), sense=pyo.minimize)
        return model
        
    def reset_starting_points(self):
        #We reset the starting points delta0, freq0, Pg0, delta_areas0
        model = self.model
        andes_url = self.andes_url
        generators = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'idx', 'area':self.area}).json()['value']
        freq_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'omega', 'idx':generators}).json()['value']
        M_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'M', 'idx':generators}).json()['value']
        tm_values = requests.post(andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'tm', 'idx':generators}).json()['value']
        response = requests.get(andes_url + '/delta_equivalent', params={'area':1}).json()
        delta_equivalent = response['value']
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
        for area in model.other_areas:
            model.delta_areas0[area].value = delta_areas0
        for gen in model.generators:
            model.tm0[gen].value = tm0[gen]
    
    
    def warm_start(self):
        for t in self.model.TimeHorizon:
            self.model.delta_previous[t].value = self.model.delta[t].value
            for area in self.model.other_areas:
                self.model.delta_areas_previous[area, t].value = self.model.delta_areas[area,t].value
                self.model.dual_vars[area, self.area, t] =  self.dual_vars[area, self.area, t]
                self.model.dual_vars[self.area, area, t] =  self.dual_vars[self.area, area, t]
        return 1
    
    def initialize_dual_vars(self):
        model = self.model
        self.dual_vars = {}
        for t in model.TimeHorizon():
            for area in model.other_areas():
                if area == self.area:
                    continue
                self.dual_vars[self.area, area, t] = 0
                self.dual_vars[area, self.area, t] = 0

    def initialize_horizon(self):
        model = self.model
        self.state_horizon = {}
        for t in model.TimeHorizon():
            for area in model.other_areas():
                self.state_horizon[self.area, area, t] = 0
                self.state_horizon[self.area, self.area, t] = 0
        self.data_write.publish(self.state_horizon)
        return

    def change_set_points(self):
        params = ['p_direct', 'b']
        responseAndes = requests.get(self.andes_url + '/sync_time')
        time_start = int(responseAndes.json()['time'])
        for gen_id in self.model.generators:
            for t in range(1, self.T+1):
                for param in params:
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
                        roleChangeDict['value'] = self.model.Pg[gen_id, t].value - self.model.Pg[gen_id, 0].value 
                    elif roleChangeDict['var'] == 'b':
                        roleChangeDict['value'] = 1
                    else:
                        roleChangeDict['value'] = self.model.Pg[gen_id, t].value
                    roleChangeDict['t'] = time_start + self.dt*t
                    a = deepcopy(roleChangeDict)
                    responseAndes = requests.get(self.andes_url + '/add_set_point', params = roleChangeDict)
                    print(f"change is {roleChangeDict['value']} at time {roleChangeDict['t']}")
        return