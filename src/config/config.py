"""
This class contains all the parameter values for the configuration of the simulation.
"""
class Config:

    andes_url = "http://127.0.0.1:5000" # andes_url = 'http://192.168.68.59:5000'
    case_name = "npcc" # case_name = "kundur" "ieee39" "npcc"
    case_path = f"{case_name}/{case_name}_modified.xlsx" 

    # Simulator 
    tstep = 0.1
    tf = 25.0

    # Disturbance 
    td = 5.0

    # DMPC
    # Status 
    controlled = True
    # Horizon
    dt = tstep * 5
    K = 20
    # Execution
    tdmpc = 2.5

    ramp_up = 0.1
    ramp_down = 0.1

    omega_ref = 1.0

    q = 1e8 # NOTE: da abbassare se l'integratore viene introdotto
    alpha = 100
    rho = 2.5e3

    # q = 10/20
    # alpha = 15
    # rho = 1e3

    # q = 1e7 # NOTE: da abbassare se l'integratore viene introdotto
    # alpha = 100
    # rho = 2.5e3

    max_iter = 500
    tol = 1e-2

    fn = 60
    colmena = False
    agent = True
