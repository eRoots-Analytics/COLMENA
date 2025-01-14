import os, sys
import matplotlib 
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
import numpy as np
import matplotlib.pyplot as plt
import andes_methods as ad_methods
import aux_function as aux
import os, sys
from andes.utils.paths import get_case, cases_root, list_cases
import andes as ad
import colmena_test as Colmena


raw_file = get_case('nordic44/N44_BC.raw')
dyr_file = get_case('nordic44/N44_BC.dyr')
new_dyr_file = dyr_file.replace('N44_BC', 'N44_BC_alt')
aux.replace_in_file(dyr_file, new_dyr_file)
ad.config_logger(stream_level=10)

system = ad.System()
system = ad.load(raw_file, addfile=new_dyr_file, setup = False)
system.Slack.alter(src ='u', idx =19, value = 0)
system.Slack.alter(src ='u', idx =20, value = 0)
system.Slack.alter(src ='u', idx =21, value = 0)
system.Slack.alter(src ='u', idx =22, value = 0)
system.Slack.alter(src ='u', idx =23, value = 0)

gen_models = ['PV', 'Slack']
load_models = ['PQ']
total_gen_p = 0
total_load_p = 0
for gen in gen_models:
    gen = getattr(system, gen)
    total_gen_p += sum(np.array(gen.p0.v)*np.array(gen.u.v)) 

for load in load_models:
    load = getattr(system, load)
    total_load_p += sum(np.array(load.p0.v)*np.array(load.u.v)) 
power_diff =  total_gen_p - total_load_p

print(f'Total gen is {total_gen_p}')
print(f'Total load is {total_load_p}')
print(f'Power diff is {power_diff}')


n_PQ = system.PQ.n
for uid, idx in enumerate(system.PQ.idx.v):
    existing_p = system.PQ.p0.v[uid]
    system.PQ.alter(src = 'p0', idx = idx, value = existing_p + 1.01*(power_diff/n_PQ))

total_gen_p = 0
total_load_p = 0
for gen in gen_models:
    gen = getattr(system, gen)
    total_gen_p += sum(np.array(gen.p0.v)*np.array(gen.u.v)) 

for load in load_models:
    load = getattr(system, load)
    total_load_p += sum(np.array(load.p0.v)*np.array(load.u.v)) 
power_diff =  total_gen_p - total_load_p

print(f'Total gen is {total_gen_p}')
print(f'Total load is {total_load_p}')
print(f'Power diff is {power_diff}')

system.setup()
system.PFlow.run()
system.TDS.run()