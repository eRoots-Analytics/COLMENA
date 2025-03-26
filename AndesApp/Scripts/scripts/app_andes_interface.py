from flask import Flask
from flask import url_for, request, render_template_string, jsonify, send_file
from typing import List, TYPE_CHECKING
from threading import Thread
from PIL import Image
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

system = None  
started = None  
print(sys.path)
app = Flask(__name__)
# In-memory storage for received JSON data (list of dictionaries)
json_storage = []
delta_t = 0.1
available_devices ={'device_1':{'model':'REDUAL', 'idx':'GENROU_1', 'assigned':False},
                    'device_2':{'model':'REDUAL', 'idx':'GENROU_2', 'assigned':False}}

# Route to load the simulation case
@app.route('/load_simulation', methods=['POST'])
def load_simulation():
    global system
    global controllable_devices
    global change
    global started
    global system_initial
    try:
        # Load the Andes simulation (but don't run it yet)ç
        change = 'None'
        app.config['started'] = False
        app.config['await_start'] = True
        n_redual = 4
        system_ieee = ad.load(get_case('ieee39/ieee39_full.xlsx'), setup=False)
        system = aux.build_new_system_legacy(system_ieee, new_model_name = 'REDUAL', n_redual =n_redual)
        system_initial = aux.build_new_system_legacy(system_ieee, new_model_name = 'REDUAL', n_redual =n_redual)
        for i in range(n_redual):
            idx = system.REDUAL.idx.v[i]
            system.REDUAL.alter(src='is_GFM', idx=idx, value = 0)
            system_initial.REDUAL.alter(src='is_GFM', idx=idx, value = 0)
        system.find_devices()
        system.REDUAL.prepare()
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
        system_initial.TDS.init()

        #We now define the controllable devices
        controllable_devices = []
        for idx in system.REDUAL.idx.v:
            device_dict = {}
            device_dict['idx'] = idx
            device_dict['model'] = 'REDUAL'
            device_dict['GridFormingRole'] = False
            device_dict['MonitoringRole'] = False
            device_dict['AutomaticGenerationResponse'] = True
            controllable_devices.append(device_dict)

        for idx in system.GENROU.idx.v[5:6]:
            continue
            device_dict = {}
            device_dict['idx'] = idx
            device_dict['model'] = 'REDUAL'
            device_dict['GridFormingRole'] = False
            device_dict['MonitoringRole'] = False
            device_dict['AutomaticGenerationResponse'] = True

            controllable_devices.append(device_dict)
        print('idx.v is ', system.REDUAL.idx.v)
        print('Simulation Loaded with controllable devices', controllable_devices)

        return jsonify({"message": f"Simulation loaded successfully"}), 200
    except Exception as e:
        print("error in loading the grid")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/assign_device', methods=['GET'])
def assign_device():
    try:
        role = request.args.get('role')
        print("role is", controllable_devices)
        # Get the case file path from the request
        for device in controllable_devices:
            print("role is", role)
            if not device[role]:
                response = device
                device[role] = True
                return jsonify(response), 200
        return jsonify(response), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/assign_out', methods=['POST'])
def assign_out():
    try:
        data = request.get_json()
        idx = data['idx'] 
        model = data['model']
        role = data['role']
        for item in controllable_devices:
            if idx == item['idx'] and model == item['model'] and role == item[role]:
                item[role] = False
                return jsonify({'message': 'Role ended'}), 200
        return jsonify({'message': 'Role ended'}), 200
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
            res = var.v[0]
            print('Var value is', var.v)
        return jsonify({"message": 'printed'}), 200
    except Exception as e:
        change = 'printed'
        print(change)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# Route to run the previously loaded simulation
@app.route('/line_pairings', methods=['GET'])
def line_pairings():
    line_pairings = {}
    try:
        for i, bus_from in enumerate(system.Lines.bus1.v):
            bus_to = system.Lines.bus2.v[i]
            line_pairings[bus_to] = bus_from      

        return jsonify(line_pairings), 200
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
        idx = data['idx']
        model_name = data['model']
        param = data['var']
        value = data['value']
        model = getattr(system, model_name)
        uid = model.idx2uid(idx)
        if hasattr(data,'add'): 
            if data['add']:
                param_in_andes = getattr(model,param)
                param_in_andes = param_in_andes.v[uid]
                value = param_in_andes + value 
        model.alter(idx =idx, src=param, value = value)
        change = 'changed'
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

@app.route('/sync_time', methods=['GET'])
def sync_time():
    app_t = system.TDS_stepwise.dae.t
    return jsonify({"time": app_t}) 

@app.route('/run', methods=['GET'])
def run():
    t_run = request.args.get('t_run')
    t_run = float(t_run)
    try:
        system.TDS_stepwise.run_andes_inapp(t_run)
        print(f't_run is {t_run}')
        print(f't_dae is {system.dae.t}')
        t_dae = float(system.dae.t)
        return jsonify({"Message": 'Success', "Time":t_dae}), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/run_real_time', methods=['GET'])
def run_real_time():
    try:
        global started

        set_points = []
        set_points += [{'model':'Line', 'idx':'Line_19', 't':10, 'param':'u', 'value':0, 'add':False}]
        set_points += [{'model':'Line', 'idx':'Line_19', 't':30, 'param':'u', 'value':1, 'add':False}]
        while app.config['await_start']:
            time.sleep(1)

        t_0 = time.time()
        t_run = float(request.args.get('t_run', 90))  
        delta_t = float(request.args.get('delta_t', 0.1))  
        app.config['started'] = True
        system.PFlow.run()
        while system.dae.t <= t_run:
            if time.time() - t_0 >= delta_t: 
                system.TDS_stepwise.run_individual_batch(t_sim = delta_t)
                print(f't_run is {t_run}')
                print(f't_run is {delta_t}')
                print(f't_dae is {system.dae.t}')
                t_0 = time.time()
            system.TDS_stepwise.set_set_points(set_points)
        return jsonify({"Message": 'Success', "Time":system.dae.t}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/plot', methods=['GET'])
def plot():
    try:
        data = request.args.to_dict()
        model_name = data['model']
        var_name = data['var']
        model = getattr(system, model_name)
        var = getattr(model, var_name)
        system.TDS_stepwise.load_plotter()
        matplotlib.use('TkAgg')
        fig, ax = system.TDS_stepwise.plt.plot(system.Bus.v)
        fig, ax = system.TDS_stepwise.plt.plot(system.GENROU.omega)
        # Save the plot to a BytesIO object rather than displaying it
        img = io.BytesIO()
        fig.savefig(img, format='png')
        img.seek(0)
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
    time.sleep(2)
    responseLoad = requests.post(andes_url + '/load_simulation', json=andes_dict)
    responseLoad = requests.post(andes_url + '/run', json=andes_dict)