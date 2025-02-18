import numpy as np

def vref_setpoints(value = 1.08):
    set_point_dict = []
    set_point_dict += [{'model':'REDUAL', 'param':'vref', 'value':(value), 'add':False, 'idx':'GENROU_3', 't': 10}]
    set_point_dict += [{'model':'REDUAL', 'param':'vref', 'value':(value), 'add':False, 'idx':'GENROU_5', 't': 10}]


def variable_charge_setpoints(Ppf1, Ppf2):
    set_point_dict = []
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.8*Ppf1, 'add':False, 'idx':'PQ_18', 't': 5}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.8*Ppf2, 'add':False, 'idx':'PQ_19', 't': 5}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.01*Ppf1, 'add':False, 'idx':'PQ_18', 't': 20}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.03*Ppf2, 'add':False, 'idx':'PQ_19', 't': 20}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.05*Ppf1, 'add':False, 'idx':'PQ_18', 't': 20}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.05*Ppf2, 'add':False, 'idx':'PQ_19', 't': 20}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1*Ppf1, 'add':False, 'idx':'PQ_18', 't': 20}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.05*Ppf2, 'add':False, 'idx':'PQ_19', 't': 20}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.05*Ppf1, 'add':False, 'idx':'PQ_18', 't': 25}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1*Ppf2, 'add':False, 'idx':'PQ_19', 't': 25}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.99*Ppf1, 'add':False, 'idx':'PQ_18', 't': 30}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.01*Ppf2, 'add':False, 'idx':'PQ_19', 't': 30}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.05*Ppf1, 'add':False, 'idx':'PQ_18', 't': 35}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.95*Ppf2, 'add':False, 'idx':'PQ_19', 't': 35}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.99*Ppf1, 'add':False, 'idx':'PQ_18', 't': 40}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.01*Ppf2, 'add':False, 'idx':'PQ_19', 't': 40}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.98*Ppf1, 'add':False, 'idx':'PQ_18', 't': 45}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.97*Ppf2, 'add':False, 'idx':'PQ_19', 't': 45}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.95*Ppf1, 'add':False, 'idx':'PQ_18', 't': 50}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.90*Ppf2, 'add':False, 'idx':'PQ_19', 't': 50}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.05*Ppf1, 'add':False, 'idx':'PQ_18', 't': 55}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.95*Ppf2, 'add':False, 'idx':'PQ_19', 't': 55}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.05*Ppf1, 'add':False, 'idx':'PQ_18', 't': 60}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.05*Ppf2, 'add':False, 'idx':'PQ_19', 't': 60}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1*Ppf1, 'add':False, 'idx':'PQ_18', 't': 65}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.0*Ppf2, 'add':False, 'idx':'PQ_19', 't': 65}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.05*Ppf1, 'add':False, 'idx':'PQ_18', 't': 70}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1*Ppf2, 'add':False, 'idx':'PQ_19', 't': 70}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.99*Ppf1, 'add':False, 'idx':'PQ_18', 't': 75}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.01*Ppf2, 'add':False, 'idx':'PQ_19', 't': 75}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.05*Ppf1, 'add':False, 'idx':'PQ_18', 't': 80}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.95*Ppf2, 'add':False, 'idx':'PQ_19', 't': 80}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.99*Ppf1, 'add':False, 'idx':'PQ_18', 't': 85}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':1.01*Ppf2, 'add':False, 'idx':'PQ_19', 't': 85}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.98*Ppf1, 'add':False, 'idx':'PQ_18', 't': 90}]
    set_point_dict += [{'model':'PQ', 'param':'Ppf', 'value':0.97*Ppf2, 'add':False, 'idx':'PQ_19', 't': 90}]
    
        
    return set_point_dict

def mode_setpoints(value = 1):
    set_point_dict = []
    #set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(not value), 'add':False, 'idx':'GENROU_6', 't': 5}]
    #set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(value), 'add':False, 'idx':'GENROU_2', 't': 5}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(value), 'add':False, 'idx':'GENROU_3', 't': 10}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(value), 'add':False, 'idx':'GENROU_5', 't': 10}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(not value), 'add':False, 'idx':'GENROU_1', 't': 20}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(not value), 'add':False, 'idx':'GENROU_2', 't': 20}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(not value), 'add':False, 'idx':'GENROU_2', 't': 20}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(value), 'add':False, 'idx':'GENROU_4', 't': 20}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':value, 'add':False, 'idx':'GENROU_1', 't': 30}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':value, 'add':False, 'idx':'GENROU_2', 't': 30}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':value, 'add':False, 'idx':'GENROU_5', 't': 30}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':value, 'add':False, 'idx':'GENROU_4', 't': 30}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(not value), 'add':False, 'idx':'GENROU_1', 't': 40}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(value), 'add':False, 'idx':'GENROU_2', 't': 40}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(value), 'add':False, 'idx':'GENROU_3', 't': 40}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(not value), 'add':False, 'idx':'GENROU_4', 't': 40}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(value), 'add':False, 'idx':'GENROU_1', 't': 55}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(not value), 'add':False, 'idx':'GENROU_2', 't': 55}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(value), 'add':False, 'idx':'GENROU_3', 't': 55}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(value), 'add':False, 'idx':'GENROU_4', 't': 55}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(value), 'add':False, 'idx':'GENROU_7', 't': 65}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(value), 'add':False, 'idx':'GENROU_2', 't': 65}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(value), 'add':False, 'idx':'GENROU_3', 't': 65}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(value), 'add':False, 'idx':'GENROU_6', 't': 65}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':value, 'add':False, 'idx':'GENROU_1', 't': 75}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(not value), 'add':False, 'idx':'GENROU_2', 't': 75}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(not value), 'add':False, 'idx':'GENROU_3', 't': 75}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':value, 'add':False, 'idx':'GENROU_4', 't': 75}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(not value), 'add':False, 'idx':'GENROU_1', 't': 85}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(value), 'add':False, 'idx':'GENROU_2', 't': 85}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(value), 'add':False, 'idx':'GENROU_3', 't': 85}]
    set_point_dict += [{'model':'REDUAL', 'param':'is_GFM', 'value':(not value), 'add':False, 'idx':'GENROU_4', 't': 85}]

    return set_point_dict

def modedouble_setpoints(tmax = 7, GFM_name = 'REGF1'):
    set_point_dict = []
    set_point_dict += [{'model':GFM_name, 'param':'u', 'value':1, 'add':False, 'idx':'GENROU_2', 't':10}]
    set_point_dict.append({'model':'REGCP1', 'param':'u', 'value':0, 'add':False, 'idx':'GENROU_2', 't':10})
    if tmax > 10:
        set_point_dict.append({'model':GFM_name, 'param':'u', 'value':1, 'add':False, 'idx':'GENROU_4', 't':30})
        set_point_dict.append({'model':'REGCP1', 'param':'u', 'value':0, 'add':False, 'idx':'GENROU_4', 't':30})
    return set_point_dict

