from flask import Flask
from markupsafe import escape
from flask import url_for, request, render_template_string, jsonify, current_app
from andes.utils.paths import get_case, cases_root, list_cases
from flask_sqlalchemy import SQLAlchemy
import os, sys
import andes as ad
import requests
import traceback
import numpy as np
from copy import deepcopy
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
print(sys.path)
app = Flask(__name__)
json_storage = []
KPI = {}

def computeKPI():
    with app.app_context(): 
        global KPI
        try:
            first = False
            metrics = []
            if KPI == {}:
                first = True
                KPI['freq'] = None
                KPI['diff_freq'] = None
            for i in json_storage:
                metric = i['value']
                metrics.append(metric)
            if len(metrics) !=0:
                KPI['freq'] = np.mean(metrics)
            if not first and KPI['freq']!=None:
                KPI['diff_freq'] = - KPI['freq'] + np.mean(metrics)    
                KPI['diff_freq'] = 1 - np.cumsum(metrics)    
            return KPI
        except Exception as e:
            print(e)
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

@app.route('/initialize', methods=['POST'])
def initialize():
    global channel_info 
    channel_info = {}
    try:
        data = request.get_json() 
        channel_info['metric'] = data['metric']
        channel_info['url'] = data['url']
        channel_info['password'] = data['password']
        return jsonify({"message": "Initialization successful"}), 200
    except Exception as e:
        print(e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/publish', methods=['POST'])
def publish(): 
    try:
        data = request.get_json()
        if data['metric'] ==  channel_info['metric']:
            json_storage[len] = data['value']
        return jsonify({"message": "Initialization successful"}), 200
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500

@app.route('/getKPI', methods=['GET'])
def getKPI(): 
    with app.app_context():    
        try:
            return jsonify({"KPI": KPI}), 200
        except Exception as e:
            print(e)
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500
    
@app.route('/update_channel', methods=['POST'])
def update_channel(): 
    with app.app_context():    
        global json_storage
        try:
            data = request.get_json()  
            t_filter = data['t_filter']
            filtered_data = []
            for measurement in json_storage:
                if measurement['t'] < t_filter:
                    filtered_data.append(measurement)
            json_storage = filtered_data
            computeKPI()
            return jsonify({"Message": "Success"}), 200
        except Exception as e:
            print(e)
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500
    

