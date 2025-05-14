from PIL import Image
from io import BytesIO
import requests
import os, sys, io
import numpy as np
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
andes_directory = ad.get_case("kundur/kundur_full.xlsx")
andes_directory = ad.get_case("ieee39/ieee39_full.xlsx")

andes_dict = {"case_file":andes_directory, 'redual':False}
andes_url = 'http://192.168.10.137:5000'
andes_url = 'http://192.168.68.71:5000'

responseLoad = requests.post(andes_url + '/load_simulation', json=andes_dict)   

queries = [('GENROU', 'tm0'), ('GENROU', 'tm'), ('TGOV1N', 'b'), ('TGOV1N', 'p_direct'), ('TGOV1N', 'pout')]
for key,val in queries:
    response = requests.get(andes_url + '/complete_variable_sync', params={'model':key, 'var':val})
    value = response.json()['value']
    print(f"final {val} is {value}")
    print(f" sum is {sum(value)}")
responseRun = requests.get(andes_url + '/run_real_time', params={'t_run':50, 'delta_t':0.1})
for key,val in queries:
    response = requests.get(andes_url + '/complete_variable_sync', params={'model':key, 'var':val})
    value = response.json()['value']
    print(f"final {val} is {value}")
    print(f" sum is {sum(value)}")

responseAndes = requests.get(andes_url + '/plot', params={'model': 'Bus', 'var':'v'})

if response.status_code == 200:
    json_data = response.json()
    GFM_values = json_data.get('value', None)
    if GFM_values is None:
        print("Warning: 'value' was not returned in response.")
else:
    print(f"Error: {response.status_code} - {response.text}")
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


