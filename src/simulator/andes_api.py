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
@app.route('/get_grid_type', methods=['grid'])
def get_grid_type():
    global tds

    if tds is None:
        return jsonify({"error": "TDS not initialized"}), 400

    if tds.t >= tds.config.tf:
        return jsonify({"message": "Simulation finished", "final_time": tds.t}), 200

    try:
        grid_type = app.config['grid']
        return jsonify({"value": grid_type}), 200
    except Exception as e:
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

        return jsonify(response), 200
    except Exception as e:
        print(e)
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