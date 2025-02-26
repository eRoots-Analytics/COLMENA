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
andes_directory = ad.get_case("ieee39/ieee39_full.xlsx")
andes_dict = {"case_file":andes_directory}
andes_url = 'http://192.168.68.61:5000'
#responseLoad = requests.post(andes_url + '/load_simulation', json=andes_dict)
#raise SystemExit

#responseLoad = requests.get(andes_url + '/assign_device', params=andes_dict)
#responseLoad = requests.get(andes_url + '/assign_device', params=andes_dict)
#responseLoad = requests.get(andes_url + '/plot', params={'model_name':'REDUAL', 'var_name':'v'})
#responseAndes = requests.post(andes_url + '/assign_out', json = {})
#responseAndes = requests.get(andes_url + '/device_sync', params={'model':'REDUAL', 'idx':'GENROU_2'})
#responseAndes = requests.post(andes_url + '/print_var', json={'keys': ['is_GFM']})
responseAndes = requests.get(andes_url + '/plot', params={'model': 'Bus', 'var':'v'})
#print(responseAndes.json()['is_GFM'])
#Check if the request was successful
if responseAndes.status_code == 200:
    # Open the image using PIL from the received bytes
    img = Image.open(BytesIO(responseAndes.content))
    img.show()  # This will open the default image viewer to display the image
else:
    print("Failed to retrieve image:", responseAndes.status_code)


