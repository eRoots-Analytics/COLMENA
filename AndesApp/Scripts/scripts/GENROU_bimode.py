import numpy as np
import andes.core as core
from andes.core import NumParam, ConstService, Algeb, ExtAlgeb, ExtState, LessThan, State, Limiter, Discrete, IdxParam
from andes.core.service import InitChecker, FlagValue
from andes.models.exciter import ExcQuadSat
from andes.models.synchronous.genbase import GENBaseData, GENBase, Flux0, Flux2
from andes.models.synchronous.genrou import GENROUData, GENROUModel, GENROU
from andes.models.area import Area
import andes as ad
import sympy as sp
import re 

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

def create_append_letter_function(letter):
    def append_letter(match):
        return match.group(0) + letter
    return append_letter

class GENROU_bimode(GENROU):
    def __init__(self, system, config):
        super().__init__(system, config)
        self.group = "DiscreteModel"
        vmin = 0.9
        vmax = 1.1
        self.vlimiter = Limiter(u=self.v, lower=vmin, upper=vmax,
            enable=True)
        
        self.Areac = IdxParam(info ='areac id', mandatory = False)
        self.Neighborhood = IdxParam(info ='areac id', mandatory = False)
        gen_mode1 = GENROU(system, config) 
        gen_mode2 = GENROU(system, config)
        exceptions1 = gen_mode1._algebs_and_ext()
        exceptions2 = gen_mode1._states_and_ext()
        exceptions  = [sp.Symbol(var) for var in exceptions1.keys()]
        exceptions += [sp.Symbol(var) for var in exceptions2.keys()]
        all_params = gen_mode1._all_params()
        
        #We change the equations for algebraic an
        for i, var in enumerate(self._algebs_and_ext().values()):
            e_eq1 = var.e_str
            e_eq2 = var.e_str
            v_eq1 = var.v_str
            v_eq2 = var.v_str
            for j, param in enumerate(all_params.values()):
                name = param.name
                pattern_a = re.escape(name) + r'(?!' + re.escape("a") + r')'
                pattern_b = re.escape(name) + r'(?!' + re.escape("b") + r')'
                append_letter_a = create_append_letter_function("a")
                append_letter_b = create_append_letter_function("b")
                e_eq1 = re.sub(pattern_a, append_letter_a, e_eq1)
                e_eq2 = re.sub(pattern_b, append_letter_b, e_eq2)
                
                if v_eq1 != None:
                    v_eq1 = re.sub(pattern_a, append_letter_a, v_eq1)
                if v_eq2 != None:
                    v_eq2 = re.sub(pattern_b, append_letter_b, v_eq2) 

            v_out = "(v_zl + v_zu)"
            v_in = "v_zi"   
                
            var.e_str = v_out + "*" + e_eq1 + " + " +  v_in + "*" + e_eq2                
            try: 
                var.v_str = v_out + "*" + v_eq1 + " + " +  v_in + "*" + v_eq2    
            except:
                _ = 0
                
        for i, var in enumerate(self._states_and_ext().values()):
            name = var.name
            e_eq1 = var.e_str
            e_eq2 = var.e_str
            v_eq1 = var.v_str
            v_eq2 = var.v_str
            for j, param in enumerate(all_params.values()):
                name = param.name
                pattern_a = re.escape(name) + r'(?!' + re.escape("a") + r')'
                pattern_b = re.escape(name) + r'(?!' + re.escape("b") + r')'
                append_letter_a = create_append_letter_function("a")
                append_letter_b = create_append_letter_function("b")
                e_eq1 = re.sub(pattern_a, append_letter_a, e_eq1)
                e_eq2 = re.sub(pattern_b, append_letter_b, e_eq2)
                
                if v_eq1 != None:
                    v_eq1 = re.sub(pattern_a, append_letter_a, v_eq1)
                if v_eq2 != None:
                    v_eq2 = re.sub(pattern_b, append_letter_b, v_eq2) 

            v_out = "(v_zl + v_zu)"
            v_in = "v_zi"   
            var.e_str = v_out + "*" + e_eq1 + " + " +  v_in + "*" + e_eq2                
            try: 
                var.v_str = v_out + "*" + v_eq1 + " + " +  v_in + "*" + v_eq2    
            except:
                _ = 0                             

        #exceptions = ["u", "Sn", "Vn"]
        #we change the parameters to variables
        for name in gen_mode1._all_params().keys():
            if name in exceptions:
                continue
            var1 = getattr(gen_mode1, name)
            var2 = getattr(gen_mode2, name)
            name_a = name + "a"
            name_b = name + "b"
            var1.name = name_a
            var2.name = name_b
            
            delattr(self, name)
            setattr(self, name_a, var1)
            setattr(self, name_b, var2)
        
class GENROU_arealimit(GENROU):
    def __init__(self, system, vmin, vmax, config1, config2):
        super().__init__(system, config1)
        
        self.vlimiter = Limiter(u=self.v, lower=vmin, upper=vmax,
            enable=self.config.pq2z)
        
        gen_mode1 = GENROU(system, config1) 
        gen_mode2 = GENROU(system, config2)
        
        self.Areac = IdxParam(info ='areac id', mandatory = False)
        self.Neighborhood = IdxParam(info ='areac id', mandatory = False)
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
                          