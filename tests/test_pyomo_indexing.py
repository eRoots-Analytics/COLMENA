"""
This script is used to understand how the indexing in pyomo works. 
NOTE: a notebook would be much better and interactive!
"""

import pyomo.environ as pyo

model = pyo.ConcreteModel()
model.T = 3
model.TimeHorizon = pyo.RangeSet(0, model.T)

model.x = pyo.Var(model.TimeHorizon, initialize=0)

for t in model.TimeHorizon:
    print(f"Index: {t}, Variable x[{t}] = {model.x[t].value}")
