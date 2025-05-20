import numpy as np
import pyomo.environ as pyo
import requests

class MPC:
    def __init__(self, area, andes_url):
        self.area = area
        self.andes_url = andes_url
        self.dt = 0.5
        self.ramp_up = 0.1

    def build(self, mpc_problem, dt=0.5, T=20, controllable_redual=False):

        # ANDES API - calls to fetch system data
        # Idxs 
        generators = requests.post(self.andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'idx', 'area':self.area}).json()['value']
        loads = requests.post(self.andes_url + '/area_variable_sync', json={'model':'PQ', 'var':'idx', 'area':self.area}).json()['value']
        buses = requests.post(self.andes_url + '/area_variable_sync', json={'model':'Bus', 'var':'idx', 'area':self.area}).json()['value']
        areas = requests.get(self.andes_url + '/complete_variable_sync', params={'model':'Area', 'var':'idx'}).json()['value']
        PV_bus = requests.post(self.andes_url + '/area_variable_sync', json={'model':'PV', 'var':'bus', 'area':self.area}).json()['value']
        generator_bus = requests.post(self.andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'bus', 'area':self.area}).json()['value']
        # bus_area = requests.get(self.andes_url + '/complete_variable_sync', params={'model':'Bus', 'var':'area'}).json()['value']
        # PQ_bus = requests.post(self.andes_url + '/area_variable_sync', json={'model':'PQ', 'var':'bus', 'area':self.area}).json()['value']

        other_areas = [i for i in areas if i != self.area]

        gen_location = {gen: generator_bus[i] for i, gen in enumerate(generators)}
        bus2idgen = {generator_bus[i]: gen for i, gen in enumerate(generators)}
        self.bus2idgen = bus2idgen

        # if controllable_redual:
        #     PV_bus = PV_bus[2:]

        # Parameters
        Sn_values = requests.post(self.andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'Sn', 'idx':generators}).json()['value']
        Pe_values = requests.post(self.andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'Pe', 'idx':generators}).json()['value']
        M_values = requests.post(self.andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'M', 'idx':generators}).json()['value']
        D_values = requests.post(self.andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'D', 'idx':generators}).json()['value']
        # p0_values = requests.get(self.andes_url + '/complete_variable_sync', params={'model':'PV', 'var':'p0'}).json()['value']

        S_area, P_demand, M_coi, D_coi, S_base = 0, 0, 0, 0, []
        for i, bus in enumerate(generator_bus):
            if bus in buses:
                Sn = Sn_values[i]
                p0 = Pe_values[i]
                M = M_values[i]
                D = D_values[i]
                S_area += Sn
                M_coi += Sn * M
                D_coi += Sn * D
                P_demand += Sn * p0
                S_base.append(Sn)

        M_coi /= S_area
        D_coi /= S_area

        slack_bus =         requests.get(self.andes_url + '/complete_variable_sync', params={'model':'Slack', 'var':'bus', 'area':self.area}).json()['value']
        pmax_slack_values = requests.get(self.andes_url + '/complete_variable_sync', params={'model':'Slack', 'var':'pmax', 'area':self.area}).json()['value']
        pmin_slack_values = requests.get(self.andes_url + '/complete_variable_sync', params={'model':'Slack', 'var':'pmin', 'area':self.area}).json()['value']
        pmax_pv_values =    requests.post(self.andes_url + '/area_variable_sync', json={'model':'PV', 'var':'pmax', 'area':self.area}).json()['value']
        pmin_pv_values =    requests.post(self.andes_url + '/area_variable_sync', json={'model':'PV', 'var':'pmin', 'area':self.area}).json()['value']

        def power_bounds(model, gen, t):
            gen_bus = gen_location[gen]
            if gen_bus in PV_bus:
                index = PV_bus.index(gen_bus)
                return (pmin_pv_values[index], pmax_pv_values[index])
            elif gen_bus in slack_bus:
                index = slack_bus.index(gen_bus)
                return (pmin_slack_values[index], pmax_slack_values[index])
            return (0, 11)
        
        # Some other parameters
        b_areas = requests.get(self.andes_url + '/system_susceptance', params={'area':self.area}).json()
        b_areas = {int(k): v for k, v in b_areas.items()}

        model.Pd =  pyo.Param(model.TimeHorizon, initialize=P_demand)
        model.b =   pyo.Param(model.other_areas, initialize=b_areas)
        model.state_horizon_values = pyo.Param(model.areas, model.TimeHorizon, initialize=T, mutable=True)

        # Initial conditions
        delta_values = requests.post(self.andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'delta', 'idx':generators}).json()['value']
        freq_values = requests.post(self.andes_url + '/partial_variable_sync', json={'model':'GENROU', 'var':'omega', 'idx':generators}).json()['value']
        delta0 = np.dot(M_values, delta_values) / np.sum(M_values)
        freq0 = np.dot(M_values, freq_values) / np.sum(M_values)

        model.delta[0].value = delta0
        model.freq[0].value = freq0

        initial_area_values = {}
        for x_area in model.other_areas:
            delta_area = requests.post(self.andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'delta', 'area':x_area}).json()['value']
            M_area = requests.post(self.andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'M', 'area':x_area}).json()['value']
            initial_area_values[x_area] = np.dot(M_area, delta_area) / np.sum(M_area)

        # PYOMO - Create model 
        # Model 
        model =     pyo.ConcreteModel()

        # Sets
        model.generators =  pyo.Set(initialize=generators)
        model.loads =       pyo.Set(initialize=loads)
        model.other_areas = pyo.Set(initialize=other_areas)
        model.areas =       pyo.Set(initialize=areas)

        # Parameters
        model.M =         pyo.Param(initialize=M_coi)
        model.D =         pyo.Param(initialize=D_coi)
        model.Sn =        pyo.Param(model.generators, initialize={gen: Sn_values[i] for i, gen in enumerate(generators)})
        model.dual_vars = pyo.Param(model.areas, model.TimeHorizon, initialize=mpc_problem.dual_vars, mutable=True)

        model.TimeHorizon = pyo.RangeSet(0, T)
        model.TimeDynamics = pyo.RangeSet(0, T-1)

        # Variables
        model.delta =       pyo.Var(model.TimeHorizon, bounds=(-50, 50))
        model.delta_areas = pyo.Var(model.other_areas, model.TimeHorizon, initialize=0.0, bounds=(-50, 50))
        model.freq =        pyo.Var(model.TimeHorizon, bounds=(0.85, 1.15))
        model.Pg =          pyo.Var(model.generators, model.TimeHorizon, bounds=power_bounds)
        model.P =           pyo.Var(model.TimeHorizon, initialize=0.0)
        model.P_exchange =  pyo.Var(model.TimeHorizon, initialize=0.0)     

        # Constraints
        model.constraint_initial_conditions =  pyo.Constraint(expr=model.delta[0] == delta0)
        model.constraint_initial_conditions2 = pyo.Constraint(expr=model.freq[0] == freq0)
        model.constraint_initial_conditions3 = pyo.Constraint(model.other_areas, rule=lambda model, i: (initial_area_values[i], model.delta_areas[i, 0], initial_area_values[i]))
        model.constraint_initial_conditions4 = pyo.Constraint(model.generators, rule=lambda model, i: model.Pg[i, 0] == Pe_values[generators.index(i)])

        model.constrains_dynamics1 = pyo.Constraint(model.TimeDynamics, rule=lambda m, t: m.delta[t+1] == m.delta[t] + dt * 2 * np.pi * (m.freq[t] - 1))
        model.constrains_dynamics2 = pyo.Constraint(model.TimeDynamics, rule=lambda m, t: m.M * (m.freq[t+1] - m.freq[t]) / dt == -m.D * (m.freq[t] - 1) + m.P[t] - m.Pd[t] - m.P_exchange[t])
        model.constrains_dynamics3 = pyo.Constraint(model.generators, model.TimeDynamics, rule=lambda m, i, t: (m.Pg[i, t+1] - m.Pg[i, t]) <= dt * self.ramp_up)
        model.constrains_dynamics4 = pyo.Constraint(model.generators, model.TimeDynamics, rule=lambda m, i, t: -dt * self.ramp_up <= (m.Pg[i, t+1] - m.Pg[i, t]))

        model.constrains_area = pyo.Constraint(model.TimeHorizon, rule=lambda m, t: m.P_exchange[t] == sum(m.b[area] * (m.delta[t] - m.delta_areas[area, t]) for area in m.other_areas))
        model.constraints_balance = pyo.Constraint(model.TimeHorizon, rule=lambda m, t: m.P[t] == sum(m.Pg[gen, t] for gen in m.generators))

        # Objective function
        cost = np.ones(len(generators)) + np.random.rand(len(generators))
        model.c = pyo.Param(model.generators, initialize={gen: cost[i] for i, gen in enumerate(generators)})

        def freq_cost(m):
            return sum((m.freq[t] - 1) ** 2 for t in m.TimeHorizon)

        def lagrangian_term(m):
            sign = 1 if self.area == 1 else -1
            return sum(sum(mpc_problem.dual_vars[i, t] * sign * (m.delta_areas[i, t] - m.state_horizon_values[i, t]) for i in m.other_areas) for t in m.TimeHorizon) + \
                   sum(sum(mpc_problem.dual_vars[area, t] * sign * (m.delta[t] - mpc_problem.agents[i].state_horizon_values[area, t]) for t in m.TimeHorizon) for i, area in enumerate(m.areas))

        def penalty_term(m):
            sign = 1 if self.area == 1 else -1
            return sum(10 * sum((m.delta_areas[i, t] - m.state_horizon_values[i, t]) ** 2 for i in m.other_areas) for t in m.TimeHorizon) + \
                   100 * sum((m.delta[t] - m.state_horizon_values[self.area, t]) ** 2 for t in m.TimeHorizon)

        model.cost = pyo.Objective(rule=lambda m: freq_cost(m) + lagrangian_term(m) + penalty_term(m), sense=pyo.minimize)

        return model
