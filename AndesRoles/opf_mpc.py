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
import inspect
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

def bounds_rule(system, mode):
    max_array = system.Bus.vmax.v[:]
    min_array = system.Bus.vmin.v[:]
    if mode == 'v':
        for i in range(len(min_array)):
            if i in system.PV.bus.v:
                max_array[i-1] += 0.2
                min_array[i-1] -= 0.2
    
    elif mode == 'Pg':
        max_array = 0*np.zeros_like(max_array)
        min_array = 0*np.zeros_like(min_array)
        for i in range(1,len(min_array)+1):
            if i in system.PV.bus.v:
                index = system.PV.bus.v.index(i) 
                max_array[i-1] += 100*system.PV.pmax.v[index] 
                min_array[i-1] += system.PV.pmin.v[index] 

    elif mode == 'Qg':
        max_array = 0*max_array
        min_array = 0*max_array
        for i in range(1, len(min_array)+1):
            if i in system.PV.bus.v:  
                index = system.PV.bus.v.index(i) 
                max_array[i-1] += system.PV.qmax.v[index] 
                min_array[i-1] += system.PV.qmin.v[index] 


    def res_function(model, i):
        res_max = max_array[i-1]
        res_min = min_array[i-1]
        #print(f"Bounds for {mode} at index {i}: ({res_min}, {res_max}) | Type: {type(res_min)}, {type(res_max)}")
        return(float(res_min), float(res_max))
    return res_function

def setup_MPC(system):
    model = pyo.ConcreteModel()
    n = system.Bus.n
    nlines = system.Bus.n
    bus_rangeSet = pyo.RangeSet(n)

    boundsrule_v = bounds_rule(system, 'v')
    boundsrule_Pg = bounds_rule(system, 'Pg')
    boundsrule_Qg = bounds_rule(system, 'Qg')
    model.bus_rangeSet = bus_rangeSet
    model.P = pyo.Var(bus_rangeSet, domain = pyo.Reals)
    model.Pg = pyo.Var(bus_rangeSet, bounds = boundsrule_Pg)
    model.Q = pyo.Var(bus_rangeSet, domain = pyo.Reals)
    model.Qg = pyo.Var(bus_rangeSet, bounds = boundsrule_Qg)
    model.v = pyo.Var(bus_rangeSet, domain = pyo.NonNegativeReals, bounds = boundsrule_v)
    model.theta = pyo.Var(bus_rangeSet)

    constraints = []
    Qcharge = np.zeros(n)
    Pcharge = np.zeros(n)
    for i in range(n):
        if i in system.PQ.bus.v:
            index = system.PQ.bus.v.index(i) 
            Qcharge[i] += system.PQ.q0.v[index]
            Pcharge[i] += system.PQ.p0.v[index]
    
    Qcharge_dict = {i+1: Qcharge[i] for i in range(len(Qcharge))}
    Pcharge_dict = {i+1: Qcharge[i] for i in range(len(Pcharge))}
    # Define Param
    model.Qcharge = pyo.Param(bus_rangeSet, initialize=Qcharge_dict)
    model.Pcharge = pyo.Param(bus_rangeSet, initialize=Pcharge_dict)
    model.constraint_Pbalance = pyo.Constraint(model.bus_rangeSet, rule=lambda model, i: model.Pg[i] - model.P[i] - model.Pcharge[i]== 0)
    model.constraint_Qbalance = pyo.Constraint(model.bus_rangeSet, rule=lambda model, i: model.Qg[i] - model.Q[i] - model.Qcharge[i]== 0)

    g = {}
    b = {}
    r_dict = {}
    x_dict = {}
    pair_set = list(product(range(1,n+1), repeat=2))
    line_set = list(zip(system.Line.bus1.v, system.Line.bus2.v)) + list(zip(system.Line.bus2.v, system.Line.bus1.v))
    for i, (bus1, bus2) in enumerate(pair_set):
        bus1, bus2 = int(bus1), int(bus2)
        if (bus1, bus2) in line_set:
            index = line_set.index((bus1, bus2)) 
            index = index%n
            r = system.Line.r.v[index]
            x = system.Line.x.v[index]
            b_line = system.Line.b.v[index]
            g[(bus1, bus2)] = r/(r**2 + x**2)
            g[(bus2, bus1)] = r/(r**2 + x**2)
            b[(bus1, bus2)] = -x/(r**2 + x**2)
            b[(bus2, bus1)] = -x/(r**2 + x**2)
            r_dict[(bus1, bus2)] = r
            r_dict[(bus2, bus1)] = r
            x_dict[(bus1, bus2)] = x
            x_dict[(bus2, bus1)] = x
        else:
            g[(bus1, bus2)] = 0
            g[(bus2, bus1)] = 0
            b[(bus1, bus2)] = 0
            b[(bus2, bus1)] = 0

    res = 0
    model.g = pyo.Param(bus_rangeSet, bus_rangeSet, initialize=g)
    model.b = pyo.Param(bus_rangeSet, bus_rangeSet, initialize=b)
    
    def constraint_rule_P(model, i):
        return model.P[i] == model.v[i]*sum(model.v[k]*(model.g[i, k]*pyo.cos(model.theta[i] - model.theta[k]) + model.b[i, k]*pyo.sin(model.theta[i] - model.theta[k])) for k in model.bus_rangeSet) 

    def constraint_rule_Q(model, i):
        return model.Q[i] == model.v[i]*sum(model.v[k]*(model.g[i, k]*pyo.cos(model.theta[i] - model.theta[k]) - model.b[i, k]*pyo.sin(model.theta[i] - model.theta[k])) for k in model.bus_rangeSet) 

    model.constraint_LinesP = pyo.Constraint(model.bus_rangeSet, rule=constraint_rule_P)
    model.constraint_LinesQ = pyo.Constraint(model.bus_rangeSet, rule=constraint_rule_Q)

    #we define the intensities
    def constraint_I(model, bus1, bus2):
        i = (bus1, bus2)
        Imax = 1.2
        r = r_dict[i]
        x = x_dict[i]
        return model.v[bus1]**2 - 2*model.v[bus1]*model.v[bus2]*pyo.cos(model.theta[bus1]-model.theta[bus2])+model.v[bus2]**2 <= Imax*(r**2 +x**2)
    
    pair_set = (product(range(1, n+1), repeat=2))
    model.line_pairs = pyo.Set(initialize=set(line_set))
    #model.Imod = pyo.Var(model.line_pairs, bounds=(0,1.5))
    #model.constraint_current = pyo.Constraint(model.line_pairs, rule =constraint_I)
    #Cost function
    cost = np.ones(n) + np.random.rand(n)
    cost_dict = {i+1:cost[i] for i in range(n)}
    model.c = pyo.Param(model.bus_rangeSet, initialize=cost_dict)
    def cost_rule(model):
        return sum(model.c[i] * model.Pg[i] for i in model.bus_rangeSet)

    model.cost = pyo.Objective(rule=cost_rule, sense=pyo.minimize)
    solver = pyo.SolverFactory('ipopt')
    print(solver.available())  
    # Solve the problem
    solve = False
    if solve:
        result = solver.solve(model, tee=True)
        # Print the results
        for i in model.bus_rangeSet:
            print(f"P[{i}] = {model.Pg[i].value}")
    return model


system = ad.load(get_case('kundur/kundur_full.xlsx'), setup = False)
system.setup()
system.PFlow.run()
model = setup_MPC(system)
for i in model.bus_rangeSet:
    if i in system.PV.bus.v:
        index = system.PV.bus.v.index(i)
        model.Pg[i].set_value( system.PV.p0.v[index] )
        model.Pg[i].set_value( system.PV.p0.v[index] )
        qg = system.PV.p0.v[index] 
        pg = system.PV.q0.v[index]
    else:
        qg = 0 
        pg = 0
    if i in system.PQ.bus.v:
        index = system.PQ.bus.v.index(i)
        pload = system.PQ.p0.v[index]
        qload = system.PQ.q0.v[index] 
    else:
        pload = 0
        qload = 0
    model.v[i].set_value(system.Bus.v.v[i-1] )  # A little below max voltage
    model.theta[i].set_value(system.Bus.a.v[i-1] )  # A little below max voltage
    model.P[i].set_value(pload - pg)  # A little below max voltage
    model.Q[i].set_value(qload - qg)  # A little below max voltage

solver = pyo.SolverFactory('ipopt')
solver.options['print_level'] = 10 # Shows detailed convergence info
solver.options['tol'] = 1e-4
result = solver.solve(model, tee=True)
# Print the results
for i in model.bus_rangeSet:
    print(f"Pg[{i}] = {model.Pg[i].value}")
    print(f"Qg[{i}] = {model.Qg[i].value}")
    print(f"P[{i}] = {model.P[i].value}")

for v in model.component_objects(pyo.Var, active=True):
    for index in v:
        value = pyo.value(v[index])
        lb, ub = v[index].bounds
        if value is not None:
            if lb is not None and value < lb:
                print(f"  Variable {v.name}[{index}] below bound: {value} < {lb}")
            if ub is not None and value > ub:
                print(f"  Variable {v.name}[{index}] above bound: {value} > {ub}")

for constr in model.component_objects(pyo.Constraint, active=True):
    print(f"Checking constraint: {constr.name}")
    for index in constr:
        expr = constr[index].body  # Get the left-hand side (LHS) of the constraint
        lhs = pyo.value(expr)  # Evaluate LHS
        lb = constr[index].lower  # Lower bound
        ub = constr[index].upper  # Upper bound

        # Identify violations
        if lb is not None and lhs < lb:
            print(f"  {constr.name}[{index}] violated: {lhs} < {lb}")
        elif ub is not None and lhs > ub:
            print(f"  {constr.name}[{index}] violated: {lhs} > {ub}")

