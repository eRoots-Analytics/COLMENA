import numpy as np
import andes.core as core
from andes.core import NumParam, DataParam, ExtParam, ConstService, Algeb, ExtAlgeb, NumReduce, NumRepeat, IdxRepeat, Limiter, Discrete, IdxParam
from andes.core.service import InitChecker, FlagValue, DeviceFinder, RefFlatten
from andes.models.exciter import ExcQuadSat
from andes.models.synchronous.genbase import GENBaseData, GENBase, Flux0, Flux2
from andes.models.synchronous.genrou import GENROUData, GENROUModel, GENROU
from andes.models.area import Area
from andes.models.line import Line
from andes.core.model import Model, ModelData
from andes.models.dc import Node
from andes.core.block import PIController
import andes as ad
import sympy as sp
import re 

def addchar_to_variables(expression, char = "", var = False, excpt = []):
    
    if isinstance(var, bool):
        vars = expression.free_symbols
    else:
        vars = [var]

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

def add_letter_except(text, pattern, letter_to_add):
    # Define a regex pattern to find the pattern not followed by a letter or digit
    regex = re.compile(r'({})(?![a-zA-Z0-9_])'.format(re.escape(pattern)))

    # Function to be used in sub to add the letter after the pattern
    def replace(match):
        return match.group(1) + letter_to_add

    # Replace the pattern with the pattern followed by the letter
    result = regex.sub(replace, text)

    return result

class GENROU_controlled(GENROU):
    def __init__(self, system, config):
        param = "M"
        epsilon = 0.003
        vmax = 1 + 0.003
        vmin = 1 - 0.003
        self.Ma = NumParam(default = 15)
        self.Mb = NumParam(default = 150)
        delattr(self, param)
        self.M = Algeb(name = "Mref",
                          v_str = "M - PI_y")
        self.vlim = Limiter(u=self.omega, lower=vmin, upper=vmax,
            enable=True)
        v_out = "(vlim_zl + vlim_zu)"
        v_in = "vlim_zi"
        self.e_error = Algeb(name = "error", 
                             v_str = v_in + "*Ma" +  v_out + "*Mb",
                             e_str = v_in + "*Ma" +  v_out + "*Mb" + "- M")
        self.PI = PIController(u= self.M_error) 
        self.M 
        
class GENROU_bimode(GENROU):
    def __init__(self, system, config):
        super().__init__(system, config)
        self.group = "SynGen"
        epsilon = 0.003
        vmin = 1 - epsilon
        vmax = 1 + epsilon
        self.vlim = Limiter(u=self.omega, lower=vmin, upper=vmax,
            enable=True)
        
        gen_mode1 = GENROU(system, config) 
        gen_mode2 = GENROU(system, config)
        all_params = gen_mode1._all_params()
        v_out = "(vlim_zl + vlim_zu)"
        v_in = "vlim_zi" 
        
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
                e_eq1 = add_letter_except(e_eq1, name, "a")
                e_eq2 = add_letter_except(e_eq2, name, "b")
                
                if v_eq1 != None:
                    v_eq1 = add_letter_except(v_eq1, name, "a")
                if v_eq2 != None:
                    v_eq2 = add_letter_except(v_eq2, name, "b")
  
            var.e_str = v_out + "*(" + e_eq1 + ") +" +  v_in + "*(" + e_eq2 + ")"
            if var.v_str == "":
                continue                
            if var.v_str is not None:              
                try: 
                    var.v_str = v_out + "*(" + v_eq1 + ") +" +  v_in + "*(" + v_eq2 + ")"    
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
                e_eq1 = add_letter_except(e_eq1, name, "a")
                e_eq2 = add_letter_except(e_eq2, name, "b")
                
                if v_eq1 != None:
                    v_eq1 = add_letter_except(v_eq1, name, "a")
                if v_eq2 != None:
                    v_eq2 = add_letter_except(v_eq2, name, "b")


            v_out = "(vlim_zl + vlim_zu)"
            v_in = "vlim_zi"   
            var.e_str = v_out + "*(" + e_eq1 + ") +" +  v_in + "*(" + e_eq2 + ")"
            if var.v_str == "":
                continue
            if var.v_str is not None:
                try: 
                    var.v_str = v_out + "*(" + v_eq1 + ") +" +  v_in + "*(" + v_eq2 + ")"    
                except:
                    _ = 0                             

        exceptions = ["u", "Sn", "Vn", "fn", "M", "D", "subidx"]
        #we change the parameters to variables
        for name in gen_mode1._all_params().keys():
            
            var1 = getattr(gen_mode1, name)
            var2 = getattr(gen_mode2, name)
            name_a = name + "a"
            name_b = name + "b"
            var1.name = name_a
            var2.name = name_b

            setattr(self, name_a, var1)
            setattr(self, name_b, var2)
            
            if name not in exceptions and False:
                delattr(self, name)
        
        for var in self.discrete.values():
            u = var.u
            u_owner = u.owner.__class__.__name__
            class_name = __class__.__name__
            if  u_owner != __class__.__name__:
                u_name = u.name
                try:
                    var.u = getattr(self, u_name + var.name[-1])
                except:
                    var.u = getattr(self, u_name)
                    
        e_eq1 = '(tm - te - D * (omega - 1))'
        e_eq2 = '(tm - te - D * (omega - 1))'
        self.omega.e_str = v_out + "*(" + e_eq1 + "*(Ma**-1)) +" +  v_in + "*(" + e_eq2 + "*(Mb**-1))"

class Areac(Area):
    def __init__(self, system, config):
        super().__init__(system, config)
        
        self.one = NumParam(default=1)
        self.ones = NumRepeat(u =self.one, ref = self.Bus)
        self.pidx = IdxRepeat(u=self.idx, ref=self.Bus)
        self.N = NumReduce(u=self.ones, fun=np.sum, ref = self.Bus)
        
        self.BusIdx = RefFlatten(ref = self.Bus)
        self.v = ExtAlgeb(model='Bus', src='v', indexer=self.Bus)
        self.v_mean = NumReduce(u=self.v, fun=np.mean, ref=self.Bus)
           
class Areac3(Area):
    def __init__(self, system, config):
        super().__init__(system, config)
        
        v_mean_string = "" 
        e_mean_string = ""
        if system is not None:
            Buses_v = system.Bus.idx.v
        else: 
            Buses_v = [i  for i in range(1,10)] 
        for i, id in enumerate(Buses_v):
            bus_i = IdxParam(model='Bus', default=id)
            v_name = "v" + str(id)
            param_name = "inbus" + str(id)
            
            #Next line probably not needed
            setattr(self, "bus" + str(id), bus_i)
            ext_alg = ExtAlgeb(model= "Bus", src = "v", indexer = getattr(self, "bus" + str(id)), tex_name='v_'+ str(id),
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
                       )

class Neighbourhood(Model, ModelData):
    def __init__(self, system, config):
        ModelData.__init__(self)
        self.bus = IdxParam(model='Bus')
        self.auxline = IdxParam(model='Line')
        self.auxbus = IdxParam(model='Bus')
        
        Model.__init__(self, system, config)
        self.lines1 = DeviceFinder(self.auxline, link = self.bus, idx_name ='bus1', default_model='Line', auto_add=False)
        self.lines2 = DeviceFinder(self.auxline, link = self.bus, idx_name ='bus2', default_model='Line', auto_add=False)
        self.bus2 =  ExtParam(model='Line', src='bus2', indexer=self.lines1)
        self.bus1 =  ExtParam(model='Line', src='bus1', indexer=self.lines2)
    
    def neighbourhood_setup(self):
        lines1 = [item for item in self.lines1.v if item is not None]
        lines2 = [item for item in self.lines2.v if item is not None]
        bus1 = [item for item in self.bus1.v if item is not None]
        bus2 = [item for item in self.bus2.v if item is not None]
        self.lines = lines1 + lines2
        self.buses = bus1 + bus2

class Buffer(ModelData, Model):
    def __init__(self, system, config):
        ModelData.__init__(self)
        #string parameter 
        self.buffer = DataParam(info='buffer')
        
class Toggle_Line(Line):
    def __init__(self, system, config):
        super().__init__(system, config) 
        self.connect = NumParam(default=1)
        for name, var in self.algebs_ext.items():
            var.e_str = 'connect*'+var.e_str + '+(1-connect)*'+name
            
def create_custom_switch_model(base_model, model_name):
    class CustomModel(base_model):
        def __init__(self, system, config):
            super().__init__()
            
            self.connect = Discrete(default=1)
            self.vaux = Algeb(default=0, name='vaux')
            
            for i, var in enumerate(self._states_and_ext().values()):
                name = var.name
                if name == 'Bus':
                    continue
                e_eq = var.e_str
                v_symbol = sp.Symbol('v')
                connect_symbol = sp.Symbol('connect')
                v_connect = v_symbol*connect_symbol
                new_eq = e_eq.subs(v_symbol, v_connect)
                var.e_str = new_eq
                
            for i, var in enumerate(self._algebs_and_ext().values()):
                name = var.name
                if name == 'Bus':
                    continue
                e_eq = var.e_str
                v_symbol = sp.Symbol('v')
                connect_symbol = sp.Symbol('connect')
                v_connect = v_symbol*connect_symbol
                new_eq = e_eq.subs(v_symbol, v_connect)
                var.e_str = new_eq
                
            self.Bus.e_str = 'connect*'+(self.Bus.e_str) + '(1-connect)*vaux'
            CustomModel.__name__ = model_name
            
    return CustomModel   