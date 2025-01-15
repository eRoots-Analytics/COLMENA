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


ieee_file = get_case('ieee39/ieee39_full.xlsx')
ad.config_logger(stream_level=20)
system = ad.load(ieee_file, setup = False)

#We Substitute the synchronous generators for renewables generators with converters
system_to = ad.System()
system_dict = system.as_dict()
new_model_name = 'REGCV1'
gen_model = 'GENROU'
gen_dependencies = ['IEEEST', 'TGOV1N', 'IEEEX1']
n_GFM = 1
n_GFL = 1
n_genrou = system.GENROU.n - n_GFL - n_GFM


for model, param_dict in system_dict.items():
    #if n_genrou is 0 we just change all generators for 
    if model == gen_model and n_genrou == 0:
        model = new_model_name
    elif model in gen_dependencies and n_genrou == 0:
        continue
    
    elif model == gen_model and n_genrou > 0:
        _ = 0
        
    elif model in gen_dependencies and n_genrou > 0:
        for i in range(n_genrou):
            new_dict = {key: value[i] for key, value in param_dict.items()}
            system_to.add(model, new_dict)
        continue

    for i in range(len(param_dict['u'])):        
        new_dict = {key: value[i] for key, value in param_dict.items() if isinstance(value, list) or isinstance(value, np.ndarray)}
        new_dict_ = 0
        generator_like = ['GENROU', 'REGCV1', 'REGCA1']
        if i < n_genrou and model in generator_like:
            model = 'GENROU'
        elif i < n_genrou + n_GFM and model in generator_like:
            model = 'REGCV1'
        elif i >= n_genrou + n_GFM and model in generator_like:
            model = 'REGCA1'
        system_to.add(model, new_dict)

system_ieee = system        
system = system_to

if n_genrou == 0:
    system.Toggle.alter(src='model', idx = 'Toggler_1', value = new_model_name)
    system.Toggle.alter(src='name', idx = 'Toggler_1', value = 'GENROU_1')
    system.Toggle.alter(src='u', idx = 'Toggler_1', value = '1')

combined = False
if combined:
    system.setup()
    new_model = getattr(system, new_model_name)
    system.PFlow.run()
    system.TDS.run()
    system.TDS.load_plotter()
    matplotlib.use('TkAgg')
    GFM_converter = system.REGCV1
    GFL_converter = system.REGCA1
    fig, ax = system.TDS.plt.plot(GFM_converter.omega, a=0)
    fig, ax = system.TDS.plt.plot(GFL_converter.v, a=0)
    fig, ax = system.TDS.plt.plot(system.Bus.v, a=tuple(range(39)))
    _ = 0

system = aux.build_new_system(system_ieee, new_model_name='REDUAL')
system.REDUAL.set(src='is_GFM', attr = 'v', idx='GENROU_10', value=1)
system.setup()
system.REDUAL.prepare()
new_model = getattr(system, 'REDUAL')
system.PFlow.run()
system.TDS.run()
system.TDS.load_plotter()
matplotlib.use('TkAgg')
fig, ax = system.TDS.plt.plot(system.REDUAL.omega, a=0)
fig, ax = system.TDS.plt.plot(system.REDUAL.v, a=0)
fig, ax = system.TDS.plt.plot(system.Bus.v, a=tuple(range(39)))
_ = 0