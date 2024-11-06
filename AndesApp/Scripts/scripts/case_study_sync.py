import os, sys

current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
import numpy as np
import tensorly as tl
import matplotlib
import matplotlib.pyplot as plt
import andes_methods as ad_methods
from scipy.integrate import odeint
from scipy.optimize import root
import os, sys
#import tensorflow as tf
from andes.utils.paths import get_case, cases_root, list_cases
import multiprocessing
import andes as ad
import colmena_test as Colmena
from scipy.optimize import approx_fprime
import matplotlib.pyplot as plt


current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
# Now you can import your package
if __name__ == '__main__':
    _ = 0
    import andes as ad
    from andes.utils.paths import get_case, cases_root, list_cases

ad.config_logger(30)
list_cases()
base_case = True
kundur_modified_case_a = True
normal_simulation = True
simulation_environment = False
colmena_environment = True   
print(ad.__file__)

#We run the normal simulation
if base_case:
    matplotlib.use('TkAgg')
    ss1 = ad.run(get_case('kundur/kundur_full.xlsx'))
    ss1.PFlow.run()
    ss1.TDS.config.tf = 20
    ss1.TDS.run()
    ss1.TDS.load_plotter()
    old_ss = ss1
    # fig, ax = ss1.TDS.plt.plot(ss1.GENROU.v, a=(0, 3))
    #plt.show()
    
test_1 = True
bimode = False
case_direction = 'kundur/kundur_full'
if test_1:
    model = 'GENROU'
    if bimode:
        model = model + "_bimode"
        case_direction = case_direction + '_bimode'
    ss = ad.load(get_case(case_direction +'.xlsx'), setup = False)
    ss.setup()
    ad_methods.initialize_system_data(ss, ss1, ss.GENROU_bimode)
    info_dict1 = {1:(1, model, "omega"), 2:(2, model, "omega")}
    info_dict2 = {3:(3, model, "omega"), 4:(4, model, "omega")}
    edge1 = Colmena.Edge(ss, id = 1, info_dict = info_dict1)
    edge2 = Colmena.Edge(ss, id = 2, info_dict = info_dict2)
    edges = [edge1, edge2]
    colmena = Colmena.Colmena(ss, edges)
    ss.PFlow.run()
    ss.files.no_outpout = True
    ss.TDS_stepwise.edges = edges
    ss.TDS_stepwise.run_batches(colmena)
    ss.TDS_stepwise.load_plotter()
    found1, found2 = ss.TDS_stepwise.plt.find('omega')
    data = ss.TDS_stepwise.plt.get_values(found1)
    data = ss.TDS_stepwise.save_roles
    plt.ion()
    plt.close('all')
    ad_methods.plot_roles(data, ss.TDS_stepwise.config.tf, condition=None)
    df = ss.TDS_stepwise.plt.data_to_df()
    fig, ax = ss.TDS_stepwise.plt.plot(ss.GENROU.omega, a=(0,1,2,3))
    plt.show()

def program_colmena(queue):
    colmena.run_colmena_sync(queue, t=0, tf=20)

def program_andes(queue):
    ss.TDS_stepwise.run_andes_sync(queue, edges = edges, batch_size =0.5)
    
if __name__ == "__main__":
    # Create a Queue for communication between Program A and Program B
    queue = multiprocessing.Queue()

    # Create and start two processes
    process_a = multiprocessing.Process(target=program_colmena, args=(queue,))
    process_b = multiprocessing.Process(target=program_andes, args=(queue,))

    process_a.start()
    process_b.start()

    # Wait for both processes to complete
    process_a.join()
    process_b.join()
