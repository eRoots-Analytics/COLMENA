import time
import numpy as np
import flask
import json
import requests
import time
import traceback
import cvxpy as cp
import traceback
import queue
import os, sys
from colmena import (
    Context,
    Service,
    Role,
    Channel,
    Requirements,
    Metric,
    Persistent,
    Async,
    KPI,
)

current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
import andes as ad
andes_url = 'http://127.0.0.1:5000'
current_directory = os.path.dirname(__file__)
json_path = os.path.join(current_directory, 'data.json')


class ExampleSaved(Service):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.t_start = time.time()
    
    class AndesTimeSync(Role):
        @Metric('frequency')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.andes_url = andes_url
            self.t_start = time.time()
            self.t_andes = 0
            self.t_run = 0.1
            self.t_max = 20
            
        @Persistent()
        def behavior(self):
            try:
                insync = False
                t_role = time.time() - self.t_start
                if insync:
                    responseRun = requests.get(andes_url + '/run', params = {'t_run':self.t_run})
                    self.t_andes = responseRun.json()['Time']
                    print('Andes is running code:', responseRun.status_code)
                elif self.t_andes + self.t_run <= t_role and self.t_andes < self.t_max:
                    responseRun = requests.get(andes_url + '/run', params = {'t_run':self.t_run})
                    self.t_andes = responseRun.json()['Time']
                    print('Andes is running code:', responseRun.status_code, "Andes time is", self.t_andes)
                else:
                    print('Andes is not running and time is', self.t_andes)
            except Exception as e:
                print(e)
                traceback.print_exc()
                
                
    class BasicRole1(Role):
        @Metric('frequency')
        @Channel('behaviorChange')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS 
            with open(json_path, 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.device_dict = {'model_name': self.model_name, 'idx': self.idx}
            self.t_start = time.time()
            self.M_value = 1
            
            #We initialize the variables once
            responseAndes = requests.get(andes_url + '/device_sync', params=self.device_dict)
            self.variables = responseAndes.json()
        
        def sync2Andes(self):
            responseAndes = requests.get(andes_url + '/device_sync', params=self.device_dict)
            self.variables = responseAndes.json()
            return responseAndes
        
        def change2Andes(self, param, value):
            roleChangeDict = self.device_dict
            roleChangeDict['param'] = param
            roleChangeDict['value'] = value
            responseAndes = requests.get(andes_url + '/device_role_change', params = self.roleChangeDict)
            return responseAndes
        
        def publish_metric(self, param):
            value = self.variables[param]
            self.frequency.publish(value)
            return value
        
        @Persistent()
        def behavior(self):
            verbose = True
            responseAndes = self.sync2Andes()
            print(f"role 1 synced at {time.time() - self.t_start}")
            value = self.publish_metric('omega')
            change = False
            if value > 1.003:
                print(f'here the frequency is {value}')
                self.M_value = 10
                self.behaviorChange.publish({'param':'M', 'value':self.M_value})
                change = True 
            if value < 1.003:
                self.M_value = 1.5
                self.behaviorChange.publish({'param':'M', 'value':self.M_value})
                change = True 
            if change and not verbose:
                print('Parameter M is =', self.M_value)
                print('Omega is', value)
    
    class BasicRole2(Role):
        @Metric('frequency')
        @Channel('behaviorChange')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS 
            with open(json_path, 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.idx = 2
            self.device_dict = {'model_name': self.model_name, 'idx': self.idx}
            self.t_start = time.time()
            self.M_value = 1
            
            #We initialize the variables once
            responseAndes = requests.get(andes_url + '/device_sync', params=self.device_dict)
            self.variables = responseAndes.json()
        
        def sync2Andes(self):
            responseAndes = requests.get(andes_url + '/device_sync', params=self.device_dict)
            self.variables = responseAndes.json()
            return responseAndes
        
        def change2Andes(self, param, value):
            roleChangeDict = self.device_dict
            roleChangeDict['param'] = param
            roleChangeDict['value'] = value
            responseAndes = requests.get(andes_url + '/device_role_change', params = self.roleChangeDict)
            return responseAndes
        
        def publish_metric(self, param):
            value = self.variables[param]
            self.frequency.publish(value)
            return value
        
        @Persistent()
        def behavior(self):
            verbose = True
            responseAndes = self.sync2Andes()
            print(f"role 2 synced at {time.time() - self.t_start}")
            value = self.publish_metric('omega')
            change = False
            if value > 1.003:
                print(f'here the frequency is {value}')
                self.M_value = 10
                self.behaviorChange.publish({'param':'M', 'value':self.M_value})
                change = True 
            if value < 1.003:
                self.M_value = 1.5
                self.behaviorChange.publish({'param':'M', 'value':self.M_value})
                change = True 
            if change and not verbose:
                print('Parameter M is =', self.M_value)
                print('Omega is', value)
    
    class BehaviorChangeRole(Role):
        @Channel('behaviorChange')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            #WE FIRST INITIALIZE THE ROLE PARAMETERS 
            with open(json_path, 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.device_dict = {'model_name': self.model_name, 'device_idx': self.idx}
            self.t_start = time.time()
            
        def change2Andes(self, param, value):
            roleChangeDict = self.device_dict
            roleChangeDict['param'] = param
            roleChangeDict['value'] = value
            responseAndes = requests.post(andes_url + '/device_role_change', json = roleChangeDict)
            print(f'Role Change performed at {time.time() - self.t_start} COLMENA time')
            return responseAndes
        
        @Async(new_behavior = 'behaviorChange')
        def behavior(self, new_behavior):
            print(f"new_behavior is {new_behavior}")
            param = new_behavior['param']
            value = new_behavior['value']
            self.change2Andes(param, value)
            
    class FrequencyOptimizerRole(Role):
        @Metric('frequency')
        @Channel('behaviorChange')
        @KPI("mean(frequency)[0.1] < 1.001")
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            with open(json_path, 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.omega_ref = 1
            self.n_generators = 4
            self.device_dict = {'model_name': self.model_name, 'device_idx': self.idx}  
            self.t_start = time.time()

        @Persistent()
        def behavior(self, freq):
            #we define the role's behavior
            t_now = time.time() - self.t_start
            print(f'Role frequency Optimizer is Active')
            self.omega_ref -= freq/max(1, self.n_generators-1)
            self.omega_ref = min(self.omega_ref, 1.001)
            self.omega_ref = max(self.omega_ref, 0.999)
            #self.behaviorChange.publish({'param':'omega_ref', 'value':self.omega_ref})
    
    class FrequencySetterRole(Role):
        @Metric('frequency')
        @Channel('behaviorChange')
        @Channel('referenceValue')
        @Requirements('GENERATOR')
        @KPI("mean(frequency)[1] < 1.001")
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            with open(json_path, 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.free_parameters = ['R']
            self.omega_ref = 1
            self.n_generators = 4
            self.device_dict = {'model_name': self.model_name, 'device_idx': self.idx}
            self.t_start = time.time()
        
        def func_wrapper(self, func, vars_dict, t):
            new_dict = {}
            for key, value in vars_dict.items():
                new_dict[key] = value[t]
            return func(**new_dict)
        
        def perform_simulation(self, var_names, ref_value):
            T = 10
            x = cp.Variable('R')
            w = cp.Variable(T)
            w_ref = np.ones(T)
            h = 0.03
            vars_dict = {}
            constraints = []
            responseMPC = requests.get()
            MPC_data = responseMPC.json()
            for var in MPC_data['vars']:
                if var not in var_names:
                    vars_dict[var] = cp.Variable(T)
            
            for var_name, func in MPC_data['differentialEquation'].items():
                var = vars_dict[var_name]
                for t in range(T-1):
                    constraints += [var[t+1] == var[t] + h*(0.5*self.func_wrapper(func, vars_dict, t)  + 0.5*self.func_wrapper(func, vars_dict, t))]    
            
            for var_name, func in MPC_data['algebraicEquation'].items():
                var = vars_dict[var_name]
                for t in range(T):
                    constraints += [self.func_wrapper(func, vars_dict, t) == 0]
            
            for var_name, func in MPC_data['initialEquation'].items():
                var = vars_dict[var_name]
                for t in range(T):
                    constraints += [self.func_wrapper(func, vars_dict, 0) == 0]
                    
            for var_name, func in MPC_data['exteriorEquation'].items():
                var = vars_dict[var_name]
                for t in range(T):
                    constraints += [self.func_wrapper(func, vars_dict, 0) == 0]     
                      
            weights = np.exp(np.linspace(0, 1, T))
            objective_function = cp.norm2(cp.multiply(weights, w - w_ref))
            mpcProb = cp.Problem(cp.Minimize(objective_function), constraints)
            mpcProb = mpcProb.solve()
        
        @Async(referenceValue = 'referenceValue')
        def behavior(self, referenceValue):
            pass
            if referenceValue['variable'] not in  ['omega', 'f']:
                raise ValueError('The referenced value is not available in this role')
            
            var_name = referenceValue['variable']
            ref_value =  referenceValue['value']
            
            #behaviorChangeDict = self.perform_simulation(var_name, ref_value)
            behaviorChangeDict = {}
            behaviorChangeDict['param'] = 'M'
            behaviorChangeDict['value'] = '1.5'
            for item in behaviorChangeDict.items():
                self.behaviorChange.publish(item)
            return 
    
    class FrequencyControlAGC(Role):
        @Metric('frequency')
        @Channel('behaviorChange')
        #@KPI('(mean(deriv(frequency))< 0.001 && mean(frequency)[1]')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            with open(json_path, 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.Ki = data.get('controller_gain', None)
            self.delta_p_ref = 0 
            self.h = 0
            self.p_ref = 1
            self.data = self.behavior
            
        @Persistent()
        def behavior(self):
            self.frequency.read()
            delta_p_ref += self.h*self.Ki*(self.omega - 1) 
            behaviorChangeDict = {}
            behaviorChangeDict['value'] = 1 + delta_p_ref
            behaviorChangeDict['add'] = False
            behaviorChangeDict['model_name'] = 'TGOV1'
            behaviorChangeDict['var_name'] = 'pref'
            self.behaviorChange.publish(behaviorChangeDict)
            
    class SecondaryAGC(Role):
        @Metric('frequency')
        @Channel('behaviorChange')
        #@KPI('(mean(deriv(frequency))< 0.001 && mean(frequency)[1]')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            with open('data.json', 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.Ki = data.get('controller_gain', None)
            self.delta_p_ref = 0 
            self.h = 0
            self.p_ref = 1
            self.data = self.behavior
            
        @Persistent()
        def behavior(self):
            frequency = self.frequency.read()
            delta_p_ref += self.h*self.Ki*(self.omega - 1) 
            behaviorChangeDict = {}
            behaviorChangeDict['value'] = 1 + delta_p_ref
            behaviorChangeDict['add'] = False
            behaviorChangeDict['model_name'] = 'TGOV1'
            behaviorChangeDict['var_name'] = 'pref'
            self.behaviorChange.publish(behaviorChangeDict)
            
    class SecondaryPowerResponse(Role):
        @Metric('frequency')
        @Channel('behaviorChange')
        #@KPI('(mean(deriv(frequency))< 0.001 && mean(frequency)[1]')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            with open('data.json', 'r') as json_file:
                data = json.load(json_file)
            self.andes_url = data.get('andes_url', None)
            self.idx = data.get('device_idx', None)
            self.model_name = data.get('model_name', None)
            self.Ki = data.get('controller_gain', None)
            self.delta_p_ref = 0 
            self.h = 0.001
            self.p_ref = 1
            self.data = self.behavior
            
        @Persistent()
        def behavior(self):
            frequency = self.frequency.read()
            behaviorChangeDict = {}
            behaviorChangeDict['value'] = self.h
            behaviorChangeDict['add'] = True
            behaviorChangeDict['model_name'] = 'TGOV1'
            behaviorChangeDict['var_name'] = 'pref'
            self.behaviorChange.publish(behaviorChangeDict)