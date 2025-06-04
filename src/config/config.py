"""
This class contains all the parameter values for the configuration of the simulation.
"""
class Config:

    andes_url = "http://127.0.0.1:5000" # andes_url = 'http://192.168.68.59:5000'
    case_path = "kundur/kundur_full.xlsx"

    # Simulator 
    tstep = 0.05
    tf = 10.0

    # Disturbance 
    td = tf/2

    # MPC
    # Status 
    controlled = False
    # Horizon
    dt = tstep
    K = 30
    # Execution
    tdmpc = tstep # imporves numeric performance

    ramp_up = 0.05
    ramp_down = 0.05

    omega_ref = 1.0

    q = 1e8
    alpha = 1.5
    rho = 15

    max_iter = 50
    tol = 1e-3

    P_exchange_max = 20
    P_exchange_min = 20

