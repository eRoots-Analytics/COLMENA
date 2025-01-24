import numpy as np
import andes.core as core
from andes.core import NumParam, DataParam, ExtParam, ConstService, ExtState, Algeb, ExtAlgeb, NumReduce, NumRepeat, IdxRepeat, Limiter, Discrete, IdxParam
from andes.core.service import InitChecker, FlagValue, DeviceFinder, RefFlatten
from andes.core import BaseVar, BaseService, BaseParam
from andes.models.renewable import REGCA1, REGCV1, REGCP1
from andes.core.model import Model, ModelData
import andes as ad
import sympy as sp
from copy import deepcopy

def not_none(a):
    if a is None:
        return '0'
    return a

class REDUALData(ModelData):
    def __init__(self, system, config):
        super().__init__(system, config)

class REDUALModel(Model):
    def __init__(self, system, config):
        super().__init__(system, config)

class REDUAL(REGCV1, REGCP1):
    def __init__(self, system, config):
        REGCP1.__init__(self, system, config)  # Initialize REGCA1
        REGCV1.__init__(self, system, config)  # Initialize REGCV1
        GFM_test = REGCV1(system, config)
        GFL_test = REGCP1(system, config) 
        self.GFM_twin = GFM_test
        self.GFL_twin = GFL_test
        common_algebs = set(GFM_test._algebs_and_ext().keys()) & set(GFL_test._algebs_and_ext().keys())
        common_states = set(GFM_test._states_and_ext().keys()) & set(GFL_test._states_and_ext().keys())
        self.common_vars_names = list(set(list(common_states) + list(common_algebs)))
        self.is_GFM = NumParam(name = 'is_GFM', default=0)

        #We change the equations for algebraic variables
        self.to_reinitialize =False
        #We change the equations for state variables
        for var in self._states_and_ext().values():
            e_eq = var.e_str
            v_eq = var.v_str

            if var.name in GFM_test._states_and_ext().keys():
                binary_str = '(is_GFM)'
            elif var.name in GFL_test._states_and_ext().keys():
                binary_str = '(1-is_GFM)'
            binary_str = '1'

            if e_eq is not None:
                var.e_str = binary_str + '*(' + e_eq + ')' 
            if v_eq is not None:
                var.v_str = binary_str + '*(' + v_eq + ')'
        
        #We then change the equations of the shared variables 
        for var_name in self.common_vars_names:
            if var_name in ['idx', 'u', 'name', 'bus', 'gen', 'Sn']:
                continue
            var_GFM = getattr(GFM_test, var_name)
            var_GFL = getattr(GFL_test, var_name)
            var = getattr(self, var_name)
            e_eq_GFM = var_GFM.e_str
            v_eq_GFM = var_GFM.v_str
            e_eq_GFL = var_GFL.e_str
            v_eq_GFL = var_GFL.v_str
            
            if e_eq_GFM is not None and e_eq_GFL is not None: 
                e_eq_new = '(1-is_GFM)*(' + not_none(e_eq_GFL) + ') + (is_GFM)*(' + not_none(e_eq_GFM) + ')' 
                setattr(var, 'e_str', e_eq_new)
            if v_eq_GFM is not None and v_eq_GFL is not None: 
                v_eq_new = '(1-is_GFM)*(' + not_none(v_eq_GFL) + ') + (is_GFM)*(' + not_none(v_eq_GFM) + ')' 
                setattr(var, 'v_str', v_eq_new)

        self.Ipout.e_str = '(1-is_GFM)*(' + self.Ipout.e_str  + ') + (is_GFM)*(Id*cos(delta) - Iq*sin(delta) -Ipout)'
        self.Iqout_y.e_str = '(1-is_GFM)*(' + self.Iqout_y.e_str  + ') + (is_GFM)*(Id*cos(delta) - Iq*sin(delta) -Iqout_y)'

    def reinitialize(self, idx):
        #Function that reinitializes the states
        uid = self.idx2uid(idx)
        is_GFM = self.is_GFM.v[uid]
        if is_GFM:
            udref0 = self.udref0.v[uid]            
            self.alter(src = 'uqref0', idx = idx, value=0)
            self.alter(src = 'udref0', idx = idx, value=udref0)
        else:
            Qe0 = self.Qe.v[uid]
            self.alter(src = 'Iqcmd', idx = idx, value=-Qe0)
            self.alter(src = 'Iqcmd0', idx = idx, value=-Qe0)

        return
        self.to_reinitialize = False
        uid = self.idx2uid(idx)
        is_GFM = self.is_GFM.v[uid]
        if is_GFM:
            twin_model = self.GFM_twin
        else:
            twin_model = self.GFL_twin
        saved_values = {}
        other_vars = ['Qe', 'Pe']
        for var_name in self.common_vars_names:
            var = getattr(self, var_name) 
            saved_values[var_name] = deepcopy(var.v)
        for var_name in other_vars:
            var = getattr(self, var_name) 
            saved_values[var_name] = deepcopy(var.v)
        for var_name, var in self.algebs_ext.items():
            saved_values[var_name] = deepcopy(var.v)
        for var_name, var in self.states_ext.items():
            saved_values[var_name] = deepcopy(var.v)
        for var_name, var in self.algebs.items():
            saved_values[var_name] = deepcopy(var.v)
            

        self.init(routine = 'tds')
        for var_name, value in saved_values.items():
            new_value = saved_values[var_name][uid]
            self.alter(src = var_name, idx = idx, value=new_value)
        self.to_reinitialize = False
        return