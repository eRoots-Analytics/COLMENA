from flask import Flask
from flask import url_for, request, render_template_string, jsonify, send_file
from typing import List, TYPE_CHECKING
from threading import Thread
from PIL import Image
import pandas as pd
import os

desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "plots")
os.makedirs(desktop_path, exist_ok=True)
from io import BytesIO
import requests
from collections import OrderedDict
import os, sys, io
import time
import numpy as np
import traceback
import aux_function as aux
import matplotlib.pyplot as plt
import matplotlib
from copy import deepcopy
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
from andes.utils.paths import get_case, cases_root, list_cases
import andes as ad

started = None  
print(sys.path)
app = Flask(__name__)
# In-memory storage for received JSON data (list of dictionaries)
json_storage = []
delta_t = 0.1
available_devices ={'device_1':{'model':'REDUAL', 'idx':'GENROU_1', 'assigned':False},
                    'device_2':{'model':'REDUAL', 'idx':'GENROU_2', 'assigned':False}}
agent_names = ['agent_a','agent_b','agent_c','agent_d','area_1','area_2']

# Route to load the simulation case
@app.route('/load_simulation', methods=['POST'])
def load_simulation():
    global system
    global started
    global system_initial
    global agent_actions
    try:
        # Load the Andes simulation (but don't run it yet)
        data = request.get_json()
        case_file = data['case_file'] 
        if 'ieee39' in case_file:
            app.config['grid'] = 'ieee39'
        elif 'kundur' in case_file:
            app.config['grid'] = 'kundur'
        elif 'ieee14' in case_file:
            app.config['grid'] = 'ieee14'

        agent_actions = {}
        app.config['stop'] = False
        app.config['last_control_time'] = 0
        for agent_name in agent_names:
            agent_actions[agent_name] = []
        app.config['started'] = False
        app.config['await_start'] = True
        n_redual = 4
        system_ieee = ad.load(case_file, setup=False)
        print(f"case_file is {case_file}")
        if data['redual'] is False:
            system = system_ieee
            system.prepare(models = system.TGOV1N)
            system.prepare(models = system.TGOV1)
            print(f"system.TGOV1N.b is {system.TGOV1N.b}")
            #system.Line.alter(src='u', idx = 'Line_7', value = 0)
            #system.Line.alter(src='u', idx = 'Line_17', value = 0)
            #system.Line.alter(src='u', idx = 'Line_20', value = 0)
            #system.Line.alter(src='u', idx = 'Line_31', value = 0)
            #system.Line.alter(src='u', idx = 'Line_32', value = 0)
            system.setup()
            system.PFlow.run()
            #system.TDS.init()
            print(f"system area is {system.Area}")
            return jsonify({"message": f"Simulation loaded successfully"}), 200

        app.config['redual'] = True
        print("redual is true")
        system = aux.build_new_system_legacy(system_ieee, new_model_name = 'REDUAL', n_redual =n_redual)
        system_initial = aux.build_new_system_legacy(system_ieee, new_model_name = 'REDUAL', n_redual =n_redual)
        for i in range(n_redual):
            idx = system.REDUAL.idx.v[i]
            system.REDUAL.alter(src='is_GFM', idx=idx, value = 0)
            system_initial.REDUAL.alter(src='is_GFM', idx=idx, value = 0)
        system.find_devices()
        system.REDUAL.prepare()

        for idx in system.REDUAL.idx.v:
            system.REDUAL.alter(src='KPi', idx = idx, value = 1)
            system.REDUAL.alter(src='KPv', idx = idx, value = 5)
            system.REDUAL.alter(src='KIi', idx = idx, value = 30)
            system.REDUAL.alter(src='KIv', idx = idx, value = 15)

        system.Toggle.alter(src='dev', idx = 'Toggler_1', value = 'GENROU_8')
        system.Toggle.alter(src='t', idx = 'Toggler_1', value = 10)
        system.setup()
        system.TDS_stepwise.config.criteria = 0
        system.PFlow.run()

        system_initial.find_devices()
        system_initial.REDUAL.prepare()
        system_initial.Toggle.alter(src='dev', idx = 'Toggler_1', value = 'GENROU_8')
        system_initial.Toggle.alter(src='t', idx = 'Toggler_1', value = 10)
        system_initial.setup()
        system_initial.TDS_stepwise.config.criteria = 0
        system_initial.PFlow.run()

        system = system_initial
        system.PQ.config.p2p = 1.0
        system.PQ.config.p2i = 0
        system.PQ.config.p2z = 0

        print(f"system area is {system.Area}")

        return jsonify({"message": f"Simulation loaded successfully"}), 200
    except Exception as e:
        print("error in loading the grid")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/assign_device', methods=['GET'])
def assign_device():
    try:

        agent_id = request.args.get('agent')
        gen1 = {'idx':"GENROU_5", 'model':'GENROU'}
        gen2 = {'idx':"GENROU_6", 'model':'GENROU'}
        transf1 = {'idx':"GENROU_2", 'model':'REDUAL'}
        transf2 = {'idx':"GENROU_3", 'model':'REDUAL'}
        area1 = {'idx':"1", 'model':'area'}
        area2 = {'idx':"2", 'model':'area'}

        device_dict = {'agent_a':gen1, 'agent_b':gen2, 'agent_c':transf1, 'agent_d':transf2, 'area_1':area1, 'area_2':area2}
        app.config['await_start'] = False
        response = device_dict[agent_id]
        return jsonify(response), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# Route to run the previously loaded simulation
@app.route('/run_simulation', methods=['POST'])
def run_simulation():
    try:
        if not loaded_system:
            return jsonify({"error": "No simulation loaded. Load a simulation first."}), 400

        # Run the loaded simulation
        system.PFlow.run()
        sim_output = system.PFlow.run()
        # Return success and results (e.g., output directory or status)
        return jsonify({"message": "Simulation ran successfully", "output": str(sim_output)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/print_var', methods=['POST'])
def print_var():
    try:
        data = request.get_json()
        for i in data['keys']:
            var = getattr(system.REDUAL, i)
            print('Var value is', var.v)
        return jsonify({"message": 'printed'}), 200
    except Exception as e:
        change = 'printed'
        print(change)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/connecting_buses', methods=['GET'])
def connecting_buses():
    area1 = request.args.get('area1', type=int)
    area2 = request.args.get('area2', type=int)
    result = set()
    response = {}
    try:
        for i, line in enumerate(system.Line.idx.v):
            bus1 = system.Line.bus1.v[i]
            bus2 = system.Line.bus2.v[i]
            bus1_index = system.Bus.idx2uid(bus1)
            bus2_index = system.Bus.idx2uid(bus2)
            area_from = system.Bus.area.v[bus1_index]
            area_to = system.Bus.area.v[bus2_index]

            if area_from in [area1,area2] and area_to in [area1,area2] and area_from != area_to:
                if area1 == area_to:
                    result.add(bus1)
                else:
                    result.add(bus2)
        response['value'] = list(result)
        return jsonify(response), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

#Function that 
@app.route('/neighbour_area', methods=['GET'])
def neighbour_area():
    area = request.args.get('area', type=int)
    result = set()
    response = {}
    try:
        for i, line in enumerate(system.Line.idx.v):
            bus1 = system.Line.bus1.v[i]
            bus2 = system.Line.bus2.v[i]
            bus1_index = system.Bus.idx2uid(bus1)
            bus2_index = system.Bus.idx2uid(bus2)
            area1 = system.Bus.area.v[bus1_index]
            area2 = system.Bus.area.v[bus2_index]

            if area2 == area or area1 == area and area2 != area1:
                area_neighbor = area2 if area2 != area else area1
                if area_neighbor != area:
                    result.add(area_neighbor)
        response['value'] = list(result)
        return jsonify(response), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Route to run the previously loaded simulation
@app.route('/lines_susceptance', methods=['GET'])
def lines_susceptance():
    data = request.get_json()
    area = data['area']
    result = {}
    response = {}
    try:
        for i, bus_to, bus_from in enumerate(zip(system.Line.bus1.v, system.Line.bus2.v)):
            bus_to_uid = system.Bus.idx2uid[bus_to]       
            bus_from_uid = system.Bus.idx2uid[bus_from]    
            area_to = system.Bus.area.v[bus_to_uid]   
            area_from = system.Bus.area.v[bus_from_uid]   
            if area_to == area and area_from == area:
                result[bus_to, bus_from] = system.Line.b.v[i]
                result[bus_from, bus_to] = system.Line.b.v[i]

        response['value'] = result
        return jsonify(response), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Route to run the previously loaded simulation
@app.route('/system_susceptance', methods=['GET'])
def system_susceptance():
    try:
        data = request.args.to_dict()
        area = int(data['area'])
        other_areas = system.Area.idx.v
        other_areas = [x_area for x_area in other_areas if x_area != area]
        connecting_lines = {}
        connecting_susceptance = {}
        for x_area in other_areas:
            connecting_lines[x_area] = []

        for i, line in enumerate(system.Line.idx.v):
            bus1 = system.Line.bus1.v[i]
            bus2 = system.Line.bus2.v[i]
            bus1_index = system.Bus.idx2uid(bus1)
            bus2_index = system.Bus.idx2uid(bus2)
            area1 = system.Bus.area.v[bus1_index]
            area2 = system.Bus.area.v[bus2_index]

            if area1 != area2 and area in [area1, area2]:
                connecting_area = area2 if area == area1 else area1
                connecting_lines[connecting_area].append(line)
                print(f"connecting")
            
        for x_area, lines in connecting_lines.items():
            bi = 0
            for line in lines:
                line_uid = system.Line.idx2uid(line)
                connection_status = system.Line.u.v[line_uid]
                xi = system.Line.x.v[line_uid]
                bi += (1/xi)*connection_status
                print(f"line is {line} bi is {bi}")
            connecting_susceptance[int(x_area)] = bi
        
        print(f"connecting_susceptance is {connecting_susceptance}")
        print(f"other_areas is {other_areas}")
        return jsonify(connecting_susceptance), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
# Route to compute the equivalent angles of the area
@app.route('/delta_equivalent', methods=['GET'])
def delta_equivalent():
    try:
        data = request.args.to_dict()
        area = int(data['area'])
        other_areas = system.Area.idx.v
        other_areas = [x_area for x_area in other_areas if x_area != area]
        connecting_lines = {}
        connecting_susceptance = {}
        delta_equivalent = {}

        for x_area in other_areas:
            connecting_lines[x_area] = []

        for i, line in enumerate(system.Line.idx.v):
            bus1 = system.Line.bus1.v[i]
            bus2 = system.Line.bus2.v[i]
            bus1_index = system.Bus.idx2uid(bus1)
            bus2_index = system.Bus.idx2uid(bus2)
            area1 = system.Bus.area.v[bus1_index]
            area2 = system.Bus.area.v[bus2_index]

            if area1 != area2 and area in [area1, area2]:
                connecting_area = area2 if area == area1 else area1
                connecting_lines[connecting_area].append(line)
                print(f"connecting")
            
        for x_area, lines in connecting_lines.items():
            bi = 0
            for line in lines:
                line_uid = system.Line.idx2uid(line)
                connection_status = system.Line.u.v[line_uid]
                xi = system.Line.x.v[line_uid]
                bi += (1/xi)*connection_status
                print(f"line is {line} bi is {bi}")
            connecting_susceptance[int(x_area)] = bi
        
        for x_area, lines in connecting_lines.items():
            p_exchanged = 0
            for line in lines:
                i = system.Line.idx2uid(line)
                bus1 = system.Line.bus1.v[i]
                bus2 = system.Line.bus2.v[i]
                bus1_index = system.Bus.idx2uid(bus1)
                bus2_index = system.Bus.idx2uid(bus2)
                area1 = system.Bus.area.v[bus1_index]
                area2 = system.Bus.area.v[bus2_index]
                delta1 = system.Bus.a.v[bus1_index]
                delta2 = system.Bus.a.v[bus2_index]
                v1 = system.Bus.v.v[bus1_index]
                v2 = system.Bus.v.v[bus2_index]
                line_uid = system.Line.idx2uid(line)
                xi = system.Line.x.v[line_uid]
                ri = system.Line.r.v[line_uid]
                b_shunt = system.Line.b.v[line_uid]
                if area == area1:
                    sign = 1
                else:
                    sign = -1
                p_exchanged += 1*sign*(-1/xi)*np.sin(delta1-delta2)*v1*v2
                p_exchanged += 0*sign*(v1*v2*((ri/xi**2)*np.cos(delta1-delta2)+(1/xi)*np.sin(delta1-delta2)) - v1*v1*((ri/xi**2)+b_shunt))
            if connecting_susceptance[int(x_area)] != 0:
                delta_equivalent[int(x_area)] = p_exchanged/connecting_susceptance[int(x_area)]
            else:
                delta_equivalent[int(x_area)] = 0
        
        p_gen = 0
        d_omega = 0
        d_M_omega = 0
        for i, gen_idx in enumerate(system.GENROU.idx.v):
            bus_idx = system.GENROU.bus.v[i]
            bus_uid = system.Bus.idx2uid(bus_idx) 
            bus_area = system.Bus.area.v[bus_uid]
            if bus_area == area:
                p_gen += system.GENROU.tm.v[i]
                d_M_omega += system.GENROU.M.v[i]*(system.GENROU.omega.e[i])
                d_omega += (system.GENROU.omega.e[i])
        p_demand = 0
        for i, gen_idx in enumerate(system.PQ.idx.v):
            bus_idx = system.PQ.bus.v[i]
            bus_uid = system.Bus.idx2uid(bus_idx) 
            bus_area = system.Bus.area.v[bus_uid]
            if bus_area == area:
                p_demand -= system.PQ.p0.v[i]
        p_losses = d_M_omega - p_exchanged - p_demand - p_gen
        result = {}
        result['value'] = delta_equivalent
        result['losses'] = p_losses

        verbose = True
        if verbose:
            print(f"d_omega are {d_omega}")
            print(f"d_M_omega are {d_M_omega}")
            print(f"p_exchanged are {p_exchanged}")
            print(f"p_demand are {p_demand}")
            print(f"p_gen are {p_gen}")
            print(f"losses are {p_losses}")
        return jsonify(result), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Route to compute the equivalent angles of the area
@app.route('/delta_equivalent_balanced', methods=['GET'])
def delta_equivalent_balanced():
    try:
        data = request.args.to_dict()
        area = int(data['area'])
        other_areas = system.Area.idx.v
        other_areas = [x_area for x_area in other_areas if x_area != area]
        connecting_lines = {}
        connecting_susceptance = {}
        delta_equivalent = {}
        for x_area in other_areas:
            connecting_lines[x_area] = []

        for i, line in enumerate(system.Line.idx.v):
            bus1 = system.Line.bus1.v[i]
            bus2 = system.Line.bus2.v[i]
            bus1_index = system.Bus.idx2uid(bus1)
            bus2_index = system.Bus.idx2uid(bus2)
            area1 = system.Bus.area.v[bus1_index]
            area2 = system.Bus.area.v[bus2_index]

            if area1 != area2 and area in [area1, area2]:
                connecting_area = area2 if area == area1 else area1
                connecting_lines[connecting_area].append(line)
                print(f"connecting")
            
        for x_area, lines in connecting_lines.items():
            bi = 0
            for line in lines:
                line_uid = system.Line.idx2uid(line)
                connection_status = system.Line.u.v[line_uid]
                xi = system.Line.x.v[line_uid]
                Sn = system.Line.Sn.v[line_uid]
                bi += (1/xi)*connection_status
                print(f"line is {line} bi is {bi}")
            connecting_susceptance[int(x_area)] = bi
        
            P_balance = 0
            p_gen = 0
            d_M_omega = 0
            d_omega = 0
            for i, gen_idx in enumerate(system.GENROU.idx.v):
                bus_idx = system.GENROU.bus.v[i]
                bus_uid = system.Bus.idx2uid(bus_idx) 
                bus_area = system.Bus.area.v[bus_uid]
                if bus_area == area:
                    p_gen += system.GENROU.tm.v[i]
                    d_M_omega += system.GENROU.M.v[i]*(system.GENROU.omega.e[i])
                    d_omega += (system.GENROU.omega.e[i])
            P_balance += p_gen

            p_demand = 0
            for i, gen_idx in enumerate(system.PQ.idx.v):
                bus_idx = system.PQ.bus.v[i]
                bus_uid = system.Bus.idx2uid(bus_idx) 
                bus_area = system.Bus.area.v[bus_uid]
                if bus_area == area:
                    p_demand -= system.PQ.p0.v[i]
            P_balance += p_demand
            
            #This works if there are only 2 areas if not we have to solve a linear system
            if connecting_susceptance[int(x_area)] != 0:
                delta_equivalent[int(x_area)] = -P_balance/connecting_susceptance[int(x_area)]
            else:
                delta_equivalent[int(x_area)] = 0

            p_losses = d_M_omega + p_demand - p_gen 
        result = {}
        result['value'] = delta_equivalent
        return jsonify(result), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/run_simulation_online', methods=['POST'])
def run_simulation_online():
    global loaded_system
    try:
        if not loaded_system:
            return jsonify({"error": "No simulation loaded. Load a simulation first."}), 400

        # Run the loaded simulation
        system.PFlow.run()
        sim_output = system.PFlow.run()

        # Return success and results (e.g., output directory or status)
        return jsonify({"message": "Simulation ran successfully", "output": str(sim_output)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/device_role_change', methods=['POST'])
def device_role_change():
    #method to post the new device role in the app
    try:
        data = request.get_json()
        print(data)
        print(system.TGOV1N.idx.v)
        idx = data['idx']
        model_name = data['model']
        param = data['var']
        value = data['value']
        agent_id = data['agent']
        agent_actions[agent_id].append(system.dae.t)
        model = getattr(system, model_name)
        uid = model.idx2uid(idx)
        if param == 'p_goal':
            param = 'paux0'
            try:
                gen_idx = model.gen.v[uid] 
            except:
                gen_idx = model.syn.v[uid] 
            gen_model = system.GENROU
            gen_uid = gen_model.idx2uid(gen_idx)
            value = value - model.pout.v[gen_uid]
        param_in_andes = getattr(model, param)
        initial_value = param_in_andes.v[uid]
        if hasattr(data,'add'): 
            if data['add']:
                param_in_andes = getattr(model,param)
                param_in_andes = param_in_andes.v[uid]
                value = param_in_andes + value 
        model.alter(idx =idx, src=param, value = value)
        print(f"role changed successfully from {initial_value} to {value}")
        print(f'value is {param_in_andes.v[uid]}')
        return jsonify({'message': 'success'}), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/set_point_change', methods=['POST'])
def set_point_change():
    #method to post the new device role in the app
    try:
        set_points_data = request.get_json()
        for set_point in set_points_data:
            system.TDS_stepwise.set_set_points(set_point)
        return jsonify({'message': 'success'}), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/device_sync', methods=['GET'])
def device_sync(all_devices = False):
    #method to post the new device role in the app
    app.config['await_start'] = False
    try:
        data = request.args.to_dict()
        if data is None:
            return jsonify({"error": "No JSON data received!"}), 400
        response = {}

        print('data keys are', data.keys())
        idx = data['idx']
        model_name = data['model']
        model = getattr(system_initial, model_name)
        uid = model.idx2uid(idx)
        response = model.as_dict()

        for key in response.keys():
            var_value = response[key][uid]
            if isinstance(var_value, np.generic):
                var_value = var_value.item()
            elif isinstance(var_value, np.ndarray):
                var_value = var_value.tolist()
            response[key] = var_value

        states = model._states_and_ext() 
        algebs = model._algebs_and_ext()
        othervars = OrderedDict(states)
        othervars.update(algebs)

        for var_name in othervars:
            var = getattr(model, var_name)
            uid = int(uid)
            if len(var.v) == 0:
                continue
            var_value = var.v[uid]
            if isinstance(var_value, np.generic):
                var_value = var_value.item()
            elif isinstance(var_value, np.ndarray):
                var_value = var_value.tolist()
            response[var_name] = var_value
        #Since this is used at the very beginning to initialize the agents we can now start the simulation 
        return jsonify(response), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/specific_device_sync', methods=['GET'])
def specific_device_sync(all_devices = False):
    #method to post the new device role in the app
    try:
        data = request.args.to_dict()
        if data is None:
            return jsonify({"error": "No JSON data received!"}), 400
        response = {}
        idx = data['idx']
        model_name = data['model']
        var_name = data['var']
        print(model_name)
        model = getattr(system, model_name, None)
        var = getattr(model, var_name)
        if len(var.v) == 0:
            model = getattr(system_initial, model_name, None)
            var = getattr(model, var_name)
        uid = model.idx2uid(idx)
        value = var.v[uid]
        print(f"value is {var}")
        try:
            response['value'] = value
        except:
            response['value'] = None
        return jsonify(response), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/complete_variable_sync', methods=['GET'])
def complete_variable_sync(all_devices = False):
    #method to post the new device role in the app
    try:
        data = request.args.to_dict()
        print(f"data is {data}")
        if data is None:
            return jsonify({"error": "No JSON data received!"}), 400
        response = {}
        model_name = data['model']
        var_name = data['var']
       
        model = getattr(system, model_name, None)
        print(f"System other is {system.GENROU}")
        print("System area is", system.Area, f"model name is {model_name}")
        var = getattr(model, var_name)
        value = var.v

        try:
            response['value'] = value
        except:
            response['value'] = None
            print("value is in ", value)
        if type(value) == np.ndarray:
            response['value'] = value.tolist()
        print(f"value is {value}")
        print(f"res is {response['value']}")
        return jsonify(response), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/partial_variable_sync', methods=['POST'])
def partial_variable_sync(all_devices = False):
    #method to post the new device role in the app
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"error": "No JSON data received!"}), 400
        response = {}
        model_name = data['model']
        var_name = data['var']
        idxs = data['idx']
        model = getattr(system, model_name, None)
        var = getattr(model, var_name)
        res = []
        print(idxs)
        print("var is", var)
        for idx in idxs:
            uid = model.idx2uid(idx)
            value = var.v[uid]
            res.append(value)
        try:
            response['value'] = res
        except:
            response['value'] = None
            print("value is in except", res)
        if type(res) == np.ndarray:
            response['value'] = res.tolist()
        print(f"res is {res}")
        return jsonify(response), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/area_variable_sync', methods=['POST'])
def area_variable_sync(all_devices = False):
    #method to post the new device role in the app
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"error": "No JSON data received!"}), 400
        response = {}
        model_name = data['model']
        var_name = data['var']
        area = data['area']
        area = int(area)
        area_buses = system.Bus.idx.v
        area_buses = [bus for i, bus in enumerate(area_buses) if system.Bus.area.v[i] == area]

        model = getattr(system, model_name, None)
        var = getattr(model, var_name)

        res = []
        #check this is not a bus
        if model_name == 'Bus':
            bus_iterate = model.idx.v
        else:
            bus_iterate = model.bus.v

        for i, bus in enumerate(bus_iterate):
            if bus in area_buses:
                value = var.v[i]
                res.append(value)

        try:
            response['value'] = res
        except:
            response['value'] = None
            print("value is in except", res)
        
        if type(res) == np.ndarray:
            response['value'] = res.tolist()

        print(f"response is {response}")
        return jsonify(response), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/specific_variable_sync', methods=['GET'])
def specific_variable_sync(all_devices = False):
    #method to post the new device role in the app
    try:
        data = request.args.to_dict()
        if data is None:
            return jsonify({"error": "No JSON data received!"}), 400
        response = {}
        uid = data['uid']
        model_name = data['model']
        var_name = data['var']
       
        model = getattr(system, model_name, None)
        var = getattr(model, var_name)
        if len(var.v) == 0:
            model = getattr(system_initial, model_name, None)
            var = getattr(model, var_name)
        value = var.v[uid]
        print(f"value is {var}")
        try:
            response['value'] = value
        except:
            response['value'] = None
        return jsonify(response), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/sync_time', methods=['GET'])
def sync_time():
    app_t = system.dae.t
    app_t = float(app_t)
    print(app_t)
    return jsonify({"time": app_t}) 

@app.route('/simulation_started', methods=['GET'])
def simulation_started():
    started = app.config['started'] 
    return jsonify({'result': started}) 

@app.route('/start_simulation', methods=['POST'])
def start_simulation():
    app.config['await_start'] = False
    return jsonify({"Result": 'Success'}) 

@app.route('/add_set_point', methods=['GET'])
def add_set_point():
    global set_points
    try:
        data = request.args.to_dict()
        data['t'] = float(data['t'])
        data['param'] = data['var']
        data['add'] = False
        if data['t'] > system.dae.t:
            set_points += [data]
        return jsonify({"Message": 'Success'}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/run_real_time', methods=['GET'])
def run_real_time():
    global set_points
    try:
        set_points = []
        speed_factor = float(request.args.get('speed', 1))
        if app.config['grid'] == 'ieee39':
            Ppf_pq5 = system.PQ.Ppf.v[4]
            Ppf_pq6 = system.PQ.Ppf.v[5]
            set_points += [{'model':'Line', 'idx':'Line_19', 't':5, 'param':'u', 'value':0, 'add':False}]
            #set_points += [{'model':'PQ', 'idx':'PQ_5', 't':20, 'param':'Ppf', 'value':1.5*Ppf_pq5, 'add':False}]
            #set_points += [{'model':'PQ', 'idx':'PQ_6', 't':35, 'param':'Ppf', 'value':1.3*Ppf_pq6, 'add':False}]
        while app.config['await_start']:
            print('Awaiting Simulation start')
            time.sleep(0.2)

        t_run = float(request.args.get('t_run', 40))  
        delta_t = float(request.args.get('delta_t', 0.1))  
        app.config['started'] = True
        t_0 = time.time()
        while system.dae.t <= t_run:
            if time.time() - t_0 >= delta_t: 
                system.TDS_stepwise.run_individual_batch(t_sim = delta_t*speed_factor)
                app.config['started'] = True
                print(f't_run is {t_run}')
                print(f'delta_t is {delta_t}')
                print(f't_dae is {system.dae.t}')
                t_0 = time.time()
                system.TDS_stepwise.set_set_points(set_points)
        app.config['await_start'] = True
        return jsonify({"Message": 'Success', "Time":t_run}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/stop_simulation', methods=['GET'])
def stop_simulation():
    try: 
        app.config['stop'] = True
        return jsonify({"Message": 'Success'}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/set_last_control_time', methods=['GET'])
def set_last_control_time():
    try: 
        t = float(request.args.get('t', None))  
        app.config['last_control_time'] = t
        return jsonify({"Message": 'Success'}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/run_stopping_time', methods=['GET'])
def run_stopping_time():
    global set_points
    try:
        print(f"Running Simulation 1")
        set_points = []
        speed_factor = float(request.args.get('speed', 1))
        if app.config['grid'] == 'ieee39':
            Ppf_pq5 = system.PQ.Ppf.v[4]
            Ppf_pq6 = system.PQ.Ppf.v[5]
            set_points += [{'model':'Line', 'idx':'Line_19', 't':3, 'param':'u', 'value':0, 'add':False}]
            #set_points += [{'model':'PQ', 'idx':'PQ_5', 't':6, 'param':'Ppf', 'value':5*Ppf_pq5, 'add':False}]
            #set_points += [{'model':'PQ', 'idx':'PQ_6', 't':35, 'param':'Ppf', 'value':1.3*Ppf_pq6, 'add':False}]
        while app.config['await_start']:
            time.sleep(0.2)

        print(f"Running Simulation 2")
        t_run = float(request.args.get('t_run', 40))  
        delta_t = float(request.args.get('delta_t', 0.1))  
        app.config['started'] = True
        system.PFlow.run()
        t_0 = time.time()
        while system.dae.t <= t_run:
            if app.config['stop']:
                time_started = time.time()
                while app.config['last_control_time'] <= system.dae.t:  
                    if time.time() - time_started > 20 or False:
                        return jsonify({"Message": 'Wait time exceeded'}), 200
                    time.sleep(0.02)
            start_time = time.time()
            print(f"Running Simulation 3")
            system.TDS_stepwise.set_set_points(set_points)
            system.TDS_stepwise.run_individual_batch(t_sim = delta_t*speed_factor)
            app.config['started'] = True
            print(f't_run is {t_run}')
            print(f'delta_t is {delta_t}')
            print(f't_dae is {system.dae.t}')
            time.sleep(max(0,delta_t-(time.time()-start_time)))
            t_0 = time.time()
            
        app.config['await_start'] = True
        return jsonify({"Message": 'Success', "Time":t_run}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/plot', methods=['GET'])
def plot():
    try:
        data = request.args.to_dict()
        model_name = data['model']
        var_name = data['var']
        output_path = f'plots/{model_name}_{var_name}.png'
        model = getattr(system, model_name)
        var = getattr(model, var_name)
        system.TDS_stepwise.load_plotter()
        matplotlib.use('TkAgg')
        plots = {
            'bus_v': system.Bus.v,
            'bus_a': system.Bus.a,
            'genrou_delta': system.GENROU.delta,
            'genrou_pe': system.GENROU.Pe,
            'genrou_omega': system.GENROU.omega,
            'genrou_tm': system.GENROU.tm,
            'tgov_pout': system.TGOV1N.pout,
            'tgov_pref': system.TGOV1N.pref,
        }

        if app.config['grid'] == 'kundur':
            plots['tgov_pout']=system.TGOV1.pout
            plots['tgov_pref']=system.TGOV1.pref

        system.TDS_stepwise.plt.export_csv(path="plots/data.csv", idx=system.TDS_stepwise.plt.find('omega')[0])
        for name, variable in plots.items():
            fig, ax = system.TDS_stepwise.plt.plot(variable)
            fig.savefig(f'plots/{name}.png', format='png')
            fig.savefig(os.path.join(desktop_path, f'{name}.svg'), format='svg')
            matplotlib.pyplot.close(fig)

        if app.config['redual']:
            fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.v)
            fig.savefig('plots/redual_v.png', format='png')
            fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.vd)
            fig.savefig('plots/redual_vd.png', format='png')
            fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.udref)
            fig.savefig('plots/redual_udref.png', format='png')
            fig, ax = system.TDS_stepwise.plt.plot(system.REDUAL.Pe)
            fig.savefig('plots/redual_Pe.png', format='png')
            # Save the plot to a BytesIO object rather than displaying it

        img = io.BytesIO()
        img.seek(0)
        fig.savefig(output_path, format='png')
        plt.close(fig)  # Close the plot to free memory

        return send_file(img, mimetype='image/png', as_attachment=False, download_name='plot.png')
        
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    host = "192.168.68.67"
    host = "0.0.0.0"
    app.run(host=host, port=5000, debug=False, threaded=True)
    andes_url = 'http://127.0.0.1:5000'
    andes_directory = ad.get_case("kundur/kundur_full.xlsx")
    andes_directory = ad.get_case("ieee39/ieee39_full.xlsx")
    andes_dict = {"case_file":andes_directory}
    kwargs = {'andes_url':andes_url, 'device_idx':1, 'model_name':'GENROU'} 
    responseLoad = requests.post(andes_url + '/load_simulation', json=andes_dict)
    responseLoad = requests.post(andes_url + '/run', json=andes_dict)