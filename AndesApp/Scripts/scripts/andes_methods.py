import andes
import numpy as np
import tensorly as tl
import copy
import os
import scipy.linalg
import tensorly.contrib.sparse.decomposition as tl_sparse
from scipy.integrate import odeint
from itertools import product
from scipy.optimize import root
from scipy.sparse import coo_array
import matplotlib.pyplot as plt
#import tensorflow as tf
import re
import io
import itertools as it
import tensorly.contrib.sparse as tlsp

import sympy as sp
from scipy.optimize import approx_fprime

def extract_number_of_devices(output):
    # Updated regular expression to match both "1 device" and "x devices"
    match = re.search(r'\((\d+) devices?\)', output)
    if match:
        return int(match.group(1))
    else:
        return None

def get_dimensions(nested_list):
    if isinstance(nested_list, list):
        if len(nested_list) == 0:
            return (0,)
        else:
            return (len(nested_list),) + get_dimensions(nested_list[0])
    else:
        return ()

def create_list_with_shape(t, initial_value = 0):
    if len(t) == 1:
        return [initial_value] * t[0]
    else:
        return [create_list_with_shape(t[1:], initial_value) for _ in range(t[0])]

def access_nested_list(nested_list, indices, value=None):
    result = nested_list
    for index in indices[:-1]:
        result = result[index]
    
    if value is not None:
        result[indices[-1]] = value
    else:
        return result[indices[-1]]

def numerical_system(sys):
    print("sys class name is", sys.__class__.__name__)
    print(dir(sys))
    for model in sys.models:
        dir_model = dir(model)
        for attr in dir_model:
            obj = getattr(model, attr)
            print("new object")
            print(obj.__class__.__name__)
            print(dir(obj))  
            
def get_attributes(var):
    for attr in dir(var):
        obj = getattr(var, attr)
        print("new object of name", attr)
        print(obj.__class__.__name__)
        print(obj)

def mononial_to_index(var, vars_dict, equation, index, order = 2):
    #finds the appropriate index
    #for a monomial
    
    try:
        a = vars_dict[var]
    except:
        raise Exception("error: the variable passed as argument is not a key for the dictionry var_dict")
    
    problem_vars = set(vars_dict.keys())
    eq_vars = equation.free_symbols
    vars_intersection = problem_vars.intersection(eq_vars)
    
    if equation == 1 or len(vars_intersection) == 0:
        return index, equation
    
    begin = next((x for x in index if x != 0), None)
    if begin == None:
        begin = 0
    
    subs_1 = equation.subs(var, 1)
    subs_2 = equation.subs(var, 2)
    division = sp.simplify(subs_2/subs_1)
    var_degree = np.log2(int(division.evalf()))
    var_degree = int(var_degree)
        
    for i in range(var_degree):
        index[begin + i] = vars_dict[var]
    
    if equation.is_constant():
        return index, equation
    
    new_eq = sp.simplify(equation.subs(var, 1))
    new_var = list(equation.free_symbols)[0]
    #take only wars that are polynomial

    return mononial_to_index(new_var, vars_dict, new_eq, index, order = 2)

def prepare_all_models(sys):
    for model in sys.models:
        try:
            model.prepare()
            print("model prepared")
        except:
            _ = 0 
    return

def symbolic_to_tensor(vars, eq, vars_dict, order = 2):
    n = len(vars)
    set_of_vars = set(vars)
    F_shape = (n+1,)*order
    F_eq_float = np.zeros(F_shape)
    
    eq = eq.expand()
    monomials = eq.as_ordered_terms()
    coefficients = eq.as_coefficients_dict()
    
    for j, monom in enumerate(monomials):
        print("monomnial is", monom)
        vars_in_monom =  monom.free_symbols
        vars_in_monom = list(set_of_vars & vars_in_monom)
        index0 = np.zeros(order)
        index0 = index0.astype(int)

        if len(vars_in_monom) == 0:
            F_eq_float[index0] = F_eq_float[index0] + coefficients_list[j]
            continue
        else:
            var = vars_in_monom[0]
            
        res_index, coeff = mononial_to_index(var, vars_dict, monom, index0)
        coefficients_list = list(coefficients.values())
        print("coef float", coefficients_list[j])
        print("coef sympy", coeff)
        
        print("monom is ", monom)
        res_index = res_index.astype(int)
        F_eq_float[tuple(res_index)] += coefficients_list[j]
        
    return F_eq_float

def param_substitution(mdl, eq, device): 
    
    if type(eq) == int:
        return eq
    for param_name, param_v in mdl.params.items():
        param_name = sp.Symbol(param_name)
        if param_name in eq.free_symbols:
            param_value = param_v.v[device]
            eq = eq.subs(param_name, param_value)
    for param_name, param_v in mdl.params_ext.items():
        param_name = sp.Symbol(param_name)
        if param_name in eq.free_symbols:
            param_value = param_v[device]
            eq = eq.subs(param_name, param_value)
            
    return eq

def set_parameters(F, model, idx, order=2):
    F_shape = get_dimensions(F)
    F_res = np.zeros(F_shape)
    for index in np.ndindex(F_shape):
        sp_expr = access_nested_list(F, index)
        for param in sp_expr.free_symbols:
            param_value = model.param[param.name][model.idx[idx]]
            sp_expr = sp_expr.subs(param, param_value)
            
        F_res[index] = float(sp_expr)
    return F_res

def explore_andes_system(sys):
    for model in sys.models.values():
        idx = getattr(model, "idx", None)
        buffer = io.StringIO()
        print(model, file=buffer)
        output = buffer.getvalue()
        buffer.close()
        num_devices = extract_number_of_devices(output)
        if  idx is not None and num_devices >=1:
            print(f"idx is {idx} for model {idx}")
            print(f" number of device is {num_devices}")
            print(idx.get_names())
            print(idx.v)
            for identificator in idx.v:
                a = 0
                try:
                    b = model[identificator]
                except:
                    a=0

def g_islands(sys):
    """
    Reset algebraic mismatches for islanded buses.
    """
    if sys.Bus.n_islanded_buses == 0:
        return
    sys.dae.g[sys.Bus.islanded_a] = 0.0
    sys.dae.g[sys.Bus.islanded_v] = 0.0    
    return 0

def e_to_dae(sys, eq_name = ('f', 'g'), order = 2):
    F_tensor = np.zeros((sys.dae.n + sys.dae.m,)*order)
    if isinstance(eq_name, str):
        eq_name = [eq_name]

    for name in eq_name:
        for i, var in enumerate(sys._adders[name]):
            np.add.at(sys.dae.__dict__[name], var.a, var.e)
            print(f" iteration i")
            print("new e str ", var.e_str)
            print("new v str ", var.v_str)
            print("new v ", var.v)
            print(f"new r {var.tex_name}", var.r)
        for var in sys._setters[name]:
            np.put(sys.dae.__dict__[name], var.a, var.e)
            print("var setters")  
            
    return F_tensor

def fg_to_tensor(sys):
    F = e_to_dae(sys, ('f', 'g'))
    
    # reset mismatches for islanded buses
    g_islands(sys)
    
    # update variable values set by anti-windup limiters
    for item in sys.antiwindups:
        if len(item.x_set) > 0:
            for key, val, _ in item.x_set:
                np.put(sys.dae.x, key, val)

    return F

def alt_prepare(sys):
    sys.syms.generate_symbols()
    sys.syms.generate_subs_expr()
    sys.syms.generate_equations()
    sys.syms.generate_services()
    sys.syms.generate_jacobians()
    return

def build_var_dict(equations):
    vars = {}
    for eq in equations:
        vars = vars|eq.free_symbols
        
    vars_dict = {}
    for i, var in enumerate(vars):
        vars_dict[var] = i
    
    return vars_dict

def update_tensor(F_equations, F, bus_info=None, homogeneous=True):
    #Given a set of p equations define by F
    #add those equation to thye existing saved equations F
    if not homogeneous:
        F_eq_const = F_equations[0,0,:]
        F_eq_linear = F_equations[0,:,:]
        F_equations = F_equations[1:,1:,:]
    
    n1, n1, l1 = F.shape
    n2, n2, l2 = F_equations.shape
    
    if bus_info == None:
        F_res_shape = (n1 + n2, n1 + n2, l1 + l2)
    else:
        bus_ids, bus_dict = bus_info
        F_res_shape = (n1 + n2, n1 + n2, l1 + l2 + 2*len(bus_id))
        
    F_res = np.zeros(F_res_shape)
    F_res[:n1, :n1, :l1] = F
    F_res[n1:(n1 + n2), n1:(n1 + n2), l1:(l1 + l2)] = F_equations
    
    if not homogeneous:
        F_res[0,0,l1:l2] += F_eq_const
        F_res[0,:,l1:l2] += F_eq_linear
        
    if bus_info == None:
        return F_res
    
    for i, bus_id in enumerate(bus_ids):
        F_res[(n1 + n2) - 2*i - 1: 0: (l1 + l2) + i] = 1
        F_res[bus_dict[bus_id][0]: 0: (l1 + l2) + i] = -1
        
        F_res[(n1 + n2) - 2*i - 2: 0: (l1 + l2) + i] = 1
        F_res[bus_dict[bus_id][1]: 0: (l1 + l2) + i] = -1
    
    return F_res

def var_substitution(eqs, initial_vars, final_vars):
    res_eqs = eqs
    try:
        if eqs == []:
            return []
    except:
        _ = 0
    
    if type(res_eqs)==list:
        for i, eq in enumerate(res_eqs):
            res_eqs[i] = var_substitution(eq, initial_vars, final_vars)
        return res_eqs
    
    for j, ini_var in enumerate(initial_vars):
        if ini_var in res_eqs.free_symbols:
            res_eqs = res_eqs.subs(ini_var, final_vars[j])
    return res_eqs

def limiter_to_indicator(mdl, device):
    initial_vars = []
    target_vars = []
    mdl_name = type(mdl).__name__
    for i in mdl.discrete:
        if i == "vcmp":
            var_name = "v"
            var_ini_name = i
        elif i[-3:] == "lim":
            var_name = i[:-3]
            var_ini_name = i[:-3] + "lim"
        else:
            var_name = i
            var_ini_name = i
        vu = sp.Symbol(var_ini_name + "_zu")
        vl = sp.Symbol(var_ini_name + "_zi")
        vi = sp.Symbol(var_ini_name + "_zl")
        initial_vars += [vu, vl, vi] 
        base_var = sp.Symbol(var_name + "_" + mdl_name + str(device+1))
        
        try:
            v_min = mdl.params[var_name+"min"].v[device] 
            v_max = mdl.params[var_name+"max"].v[device] 
        except:
            continue
        
        indic_u = sp.Piecewise((1, base_var > v_max), (0, True))
        indic_l = sp.Piecewise((1, base_var < v_min), (0, True))
        indic_i = sp.Piecewise((1, (base_var > v_min)&(base_var < v_max)), (0, True))
        
        target_vars += [indic_u, indic_l, indic_i]
    
    return initial_vars, target_vars

def sys_to_eq(sys, mode = "dynamic", bool_print = True):
    #this function takers a system as input and returns
    #to set of lists one related to the combined f_function
    # and the other to the combined g_funtion
    F_res = []
    G_res = []
    X_dot = []
    var_2_Tcoef = {}
    var_2_idx = {}
    
    for mdl in sys.models.values():
        num_devices = mdl.n
        mdl_name = type(mdl).__name__
        
        try:
            mdl.prepare()
        except:
            print(mdl)
        try:
            vars_xy = copy.deepcopy(mdl.syms.vars_list)
            f_equations = copy.deepcopy(mdl.syms.f_list)
            g_equations = copy.deepcopy(mdl.syms.g_list)
            service_eqs = copy.deepcopy(mdl.syms.s_syms)
            _ = 0
        except:
            continue
        
        if mode == "static" and mdl.group in ["SynGen", "TurbineGov", "Exciter"]:
            f_equations = []
        
        for device in range(num_devices):
            f_equations_dev = copy.deepcopy(f_equations)    
            g_equations_dev = copy.deepcopy(g_equations)
            
            if mdl_name == "Toggle":
                continue
            elif mdl_name == "Bus":
                bus_id = mdl.idx.v[device]
                bus_ids = [bus_id]
                continue
                
            elif mdl_name == "Line":
                bus_id_from = mdl.bus1.v[device]
                bus_id_to = mdl.bus2.v[device]
                bus_ids = [bus_id_from , bus_id_to]
                
            elif mdl.group in ["TurbineGov", "Exciter"]:
                generator = "GENROU"
                gen = getattr(sys, generator)
                syn_id = mdl.syn.v[device]
                bus_id = gen.bus.v[syn_id-1]
                bus_ids = [bus_id] 
            
            #WE FIRST CHANGE THE VAR NAMES SO THAT IT POINTS TO THE DEVICE
            algeb_vars = mdl.algebs.keys()|mdl.algebs_ext.keys() 
            state_vars = mdl.states.keys()|mdl.states_ext.keys()
            algeb_vars_device = [var + "_" + mdl_name + "_" + str(device+1) for var in algeb_vars]
            state_vars_device = [var + "_" + mdl_name + "_" + str(device+1) for var in state_vars]
            algeb_vars_device = [sp.Symbol(var) for var in algeb_vars_device]
            state_vars_device = [sp.Symbol(var) for var in state_vars_device]
            algeb_vars = [sp.Symbol(var) for var in algeb_vars]
            state_vars = [sp.Symbol(var) for var in state_vars]
            
            
            #We substitute the known parameters in the service equations
            for key in service_eqs.keys():
                key_var = sp.Symbol(key)
                eq = service_eqs[key]
                service_eqs[key] = param_substitution(mdl, eq, device)
            
            #WE SUBSTITUE THE SERVICES IN THE EQUATIONS 
            service_dict = {}               
            for key in service_eqs.keys():
                v_key = getattr(mdl, key).v
                key_value = v_key[device]
                service_dict[sp.Symbol(key)] = key_value
            
            service_list = list(service_dict.keys())
            service_values = [service_dict[key] for key in service_list]
            
            config_list = list(mdl.config._dict.keys())
            config_values = [mdl.config._dict[key] for key in config_list]
            config_list = [sp.Symbol(key) for key in config_list]
            
            #We substitute the limiter parameters to indicators functions
            initial_lim, target_lim = limiter_to_indicator(mdl, device) 
            
            for i, eq in enumerate(f_equations_dev):
                if type(eq)==int:
                    continue
                f_equations_dev[i] = param_substitution(mdl, eq, device)
                f_equations_dev[i] = var_substitution(f_equations_dev[i], algeb_vars, algeb_vars_device)
                f_equations_dev[i] = var_substitution(f_equations_dev[i], state_vars, state_vars_device)
                f_equations_dev[i] = var_substitution(f_equations_dev[i], service_list, service_values)
                f_equations_dev[i] = var_substitution(f_equations_dev[i], config_list, config_values)
                f_equations_dev[i] = var_substitution(f_equations_dev[i], initial_lim, target_lim)
            
            for i, eq in enumerate(g_equations_dev):
                if type(eq)==int:
                    continue
                g_equations_dev[i] = param_substitution(mdl, eq, device)
                g_equations_dev[i] = var_substitution(g_equations_dev[i], algeb_vars, algeb_vars_device)
                g_equations_dev[i] = var_substitution(g_equations_dev[i], state_vars, state_vars_device)
                g_equations_dev[i] = var_substitution(g_equations_dev[i], service_list, service_values)
                g_equations_dev[i] = var_substitution(g_equations_dev[i], config_list, config_values)
                g_equations_dev[i] = var_substitution(g_equations_dev[i], initial_lim, target_lim)
                
            if mdl.group in ["TurbineGov", "Exciter"]:
                generator = "GENROU"
                ext_vars = mdl.states_ext.keys()|mdl.algebs_ext.keys()
                g_eq = []
                for var in ext_vars:
                    var_gen = sp.Symbol(var + "_" + generator + "_" +str(syn_id))     
                    var_original = sp.Symbol(var + "_" + mdl_name + "_" + str(device+1))     
                    g_eq += [var_gen - var_original]
            
            for i, bus_id in enumerate(bus_ids):
                a_symbol = sp.Symbol("a")
                a1_symbol = sp.Symbol("a1")
                connected_to_bus = (a_symbol in vars_xy) or (a1_symbol in vars_xy)
                if mdl_name == "Bus" or not connected_to_bus:
                    break
                a_bus = sp.Symbol("a_Bus" + "_" +str(i+1))
                a_model = sp.Symbol("a_" + mdl_name + "_" + str(device+1))
                v_bus = sp.Symbol("v_Bus" + "_" +str(i+1)) 
                v_model = sp.Symbol("v_"+ mdl_name + "_" + str(device+1)) 
                g_equations_dev += [a_model - a_bus]                 
                g_equations_dev += [v_model - v_bus]                 
            
            f_equations_dev = [eq for eq in f_equations_dev if not (isinstance(eq, float) or isinstance(eq, int))]
            g_equations_dev = [eq for eq in g_equations_dev if not (isinstance(eq, float) or isinstance(eq, int))]


            initial_vars = list(service_dict.keys())
            final_vars = list(service_dict.values())
            for i, eq in enumerate(f_equations_dev):
                for _ in range(3):
                    f_equations_dev[i] = var_substitution(f_equations_dev[i], initial_vars, final_vars)
                undefined_vars = eq.free_symbols - set(vars_xy)
                if len(undefined_vars)!=0:
                    print("model is ", mdl)
                    print(f"equation is {eq}")
                    print(undefined_vars)
                    
            for i, eq in enumerate(g_equations_dev):
                for _ in range(3):
                    g_equations_dev[i] = var_substitution(g_equations_dev[i], initial_vars, final_vars)
                undefined_vars = eq.free_symbols - set(vars_xy)
                if len(undefined_vars)!=0:
                    print(f"model is {mdl} at device {device}")
                    print(f"equation is {eq}")
                    print(undefined_vars)

            x_dot = state_vars 
            x_dot = [str(s) for s in x_dot]    
            x_dot = [str(s + "_" + mdl_name + "_" + str(device+1)) for s in x_dot]    
            x_dot = [sp.Symbol(s) for s in x_dot]    
            
            F_res += f_equations_dev
            G_res += g_equations_dev
            X_dot += x_dot
    
    G_res = [eq for eq in G_res if eq != sp.Integer(0)]  
    
    
    #WE CHANGE THE INDICATOR FUNCTIONS DEPENDING ON DAE_t
    dae_t = sp.Symbol("dae_t")
    ini_var = [sp.Heaviside(dae_t, 0), sp.Piecewise((1, dae_t < 0), (0, dae_t >= 0))]
    if mode == "dynamic":
        target_var = [1, 0]
    else:
        target_var = [0, 1]
    for i, eq in enumerate(g_equations_dev):
        if type(eq)==int:
            continue
        g_equations_dev[i] = var_substitution(g_equations_dev[i], ini_var, target_var)
    for i, eq in enumerate(f_equations_dev):
        if type(eq)==int:
            continue
        f_equations_dev[i] = var_substitution(f_equations_dev[i], ini_var, target_var)
    
    #We recoup the LHS of the differentiable equations 
    for i, x_name in enumerate(sys.dae.x_name):
        x_name = x_name.replace(" ","_")
        var_2_Tcoef[x_name] = sys.dae.Tf[i]   
        var_2_idx[x_name] = i
           
    #We print all equations if necessary
    if bool_print:
        for g in G_res:
            print(g, "= 0")
        for i, f in enumerate(F_res):
            T_factor = var_2_Tcoef[X_dot[i]]
            print(f"{T_factor}({X_dot[i]})' = {f}")
    
    return F_res, G_res

def is_multilinear(expr, variables):
    for var in variables:
        # Test if the expression is linear in var
        a, b = sp.symbols('a b')
        expr_with_a = expr.subs(var, a * var)
        expr_with_b = expr.subs(var, b * var)
        expr_with_ab = expr.subs(var, a * var + b * var)
        
        # Check if the expression is linear in var
        if expr_with_ab != a * expr_with_a.subs(var, var) + b * expr_with_b.subs(var, var):
            return False

    return True

def equations_to_poly(equations, order=2):
    aux_variables_dict = {}
    diff_equations = []
    alg_equations = []
    for i, eq in enumerate(equations):
        if eq.is_polynomial():
           continue
        for monom in eq.monoms():
            if monom.is_polynomial():
                a_ = 0
            elif monom.has(sp.cos):
                generators = monom.gens
                for gen in generators:
                    
                    if gen.is_polynomial():
                        continue
                    
                    #we check for trigonometric expressions
                    if gen.has(sp.cos) or gen.has(sp.sin):
                        cos_expr = gen
                        sin_expr = sp.sin(sp.acos(cos_expr))
                
                        first = (not cos_expr in aux_variables_dict.keys() or not cos_expr in aux_variables_dict.keys())
                        if first:
                            n = len(aux_variables_dict)
                            v_aux_cos = sp.Symbol("v_aux_cos" + str(n+1))
                            v_aux_sin = sp.Symbol("v_aux_sin" + str(n+2))
                            aux_variables_dict[cos_expr] = v_aux_cos
                            aux_variables_dict[sin_expr] = v_aux_sin
                            alg_equations += [v_aux_cos**2 + v_aux_sin**2]
                                                                                    
                        else:
                            v_aux_cos = aux_variables_dict[cos_expr]
                            v_aux_sin = aux_variables_dict[sin_expr]
                        
                        if gen.has(sp.cos):
                            equations[i] = equations[i].subs(cos_expr, v_aux_cos)
                        elif gen.has(sp.sin):    
                            equations[i] = equations[i].subs(sin_expr, v_aux_sin)
                    
                    #we check for indicator function/piecewise expression                            
                    if gen.has(sp.Piecewise):
                        piecewise_expr = gen
                        first = not piecewise_expr in aux_variables_dict.keys()
                        if first:
                            n = len(aux_variables_dict)
                            v_aux = sp.Symbol("v_aux" + str(n+1))
                            aux_variables_dict[piecewise_expr] = v_aux
                        else:
                            v_aux = aux_variables_dict[pow_expr]
                            equations[i] = equations[i].subs(pow_expr, v_aux)
                        alg_equations += [v_aux]
                        equations[i] = equations[i].subs(pow_expr, v_aux)
                        
                    
                    #we check for power expression with power > order fixed previously        
                    if gen.has(sp.Pow):
                        var = list(gen.free_symbols)[0]
                        pow_expr = gen
                        poly_order = gen.degree(var)
                        if poly_order <= 2:
                            continue
                        first = not piecewise_expr in aux_variables_dict.keys()
                        if first:
                            n = len(aux_variables_dict)
                            v_aux = sp.Symbol("v_aux" + str(n+1))
                            aux_variables_dict[pow_expr] = v_aux
                        else:
                            v_aux = aux_variables_dict[pow_expr]
                        
                        if poly_order == 3:
                            equations[i] = equations[i].subs(pow_expr, v_aux*var**2)
                            alg_equations += [v_aux - var**2]
                        if poly_order == 4:
                            equations[i] = equations[i].subs(pow_expr, v_aux**2)
                            alg_equations += [v_aux - var**2]
                        
    res = diff_equations, alg_equations, aux_variables_dict                    
    return res                   
        
def poly_to_tensor(equations, order=2):
    vars_dict = build_var_dict(equations)
    n = len(vars_dict)
    l = len(equations)
    
    F_shape = (n+1,)*order + (l,)
    F_res = np.zeros(F_shape)
    
    for i, eq in enumerate(equations):
        index = (slice(0,n),)*order + (i,)
        F_res[index] = symbolic_to_tensor(vars_dict, eq, order)
        
    return F_res
    
def vars_dict_dae(sys):
    dict_res_sp = {}
    dict_res_str = {}
    for mdl in sys.models:
        if mdl.n == 0:
            continue
        for v in mdl.states:
            for i, address in enumerate(v.a):
                var_name = v.name + "_" + mdl.name + "_" + str(i+1)
                key_sp = sp.Symbol(var_name)
                dict_res_sp[var_name] = address   
                dict_res_str[key_sp] = address
    
    return dict_res_sp, dict_res_str 

def initialize_system_data(system, twin_system, model, twin_model = "GENROU"):
    #Function
    idx = 0
    n = model.n
    twin_model = getattr(twin_system, twin_model)
    for name, param in twin_model._all_params().items():
        name_a =  name + 'a'
        name_b =  name + 'b'
        try:
            param_a = getattr(model, name_a)
            param_b = getattr(model, name_b)
            if isinstance(param_a.v, float):
                param_a.v = param.v
                param_b.v = param.v
            else:
                param_a.v[:n] = param.v[idx]*np.ones(n)
                param_b.v[:n] = param.v[idx]*np.ones(n)
        except:
            _ = 0 
    return

def plot_roles(data, tf, condition=None):
    if condition == 'omega':
        def f(x):
            res = 0.997<x<1.003 
            if res:
                return 1
            else:
                return 0
    elif condition is None:
        def f(x):
            return x
        
    data = np.array(data)
    data = np.where(np.vectorize(f)(data), 0, 1)
    x_values = np.linspace(0, tf, data.shape[0])
    plt.clf()
    fig, axs = plt.subplots(4, 1, figsize=(8, 12))  # 4 plots in 1 column layout

    for i in range(4):
        axs[i].plot(x_values, data[:, i], marker='o', markersize=2)  # Plot each column
        axs[i].set_title(f'Agent {i+1}')
        axs[i].set_ylim([-0.5, 1.5])  # Set y-axis range for binary data
        axs[i].set_ylabel('Role')
        axs[i].grid(True)

    plt.tight_layout()  # Adjust the layout to prevent overlap
    plt.show() 
    plt.savefig("plots/roles_plot.png")

def setup_system(model):
    for uid in range(model.n):
        idx = uid + 1  
        model.alter("M", idx=idx, value= 0.4)
        model.alter("Ma", idx=idx, value= 0.4)
        model.alter("Mb", idx=idx, value= 0.4)