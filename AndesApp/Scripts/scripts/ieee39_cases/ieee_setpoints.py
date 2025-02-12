import numpy as np

def variable_charge_setpoints(Ppf1, Ppf2):
    set_point_dict = []
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.1*Ppf1, 'add':False, 'idx':'PQ_18', 't': 5}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.9*Ppf2, 'add':False, 'idx':'PQ_19', 't': 5}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.9*Ppf1, 'add':False, 'idx':'PQ_18', 't': 30}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.1*Ppf2, 'add':False, 'idx':'PQ_19', 't': 30}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.9*Ppf1, 'add':False, 'idx':'PQ_18', 't': 60}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.3*Ppf2, 'add':False, 'idx':'PQ_19', 't': 60}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.05*Ppf1, 'add':False, 'idx':'PQ_18', 't': 90}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.95*Ppf2, 'add':False, 'idx':'PQ_19', 't': 90}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.7*Ppf1, 'add':False, 'idx':'PQ_18', 't': 120}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.3*Ppf2, 'add':False, 'idx':'PQ_19', 't': 120}]
    return set_point_dict

def mode_setpoints():
    set_point_dict = []
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':0, 'add':False, 'idx':'GENROU_1', 't': 10}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':1, 'add':False, 'idx':'GENROU_2', 't': 10}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':0, 'add':False, 'idx':'GENROU_2', 't': 30}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':1, 'add':False, 'idx':'GENROU_3', 't': 30}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':0, 'add':False, 'idx':'GENROU_3', 't': 50}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':1, 'add':False, 'idx':'GENROU_4', 't': 50}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':0, 'add':False, 'idx':'GENROU_4', 't': 70}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':1, 'add':False, 'idx':'GENROU_1', 't': 70}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':0, 'add':False, 'idx':'GENROU_1', 't': 90}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':1, 'add':False, 'idx':'GENROU_2', 't': 90}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':0, 'add':False, 'idx':'GENROU_2', 't': 110}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':1, 'add':False, 'idx':'GENROU_4', 't': 110}]
    return set_point_dict

def modedouble_setpoints(tmax = 7, GFM_name = 'REGF1'):
    set_point_dict = []
    set_point_dict += [{'model':GFM_name, 'param':'u', 'value':1, 'add':False, 'idx':'GENROU_2', 't':5}]
    set_point_dict.append({'model':'REGCP1', 'param':'u', 'value':0, 'add':False, 'idx':'GENROU_2', 't':5})
    if tmax > 10:
        set_point_dict.append({'model':GFM_name, 'param':'u', 'value':1, 'add':False, 'idx':'GENROU_4', 't':10})
        set_point_dict.append({'model':'REGCP1', 'param':'u', 'value':0, 'add':False, 'idx':'GENROU_4', 't':10})
    return set_point_dict