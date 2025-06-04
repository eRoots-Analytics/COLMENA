from PIL import Image
from io import BytesIO
import requests
import os, sys, io
import numpy as np
import time
import threading
import matplotlib.pyplot as plt
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(os.path.dirname(current_directory))
sys.path.insert(0, two_levels_up)
from andes.utils.paths import get_case, cases_root, list_cases
import andes as ad

def plot_response(responseAndes, filename):
    if responseAndes.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(responseAndes.content)
        print(f"Plot saved as {filename}")
    else:
        print("Failed to get plot:", responseAndes.text)

andes_directory = ad.get_case("ieee14/ieee14_gentrip.xlsx")
andes_directory = ad.get_case("ieee39/ieee39_full.xlsx")
andes_directory = ad.get_case("kundur/kundur_full.xlsx")

andes_dict = {"case_file":andes_directory, 'redual':False}
andes_url = 'http://192.168.68.74:5000'

responseLoad = requests.post(andes_url + '/load_simulation', json=andes_dict)   

queries = [('GENROU', 'Pe'), ('TGOV1N', 'b'), ('TGOV1N', 'p_direct'), ('TGOV1N', 'pout'), ('PQ', 'p0'), ('PQ', 'Ppf')]

def query_variables(label):
    if label == 'initial':
        started = False
        while not started:
            print('Awaiting')
            response = requests.get(f"{andes_url}/simulation_started")
            started = response.json()['result']
            time.sleep(0.2)
    for key, val in queries:
        response = requests.get(f"{andes_url}/complete_variable_sync", params={'model': key, 'var': val})
        value = response.json()['value']
        print(f"{label} {val} of {key} is {value}")
        print(f" sum of {key} is {sum(value)}")

def run_simulation():
    response = requests.get(f"{andes_url}/run_real_time", params={'t_run':80, 'delta_t': 0.1})
    print("[Simulation] Response:", response)
    print("[Simulation] Output:", response.json())

# Start both threads in parallel
init_thread = threading.Thread(target=query_variables, args=("initial",))
sim_thread = threading.Thread(target=run_simulation)

init_thread.start()
sim_thread.start()

# Wait for both to finish (optional)
init_thread.join()
sim_thread.join()
query_variables("final")
responseAndes = requests.get(andes_url + '/plot', params={'model': 'Bus', 'var':'v'})

if responseAndes.status_code == 200:
    json_data = responseAndes.json()
    GFM_values = json_data.get('value', None)
    if GFM_values is None:
        print("Warning: 'value' was not returned in response.")
else:
    print(f"Error: {responseAndes.status_code} - {responseAndes.text}")
    GFM_values = None
print(f"is GFM final values {GFM_values}")

#print(responseAndes.json()['is_GFM'])
#Check if the request was successful
if responseAndes.status_code == 200:
    # Open the image using PIL from the received bytes
    img = Image.open(BytesIO(responseAndes.content))
    img.show()  # This will open the default image viewer to display the image
else:
    print("Failed to retrieve image:", responseAndes.status_code)