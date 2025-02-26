from flask import Flask
from flask import url_for, request, render_template_string, jsonify, current_app
from copy import deepcopy
from threading import Thread
import os, sys
import andes as ad
import requests
import time
import traceback
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
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
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
db = SQLAlchemy(app)
# In-memory storage for received JSON data (list of dictionaries)
json_storage = {}
# Define a model to store JSON data
class Data(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    json_data = db.Column(db.Text, nullable=False)

# Initialize the database
with app.app_context():
    db.create_all()

def publishMetric(channel):
    with app.app_context():
        try:
            channel_url = channel['url']
            metric = channel['metric']
            publish_dict = {'value':None, 't': time.time()}
            publish_dict['value'] = getattr(json_storage, metric)
            response = requests.post(channel_url, json = publish_dict)
            return response,200
        except Exception as e:
            return jsonify({'Message':'Success'}), 500
            

def syncInfo():
    with app.app_context():
        sync_param = json_storage['device']
        response = requests.get(andes_url + '/device_sync', params = sync_param)
        new_data = response.json()
        for var, value in new_data.items():
            json_storage['params'][var] = value
        return True    
        
def RoleBasicSync():
    with app.app_context():
        try:
            syncInfo()
            for channel in json_storage['channels'].values(): 
                publishMetric(channel)
            return jsonify({'Message':'Success'}), 200
        except Exception as e:
            print(e)
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500
    
def RoleBasicChange():
    with app.app_context():
        roleChange()
        return jsonify({'Message':'Success'}), 200
        
def roleChange(role = None):
    with app.app_context():
        try:
            if role == None:
                states = json_storage['params']
                roles_dict = deepcopy(json_storage['device'])
                roles_dict['param'] = 'M'
                roles_dict['value'] = (states['omega'] > 1.003)*1.5 + (states['omega'] < 1.003)*0.6
                responseParam = requests.post(andes_url + '/device_role_change', param = roles_dict)
            else:
                roles_dict = role
                responseParam = requests.post(andes_url + '/device_role_change', param = roles_dict)
            print(f"Response status code for device : {responseParam.status_code}")
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
def execute_roles():
    with app.app_context():
        try:
            for role in active_roles:
                method = role['method']
                role_thread = Thread(target=method)
                role_thread.start()
            return jsonify({'Message': 'Success'}), 200

        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
def set_active_roles():
    with app.app_context():
        new_active_roles = []
        for role in json_storage['roles']:
            if role['permanent']:
                new_active_roles.append(role)
            else:
                metric = role['metric']
                condition = role['condition']
                KPI = None
                for channel in json_storage['channels']:
                    if metric == channel['metric']:
                        channel_url = channel['url']
                        KPI = requests.get(channel_url + '/getKPI')
                if condition(KPI):
                    new_active_roles.append(role)
        active_roles = new_active_roles

def RoleFreqOptimizer(role):
    #This 
    with app.app_context():
        try:    
            roles_dict = {}
            channel = json_storage['channels'].values()[0]
            channel_url = channel['url']
            responseKPI = requests.get(channel_url + '/getKPI')
            KPI = responseKPI.json() 

            roles_dict['model'] = 'TGOV1'
            roles_dict['param'] = 'wref'
            roles_dict['value'] = 1 + KPI['freq_diff']/3
            return roles_dict
        except Exception as e:
            print(e)
            return jsonify({"error": str(e)}), 500

def RoleFreqSetter():
    return
    with app.app_context():  
        try:    
            roles_dict = {}
            channel = json_storage['channels'].values()[0]
            channel_url = channel['url']
            responseKPI = requests.get(channel_url + '/getKPI')
            KPI = responseKPI.json() 

            roles_dict['model'] = 'TGOV1'
            roles_dict['param'] = 'omega'
            roles_dict['value'] = KPI['freq_diff']/3
        except Exception as e:
            print(e)
            return jsonify({"error": str(e)}), 500

def RoleConstant(role):
    with app.app_context():  
        try:
            role_method = role['method']
            while role in active_roles:
                role_method()
        except Exception as e:
            print(e)
            return jsonify({'error'. str(e)}), 500 
        
roleBasicSync = {'name':'RoleBasicSync', 'requirements':None, 'permanent':True, 'method': RoleBasicSync}
roleBasicChange = {'name':'RoleBasicChange', 'requirements':None, 'permanent':True, 'method': RoleBasicChange}
roleFreqOptimizer = {'name':'RoleBasicChange', 'requirements':None, 'permanent':True, 'method': RoleFreqOptimizer}
roleFreqSetter = {'name':'RoleBasicChange', 'requirements':None, 'permanent':True, 'method': RoleFreqSetter}

@app.route('/initialize', methods=['POST'])
def initialize():
    global andes_url
    global active_roles
    try:
        data = request.get_json() 
        json_storage['characteristics'] = data['characteristics'] 
        json_storage['channels'] = data['channels'] 
        json_storage['device'] = data['device'] 
        json_storage['andes'] = data['andes'] 
        andes_url = data['andes']['url']
        json_storage['params'] = data['params'] 
        json_storage['roles'] = [roleBasicSync, roleBasicChange, roleFreqOptimizer, roleFreqSetter]
        
        #we check if the agent is paired with a device
        if len(data['device'].keys()) > 0:
            active_roles = [roleBasicSync, roleBasicChange]
            available_roles = [ roleFreqOptimizer, roleFreqSetter]
        else:
            active_roles = []
        return jsonify({"message": "Initialization successful"}), 200
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500
    
@app.route('/run_agent', methods = ['GET'])
def run_agent():
    #this is executed consistently
    try:
        for role in active_roles:
            print(role['name'])
            run_role = role['method']
            agent_thread = Thread(target=run_role)
            agent_thread.start()
        set_active_roles()
        return jsonify({'Message':'Success'}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

        