import traceback
import numpy as np
from pathlib import Path
from flask import Flask
from flask import request, jsonify

from src.config.config import Config
from andes import load
from andes.routines.tds import TDS

import pdb

app = Flask(__name__)
system = None
tds = None

@app.route('/load_simulation', methods=['POST'])
def load_simulation():
    global system
    global tds

    try:
        # Parse sent case into Python dict.
        case = request.get_json()
        case_file = case['case_file']
        if 'ieee39' in case_file:
            app.config['grid'] = 'ieee39'
        elif 'kundur' in case_file:
            app.config['grid'] = 'kundur'
        elif 'ieee14' in case_file:
            app.config['grid'] = 'ieee14'

        # Initialize ANDES system 
        system = load(
            case_file,
            setup=False
        )
        system.prepare()
        system.setup()
        system.files.no_output = True # no .lst, .npz and .txt output
        system.PFlow.run()

        # Initialize ANDES TDS
        tds = TDS(system)
        tds.config.fixt = 1
        tds.config.shrinkt = 0
        tds.config.tstep = Config.tstep
        tds.config.tf = Config.tf
        tds.t = 0.0
        tds.init()
        return jsonify({"message": "Simulation initialized successfully.", "start_time": tds.t}), 200
    except Exception as e:
        print("Error in initializing the simulation.")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
# @app.route('/init_tds', methods=['POST'])
# def init_tds():
#     global system
#     global tds

#     if system is None:
#         return jsonify({"error": "System not loaded."}), 400

#     try:
#         # Initialize Time-Domain-Simulation
#         tds = TDS(system)
#         tds.config.fixt = 1
#         tds.config.shrinkt = 0
#         tds.config.tstep = Config.tstep
#         tds.config.tf = Config.tf
#         tds.t = 0.0
#         tds.init()

#         return jsonify({"message": "TDS initialized", "start_time": tds.t}), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500
    
@app.route('/run_step', methods=['POST'])
def run_step():
    global tds

    if tds is None:
        return jsonify({"error": "TDS not initialized"}), 400

    if tds.t >= tds.config.tf:
        return jsonify({"message": "Simulation finished", "final_time": tds.t}), 200

    try:
        tds.itm_step()
        tds.t += tds.config.tstep
        return jsonify({"message": "Step executed successfully", "time": tds.t}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
 
@app.route('/neighbour_area', methods=['GET'])
def neighbour_area():
    global system
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

@app.route('/system_susceptance', methods=['GET'])
def system_susceptance():
    global system
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
            
        for x_area, lines in connecting_lines.items():
            bi = 0
            for line in lines:
                line_uid = system.Line.idx2uid(line)
                connection_status = system.Line.u.v[line_uid]
                xi = system.Line.x.v[line_uid]
                Sn = system.Line.Sn.v[line_uid]
                bi += (1/xi)*connection_status
            connecting_susceptance[int(x_area)] = bi

        return jsonify(connecting_susceptance), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/delta_equivalent', methods=['GET'])
def delta_equivalent():
    global system
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
            
        for x_area, lines in connecting_lines.items():
            bi = 0
            for line in lines:
                line_uid = system.Line.idx2uid(line)
                connection_status = system.Line.u.v[line_uid]
                xi = system.Line.x.v[line_uid]
                Sn = system.Line.Sn.v[line_uid]
                bi += (1/xi)*connection_status
            connecting_susceptance[int(x_area)] = bi
        
        for x_area, lines in connecting_lines.items():
            p_exchanged = 0
            p_exchanged_other = 0
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
        
        result = {}
        result['value'] = delta_equivalent
        return jsonify(result), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/set_point_change', methods=['POST'])
def set_point_change():
    global system
    try:
        set_points_data = request.get_json()
        for set_point in set_points_data:
            system.TDS_stepwise.set_set_points(set_point)
        return jsonify({'message': 'success'}), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/complete_variable_sync', methods=['GET'])
def complete_variable_sync(all_devices = False):
    global system
    try:
        data = request.args.to_dict()
        if data is None:
            return jsonify({"error": "No JSON data received!"}), 400
        response = {}
        model_name = data['model']
        var_name = data['var']
       
        model = getattr(system, model_name, None)
        var = getattr(model, var_name)
        value = var.v

        try:
            response['value'] = value
        except:
            response['value'] = None
        if type(value) == np.ndarray:
            response['value'] = value.tolist()
        return jsonify(response), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/partial_variable_sync', methods=['POST'])
def partial_variable_sync(all_devices = False):
    global system
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
        for idx in idxs:
            uid = model.idx2uid(idx)
            value = var.v[uid]
            res.append(value)
        try:
            response['value'] = res
        except:
            response['value'] = None
        if type(res) == np.ndarray:
            response['value'] = res.tolist()
        return jsonify(response), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/area_variable_sync', methods=['POST'])
def area_variable_sync(all_devices = False):
    global system
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
        
        if type(res) == np.ndarray:
            response['value'] = res.tolist()

        print(f"response is {response}")
        return jsonify(response), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/sync_time', methods=['GET'])
def sync_time():
    global system
    app_t = system.dae.t
    app_t = float(app_t)
    return jsonify({"time": app_t}) 

@app.route('/send_set_point', methods=['POST'])
def send_set_point():
    global system
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"error": "No JSON data received"}), 400

        required = ['model', 'idx', 'var', 'value']
        for field in required:
            if field not in data:
                return jsonify({"error": f"Missing required field '{field}'"}), 400

        model_name = data['model']
        var_name = data['var']
        idx = data['idx']
        value = float(data['value'])

        if not hasattr(system, model_name):
            return jsonify({"error": f"Model '{model_name}' not found"}), 400
        model = getattr(system, model_name)

        if not hasattr(model, var_name):
            return jsonify({"error": f"Variable '{var_name}' not in model '{model_name}'"}), 400
        var = getattr(model, var_name)

        try:
            uid = model.idx2uid(idx)
        except Exception:
            return jsonify({"error": f"Index '{idx}' not found in model '{model_name}'"}), 400

        var.v[uid] = value
        # print(f"[Setpoint] {model_name}.{var_name}[{idx}] ← {value}")

        return jsonify({"message": "Setpoint applied successfully"}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/ping', methods=['GET'])
def ping():
    return 'pong', 200