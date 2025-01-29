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
import matplotlib.pyplot as plt
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
from andes.utils.paths import get_case, cases_root, list_cases
import andes as ad

print(sys.path)
app = Flask(__name__)
# Placeholder login form
login_form_html = """
    <form method="post">
        <p><input type="text" name="username"></p>
        <p><input type="password" name="password"></p>
        <p><input type="submit" value="Login"></p>
    </form>
"""
# In-memory storage for received JSON data (list of dictionaries)
json_storage = []
delta_t = 0.1

@app.route('/')
def index():
    return 'index'


# Route to load the simulation case
@app.route('/load_simulation', methods=['POST'])
def load_simulation():
    global loaded_system
    global system
    try:
        # Get the case file path from the request
        case_file = request.json.get('case_file')

        # Load the Andes simulation (but don't run it yet)
        system = ad.load(case_file, setup=True)
        system.PFlow.run()
        system.TDS_stepwise.init()
        loaded_system = (system.Bus.n > 0)
        return jsonify({"message": f"Simulation {case_file} loaded successfully"}), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Route to run the previously loaded simulation
@app.route('/run_simulation', methods=['POST'])
def run_simulation():
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

@app.route('/upload_json', methods=['POST'])
def upload_json():
    global andes_dir
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"error": "No JSON data received!"}), 400

        #Store data in JSON storage
        andes_dir = len(json_storage)
        json_storage.append(data)

        # Store the received JSON in the database
        json_entry = Data(json_data=str(data))
        db.session.add(json_entry)
        db.session.commit()

        print(f"DEBUG: Received JSON: {data}")
        return jsonify({"message": "JSON received successfully!", "data": data}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to retrieve all stored JSON data
@app.route('/show_db_data', methods=['GET'])
def show_db_data():
    all_data = Data.query.all()
    result = [{'id': entry.id, 'json_data': entry.json_data} for entry in all_data]
    return jsonify(result)

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
def device_role_change():
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
        idx = int(idx)
        model_name = data['model_name']
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
        if 'v' in response.keys():
            return jsonify(response), 200
        
        states = model._states_and_ext() 
        algebs = model._algebs_and_ext()
        othervars = OrderedDict(states)
        othervars.update(algebs)

        for var_name in othervars:
            var = getattr(model, var_name)
            uid = int(uid)
            var_value = var.v[uid]
            if isinstance(var_value, np.generic):
                var_value = var_value.item()
            elif isinstance(var_value, np.ndarray):
                var_value = var_value.tolist()
            response[var_name] = var_value

        #Since this is used at the very beginning to initialize the agents we can now start the simulation 
        json_storage['start'] = True
        return jsonify(response), 200
    except Exception as e:
        print(e)
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
    app_t = system.TDS.dae.t
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
        fig, ax = system.TDS_stepwise.plt.plot(var, a=(0,1,2,3))
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
    app.run(debug=True)
    andes_url = 'http://127.0.0.1:5000'
    andes_directory = ad.get_case("kundur/kundur_full.xlsx")
    andes_directory = ad.get_case("ieee39/ieee39_full.xlsx")
    andes_dict = {"case_file":andes_directory}
    kwargs = {'andes_url':andes_url, 'device_idx':1, 'model_name':'GENROU'} 
    responseLoad = requests.post(andes_url + '/load_simulation', json=andes_dict)
    responseSimulation = requests.get(andes_url + '/run_real_time', params = {'model_name':'GENROU', 'var_name':'omega'})
    responsePlot = requests.get(andes_url + '/plot', params = {'model_name':'GENROU', 'var_name':'omega'})
    
    #responsePlot = 600
    if not isinstance(responsePlot, int) and responsePlot.status_code == 200:
        img = Image.open(BytesIO(responsePlot.content))
        # Save or display the image as needed
        img.show()  # To display it directly
        img.save("plot.png")  # To save it to a file
    elif not isinstance(responsePlot, int):
        print(f"Error: {responsePlot.status_code} - {responsePlot.json().get('error')}")