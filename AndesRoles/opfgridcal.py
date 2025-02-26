import numpy as np
import sys, os
import pickle
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(current_directory)
sys.path.insert(0, two_levels_up+'/AndesApp')
from andes.utils.paths import get_case, cases_root, list_cases
import andes as ad
import inspect
import matplotlib.pyplot as plt
import matplotlib

from GridCalEngine.api import *
from GridCalEngine.Devices import Bus, Generator, Load
from GridCalEngine.Devices.multi_circuit import MultiCircuit
import GridCalEngine as gce
def opf_cost(p, c):
    res_cost = c.T@p
    return res_cost

def compute_cost(system, model, c):
    res_cost = 0
    if model.__class__.__name__ == 'PV':
        res_cost = c[:-1].T@(model.p0.v) 
        res_cost += c[-1]*system.Slack.p0.v[0]
    else:
        res_cost = c.T@(model.Pe.v)
    return res_cost

def build_gridcal_circuit(system = None):
    grid = MultiCircuit(name='andes_grid')
    gen_cost = np.zeros(system.GENROU.n)
    if system is None:
        system = ad.load(get_case('ieee39/ieee39_full.xlsx'), setup = False)
    model_dict = system.Bus.as_dict()
    buses = []
    for i in range(system.Bus.n):
        kwargs = {key:val[i] for key,val in model_dict.items()}
        valid_params = inspect.signature(Bus.__init__).parameters

        if i == (system.Slack.bus.v[0]-1):
            kwargs['is_slack'] = True

        kwargs['Vm0'] = kwargs['v0']
        kwargs['Va0'] = kwargs['a0']
        kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
        kwargs['vmin'] = 0.9
        kwargs['vmax'] = 1.1
        bus_i = Bus(**kwargs)
        grid.add_bus(bus_i)
        buses.append(bus_i)

    model_dict = system.PQ.as_dict()
    for i in range(system.PQ.n):
        kwargs = {key:val[i] for key,val in model_dict.items()}
        kwargs['P'] = 100*kwargs['p0']
        kwargs['Q'] = 100*kwargs['q0']
        valid_params = inspect.signature(Load.__init__).parameters
        kwargs = {k: v for k, v in kwargs.items() if k in valid_params}

        bus = system.PQ.bus.v[i]
        bus_uid = system.Bus.idx2uid(bus)
        Load_i = Load(**kwargs)
        grid.add_load(buses[bus_uid], Load_i)

    model_dict = system.PV.as_dict()
    for i in range(system.PV.n):
        kwargs = {key:val[i] for key,val in model_dict.items()}
        kwargs['P'] = 100*kwargs['p0']
        kwargs['Q'] = 100*kwargs['q0']
        valid_params = inspect.signature(Generator.__init__).parameters

        bus = system.PV.bus.v[i]
        bus_uid = system.Bus.idx2uid(bus)
        Sn = kwargs['Sn']
        kwargs['Pmax'] =kwargs['pmax']*Sn
        kwargs['Pmin'] =kwargs['pmin']*Sn*0
        kwargs['Qmax'] =kwargs['qmax']*Sn
        kwargs['Qmin'] =kwargs['qmin']*Sn
        kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
        cost = (1 + np.random.rand(1))
        gen_cost[i] = cost[0]
        generator_i = Generator(**kwargs, Cost=cost)
        grid.add_generator(buses[bus_uid], generator_i)

    model_dict = system.Slack.as_dict()
    kwargs = {key:val[0] for key,val in model_dict.items()}
    kwargs['P'] = 100*kwargs['p0']
    kwargs['Q'] = 100*kwargs['q0']
    valid_params = inspect.signature(Generator.__init__).parameters
    bus = system.PV.bus.v[i]
    bus_uid = system.Bus.idx2uid(bus)
    Sn = kwargs['Sn']
    kwargs['Pmax'] =kwargs['pmax']*Sn
    kwargs['Pmin'] =kwargs['pmin']*Sn*0
    kwargs['Qmax'] =kwargs['qmax']*Sn
    kwargs['Qmin'] =kwargs['qmin']*Sn
    kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
    cost = (1 + np.random.rand(1))
    gen_cost[-1] = cost[0]
    generator_i = Generator(**kwargs, Cost=cost)
    grid.add_generator(buses[bus_uid], generator_i)


    model_dict = system.Line.as_dict()
    for i in range(system.Line.n):
        kwargs = {key:val[i] for key,val in model_dict.items()}
        valid_params = inspect.signature(Line.__init__).parameters

        bus1_uid = system.Bus.idx2uid(kwargs['bus1'])
        bus2_uid = system.Bus.idx2uid(kwargs['bus2'])
        bus1_gce = buses[bus1_uid]
        bus2_gce = buses[bus2_uid]
        kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
        line_i = Line(bus_from=bus1_gce, bus_to=bus2_gce, **kwargs)
        grid.add_line(line_i)

    opf_options = gce.OptimalPowerFlowOptions(ips_init_with_pf=True, verbose =0, ips_tolerance=1e-6, solver=SolverType.NONLINEAR_OPF)
    opf_driver = gce.OptimalPowerFlowDriver(grid=grid, options=opf_options)

    print('Solving...')
    opf_driver.run()
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    pf_driver = gce.PowerFlowDriver(grid=grid,
                                    options=pf_options,
                                    opf_results=opf_driver.results)
    pf_driver.run()
    res = pf_driver.results.get_bus_df()
    print('Converged:', pf_driver.results.converged, '\nerror:', pf_driver.results.error)
    print(res.columns)

    res.Va = res.Va*180/np.pi  
    res.P = res.P/100
    res.Q = res.Q/100
    return grid, res, gen_cost

system = ad.load(get_case('ieee39/ieee39_full.xlsx'), setup = False)
system.setup()
system.PFlow.run()
data = {}
save = False
if save:
    grid, res, cost = build_gridcal_circuit(system)
    data['res'] = res
    data['cost'] = cost
    with open("data.pkl", "wb") as f:
        pickle.dump(data, f)
else:
    with open("data.pkl", "rb") as f:
        data = pickle.load(f)
        res, cost = data["res"], data["cost"]

res.loc['GEN31', 'P'] += 0.8
res.loc['GEN39', 'P'] += 4
cost_opf = opf_cost(res.P[-10:], cost)
cost_1 = compute_cost(system, system.PV, cost)

system.TDS_stepwise.run_opf_setpoints(system, opf_res = res, models = [system.GENROU], t_max=20)
cost_2 = compute_cost(system, system.GENROU, cost)
system.TDS_stepwise.load_plotter()
matplotlib.use('TkAgg')
n_tuple = tuple(range(10))
fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega)
fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.a)
fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.v)
fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.Pe, a = n_tuple, yheader=[str(a) for a in n_tuple])
print(f'Initial cost is {cost_1}, final cost is {cost_2}, original opfg is {cost_opf}')
print(res.P[-10:].values)
print(system.GENROU.Pe.v)
print(system.GENROU.Pe.v - res.P[-10:].values)
plt.show()