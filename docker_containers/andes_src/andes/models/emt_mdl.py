import numpy as np
import andes.core as core
from andes.core import NumParam, ConstService, Algeb, ExtAlgeb, ExtState, LessThan, State, Limiter, Discrete, IdxParam
from andes.core.service import InitChecker, FlagValue
from andes.models.exciter import ExcQuadSat
from andes.models.synchronous.genbase import GENBaseData, GENBase, Flux0, Flux2
from andes.models.synchronous.genrou import GENROUData, GENROUModel, GENROU
from andes.models.bus import Bus
from andes.models.measurement import PLL2
from andes.core import Model, ModelData
from andes.core.block import PITrackAW, PIController, DQtransform, Inner_Loop
from andes.models.area import Area
from andes.models.distributed import PVD1
from andes.models.renewable import REGF1, REECA1
import andes as ad
import sympy as sp
import re 

#class representing a shunt inductance in a given bus
class Bus_AC(Bus):
    def __init__(self, system, config):
        Bus.__init__(self, system , config)
        self.v_temp = Algeb(info='d-axis voltage',
                        v_str='u * v0 * sin( sys_f*t_dae * + a0)',
                        e_str='u * v * sin( sys_f*t_dae * + a)',
                        tex_name='v_temp',
                        )
        
class Bus_abc(Bus):
    def __init__(self, system, config):
        Bus.__init__(self, system , config)
        self.v_a = Algeb(info='d-axis voltage',
                        v_str='u * v0 * sin( sys_f*t_dae * + a0)',
                        e_str='u * v * sin( sys_f*t_dae * + a)',
                        tex_name='v_temp',
                        )
        self.v_b = Algeb(info='d-axis voltage',
                        v_str='u * v0 * sin( sys_f*t_dae * + a0 + 2*pi/3)',
                        e_str='u * v * sin( sys_f*t_dae * + a + 2*pi/3)',
                        tex_name='v_temp',
                        )
        self.v_c = Algeb(info='d-axis voltage',
                        v_str='u * v0 * sin( sys_f*t_dae * + a0 - 2*pi/3)',
                        e_str='u * v * sin( sys_f*t_dae * + a - 2*pi/3)',
                        tex_name='v_temp',
                        )
                        

class RLC_AC(ModelData, Model):
    def __init__(self, system, config):
        ModelData.__init__(self)
        self.R = NumParam(unit='p.u.',
                          tex_name='R',
                          info='DC line resistance',
                          non_zero=True,
                          default=0.01,
                          r=True,
                          )
        self.L = NumParam(unit='p.u.',
                          tex_name='L',
                          info='DC line inductance',
                          non_zero=True,
                          default=0.001,
                          r=True,
                          )
        self.C = NumParam(unit='p.u.',
                          tex_name='C',
                          info='DC capacitance',
                          non_zero=True,
                          default=0.001,
                          g=True,
                          )
        self.bus1 = IdxParam(model='Bus')
        self.bus2 = IdxParam(model='Bus')
        
        self.I0 = NumParam(unit ='p.u,', default =1)
        self.Id10 = NumParam(unit ='p.u,', default =1)
        
        Model.__init__(self, system, config)
        self.a1 = ExtAlgeb(model="Bus", src="a", indexer = self.bus1)
        self.a2 = ExtAlgeb(model="Bus", src="a", indexer = self.bus2)
        
        self.v1 = ExtAlgeb(model="Bus", src="v", indexer = self.bus1)
        self.v2 = ExtAlgeb(model="Bus", src="v", indexer = self.bus2)
        
        self.I = State(tex_name='I',
                        info='Current',
                        unit='p.u.',
                        v_str='I0',
                        e_str='Id1'
                        )
                
        self.Id1 = State(tex_name='I',
                        info='Capacitor current',
                        unit='p.u.',
                        e_str='-I/(L*C) +R*Id1/L'
                        )
        
class V_Source_AC(ModelData, Model):
    def __init__(self, system, config):
        ModelData.__init__(self)
        
        self.Vs = NumParam(default=60)
        self.a = NumParam(default= 0)
        
        self.bus1 = IdxParam(model='Bus')
        self.bus2 = IdxParam(model='Bus')
        
        Model.__init__(self, system, config)
        self.a1 = ExtAlgeb(model="Bus", src="a", indexer = self.bus1)
        self.a2 = ExtAlgeb(model="Bus", src="a", indexer = self.bus2)
        
        self.v1 = ExtAlgeb(model="Bus", src="v", indexer = self.bus1)
        self.v2 = ExtAlgeb(model="Bus", src="v", indexer = self.bus2)
        
        self.V = Algeb(name="V",
                       info="voltage difference",
                       tex_name="V",
                       v_str="Vs*sin(a)",
                       e_str="Vs*sin(2*pi*sys_f*dae_t + a) - v2*sin(2*pi*sys_f*dae_t + a2) + v1*sin(2*pi*sys_f*dae_t + a1)",
                       )
        
class VSC_emt(ModelData, Model):
    def __init__(self, system, config):
        ModelData.__init__(self)
        self.PLL = IdxParam(name = "PLL1")
        self.bus = IdxParam(name = "Busabc")
        self.busfreq = IdxParam(name = "BusFreq")
        self.Sn = NumParam(default =1, info= "Active power reference")
        self.P_ref = NumParam(default =1, info= "Active power reference")
        self.Q_ref = NumParam(default =1, info= "Reactive power reference")
        self.Rl = NumParam(default = 0.1, info = "Resistance Value")        
        self.Ll = NumParam(default = 0.1, info = "Self-Inductance Value")
                
        Model.__init__(self, system, config)
        
        self.theta_m = ExtAlgeb(model="PLL1", src = "am", indexer = self.PLL)
        self.f = ExtAlgeb(model= "BusFreq", src = "f", indexer = self.busfreq)
        self.omega = Algeb(name = "omega", v_str = "2*pi*f", e_str="2*pi*f - omega")
        self.Ia = Algeb(name = "Current at a")
        self.Ib = Algeb(name = "Current at b")
        self.Ic = Algeb(name = "Current at c")
        self.va_g = ExtAlgeb(name = "voltage at grid connexion", model = 'Bus_abc', src = 'v_a', indexer = self.bus)
        self.vb_g = ExtAlgeb(name = "voltage at grid connexion", model = 'Bus_abc', src = 'v_b', indexer = self.bus)
        self.vc_g = ExtAlgeb(name = "voltage at grid connexion", model = 'Bus_abc', src = 'v_c', indexer = self.bus)
        
        
        #WE MAKE THE qd TRANSFORMATION
        self.I = DQtransform(ua = self.Ia, ub = self.Ib, uc = self.Ic, theta=self.theta_m, name='I')
        self.V = DQtransform(ua = self.Ia, ub = self.Ib, uc = self.Ic, theta=self.theta_m, name='V')
        
        #We define P,Q, iq*, id* algebraic variables
        self.P = Algeb(name = "P")
        self.Q = Algeb(name = "P")
        self.iqstar = Algeb(name="Iqstar")
        self.idstar = Algeb(name="Ipstar")
        
        self.P.v_str = "3/2*(V_q*I_q + V_d*I_d) " 
        self.iqstar.v_str = '(2/3)*Pref/V_q'
        self.idstar.v_str = '(2/3)*Qref/V_q'
        
        self.P.e_str = "3/2*(V_q*I_q + I_q*I_q) -P"
        #self.P.e_str = "3/2*(V_q*I_q + V_d*I_d) -P"
        self.Q.e_str = "3/2*(V_q*I_d + V_d*I_q) -Q"
        self.iqstar.e_str = '(2/3)*Pref/V_q - iqstar'
        self.idstar.e_str = '(2/3)*Qref/V_q - idstar'
        
        
        #WE DEFINE THE OUTER LOOP
        self.PIP = PIController(u = self.P_ref, kp = 1, ki = 1, ref = self.P)
        self.PIQ = PIController(u = self.Q_ref, kp = 1, ki = 1, ref = self.Q)
        
        #We DEFINE THE INNER LOOP 
        #ki = Ll/tau, Kp = rl/tau
        self.IL = Inner_Loop(iqstar=self.iqstar, idstar=self.idstar,
                                    iq=self.I.q, id=self.V.d, omega = self.omega, name='IL')
        
class VSC(PVD1):
    #Class defining a AC-DC converter
    #Obs be aware of p.u.
    def __init__(self, system, config):
        super().__init__(system, config)
        
        self.node1 = IdxParam(name="Node")
        self.node2 = IdxParam(name="Node")
        
        self.Vdc1 = ExtAlgeb(model="Node", src="v", indexer=self.node1)
        self.Vdc2 = ExtAlgeb(model="Node", src="v", indexer=self.node2)
        
        self.deltaV = Algeb(name="deltaV", 
                            e_str = "Vdc2 - Vdc1",
                            v_str = "Vdc2 - Vdc1 - deltaV") 
        self.Idc = Algeb(name= "Idc",
                        e_str = "deltaV/gammap*Sn",
                        v_str = "deltaV/gammap*Sn - Idc")
    
class GFMGFWConverter(REECA1, REGF1):
    def __init__(self, system, config):
        
        self.roleA = Discrete(name = 'ua', value = 1)
        REGF1.__init__(self, system, config)
        REECA1.__init__(self, system, config)
        
        model_GFM = REGF1(system, config)
        model_GFL = REECA1(system, config)
        
        self.ua = Discrete(info = 'discrete parameter defining role', value =1)
        conflicting_vars = []
        initial_var_GFM = []
        changed_var_GLW = []
        exceptions = ["u", "Sn", "Vn", "fn", "M", "D", "subidx"]
        
        all_vars = self._states_and_ext().values() + self._algebs_and_ext().values() + self._all_params.values()
        all_vars_name = [var.name for var in all_vars]
        for var_name in all_vars_name:
            in_GFM = hasattr(model_GFM, var_name)
            in_GFW = hasattr(model_GFL, var_name)
            in_exceptions = i in exceptions
            if in_GFM and in_GFW and (not in_exceptions):
                conflicting_vars += [var_name]
                
        
                
        for i, var in enumerate(self._states_and_ext().values()):
            var_name = var.name
            
            in_GFM = hasattr(model_GFM, var_name)
            in_GFW = hasattr(model_GFL, var_name)
            
            #We choose the equations depending on what 
            if in_GFM and in_GFM:
                e_eq1 = getattr(model_GFM, var_name).e_str
                v_eq1 = getattr(model_GFM, var_name).v_str
                e_eq2 = getattr(model_GFM, var_name).e_str
                v_eq2 = getattr(model_GFM, var_name).v_str
            elif in_GFM:
                e_eq1 = getattr(model_GFM, var_name).e_str
                v_eq1 = getattr(model_GFM, var_name).v_str
                e_eq2 = '0'
                v_eq2 = '0'
                continue
            elif in_GFW:
                e_eq1 = '0'
                v_eq1 = '0'
                e_eq2 = getattr(model_GFM, var_name).e_str
                v_eq2 = getattr(model_GFM, var_name).v_str
                continue
            
            var.e_eq = 'ua*('+e_eq1+') + (1-ua)*('+e_eq2+')'
            if var.v_eq is None:
                var.v_eq = 'ua*('+v_eq1+') + (1-ua)*('+v_eq2+')'
        
        for i, var in enumerate(self._states_and_ext().values()):
            var_name = var.name
            
            in_GFM = hasattr(model_GFM, var_name)
            in_GFW = hasattr(model_GFL, var_name)
            
            #We choose the equations depending on what 
            if in_GFM and in_GFM:
                e_eq1 = getattr(model_GFM, var_name).e_str
                v_eq1 = getattr(model_GFM, var_name).v_str
                e_eq2 = getattr(model_GFM, var_name).e_str
                v_eq2 = getattr(model_GFM, var_name).v_str
            elif in_GFM:
                e_eq1 = getattr(model_GFM, var_name).e_str
                v_eq1 = getattr(model_GFM, var_name).v_str
                e_eq2 = '0'
                v_eq2 = '0'
                continue
            elif in_GFW:
                e_eq1 = '0'
                v_eq1 = '0'
                e_eq2 = getattr(model_GFM, var_name).e_str
                v_eq2 = getattr(model_GFM, var_name).v_str
                continue
            
            var.e_eq = 'ua*('+e_eq1+') + (1-ua)*('+e_eq2+')'
            if var.v_eq == None:
                var.v_eq = 'ua*('+v_eq1+') + (1-ua)*('+v_eq2+')'
                
    def smooth_switching_GFL2GFM(self, idx):
        #we switch the operating mode on a smooth way
        uid = self.idx2uid(idx)
        
        self.set(src ='ua', idx = idx, value =0)
        self.set(src ='delta', idx = idx, value =0)
        
        v = self.v.v[uid] 
        Iq = self.Pe.v[uid]/v
        Ip = self.Qe.v[uid]/v
        
        self.set(src ='S1_y', idx = idx, value = -Iq)
        self.set(src ='S2_y', idx = idx, value = v)
        self.set(src ='S0_y', idx = idx, value = Ip)
        
        #alternativa suponer Steady-State y hacer ia = ip + j*iq y el resto a 120º 
        
    def smooth_switching_GFM2GFL(self, idx):
        #we switch the operating mode on a smooth way
        uid = self.idx2uid(idx)
        
        self.set(src ='ua', idx = idx, value =1)
        
        delta0 = self.pll.thetam[uid]
        Id0 = self.Pe.v[uid]/self.v.v[uid]
        Iq0 = self.Qe.v[uid]/self.v.v[uid]
        ud0 = self.vd.v[uid]
        uq0 = self.vq.v[uid]

        self.set(src ='dw', idx = idx, value = 0)
        self.set(src ='delta', idx = idx, value = delta0)
        self.set(src ='PIvd_xi', idx = idx, value = Iq0)
        self.set(src ='PIvq_xi', idx = idx, value = Id0)
        self.set(src ='PIId_xi', idx = idx, value = 0)
        self.set(src ='PIIq_xi', idx = idx, value = 0)
        self.set(src ='udLag_y', idx = idx, value = ud0)
        self.set(src ='uqLag_y', idx = idx, value = uq0)
        