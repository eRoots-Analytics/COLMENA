"""
This class contains all the parameter values for the configuration of the simulation.
"""
class Config:

    andes_url = "http://127.0.0.1:5000" # andes_url = 'http://192.168.68.59:5000'
    case_path = "ieee39/ieee39_full.xlsx"

    # Simulator 
    tstep = 0.05
    tf = 5.0

    # Disturbance 
    td = tf/2

    # MPC
    # Status 
    controlled = True
    # Horizon
    dt = tstep
    K = 50
    # Execution
    tdmpc = tstep # imporves numeric performance

    ramp_up = 0.05
    ramp_down = 0.05

    freq_ref = 1.0

    q = 1e3
    alpha = 10
    rho = 30

    max_iter = 100
    tol = 1e-3

