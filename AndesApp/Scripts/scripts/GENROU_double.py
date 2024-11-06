import numpy as np
import andes.core as core
from andes.core import (Model, ModelData, NumParam, ConstService, Algeb, ExtAlgeb, 
                        ExtState, LessThan, State, Limiter, Discrete, IdxParam)
from andes.core.service import InitChecker, FlagValue
from andes.models.exciter import ExcQuadSat
from andes.models.synchronous.genbase import GENBaseData, GENBase, Flux0, Flux2
from andes.models.synchronous.genrou import GENROUData, GENROUModel, GENROU
from andes.models.bus import Bus
from andes.models.line import Line
from andes.models.area import Area
import andes as ad
import sympy as sp

def addchar_to_variables(expression, char = "", excpt = []):
    vars = expression.free_symbols
    vars = [item for item in vars if item not in excpt]
    for var in vars:
        new_var = sp.Symbol( str(var) + char)
        expression = expression.subs(var, new_var)
    
    return expression

def neighbours(system, bus, degree = 2):
    #given a system and bus belonging to that system
    #
    neighbours = {}
    return neighbours

def model_to_double(system, model, idx, config):
    #transform the device
    original_bus = model.bus.v[idx]
    
    #We disconnect the actual device
    model.alter("u", idx, 0)
    
    vmin = 0.9
    vmax = 1.1
    system.add(system.Line_Conditional, (True, vmin, vmax))
    system.add(system.Line_Conditional, (True, vmin, vmax))

class Line_Conditional(Line):
    def __init__(self, system, bus_config, vmin, vmax):
        Line.__init__(system, bus_config)
        
        self.d =  Limiter(u=self.v1, lower=vmin, upper=vmax,
            enable=self.config.pq2z)
        self.a1.e_str = "d*" + self.a1.e_str + " + a1 * (d - 1)" 
        self.v1.e_str = "d*" + self.v1.e_str + " + v1 * (d - 1)" 
        self.a2.e_str = "d*" + self.a2.e_str + " + 0 * (d - 1)" 
        self.v2.e_str = "d*" + self.v2.e_str + " + 0 * (d - 1)" 
        
class Line_Info(Model, ModelData):
    #create a line where info is shared between buses
    def __init__(self, system):
        ModelData.__init__(self, system)
        Model.__init__(self, system)
        self.group = 'ACLine'
        self.flags.pflow = True
        self.flags.tds = True 
        
        self.bus1 = IdxParam(model='Bus', info="idx of to bus")
        self.bus2 = IdxParam(model='Bus', info="idx of from bus")
        
        self.v1 = ExtAlgeb(model='Bus', src='v', indexer=self.bus1, tex_name='v_1',
                           info='voltage magnitude of the from bus',
                           ename='vij',
                           tex_ename='v_ij',
                           )
        self.v2 = ExtAlgeb(model='Bus', src='v', indexer=self.bus2, tex_name='v_2',
                           info='voltage magnitude of the from bus',
                           ename='vij',
                           tex_ename='v_ij',
                           )
        self.vinfo = Algeb(info='Shared info',
                          tex_name='V_{info}',
                          v_str= 'v0',
                          e_str= 'v1/2 + v2/2',
                          )

class Bus_info(Bus):
    def __init__(self, system, config):
        super().__init__(system, config)
        self.BackRef()

def create_custom_infolink(config, Class_type):
    class Custom_infolink(Model, ModelData, Class_type):
        def __init__(self, system=None, config=None):
            ModelData.__init__(self, system)
            Model.__init__(self, system)
            self.group = 'ACLine'
            self.flags.pflow = True
            self.flags.tds = True 

            self.bus1 = IdxParam(model='Bus', info="idx of to bus")
            self.bus2 = IdxParam(model='Bus', info="idx of from bus")

            self.v1 = ExtAlgeb(model='Bus', src='v', indexer=self.bus1, tex_name='v_1',
                               info='voltage magnitude of the from bus',
                               ename='vij',
                               tex_ename='v_ij',
                               )
            self.v2 = ExtAlgeb(model='Bus', src='v', indexer=self.bus2, tex_name='v_2',
                               info='voltage magnitude of the from bus',
                               ename='vij',
                               tex_ename='v_ij',
                               )
            self.vinfo = Algeb(info='Shared info',
                              tex_name='V_{info}',
                              v_str= 'v0',
                              e_str= 'v1/2 + v2/2',
                              )
    return Custom_infolink

class GENROU_double(GENROU):
    def __init__(self, system, vmin, vmax, config1, config2):
        super().__init__(system, config1)
        
        self.vlimiter = Limiter(u=self.v, lower=vmin, upper=vmax,
            enable=self.config.pq2z)
        
        gen_mode1 = GENROU(system, config1) 
        gen_mode2 = GENROU(system, config2)
        exceptions = gen_mode1._algebs_and_ext()
        exceptions += gen_mode1._states_and_ext()
        exceptions = [sp.Symbol(var.name) for var in exceptions]
        
        for i, var in enumerate(self._algebs_and_ext()):
            name = var.name
            e_str_mode1 = sp.simpify(getattr(gen_mode1, name).e_str) 
            v_str_mode1 = sp.simpify(getattr(gen_mode1, name).v_str) 
            e_str_mode2 = sp.simpify(getattr(gen_mode2, name).e_str) 
            v_str_mode2 = sp.simpify(getattr(gen_mode2, name).v_str) 
            
            e_str_mode1 = addchar_to_variables(e_str_mode1, string = "a", excpt = exceptions)
            v_str_mode1 = addchar_to_variables(v_str_mode1, string = "a", excpt = exceptions)
            e_str_mode2 = addchar_to_variables(e_str_mode2, string = "b", excpt = exceptions)
            v_str_mode2 = addchar_to_variables(v_str_mode2, string = "b", excpt = exceptions)
            
            var_v_out = sp.Symbol("v_zl") + sp.Symbol("v_zu")
            var.e_str = var_v_out*e_str_mode1 + sp.Symbol("v_zi")*e_str_mode2                   
            var.e_str = str(var.e_str)                   
            var.v_str = var_v_out*v_str_mode1 + sp.Symbol("v_zi")*v_str_mode2   
            var.v_str = str(var.v_str)    
        
        for i, var in enumerate(self._states_and_ext()):
            name = var.name
            e_str_mode1 = sp.simpify(getattr(gen_mode1, name).e_str) 
            v_str_mode1 = sp.simpify(getattr(gen_mode1, name).v_str) 
            e_str_mode2 = sp.simpify(getattr(gen_mode2, name).e_str) 
            v_str_mode2 = sp.simpify(getattr(gen_mode2, name).v_str) 
            
            e_str_mode1 = addchar_to_variables(e_str_mode1, string = "a")
            v_str_mode1 = addchar_to_variables(v_str_mode1, string = "a")
            e_str_mode2 = addchar_to_variables(e_str_mode2, string = "b")
            v_str_mode2 = addchar_to_variables(v_str_mode2, string = "b")
            
            var_v_out = sp.Symbol("v_zl") + sp.Symbol("v_zu")
            var.e_str = var_v_out*e_str_mode1 + sp.Symbol("v_zi")*e_str_mode2                   
            var.e_str = str(var.e_str)                   
            var.v_str = var_v_out*v_str_mode1 + sp.Symbol("v_zi")*v_str_mode2   
            var.v_str = str(var.v_str)                             

        #we change the parameters to variables                                                                                                                                           
        for i, var in enumerate(gen_mode2._all_params()):
            name = var.i.__name__
            name_a = var.i.__name__ + "a"
            name_b = var.i.__name__ + "b"
            setattr(self, name_a, gen_mode1.var)
            setattr(self, name_b, gen_mode2.var)