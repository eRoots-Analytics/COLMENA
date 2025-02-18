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
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
from andes.utils.paths import get_case, cases_root, list_cases
import andes as ad

controllable_devices = []  
system = None  
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
    global controllable_devices
    global system
    try:

        # Load the Andes simulation (but don't run it yet)
        system = ad.load(get_case('ieee39/ieee39_full.xlsx'), setup=False)
        system = aux.build_new_system_legacy(system, new_model_name = 'REDUAL', n_redual =4)
        system.find_devices()
        system.REDUAL.prepare()
        system.Toggle.alter(src='dev', idx = 'Toggler_1', value = 'GENROU_8')
        system.setup()
        system.TDS_stepwise.config.criteria = 0
        system.PFlow.run()
        system.TDS.init()

        #We now define the controllable devices
        controllable_devices = []
        for idx in system.REDUAL.idx.v:
            device_dict = {}
            device_dict['idx'] = idx
            device_dict['model'] = 'REDUAL'
            device_dict['assigned'] = False
            controllable_devices.append(device_dict)
        return jsonify({"message": f"Simulation loaded successfully"}), 200
    except Exception as e:
        print("error in loading the grid")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/assign_device', methods=['GET'])
def assign_device():
    global controllable_devices
    global system
    try:
        # Get the case file path from the request
        for device in controllable_devices:
            if not device['assigned']:
                response = device
                device['assigned'] = True
                return jsonify(response), 200
        return jsonify({"message": f"All devices already assigned"}), 200
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
        idx = data['device_idx']
        model_name = data['model_name']
        param = data['param']
        value = data['value']
        model = getattr(system, model_name)
        uid = model.idx2uid(idx)
        if getattr(data,'add', None) is not None and data['add']:
            param_in_andes = getattr(model,param)
            param_in_andes = param_in_andes.v[uid]
            value = param_in_andes + value 
        model.alter(idx =idx, src=param, value = value)
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
    try:
        data = request.args.to_dict()
        if data is None:
            return jsonify({"error": "No JSON data received!"}), 400
        response = {}

        idx = data['idx']
        model_name = data['model']
        model = getattr(system, model_name)
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
        idx = int(idx)
        model_name = data['model_name']
        param_name = data['param']
       
        model = getattr(system, model_name)
        param = getattr(model, param_name)
        uid = model.idx2uid(idx)
        value = param.v[uid]
        response['value'] = value
        
        return jsonify(response), 200
    except Exception as e:
        print(e)
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
    while not json_storage['start']:
        _=0
    t_0 = time.time()
    t_run = float(request.args.get('t_run', 30))  
    delta_t = float(request.args.get('delta_t', 30))  
    try:
        while system.dae.t <= t_run:
            if time.time() - t_0 >= delta_t: 
                system.TDS_stepwise.run_individual_batch(delta_t)
                print(f't_run is {t_run}')
                print(f't_dae is {system.dae.t}')
                t_0 = time.time()
        return jsonify({"Message": 'Success', "Time":system.dae.t}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/plot', methods=['GET'])
def plot():
    try:
        data = request.args.to_dict()
        model_name = data['model_name']
        var_name = data['var_name']
        model = getattr(system, model_name)
        var = getattr(model, var_name)
        system.TDS_stepwise.load_plotter()
        fig, ax = system.TDS_stepwise.plt.plot(var, a=(0))
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
    app.run(host="0.0.0.0", port=5000, debug=True)
    andes_url = 'http://127.0.0.1:5000'
    andes_directory = ad.get_case("kundur/kundur_full.xlsx")
    andes_directory = ad.get_case("ieee39/ieee39_full.xlsx")
    andes_dict = {"case_file":andes_directory}
    kwargs = {'andes_url':andes_url, 'device_idx':1, 'model_name':'GENROU'} 
    responseLoad = requests.post(andes_url + '/load_simulation', json=andes_dict)