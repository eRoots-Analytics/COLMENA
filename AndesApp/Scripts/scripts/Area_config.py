import numpy as np
import andes.core as core
from andes.core import NumParam, ConstService, Algeb, ExtAlgeb, ExtState, LessThan, State, Limiter, Discrete, IdxParam
from andes.models.synchronous.genrou import GENROUData, GENROUModel, GENROU
from andes.core.service import InitChecker, FlagValue
from andes.models.exciter import ExcQuadSat
from andes.models.area import Area
import andes as ad
import sympy as sp

def neighbours(system, bus, degree = 2):
    #given a system and bus belonging to that system
    #
    neighbours = {}
    return neighbours

class Area_Colmena(Area):
    def __init__(self, system, config1):
        super().__init__(system, config1)
        
        v_mean_string = "" 
        e_mean_string = ""
        for id, buses in zip(self.idx.v, self.Bus.v):
            N_area = len(buses)
            v_mean_string_area = ""
            e_mean_string_area = ""
            
            for bus in buses:
                v_name = "v" + str(bus)
                ext_alg = Algeb(name='a',
                       tex_name=r'\theta',
                       info='voltage angle',
                       unit='rad',
                       is_output=True,
                       ) 
                setattr(self, v_name, ext_alg)
                v_mean_string_area += " + " + v_name
                e_mean_string_area += " + " + v_name
                
            indicator_str = "Indicator(idx =" + str(id) + ")/" + str(N_area)
            v_mean_string += indicator_str + v_mean_string_area 
            e_mean_string += indicator_str + e_mean_string_area
            
        self.vmean = Algeb(name='v_mean',
                       tex_name=r'v_mean',
                       info='mean voltage',
                       unit='p.u.',
                       is_output=True,
                       e_str = e_mean_string,
                       v_str = v_mean_string
                       )

class Area_Colmena_General(Area):
    def __init__(self, system, config1):
        super().__init__(system, config1)
        
        v_mean_string = "" 
        e_mean_string = ""
        for i, bus in enumerate(system.Bus.idx):
            v_name = "v" + bus.name
            param_name = "in" + bus.name
            
            #Next liune probably not needed
            #setattr(self, "bus" + bus.name, bus)
            ext_alg = ExtAlgeb(model= "Bus", src = "v", indexer = bus, tex_name='v_'+ str(bus),
                           info='voltage magnitude of the from bus',
                           ename='Qij',
                           tex_ename='Q_{ij}',
                           )
            num_param = NumParam(default = 0, info = "indicator", tex_name="id_"+str(i))
            
            setattr(self, v_name, ext_alg)
            setattr(self, param_name, num_param)
            e_mean_string += "+ " + v_name + "*" + param_name
            v_mean_string += "+ " + v_name + "0" + "*" + param_name + "0"
            
            
            
        self.vmean = Algeb(name='v_mean',
                       tex_name=r'v_mean',
                       info='mean voltage',
                       unit='p.u.',
                       is_output=True,
                       e_str = e_mean_string,
                       v_str = v_mean_string
                       )
        
class GENROU_Global(GENROU):
    def __init__(self, system, config):
        super().__init__(system, config)
        
        self.area_col = IdxParam(model='Area_Colmena', info="Area Colmena")
        
        self.v_mean = ExtAlgeb(model='Area_Colmena', src='v_mean', indexer=self.area_col, tex_name='v_{mean}',
                           info='mean voltage',
                           ename='v_mean',
                           )
        
        self.vlimiter = Limiter(u=self.v_mean, lower=0.9*self.Vn, upper=1.1*self.Vn, enable=True)