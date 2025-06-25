import os, sys
import matplotlib 
current_directory = os.path.dirname(os.path.abspath(__file__))
one_levels_up = os.path.dirname(current_directory)
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
three_levels_up = os.path.dirname(os.path.dirname(os.path.dirname(current_directory)))
sys.path.insert(0, one_levels_up)
sys.path.insert(0, three_levels_up)
import numpy as np
import matplotlib.pyplot as plt
import os, sys
from andes.utils.paths import get_case, cases_root, list_cases
import andes as ad
from copy import deepcopy



ieee_file = get_case('ieee39/ieee39_full.xlsx')
ieee_file = get_case('kundur/kundur_full.xlsx')
ieee_file = get_case('kundur/kundur_full.xlsx')

ad.config_logger(stream_level=10)
system = ad.load(ieee_file, setup = False)
system.setup()
system.PFlow.run()
system.TDS.init()
initial_delta = []
initial_a = []
for i in system.GENROU.delta.v:
    initial_delta.append(deepcopy(i))
    print(f"initial angle is {i}")
for i in system.Bus.a.v:
    initial_a.append(deepcopy(i))
    print(f"initial bus angle is {i}")

system.TDS.run()
lines = [7,17,20,31,21]
for i, line_id in enumerate(system.Line.idx.v):
    print(i)
    if i+1 in lines:
        bus_1 = system.Line.bus1.v[i]
        bus_2 = system.Line.bus2.v[i]
        bus_1 = system.Bus.idx2uid(bus_1)
        bus_2 = system.Bus.idx2uid(bus_2)
        print(system.Bus.a.v[bus_1] - system.Bus.a.v[bus_2])

for i, delta in enumerate(system.GENROU.delta.v):
    print(f"delta diff a is {delta - initial_delta[i]}")
for i, delta in enumerate(system.Bus.a.v):
    print(f"delta diff b is {delta - initial_a[i]}")

print(f" for system load is {sum(system.PQ.p0.v)} and generation is {sum(system.PV.p0.v) + sum(system.Slack.p0.v) }")
#system.TDS_stepwise.run()

for area in [1, 2]:
    P_balance = 0
    connecting_lines = {}
    connecting_susceptance = {}

    other_areas = system.Area.idx.v
    other_areas = [x_area for x_area in other_areas if x_area != area]
    connecting_lines = {}
    connecting_susceptance = {}
    delta_equivalent = {}
    for x_area in other_areas:
        connecting_lines[x_area] = []

    for i, line in enumerate(system.Line.idx.v):
        bus1 = system.Line.bus1.v[i]
        bus2 = system.Line.bus2.v[i]
        bus1_index = system.Bus.idx2uid(bus1)
        bus2_index = system.Bus.idx2uid(bus2)
        area1 = system.Bus.area.v[bus1_index]
        area2 = system.Bus.area.v[bus2_index]
        if area1 != area2 and area in [area1, area2]:
            connecting_area = area2 if area == area1 else area1
            connecting_lines[connecting_area].append(line)
            print(f"connecting from {bus1} to {bus2}")
            print(f"connecting from {area1} to {area2}")

    for x_area, lines in connecting_lines.items():
        bi = 0
        for line in lines:
            line_uid = system.Line.idx2uid(line)
            connection_status = system.Line.u.v[line_uid]
            xi = system.Line.x.v[line_uid]
            Sn = system.Line.Sn.v[line_uid]
            bi += (1/xi)*connection_status
        connecting_susceptance[int(x_area)] = bi
    
    p_exchanged = 0
    p_exchanged_other = 0
    for x_area, lines in connecting_lines.items():
        for line in lines:
            i = system.Line.idx2uid(line)
            bus1 = system.Line.bus1.v[i]
            bus2 = system.Line.bus2.v[i]
            bus1_index = system.Bus.idx2uid(bus1)
            bus2_index = system.Bus.idx2uid(bus2)
            area1 = system.Bus.area.v[bus1_index]
            area2 = system.Bus.area.v[bus2_index]
            delta1 = system.Bus.a.v[bus1_index]
            delta2 = system.Bus.a.v[bus2_index]
            v1 = system.Bus.v.v[bus1_index]
            v2 = system.Bus.v.v[bus2_index]
            line_uid = system.Line.idx2uid(line)
            xi = system.Line.x.v[line_uid]
            ri = system.Line.r.v[line_uid]
            b_shunt = system.Line.b.v[line_uid]
            if area == area1:
                sign = 1
            else:
                sign = -1
            p_line = sign*v1*v2*((-1/xi)*np.sin(delta1-delta2)) 
            denom = ri**2 + xi**2
            p_ij = sign * v1 * v2 * ((ri / denom) * np.cos(delta1 - delta2) - (xi / denom) * np.sin(delta1 - delta2))
            p_exchanged += 0*p_ij
            p_exchanged += 1*(sign*v1*v2*((-1/xi)*np.sin(delta1-delta2)) )
            p_exchanged_other += 0*sign*v1*v2*((ri/(xi**2))*np.cos(delta1-delta2)) 
            print(f"line is {p_exchanged} with p_line {p_exchanged_other}")
    P_balance += p_exchanged

    p_gen = 0
    for i, gen_idx in enumerate(system.GENROU.idx.v):
        bus_idx = system.GENROU.bus.v[i]
        bus_uid = system.Bus.idx2uid(bus_idx) 
        bus_area = system.Bus.area.v[bus_uid]
        if bus_area == area:
            p_gen += system.GENROU.Pe.v[i]
    P_balance += p_gen
    
    p_demand = 0
    for i, gen_idx in enumerate(system.PQ.idx.v):
        bus_idx = system.PQ.bus.v[i]
        bus_uid = system.Bus.idx2uid(bus_idx) 
        bus_area = system.Bus.area.v[bus_uid]
        if bus_area == area:
            p_demand -= system.PQ.p0.v[i]
    P_balance += p_demand
    
    gamma_exchange = (p_gen + p_demand)/p_exchanged
    print(f"For area {area}, Balance is {P_balance}, exchanged is {p_exchanged}, demand is {p_demand}, generation is {p_gen}")
    print(f"gamma is {gamma_exchange}")

system.TDS_stepwise.load_plotter()
#matplotlib.use('TkAgg')
#fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Qe, a = n_tuple)
fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.delta, savefig=True)
fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega)
fig, ax = system.TDS_stepwise.plt.plot(system.Bus.a, a = (0,1,2,3))
_ = 0
