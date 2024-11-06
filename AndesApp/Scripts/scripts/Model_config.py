import numpy as np
import andes.core as core
from andes.core import NumParam, ConstService, Algeb, ExtAlgeb, ExtState, LessThan, State, Limiter, Discrete
from andes.models.synchronous.genrou import GENROUData, GENROUModel, GENROU
from andes.core.service import InitChecker, FlagValue
from andes.models.exciter import ExcQuadSat
from andes.models import Area
import andes as ad
import sympy as sp

def neighbours(system, bus, degree = 2):
    #given a system and bus belonging to that system
    #
    neighbours = {}
    return neighbours

class Area_colmena(Area):
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
            
        self.vmean = Algeb(name='vmean',
                       tex_name=r'v_mean',
                       info='mean voltage',
                       unit='p.u.',
                       is_output=True,
                       e_str = e_mean_string,
                       v_str = v_mean_string
                       )
        
class GENROU_area(GENROU):
    def __init__(self, system, config):
        super().__init__(system, config)
        
        self.vmean = ExtAlgeb(model='Area_colmena', src='v_mean', indexer=self.v_area, tex_name='v_area',
                           info='mean voltage of the buses belonging to the area',
                           ename='v_mean',
                           tex_ename='v_mean',
                           )
        
        self.vmean_lim =  Limiter(u=self.vmean, lower=0.9*self.vn, upper=1.1*self.vn,
            enable=self.config.pq2z)