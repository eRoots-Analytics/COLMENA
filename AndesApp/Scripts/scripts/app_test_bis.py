from typing import List, TYPE_CHECKING
from threading import Thread
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

agent_id = 'area_1'
andes_directory = ad.get_case("kundur/kundur_full.xlsx")
andes_dict = {"case_file":andes_directory}
andes_url = 'http://192.168.10.137:5000'
andes_url = 'http://192.168.68.71:5000'

andes_dict["redual"] = False
responseRun = requests.post(andes_url + '/start_simulation')
exit()
responseLoad = requests.post(andes_url + '/load_simulation', json=andes_dict)
responseAndes = requests.get(andes_url + '/assign_device', params = {'agent': agent_id})
res = requests.post(andes_url + '/area_variable_sync', json={'model':'GENROU', 'var':'idx', 'area':1}).json()['value']
print(res)

#responseLoad = requests.post(andes_url + '/start_simulation', json=andes_dict)
