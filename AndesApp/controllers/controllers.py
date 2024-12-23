import numpy as np
import control as ctrl
import matplotlib.pyplot as plt


class PIcontroller:
    def __init__(self, **kwargs):
        self.params = {}
        self.dt = kwargs.get("dt", 0.01)
        self.Kp = kwargs.get("Kp", 0.1)  # Proportional gain
        self.Ki = kwargs.get("Ki", 0.1)  # Integral gain
        self.Lmin = kwargs.get("Lmin", -10.0)  # Minimum limit
        self.Lmax = kwargs.get("Lmax", 10.0)  # Maximum limit
        self.reference = kwargs.get("ref", 1.0)  # Maximum limit
        self.model = kwargs.get("model", 'GENROU')  # Maximum limit
        self.idx = kwargs.get("idx", 1)  # Maximum limit

        # Transfer function for the PI controller: H(s) = Kp + Ki/s
        num = [self.Kp, self.Ki]
        den = [1, 0]  # s in the denominator
        self.pi_tf = ctrl.TransferFunction(num, den)

        # Initialize limiter function
        def limiter_min_max(input):
            if input < self.Lmin:
                res = self.Lmin
            elif input > self.Lmax:
                res = self.Lmax
            else:
                res = input
            return res
        self.limiter = limiter_min_max

         # Convert to state-space form
        self.pi_tf = ctrl.c2d(self.pi_tf, self.dt, method='zoh')
        self.pi_ss = ctrl.tf2ss(self.pi_tf)

        # Initialize states for the state-space representation
        self.x0 = np.zeros(self.pi_ss.A.shape[0])

    def apply(self, input):
        """
        Process a single input value through the PI controller with feedback.

        Args:
        - setpoint (float): The desired reference value.
        - measurement (float): The measured feedback value.

        Returns:
        - output_value (float): The controller's output.
        """
        # Calculate the error between the setpoint and the measurement
        error = self.reference - input

        # Simulate one step using the discrete-time transfer function
        self.pi_tf
        response= ctrl.forced_response(
            self.pi_tf,
            T = [0, self.dt],
            U=[error, error],  # Error signal as input
            X0 =self.x0  # Initial state
        )

        self.x0 = response.states[:, -1]
        y = response.outputs[-1]
    
        # Apply the limiter to the output
        res = self.limiter(y)
        return res

    def reset_state(self):
        self.x0 = 0*self.x0
        return
    
    def get_set_point(self, input):
        res = []
        output = self.apply(input)
        new_set_point = {}
        new_set_point['model'] = 'TGOV1'
        new_set_point['param'] = 'paux0'
        new_set_point['idx'] = self.idx
        new_set_point['value'] = output
        new_set_point['add'] = False

        if self.model != 'GENROU':
            new_set_point['model'] = self.model
            new_set_point['param'] ='pref0'
        res.append(new_set_point)
        return res

class Stabilizer():
    def __init__(self, **kwargs):
        self.params = 0
        self.dt = 0.1
        self.idx = kwargs.get("idx", 1)
        self.T1 = kwargs.get("T1", 1.0)
        self.T2 = kwargs.get("T2", 1.0)
        self.T3 = kwargs.get("T3", 1.0)
        self.T4 = kwargs.get("T4", 1.0)
        self.T5 = kwargs.get("T5", 1.0)
        self.T6 = kwargs.get("T6", 1.0)
        self.A1 = kwargs.get("A1", 1.0)
        self.A2 = kwargs.get("A2", 1.0)
        self.A3 = kwargs.get("A3", 1.0)
        self.A4 = kwargs.get("A4", 1.0)
        self.A5 = kwargs.get("A5", 1.0)
        self.A6 = kwargs.get("A6", 1.0)
        self.Ks = kwargs.get("Ks", 1.0)
        self.Lmin = kwargs.get("Lmin", 1.0)
        self.Lmax = kwargs.get("Lmax", 1.0)
        self.Vlast = 0

        num_filter = [1, self.A1, self.A2]  # Numerator
        den_filter = np.polymul([1, self.A3, self.A4], [1, self.A5, self.A6])  # Denominator
        self.filter_tf = ctrl.TransferFunction(num_filter, den_filter)

        # Block 5: H(s) = (1 + s*T1) / (1 + s*T2)
        self.block5_tf = ctrl.TransferFunction([self.T1, 1], [self.T2, 1])

        # Block 6: H(s) = (1 + s*T3) / (1 + s*T4)
        self.block6_tf = ctrl.TransferFunction([self.T3, 1], [self.T4, 1])

        # Limiter dynamics (Block 7): H(s) = (Ks * s * T6) / (1 + s * T6)
        self.limiter_tf = ctrl.TransferFunction([self.Ks * self.T6, 0], [self.T6, 1])
        self.high_pass = ctrl.TransferFunction([self.Ks * self.T5, 0], [self.T5, 1])

        self.combined_tf = ctrl.series(self.filter_tf, self.high_pass, self.block5_tf, self.block6_tf, self.limiter_tf)
        # Combine all blocks in series

        self.combined_tf = ctrl.c2d(self.combined_tf, self.dt, method='zoh')


        def limiter_min_max(input):
            if input < self.Lmin:
                res = self.Lmin
            elif input > self.Lmax:
                res = self.Lmax
            else:
                res = input
            return res
        self.limiter = limiter_min_max

        # Initialize real-time simulation variables
        self.pi_ss = ctrl.tf2ss(self.combined_tf)

        # Initialize states for the state-space representation
        self.x0 = np.zeros(self.pi_ss.A.shape[0])
        ctrl.bode(self.pi_ss, dB=True)
        plt.show()

    #input is a single value
     # Process a single input value
    def apply(self, current_input):
        """
        Process a single input value through the controller.

        Args:
        - current_input (float): The input signal to the controller.

        Returns:
        - output_value (float): The controller's output.
        """
        # Simulate one step using the discrete-time transfer function
        """response = ctrl.forced_response(
            self.pi_ss, 
            T=[0, self.dt],  # Time window for this step
            U=[current_input, current_input],  # Input signal
            X0=self.x0  # Initial state
        )

        #We save the state and the output
        self.x0 = response.states[:, -1]
        y = response.outputs[-1]"""

        # Extract state-space matrices
        A, B, C, D = self.pi_ss.A, self.pi_ss.B, self.pi_ss.C, self.pi_ss.D

        # Compute next state and output for one timestep
        y = C @ self.x0 + D * current_input
        self.x0 = A @ self.x0 + B * current_input

        print('v stabilizer is', y[0,0])
        return self.limiter(y[0,0])
    
    def define_inputs_dict(self):
        vars = ['SW_s1', 'omega', 'SW_s3', 'tm0', 'Sn', 'Sb', 'SW_s4', 'tm', 'SW_s5', 'v']
        return vars

    def compute_input(self,**kwargs):
        vars = ['SW_s1', 'omega', 'SW_s3', 'tm0', 'Sn', 'Sb', 'SW_s4', 'tm', 'SW_s5', 'v']
        self.param = {}
        for var in vars:
            self.param[var] = kwargs.get(var, 1.0)
        
        sum1 = self.param['SW_s1']*(self.param['omega']-1)
        sum2 = self.param['SW_s3']*self.param['tm0']/(self.param['tm0'])
        sum3 = self.param['SW_s4']*(self.param['tm0'] - self.param['tm'])
        sum4 = self.param['SW_s5']*(self.param['v'])

        sig = sum1 + sum2 + sum3 + sum4
        return sig
    
    def get_set_point(self, input):
        res = []
        output = self.apply(input)
        new_set_point = {}
        new_set_point['model'] = 'EXDC2'
        new_set_point['param'] = 'v_aux'
        new_set_point['idx'] = self.idx
        new_set_point['value'] = self.Vlast
        new_set_point['add'] = False
        self.Vlast = output
        res.append(new_set_point)
        return res

class ActivePowerRegulator():
    def __init__(self, **kwargs):
        self.a = kwargs.get("a", 1.0)
        self.idx = kwargs.get("idx", 1.0)
        self.neighbors = kwargs.get("neighbors", 1.0)
        self.w0 = kwargs.get("ref", 1.0)

    def get_power(self, idx, system = None):
        if system is None:
            #when in colmena change this to access the data differently
            return
        
        uid = system.GENROU.idx2uid(idx)
        res = system.GENROU.p.v[uid]
        return res

    def compute_input(self, p_i, system =None):
        res = 0
        p_neighbors = [self.get_power(idx, system) for idx in self.neighbors]
        for p_j in p_neighbors:
            res = (p_j - p_i)
        
        return self.a*res
        
    def get_set_point(self, input, system):
        p_i = input
        d_w = self.compute_input(p_i, system)

        new_set_point = {}
        new_set_point['model'] = 'TGOV1'
        new_set_point['param'] = 'wref0'
        new_set_point['idx'] = self.idx
        new_set_point['value'] = self.w0 + d_w
        new_set_point['add'] = False

class VoltageRegulator():
    def __init__(self, **kwargs):
        self.PI_voltage = kwargs.get('pi_e', None)
        self.PI_reactive = kwargs.get('pi_q', None)
        self.b = kwargs.get('pi_q', 1)
        self.neighbors = kwargs.get('neighbors', [])

    def get_power(self, idx, system = None):
        if system is None:
            #when in colmena change this to access the data differently
            return
        
        uid = system.GENROU.idx2uid(idx)
        res = system.GENROU.p.v[uid]
        return res

    def compute_input(self, q_i, system =None):
        res = 0
        p_neighbors = [self.get_power(idx, system) for idx in self.neighbors]
        for q_j in p_neighbors:
            res = (q_j - q_i)
        
        return self.b*res
    
    def get_set_point(self, input1, input2, system):
        q_i = input2
        input2 = self.compute_input2(q_i, system)

        d_u1 = self.PI_voltage.apply(input1)
        d_u2 = self.PI_reactive.apply(input2)

        new_set_point = {}
        new_set_point['model'] = 'PVD1'
        new_set_point['param'] = 'uref0'
        new_set_point['idx'] = self.idx
        new_set_point['value'] = self.u0 + d_u1 + d_u2
        new_set_point['add'] = False