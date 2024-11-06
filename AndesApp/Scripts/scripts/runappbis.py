from app_andes_interface import app
from flask import Flask
from markupsafe import escape
from flask import url_for, request, render_template_string, jsonify
from andes.utils.paths import get_case, cases_root, list_cases
from flask_sqlalchemy import SQLAlchemy
import requests
from threading import Thread
import time, os, sys
from agent_app_bis import app as agentapp
from channel_app import app as channelapp

#We first define the andes directory
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
import andes as ad
andes_directory = ad.get_case("kundur/kundur_full.xlsx")
andes_dict = {"case_file":andes_directory}

#We test a simple change of behavior
roles_dict = {"idx": 1,"model_name": 'Bus',"param" : 'a0',"value" : 0.5}
sync_param ={"idx": 1, 'model_name': ['Bus'],'var_name': ['v']}
andes_url = 'http://127.0.0.1:5000'
agent_url = 'http://127.0.0.1:'
channel_url = 'http://127.0.0.1:'

sys = ad.System()

def run_app(port, app):
    """Runs the Flask app on a specified port."""
    app.run(debug=False, port=port)

def colmena_iteration():
    responseRun = requests.get(andes_url + '/run', params = {'t_run':0.1})
    if responseRun.status_code == 200:
        # Print the raw content of the response for debugging
        print("Response content:", responseRun.text)
    elif responseRun.status_code == 500:
        e = responseRun.json()['error']
        print(e)
    #response_dict = responseRun.json()
    response_dict = responseRun.json()
    print(f'responseRun is {responseRun}')
    return response_dict['Time']

def initialize_agents(n):
    for i in range(1,n+1):
        port = 6000 + i  # Assign a unique port to each agent
        channel_port = 7000 + 1
        agent_i_url = agent_url + str(port)
        channel_i_url = channel_url + str(channel_port)
        device_dict = {"idx": i, 'model_name': 'GENROU'}
        andes_dict = {'url': andes_url}
        channel_1 = {'url':str(channel_i_url), 'metric':'omega'}
        channels_dict = {'channel_1': channel_1}
        agent_dict = {'device': device_dict, 'andes': andes_dict, 'channels': channels_dict, 'characteristics': ['generators'], 'params': {}}
        
        # Sync device (GET request)
        responseVarInit = requests.get(andes_url + '/device_sync', params=device_dict)
        print(f"Response status code for device {i}: {responseVarInit.status_code}")
        
        # Assuming the response is valid and JSON
        agent_dict['params'] = responseVarInit.json()

        # Start the agent app in a new thread so that it doesn't block
        agent_thread = Thread(target=run_app, args=(port, agentapp))
        agent_thread.start()
        # Send the POST request to the running agent
        responseInit = requests.post(agent_i_url + '/initialize', json=agent_dict)
        print(f"Post request to agent {i} returned status code: {responseInit.status_code}")
    return

def initialize_channels(n):
    for i in range(1,n+1):
        port = 7000 + i  # Assign a unique port to each agent
        channel_i_url = agent_url + str(port)
        andes_dict = {'url': andes_url}
        channel_dict = {'url': channel_i_url, 'andes': andes_url, "metric":'omega', 'password':'password'}

        # Start the agent app in a new thread so that it doesn't block
        agent_thread = Thread(target=run_app, args=(port, channelapp))
        agent_thread.start()
        
        # Send the POST request to the running agent
        responseInit = requests.post(channel_i_url + '/initialize', json=channel_dict)
        print(f"Post request to agent {i} returned status code: {responseInit.status_code}")
        
if __name__ == '__main__':
    T = 50
    n = 4
    c = 1 
    agents = range(1,5)
    responseLoad = requests.post(andes_url + '/load_simulation', json=andes_dict)
    
    initialize_channels(c)
    initialize_agents(n)
    
    for i in range(T):
        t_dae = colmena_iteration()
        for agent in range(n):
            print(f'iteration {agent}')
            port = 6000 + 1 + agent 
            agent_i_url = agent_url + str(port)
            responseRoles = requests.get(agent_i_url + '/run_agent')
            active_roles = responseRoles.json()
            print(active_roles)
        for channel in range(c):
            print(f'iteration {agent}')
            port = 7000 + 1 + channel 
            filter_dict = {'t_filter': 0.1}
            channel_i_url = agent_url + str(port)
            responseChannel = requests.post(channel_i_url + '/update_channel', json = filter_dict)
            print(responseChannel)
    responsePlot = requests.get(andes_url + '/plot', params = {'model_name':'GENROU' ,'variable':'omega'})
            