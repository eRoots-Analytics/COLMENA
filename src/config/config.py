"""
This class contains all the parameter values for the configuration of the simulation.
"""
class Config:

    andes_url = "http://127.0.0.1:5000" # andes_url = 'http://192.168.68.59:5000'
    case_path = "ieee39/ieee39_full.xlsx"

    # Simulator 
    tstep = 0.1
    tf = 10.0

    # MPC
    # Horizon
    dt = tstep
    K = 50
    # Execution
    tdmpc = 0.5

    ramp_up = 0.05
    ramp_down = 0.05

    freq_ref = 1.0

    q = 1
    alpha = 10
    rho = 100

    max_iter = 100
    tol = 1e-4

