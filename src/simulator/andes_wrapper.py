"""
Andes API wrapper to simplfy calls.
"""

import requests

from src.config.config import Config
from andes import get_case

class AndesWrapper:
    def __init__(self):

        self.andes_url = Config.andes_url
        self.case_path = get_case(Config.case_path)

        if self.case_path is not None:
            
            self.load_simulation(self.case_path)

    def load_simulation(self, case_path, redual=False):
        payload = {'case_file': case_path, 'redual': redual}
        response = requests.post(f'{self.andes_url}/load_simulation', json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to load simulation: {response.text}")
        print("[ANDES] Simulation loaded.")
        self.start_time = response.json().get("start_time")
    
    def sync_time(self):
        """
        Synchronize the time with the Andes server by sending a GET request.
        """
        response = requests.get(f"{self.andes_url}/sync_time")
        return int(response.json()['time'])

    def get_neighbour_areas(self, area):
        response = requests.get(f"{self.andes_url}/neighbour_area", params={"area": str(area)})
        return response.json()['value']

    def get_area_variable(self, model: str, var: str, area: int):
        response = requests.post(
            f"{self.andes_url}/area_variable_sync",
            json={'model': model, 'var': var, 'area': area}
        )
        return response.json()['value']

    def get_complete_variable(self, model: str, var: str, area: int = None):
        params = {'model': model, 'var': var}
        if area is not None:
            params['area'] = area
        response = requests.get(f"{self.andes_url}/complete_variable_sync", params=params)
        return response.json()['value']

    def get_partial_variable(self, model: str, var: str, idx: list):
        response = requests.post(self.andes_url + '/partial_variable_sync', json={'model': model, 'var': var, 'idx': idx})
        try:
            response_json = response.json()
        except Exception as e:
            raise ValueError(f"Failed to parse JSON from response: {response.text}") from e

        if 'value' not in response_json:
            raise KeyError(f"'value' key not found in response JSON: {response_json}")
        
        return response_json['value']

    def get_system_susceptance(self, area: int):
        response = requests.get(
            f"{self.andes_url}/system_susceptance",
            params={"area": area}
        )
        raw_dict = response.json()
        return {int(k): v for k, v in raw_dict.items()}
    
    def get_theta_equivalent(self, area: int):    #NOTE: Hard coded, needs to be changed
        response = requests.get(
            f"{self.andes_url}/delta_equivalent", #NOTE: name needs to be changed
            params={"area": 1}
        )
        response.raise_for_status() 
        raw = response.json()

        return [float(v) for v in raw["value"].values()]

    def send_setpoint(self, role_change_dict: dict):
        try:
            response = requests.post(
                f"{self.andes_url}/send_set_point",
                json=role_change_dict
            )
            # if response.status_code == 200:
            #     print(f"[Send] OK → {role_change_dict}")
            # else:
            #     print(f"[Send] ERROR {response.status_code}: {response.json()}")
        except Exception as e:
            print(f"[Send] Failed to send setpoint: {e}")

    def init_tds(self):
        response = requests.post(f"{self.andes_url}/init_tds")
        if response.status_code == 200:
            start_time = response.json().get("start_time")
            print(f"[Init] TDS initialized at time {start_time}")
            return True, start_time
        else:
            print("[Error] Failed to initialize TDS:", response.text)
            return False, None
    
    def run_step(self):
        response = requests.post(f"{self.andes_url}/run_step")  # empty dict just to be valid JSON
        if response.status_code == 200:
            new_time = response.json().get("time")
            return True, new_time
        else:
            print("Step failed:", response.text)
            return False, None

    # def plot(self, model, var):
    #     response = requests.get(f'{self.api_url}/plot', params={'model': model, 'var': var})
    #     if response.status_code == 200:
    #         return response.content
    #     raise RuntimeError("Failed to retrieve plot.")
