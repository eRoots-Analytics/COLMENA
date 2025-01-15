import numpy as np
import andes.core as core
from andes.core import NumParam, DataParam, ExtParam, ConstService, Algeb, ExtAlgeb, NumReduce, NumRepeat, IdxRepeat, Limiter, Discrete, IdxParam
from andes.core.service import InitChecker, FlagValue, DeviceFinder, RefFlatten
from andes.models.exciter import ExcQuadSat
from andes.models.area import Area
from andes.models.line import Line
from andes.models.renewable import REGCA1, REGCV1
from andes.core.model import Model, ModelData
from andes.core.block import PIController
import andes as ad
import sympy as sp
from copy import deepcopy

class REDUAL(REGCA1, REGCV1):
    def __init__(self, system, config):
        REGCA1.__init__(self, system, config)  # Initialize REGCA1
        REGCV1.__init__(self, system, config)  # Initialize REGCV1
        GFM_test = REGCV1(system, config)
        GFL_test = REGCA1(system, config)
        Common_algebs = list(GFM_test._algebs_and_ext().keys()) + list(GFL_test._algebs_and_ext().keys())
        Common_states = list(GFM_test._states_and_ext().keys()) + list(GFL_test._states_and_ext().keys())
        self.is_GFM = NumParam(name = 'is_GFM', default=0)

        #We change the equations for algebraic variables
        for var in self._algebs_and_ext().values():
            e_eq = var.e_str
            v_eq = var.v_str

            if var.name in GFM_test._algebs_and_ext().keys():
                binary_str = '(is_GFM)'
            elif var.name in GFL_test._algebs_and_ext().keys():
                binary_str = '(1-is_GFM)'

            if e_eq is not None:
                var.e_eq = binary_str + '*(' + e_eq + ')'  
            if v_eq is not None:
                var.v_eq = binary_str + '*(' + v_eq + ')'

        for var in self._states_and_ext().values():
            e_eq = var.e_str
            v_eq = var.v_str

            if var.name in GFM_test._states_and_ext().keys():
                binary_str = '(is_GFM)'
            elif var.name in GFL_test._states_and_ext().keys():
                binary_str = '(1-is_GFM)'

            if e_eq is not None:
                var.e_eq = binary_str + '*(' + e_eq + ')' 
            if v_eq is not None:
                var.v_eq = binary_str + '*(' + v_eq + ')'

    def reinitialize_states(self, idx):
        #Function that reinitializes the states
        uid = self.idx2uid(idx)

        """
        model could depend on the value of b
        if self.b.v[uid] == 0:
            model_copy = REGCA1()
        else:
            model_copy = REGCV1()   

        for var in model_copy._states_and_ext().values():
            ...        
        """
        model_copy = deepcopy(self)
        model_copy.init()
        for var_name, var in self._states_and_ext.items():
            var_copy = getattr(model_copy, var_name)
            var.v[uid] = var_copy.v[uid]
        return