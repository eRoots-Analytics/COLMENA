from flask import Flask
from markupsafe import escape
from flask import url_for, request, render_template_string, jsonify
from andes.utils.paths import get_case, cases_root, list_cases
import os, sys
import andes as ad
import requests
import traceback
import Scripts.scripts.Roles as Roles
from copy import deepcopy
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

roleBasicSync = {'name':'RoleBasicSync', 'requirements':None, 'permanent':True, 'method': None}
roleBasicChange = {'name':'RoleBasicChange', 'requirements':None, 'permanent':True, 'method': None}

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
        
        #we check if the agent is paired with a device
        if len(data['device'].keys()) > 0:
            active_roles = [Roles.RoleBasicSync, Roles.RoleBasicChange]
            available_roles = [ Roles.RoleFreqOptimizer, Roles.RoleFreqSetter]
        return jsonify({"message": "Initialization successful"}), 200
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500

def publishMetric(param, channel):
    channel_url = []
    return
    for metric, channel in param.items():
        response = requests.post(channel_url[channel])

def syncInfo():
    sync_param = json_storage['device']
    response = requests.get(andes_url + '/device_sync', params = sync_param)
    new_data = response.json()
    for var, value in new_data.items():
        json_storage['params'][var] = value
    return True    
        
@app.route('/RoleBasicSync', methods=['GET'])
def RoleBasicSync():
    try:
        syncInfo()
        for channel, param in json_storage['channels']: 
            publishMetric(param, channel)
        return jsonify({'Message':'Success'}), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/RoleBasicChange', methods=['POST'])
def RoleBasicChange():
    roleChange()
    return jsonify({'Message':'Success'}), 200

@app.route('/run_get_roles', methods=['GET'])
def run_get_roles():
    for role in active_roles:
        method = role['method']
        method()
            

def roleChange():
    try:
        states = json_storage['params']
        roles_dict = deepcopy(json_storage['device'])
        roles_dict['param'] = 'M'
        roles_dict['value'] = (states['omega'] > 1.003)*1.5 + (states['omega'] < 1.003)*0.6
        response = requests.post(andes_url + '/device_role_change', param = roles_dict)
    except Exception as e:
        return jsonify({"error": str(e)}), 500