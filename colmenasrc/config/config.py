"""
This class contains all the parameter values for the configuration of the simulation.
"""
import os

class Config:

    andes_url = "http://andes:5000" # andes_url = 'http://192.168.68.59:5000'
    case_name = "npcc" # case_name = "kundur" "ieee39" "npcc"
    case_path = f"{case_name}/{case_name}.xlsx"
    failure = 'load_multiple_10'
    additional_failures = []
    failure_params = ['GENROU_46', 'GENROU_38']
    converters = False
    load_curtailment = False
    sim_ratio = 1.5

    # Simulator
    tstep = 0.05
    tf = 50.0

    # Disturbance
    td = 7.0

    # DMPC
    # Status
    controlled = True
    # Horizon
    dt = 0.25
    K = 2
    # Execution
    tdmpc = 2.5

    ramp_up = 1
    ramp_down = 1

    T_send = K
    angles = False
    omega_ref = 1.0

    q = 1e8 # NOTE: da abbassare se l'integratore viene introdotto
    alpha = 100
    rho = 2.5e3

    rho_diff = 1e1
    rho_scaled = {t:1.3e1*max(min(1,0.98**t),0.01) for t in range(K + 1)}
    T_send = K
    if angles:
        rho = 5e1
        dt = 0.1
        K = 18
        T = K
        T_send = min(T, 8)

    # q = 10/20
    # alpha = 15
    # rho = 1e3

    # q = 1e7 # NOTE: da abbassare se l'integratore viene introdotto
    # alpha = 100
    # rho = 2.5e3

    w_shed = 1e5

    max_iter = 3 #2 intentar
    tol = 1e-3 # ieee 1e-2

    fn = 60

    colmena = True
    agent = False
    