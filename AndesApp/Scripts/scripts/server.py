from flask import Flask
from flask import request, jsonify, send_file
import os

desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "plots")
os.makedirs(desktop_path, exist_ok=True)
import requests
import os, sys, io
import time
import numpy as np
import traceback
import aux_function as aux
import matplotlib.pyplot as plt
import matplotlib
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
# from andes.utils.paths import get_case, cases_root, list_cases
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
            print(f"system.TGOV1N.b is {system.TGOV1N.b}")
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
                Sn = system.Line.Sn.v[line_uid]
                bi += (1/xi)*connection_status
                print(f"line is {line} bi is {bi}")
            connecting_susceptance[int(x_area)] = bi
        
        print(f"connecting_susceptance is {connecting_susceptance}")
        print(f"other_areas is {other_areas}")
        return jsonify(connecting_susceptance), 200
    except Exception as e:
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

@app.route('/sync_time', methods=['GET'])
def sync_time():
    app_t = system.dae.t
    app_t = float(app_t)
    return jsonify({"Simuation time": app_t}) 

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
            set_points += [{'model':'PQ', 'idx':'PQ_5', 't':6, 'param':'Ppf', 'value':5*Ppf_pq5, 'add':False}]
        
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
    
@app.route('/run_step', methods=['POST'])
def run_step():
    global set_points
    try:
        data = request.get_json()
        delta_t = float(data.get('delta_t', 0.1))   # Default step size: 0.1s
        speed_factor = float(data.get('speed', 1))  # Optional speed-up for testing

        # Apply scheduled setpoints before stepping
        if set_points:
            system.TDS_stepwise.set_set_points(set_points)

        # Run just one individual step
        system.TDS_stepwise.run_individual_batch(t_sim=delta_t * speed_factor)

        # Return the new simulation time
        return jsonify({
            "message": "Step completed",
            "t": float(system.dae.t)
        }), 200

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
            plots['tgov_pout']=system.TGOV1.pref

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
    time.sleep(2)
    responseLoad = requests.post(andes_url + '/load_simulation', json=andes_dict)
    responseLoad = requests.post(andes_url + '/run', json=andes_dict)