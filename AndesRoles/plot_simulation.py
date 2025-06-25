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

andes_directory = ad.get_case("kundur/kundur_full.xlsx")
andes_directory = ad.get_case("ieee39/ieee39_full.xlsx")

andes_dict = {"case_file":andes_directory, 'redual':False}
andes_url = 'http://127.0.0.1:5000'
response_delta_equivalent = requests.get(andes_url + '/delta_equivalent', params={'area':1})
print(response_delta_equivalent.json())
responseAndes = requests.get(andes_url + '/plot', params={'model': 'Bus', 'var':'v'})