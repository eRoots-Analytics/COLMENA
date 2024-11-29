from example_eroots import ErootsUseCase
from typing import List, TYPE_CHECKING
from threading import Thread
from PIL import Image
from io import BytesIO
from test_examples import TestExamples
import requests
import time
import multiprocessing
import os, sys
import colmena
import matplotlib.pyplot as plt
#We first define the andes directory
current_directory = os.path.dirname(os.path.abspath(__file__))
two_levels_up = os.path.dirname(current_directory)
sys.path.insert(0, two_levels_up)
sys.path.insert(0, two_levels_up + '/AndesApp')

from AndesApp import andes as ad
andes_directory = ad.get_case("kundur/kundur_full.xlsx")
andes_dict = {"case_file":andes_directory}

from scripts.colmena_build import (
    clean,
    build_temp_folders,
    write_service_description,
    get_service,
    build,
)

def aux_role(role):
    role.execute()

if __name__ == "__main__":
    andes_url = 'http://127.0.0.1:5000'
    kwargs = {'andes_url':andes_url, 'device_idx':1, 'model_name':'GENROU'} 
    responseLoad = requests.post(andes_url + '/load_simulation', json=andes_dict)
    
    test_example = TestExamples()
    test_example.execute_roles_in_service(service_class = ErootsUseCase)
    
    responsePlot = requests.get(andes_url + '/plot', params = {'model_name':'GENROU', 'var_name':'omega'})
    #responsePlot = 600
    if not isinstance(responsePlot, int) and responsePlot.status_code == 200:
        img = Image.open(BytesIO(responsePlot.content))
        # Save or display the image as needed
        img.show()  # To display it directly
        img.save("plot.png")  # To save it to a file
    elif not isinstance(responsePlot, int):
        print(f"Error: {responsePlot.status_code} - {responsePlot.json().get('error')}")

            
    
    