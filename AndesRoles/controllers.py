import numpy as np 
import time
import requests
import control as ctrl

class Stabilizer():
    def __init__(self, **kwargs):
        self.params = 0
        self.dt = 0.01
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

        num_filter = [1, self.A1, self.A2]  # Numerator
        den_filter = np.polymul([1, self.A3, self.A4], [1, self.A5, self.A6])  # Denominator
        self.filter_tf = ctrl.TransferFunction(num_filter, den_filter)

        # Block 5: H(s) = (1 + s*T1) / (1 + s*T2)
        self.block5_tf = ctrl.TransferFunction([self.T1, 1], [self.T2, 1])

        # Block 6: H(s) = (1 + s*T3) / (1 + s*T4)
        self.block6_tf = ctrl.TransferFunction([self.T3, 1], [self.T4, 1])

        # Limiter dynamics (Block 7): H(s) = (Ks * s * T6) / (1 + s * T6)
        self.limiter_tf = ctrl.TransferFunction([self.Ks * self.T6, 0], [1, self.T6])

        self.combined_tf = ctrl.series(self.filter_tf, self.block5_tf, self.block6_tf, self.limiter_tf)
        # Combine all blocks in series

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
        self.x0 = np.zeros(self.combined_tf.states)

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
        _, y, self.x0 = ctrl.forced_response(
            self.combined_tf, 
            T=[0, self.dt],  # Time window for this step
            U=[current_input, current_input],  # Input signal
            X0=self.x0  # Initial state
        )
        return y[-1]
    
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