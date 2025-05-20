import numpy as np
import andes.core as core
from andes.core import NumParam, DataParam, ExtParam, ConstService, ExtState, Algeb, ExtAlgeb, NumReduce, NumRepeat, IdxRepeat, Limiter, Discrete, IdxParam
from andes.core.service import InitChecker, FlagValue, DeviceFinder, RefFlatten
from andes.core import BaseVar, BaseService, BaseParam
from andes.models.renewable import REGCA1, REGF1, REGCP1
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

class REDUAL(REGF1, REGCP1):
    def __init__(self, system, config):
        REGCP1.__init__(self, system, config)  # Initialize REGCA1
        REGF1.__init__(self, system, config)  # Initialize REGF1
        GFM_test = REGF1(system, config)
        GFL_test = REGCP1(system, config) 
        self.GFM_twin = GFM_test
        self.GFL_twin = GFL_test
        common_algebs = set(GFM_test._algebs_and_ext().keys()) & set(GFL_test._algebs_and_ext().keys())
        common_states = set(GFM_test._states_and_ext().keys()) & set(GFL_test._states_and_ext().keys())
        self.common_vars_names = list(set(list(common_states) + list(common_algebs)))
        self.is_GFM = NumParam(name = 'is_GFM', default=0)

        self.vref_aux = NumParam(default = 0) 
        self.wref_aux = NumParam(default = 0) 
        self.paux_bis = NumParam(default = 0) 

        self.vref2.e_str = self.vref2.e_str + '+vref_aux'
        #self.dw.e_str = self.dw.e_str.replace('dw', '*(dw-dwref_aux)')
        #self.Pe.e_str = self.Pe.e_str + '-0*paux_bis'
        #self.a.e_str = self.a.e_str + '-0*u*paux_bis'
        #self.Pref2.e_str = self.Pref2.e_str 

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
        
        self.to_reinitialize = np.zeros(self.n)

    def reinitialize(self, idx, type='no_change'):
        #Function that reinitializes the states
        
        uid = self.idx2uid(idx)
        is_GFM = self.is_GFM.v[uid]
        v = self.v.v[uid]
        am = self.am.v[uid]
        a = self.a.v[uid]
        if type == 'no_change':
            if is_GFM:
                self.alter(src = 'delta', idx = idx, value=a)
                _ = 0
            else:
                _ = 0
            
            return

        if type == 'initial_conditions':
            if is_GFM:
                Pe = self.Pref.v[uid]
                Qe = self.Qref.v[uid]
                Paux = self.Paux.v[uid]
                Qaux = self.Qaux.v[uid]
                Id0 = self.Id0.v[uid]
                Iq0 = self.Iq0.v[uid]
                udref0 = self.udref0.v[uid]
                uqref0 = self.uqref0.v[uid]

                self.alter(src = 'delta', idx = idx, value=a)
                self.alter(src = 'Psen_y', idx = idx, value=Pe)
                self.alter(src = 'Qsen_y', idx = idx, value=Qe)
                self.alter(src = 'Psig_y', idx = idx, value=Paux+Pe)
                self.alter(src = 'Qsig_y', idx = idx, value=Qaux+Qe)
                self.alter(src = 'PIplim_xi', idx = idx, value=Id0)
                self.alter(src = 'PIqlim_xi', idx = idx, value=Iq0)
                self.alter(src = 'PIId_xi', idx = idx, value=0)
                self.alter(src = 'PIIq_xi', idx = idx, value=0)
                self.alter(src = 'udLag_y', idx = idx, value=udref0)
                self.alter(src = 'uqLag_y', idx = idx, value=uqref0)
            else:
                return
                p = self.p0.v[uid]
                q = self.q0.v[uid]
                Iqcmd0 = self.Iqcmd0.v[uid]
                Ipcmd0 = self.Ipcmd0.v[uid]
                self.alter(src = 'S0_y', idx = idx, value=-Iqcmd0)
                self.alter(src = 'S1_y', idx = idx, value=v)
                self.alter(src = 'S2_y', idx = idx, value=Ipcmd0)
            
            _= 0
            return

        if type == 'continuous':
            if is_GFM:
                Pe = self.Pe.v[uid]
                Qe = self.Qe.v[uid]
                Paux = self.Paux.v[uid]
                Qaux = self.Qaux.v[uid]
                Id0 = self.Id.v[uid]
                Iq0 = self.Iq.v[uid]
                udref0 = self.udref.v[uid]
                uqref0 = self.uqref.v[uid]
                Iq = self.Iqcmd.v[uid]
                Iq = self.Iqout_x.v[uid]

                #self.alter(src = 'delta', idx = idx, value=a)
                #self.alter(src = 'Psen_y', idx = idx, value=Pe)
                #self.alter(src = 'Qsen_y', idx = idx, value=Qe)
                self.alter(src = 'Psig_y', idx = idx, value=Paux+Pe)
                self.alter(src = 'Qsig_y', idx = idx, value=Qaux+Qe)
                #self.alter(src = 'PIplim_xi', idx = idx, value=Ip)
                #self.alter(src = 'PIqlim_xi', idx = idx, value=Iq)
                self.alter(src = 'PIId_xi', idx = idx, value=Id0)
                self.alter(src = 'PIIq_xi', idx = idx, value=Iq0)
                self.alter(src = 'udLag_y', idx = idx, value=udref0)
                self.alter(src = 'uqLag_y', idx = idx, value=uqref0)
            else:
                return
                p = self.Pe.v[uid]
                q = self.Qe.v[uid]
                Iqcmd0 = p/v
                Ipcmd0 = -q/v
                self.alter(src = 'S0_y', idx = idx, value=-Iqcmd0)
                self.alter(src = 'S1_y', idx = idx, value=v)
                self.alter(src = 'S2_y', idx = idx, value=Ipcmd0)
            
            _= 0
            return
        if type=='reference_change' and is_GFM:
            v = self.Pref
            if type=='reference_change' and True:
                Pe = self.Pe.v[uid]
                Qe = self.Qe.v[uid]
                Paux = self.Paux.v[uid]
                Qaux = self.Qaux.v[uid]
                Id0 = self.Id0.v[uid]
                Id = self.Id.v[uid]
                Iq0 = self.Iq0.v[uid]
                Iq = self.Iq.v[uid]
                udref0 = self.udref.v[uid]
                uqref0 = self.uqref.v[uid]
            else:
                Pe = self.Pe.v[uid]
                Qe = self.Qe.v[uid]
                Paux = self.Paux.v[uid]
                Qaux = self.Qaux.v[uid]
                Id0 = self.Id.v[uid]
                Iq0 = self.Iq.v[uid]
                udref0 = self.udref.v[uid]
                uqref0 = self.uqref.v[uid]
            ra = self.rf.v[uid]
            xs = self.xf.v[uid]
            vd = self.vd.v[uid]
            vq = self.vq.v[uid]

            vref2 = self.vref2.v[uid] 
            #Kp = self.Kp.v[uid] 
            udref0 = Id*ra - Iq*xs + vd         
            uqref0 = Id*xs - Iq*ra + vq   
    
            #We set the operating points given the present values      
            self.alter(src = 'delta', idx = idx, value=a)
            self.alter(src = 'Psen_y', idx = idx, value=Pe)
            self.alter(src = 'Qsen_y', idx = idx, value=Qe)
            self.alter(src = 'Psig_y', idx = idx, value=Paux+Pe)
            self.alter(src = 'Qsig_y', idx = idx, value=Qaux+Qe)
            self.alter(src = 'PIplim_xi', idx = idx, value=Id0)
            self.alter(src = 'PIqlim_xi', idx = idx, value=Iq0)
            self.alter(src = 'PIId_xi', idx = idx, value=0)
            self.alter(src = 'PIIq_xi', idx = idx, value=0)
            self.alter(src = 'udLag_y', idx = idx, value=udref0)
            self.alter(src = 'uqLag_y', idx = idx, value=uqref0)
        else:
            return
            Qe0 = self.Qe.v[uid]/self.v.v[uid]
            Pe0 = self.Pe.v[uid]/self.v.v[uid]

            #We set the operating points given the present values      
            self.alter(src = 'Iqcmd', idx = idx, value=-Qe0)
            self.alter(src = 'Iqcmd0', idx = idx, value=-Qe0)
            self.alter(src = 'Ipcmd', idx = idx, value=Pe0)
            self.alter(src = 'Ipcmd0', idx = idx, value=Pe0)

            #we set some state differently to smooth the transition
            self.alter(src = 'S0_y', idx = idx, value=Pe0)
            self.alter(src = 'S2_y', idx = idx, value=Pe0)

        return

    def reinitialize_legacy(self, idx, type='no_change'):
        #Function that reinitializes the states
        
        uid = self.idx2uid(idx)
        is_GFM = self.is_GFM.v[uid]
        v = self.v.v[uid]
        am = self.am.v[uid]
        a = self.a.v[uid]
        if type == 'no_change':
            return

        if type == 'continuous':
            if is_GFM:
                Id = self.Id.v[uid]
                Iq = self.Iq.v[uid]
                vd = self.vd.v[uid] 
                vq = self.vq.v[uid]
                ra = self.ra.v[uid]
                xs = self.xs.v[uid]
                uqref = self.uqref.v[uid]
                udref = self.udref.v[uid]
                udref0 = Id*ra - Iq*xs + vd         
                uqref0 = Id*xs - Iq*ra + vq   
                self.alter(src = 'dw', idx = idx, value=0)
                self.alter(src = 'delta', idx = idx, value=a)
                self.alter(src = 'PIvd_xi', idx = idx, value=Id)
                self.alter(src = 'PIvq_xi', idx = idx, value=Iq)
                self.alter(src = 'PIId_xi', idx = idx, value=0)
                self.alter(src = 'PIIq_xi', idx = idx, value=0)
                self.alter(src = 'udLag_y', idx = idx, value=udref0)
                self.alter(src = 'uqLag_y', idx = idx, value=uqref0)
            else:
                p = self.Pe.v[uid]
                q = self.Qe.v[uid]
                Iqcmd0 = p/v
                Ipcmd0 = -q/v
                self.alter(src = 'S0_y', idx = idx, value=-Iqcmd0)
                self.alter(src = 'S1_y', idx = idx, value=v)
                self.alter(src = 'S2_y', idx = idx, value=Ipcmd0)
            
            _= 0
            return

        elif type == 'initial_conditions':
            if is_GFM:
                Id = self.Id0.v[uid]
                Iq = self.Iq0.v[uid]
                vd = self.vd.v[uid] 
                vq = self.vq.v[uid]
                ra = self.ra.v[uid]
                xs = self.xs.v[uid]
                udref = self.udref.v[uid]
                uqref = self.uqref.v[uid]
                udref0 = Id*ra - Iq*xs + vd         
                uqref0 = Id*xs - Iq*ra + vq
                udref0 = self.udref0.v[uid]
                uqref0 = self.uqref0.v[uid]

                self.alter(src = 'dw', idx = idx, value=0)
                self.alter(src = 'delta', idx = idx, value=a)
                self.alter(src = 'PIvd_xi', idx = idx, value=Id)
                self.alter(src = 'PIvq_xi', idx = idx, value=Iq)
                self.alter(src = 'PIId_xi', idx = idx, value=0)
                self.alter(src = 'PIIq_xi', idx = idx, value=0)
                self.alter(src = 'udLag_y', idx = idx, value=udref0)
                self.alter(src = 'uqLag_y', idx = idx, value=uqref0)
            else:
                p = self.p0.v[uid]
                q = self.q0.v[uid]
                Iqcmd0 = self.Iqcmd0.v[uid]
                Ipcmd0 = self.Ipcmd0.v[uid]
                self.alter(src = 'S0_y', idx = idx, value=-Iqcmd0)
                self.alter(src = 'S1_y', idx = idx, value=v)
                self.alter(src = 'S2_y', idx = idx, value=Ipcmd0)
            
            _= 0
            return
        if is_GFM:
            v = self.Pref
            if type=='reference_change':
                Id = self.Id.v[uid]
                Iq = self.Iq.v[uid]
                vd = self.vd.v[uid] 
                vq = self.vq.v[uid]
            else:
                Id = self.Pref.v[uid]/v
                Iq = -self.Qref.v[uid]/v
                vd = v
                vq = 0
            ra = self.ra.v[uid]
            xs = self.xs.v[uid]
             
            vref2 = self.vref2.v[uid] 
            #Kp = self.Kp.v[uid] 
            udref0 = Id*ra - Iq*xs + vd         
            uqref0 = Id*xs - Iq*ra + vq   
    
            #We set the operating points given the present values      
            self.alter(src = 'uqref', idx = idx, value=uqref0)
            self.alter(src = 'uqref0', idx = idx, value=uqref0)
            self.alter(src = 'udref', idx = idx, value=udref0)
            self.alter(src = 'udref0', idx = idx, value=udref0)

            #We reset state values
            self.alter(src = 'delta', idx = idx, value=a)
            self.alter(src = 'dw', idx = idx, value=am)
            self.alter(src = 'PIvd_xi', idx = idx, value=Id)
            self.alter(src = 'PIvq_xi', idx = idx, value=Iq)
            self.alter(src = 'udLag_y', idx = idx, value=udref0)
            self.alter(src = 'uqLag_y', idx = idx, value=uqref0)

        else:
            Qe0 = self.Qe.v[uid]/self.v.v[uid]
            Pe0 = self.Pe.v[uid]/self.v.v[uid]

            #We set the operating points given the present values      
            self.alter(src = 'Iqcmd', idx = idx, value=-Qe0)
            self.alter(src = 'Iqcmd0', idx = idx, value=-Qe0)
            self.alter(src = 'Ipcmd', idx = idx, value=Pe0)
            self.alter(src = 'Ipcmd0', idx = idx, value=Pe0)

            #we set some state differently to smooth the transition
            self.alter(src = 'S0_y', idx = idx, value=Pe0)
            self.alter(src = 'S2_y', idx = idx, value=Pe0)

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
            continue
            saved_values[var_name] = deepcopy(var.v)
            

        self.init(routine = 'tds')
        for var_name, value in saved_values.items():
            new_value = saved_values[var_name][uid]
            self.alter(src = var_name, idx = idx, value=new_value)
        self.to_reinitialize = False
        return