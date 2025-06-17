"""
This class contains all the parameter values for the configuration of the simulation.
"""
class Config:

    andes_url = "http://127.0.0.1:5000" # andes_url = 'http://192.168.68.59:5000'
    case_path = "kundur/kundur_full.xlsx"

    # Simulator 
    tstep = 0.1
    tf = 10.0

    # Disturbance 
    td = 1.0

    # MPC
    # Status 
    controlled = True
    # Horizon
    dt = tstep * 5
    K = 20
    # Execution
    tdmpc = 1.0

    ramp_up = 0.1
    ramp_down = 0.1

    omega_ref = 1.0

    q = 1e7
    alpha = 1e4
    rho = 1e7

    max_iter = 300
    tol = 1e-3

    fn = 60

