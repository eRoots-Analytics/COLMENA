"""
Andes server API: rules and protocols to communicate with Andes via a flask app.
"""

import traceback
import numpy as np
from flask import Flask
from flask import request, jsonify

from src.config.config import Config
from andes import load
from andes.routines.tds import TDS

# App 
app = Flask(__name__)

# Global variables
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

        # Force PQ loads to behave as constant power in TDS
        system.PQ.config.p2p = 1.0
        system.PQ.config.p2i = 0.0
        system.PQ.config.p2z = 0.0
        # system.PQ.config.p2p = 0.5
        # system.PQ.config.p2i = 0.3
        # system.PQ.config.p2z = 0.2

        system.PQ.pq2z = 0

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
    result = set()  # to ensure uniqueness.
    response = {}
    
    try:
        area = request.args.get('area', type=int)

        for i, line in enumerate(system.Line.idx.v):
            bus1 = system.Line.bus1.v[i]
            bus2 = system.Line.bus2.v[i]
            bus1_idx = system.Bus.idx2uid(bus1)
            bus2_idx = system.Bus.idx2uid(bus2)
            area1 = system.Bus.area.v[bus1_idx]
            area2 = system.Bus.area.v[bus2_idx]

            if area1 != area2 and (area1 == area or area2 == area):
                if area1 == area:
                    area_nbr = area2
                else: 
                    area_nbr = area1
                if area_nbr != area:
                    result.add(area_nbr)
        response['value'] = list(result)
        return jsonify(response), 200
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/system_susceptance', methods=['GET'])
def system_susceptance():
    global system

    try:
        area = request.args.get('area', type=int)
        area_list_str = request.args.get('area_list')

        if not area_list_str:
            return jsonify({"error": "Missing required parameter: area_list"}), 400

        target_areas = [int(a) for a in area_list_str.split(',')]
        connecting_lines = {x_area: [] for x_area in target_areas}
        connecting_susceptance = {}

        for i, line in enumerate(system.Line.idx.v):
            bus1 = system.Line.bus1.v[i]
            bus2 = system.Line.bus2.v[i]
            bus1_index = system.Bus.idx2uid(bus1)
            bus2_index = system.Bus.idx2uid(bus2)
            area1 = system.Bus.area.v[bus1_index]
            area2 = system.Bus.area.v[bus2_index]

            # Only look at the known neighbor connections
            if area == area1 and area2 in target_areas:
                connecting_lines[area2].append(line)
            elif area == area2 and area1 in target_areas:
                connecting_lines[area1].append(line)

        for area, lines in connecting_lines.items():
            bi = 0
            for line in lines:
                line_uid = system.Line.idx2uid(line)
                connection_status = system.Line.u.v[line_uid]
                xi = system.Line.x.v[line_uid]
                bi += (1 / xi) * connection_status
            connecting_susceptance[area] = bi

        return jsonify(connecting_susceptance), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/interface_buses', methods=['GET'])
def interface_buses():
    global system
    try:
        area = request.args.get('area', type=int)
        area_list_str = request.args.get('area_list')

        if not area_list_str:
            return jsonify({"error": "Missing required parameter: area_list"}), 400

        target_areas = [int(a) for a in area_list_str.split(',')]
        all_areas = set(target_areas + [area])
        interface_buses_by_area = {a: set() for a in all_areas}

        for i, line in enumerate(system.Line.idx.v):
            bus1 = system.Line.bus1.v[i]
            bus2 = system.Line.bus2.v[i]
            bus1_index = system.Bus.idx2uid(bus1)
            bus2_index = system.Bus.idx2uid(bus2)
            area1 = system.Bus.area.v[bus1_index]
            area2 = system.Bus.area.v[bus2_index]

            if area1 in all_areas and area2 in all_areas and area1 != area2:
                interface_buses_by_area[area1].add(bus1)
                interface_buses_by_area[area2].add(bus2)

        # Convert sets to sorted lists for JSON serialization
        interface_buses_by_area = {
            k: sorted(list(v)) for k, v in interface_buses_by_area.items()
        }

        return jsonify(interface_buses_by_area), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/exact_power_transfer', methods=['POST'])
def exact_power_transfer():
    global system
    try:
        data = request.get_json()
        area = int(data['area'])
        interface_buses = {int(k): [int(b) for b in v] for k, v in data['interface_buses'].items()}

        power_transfer = {int(other_area): 0.0 for other_area in interface_buses.keys() if int(other_area) != area}


        for i, line in enumerate(system.Line.idx.v):
            line_uid = system.Line.idx2uid(line)
            if system.Line.u.v[line_uid] == 0:
                continue  # skip out-of-service lines

            bus1 = system.Line.bus1.v[i]
            bus2 = system.Line.bus2.v[i]
            bus1_uid = system.Bus.idx2uid(bus1)
            bus2_uid = system.Bus.idx2uid(bus2)

            area1 = system.Bus.area.v[bus1_uid]
            area2 = system.Bus.area.v[bus2_uid]

            # Only process lines where this area is the 'from' side
            if area1 == area and area2 != area and area2 in interface_buses.keys():
                v1 = system.Bus.v.v[bus1_uid]
                v2 = system.Bus.v.v[bus2_uid]
                a1 = system.Bus.a.v[bus1_uid]
                a2 = system.Bus.a.v[bus2_uid]
                gh = system.Line.gh.v[line_uid]
                ghk = system.Line.ghk.v[line_uid]
                bhk = system.Line.bhk.v[line_uid]
                phi = system.Line.phi.v[line_uid]
                itap = system.Line.itap.v[line_uid]
                itap2 = system.Line.itap2.v[line_uid]
                u = system.Line.u.v[line_uid]

                p_flow = u * (v1**2 * (gh + ghk) * itap2 -
                              v1 * v2 * (ghk * np.cos(a1 - a2 - phi) +
                                         bhk * np.sin(a1 - a2 - phi)) * itap)

                power_transfer[int(area2)] += p_flow
            
            elif area2 == area and area1 != area and area1 in interface_buses.keys():
                v1 = system.Bus.v.v[bus1_uid]
                v2 = system.Bus.v.v[bus2_uid]
                a1 = system.Bus.a.v[bus1_uid]
                a2 = system.Bus.a.v[bus2_uid]
                gh = system.Line.gh.v[line_uid]
                ghk = system.Line.ghk.v[line_uid]
                bhk = system.Line.bhk.v[line_uid]
                phi = system.Line.phi.v[line_uid]
                itap = system.Line.itap.v[line_uid]
                u = system.Line.u.v[line_uid]

                p_flow = u * (v2 ** 2 * (gh + ghk) -
                              v1 * v2 * (ghk * np.cos(a1 - a2 - phi) -
                                         bhk * np.sin(a1 - a2 - phi)) * itap)

                power_transfer[int(area1)] += p_flow

        return jsonify({"power_transfer": power_transfer}), 200

    except Exception as e:
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
def area_variable_sync(all_devices=False):
    global system
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"error": "No JSON data received!"}), 400

        response = {}
        model_name = data['model']
        var_name = data['var']
        area = int(data['area'])

        # Get all buses in this area
        area_buses = [
            system.Bus.idx.v[i]
            for i in range(len(system.Bus.idx.v))
            if system.Bus.area.v[i] == area
        ]

        model = getattr(system, model_name, None)
        var = getattr(model, var_name)

        res = []

        if model_name == 'Bus':
            # Simple case: use bus directly
            for i, bus in enumerate(model.idx.v):
                if bus in area_buses:
                    res.append(var.v[i])

        elif model_name in ['TGOV1', 'TGOV1N']:
            if hasattr(model, 'syn'):
                # First, get GENROUs in the area
                genrou_in_area = [
                    (system.GENROU.idx.v[i], system.GENROU.name.v[i])
                    for i in range(len(system.GENROU.idx.v))
                    if system.GENROU.bus.v[i] in area_buses
                ]
                genrou_idx_set = set(idx for idx, _ in genrou_in_area)
                genrou_name_set = set(name for _, name in genrou_in_area)

                for i, syn in enumerate(model.syn.v):
                    if syn in genrou_idx_set or syn in genrou_name_set:
                        res.append(var.v[i])

            else:
                return jsonify({"error": f"{model_name} model lacks 'syn' or 'gen' attribute"}), 400

        else:
            # All other models assumed to have a bus field
            for i, bus in enumerate(model.bus.v):
                if bus in area_buses:
                    res.append(var.v[i])

        response['value'] = res.tolist() if isinstance(res, np.ndarray) else res
        return jsonify(response), 200

    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    
@app.route('/set_value', methods=['POST'])
def set_value():
    global system
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"error": "No JSON data received"}), 400

        required = ['model', 'src', 'idx', 'attr', 'value']
        for field in required:
            if field not in data:
                return jsonify({"error": f"Missing required field '{field}'"}), 400

        model_name = data['model']
        src = data['src']
        idx = data['idx']
        attr = data['attr']
        value = data['value']

        if not hasattr(system, model_name):
            return jsonify({"error": f"Model '{model_name}' not found"}), 400

        model = getattr(system, model_name)

        # Apply the value using .set()
        model.set(src=src, idx=idx, attr=attr, value=value)

        return jsonify({"message": "Value set successfully"}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


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

        return jsonify({"message": "Setpoint applied successfully"}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/change_parameter_value', methods=['POST'])
def change_parameter_value():
    global system
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"error": "No JSON data received"}), 400

        required = ['model', 'idx', 'param', 'value']
        for field in required:
            if field not in data:
                return jsonify({"error": f"Missing required field '{field}'"}), 400

        model_name = data['model']
        param_name = data['param']
        idx = data['idx']
        value = float(data['value'])

        if not hasattr(system, model_name):
            return jsonify({"error": f"Model '{model_name}' not found"}), 400
        model = getattr(system, model_name)

        if not hasattr(model, param_name):
            return jsonify({"error": f"Variable '{param_name}' not in model '{model_name}'"}), 400
        param = getattr(model, param_name)

        try:
            uid = model.idx2uid(idx)
        except Exception:
            return jsonify({"error": f"Index '{idx}' not found in model '{model_name}'"}), 400

        param.v[uid] = value

        return jsonify({"message": "Setpoint applied successfully"}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/ping', methods=['GET'])
def ping():
    return 'pong', 200