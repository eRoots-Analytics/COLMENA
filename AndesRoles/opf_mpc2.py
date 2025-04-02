import requests
import time
import numpy as np
import requests
import time
import sys
import json
import cvxpy as cp
from itertools import product
import GridCalEngine
sys.path.append('/home/pablo/Desktop/eroots/COLMENA/AndesApp/Scripts/scripts')
import os
import pyomo.environ as pyo
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(current_directory)
sys.path.insert(0, two_levels_up+'/AndesApp')
from andes.utils.paths import get_case, cases_root, list_cases
import andes as ad
import matplotlib.pyplot as plt
import matplotlib
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
)

def setup_mpc(system, area, dt = 0.5, T = 20):
    generators = system.PV.idx.v[:]
    loads = system.PQ.idx.v[:]
    areas = system.Area.idx.v[:]
    other_areas = [i for i in areas if i !=area]

    buses = system.Bus.idx.v
    buses = [bus for i, bus in enumerate(buses) if system.Bus.area.v[i] == 1]
    loads = [loads[i] for i, bus in enumerate(system.PQ.bus.v) if bus in buses]
    generators = [generators[i] for i, bus in enumerate(system.PV.bus.v) if bus in buses]

    M_coi = 0
    D_coi = 0
    S_area = 0
    P_demand = 0
    S_base = []
    for i, bus in enumerate(system.GENROU.bus.v):
        if bus in buses:
            S_area += system.GENROU.Sn.v[i]
    for i, bus in enumerate(system.GENROU.bus.v):
        if bus in buses:
            Sn = system.GENROU.Sn.v[i]
            p0 = system.GENROU.Pe.v[i]
            M = system.GENROU.M.v[i]
            D = system.GENROU.D.v[i]
            M_coi = Sn*M/S_area
            M_coi = Sn*D/S_area
            P_demand += Sn*p0
            S_base.append(S_base)

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
    def power_bounds(model, gen, t):
        if gen in system.PV.bus.v:
            index = system.PV.bus.v.index(gen)
            Sn = system.PV.Sn.v[index]     
            pmax = (system.PV.pmax.v[index])*Sn
            pmin = (system.PV.pmin.v[index])*Sn
        elif gen in system.Slack.bus.v:
            Sn = system.Slack.Sn.v[index]     
            pmax = (system.Slack.pmax.v[index])*Sn
            pmin = (system.Slack.pmin.v[index])*Sn
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
    delta0 = 0
    freq0 = 0
    for i, bus in enumerate(system.GENROU.bus.v):
        if bus in buses:
            delta0 += (system.GENROU.delta0.v[i])
    for i, bus in enumerate(system.GENROU.bus.v):
        if bus in buses:
            freq0 += (system.GENROU.omega.v[i]-1)
    
    def initial_p(model, i):
        try:
            index = system.GENROU.bus.v.index(i)
            Sn = system.GENROU.Sn.v[index]
            Pe = system.GENROU.Pe.v[index]*Sn
        except:
            index = system.PV.bus.v.index(i)
            Sn = system.GENROU.Sn.v[index]
            Pe = system.PV.p0.v[index]*Sn
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

system = ad.load(get_case('kundur/kundur_full.xlsx'), setup = False)
system.setup()
system.PFlow.run()
system.TDS.init()
model, solver = setup_mpc(system, area = 1)
solver = pyo.SolverFactory('ipopt')
solver.options['print_level'] = 10 # Shows detailed convergence info
solver.options['tol'] = 1e-4
result = solver.solve(model, tee=True)
# Print the results
for i in model.TimeHorizon:
    print(f"delta[{i}] = {model.delta[i].value}")
    print(f"freq[{i}] = {model.freq[i].value}")
    #print(f"P[{i}] = {model.P[i].value}")
    #print(f"Pd[{i}] = {model.Pd[i]}")
    #print(f"P_exchange[{i}] = {model.P_exchange[i].value}")