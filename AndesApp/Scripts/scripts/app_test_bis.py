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

andes_directory = ad.get_case("ieee39/ieee39_full.xlsx")
andes_dict = {"case_file":andes_directory}
andes_url = 'http://192.168.68.67:5000'
responseLoad = requests.post(andes_url + '/start_simulation', json=andes_dict)
