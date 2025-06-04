"""
Andes client API wrapper to simplfy calls.
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
        try:
            response = requests.post(
                f'{self.andes_url}/load_simulation', 
                json=payload
            )
            print("[ANDES] Simulation loaded.")
            self.start_time = response.json().get("start_time")

        except Exception as e:
            print(f"[Load] Failed to load simulation: {e}")

    def get_neighbour_areas(self, area):
        try:
            response = requests.get(
                f"{self.andes_url}/neighbour_area", 
                params={"area": str(area)}
            )
            return response.json()['value']
        
        except Exception as e:
            print(f"[Get] Failed to get neighbour areas: {e}")
    
    def get_system_susceptance(self, area: int, other_areas: list[int]):
        try:
            response = requests.get(
                f"{self.andes_url}/system_susceptance",
                params={
                    "area": area,
                    "area_list": ",".join(map(str, other_areas))
                }
            )
            raw_dict = response.json()
            return {int(k): v for k, v in raw_dict.items()}
        
        except Exception as e:
            print(f"[Get] Failed to get susceptance: {e}")
    
    def get_interface_buses(self, area: int, other_areas: list[int]):
        try: 
            response = requests.get(
            f"{self.andes_url}/interface_buses",
            params={
                "area": area,
                "area_list": ",".join(map(str, other_areas))
            }
            )
            raw_dict = response.json()
            return {int(k): v for k, v in raw_dict.items()}
        
        except Exception as e:
            print(f"[Get] Failed to get interface buses: {e}")


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
        response = requests.get(
            f"{self.andes_url}/complete_variable_sync", 
            params=params
        )
        return response.json()['value']

    def get_partial_variable(self, model: str, var: str, idx: list):
        response = requests.post(
            self.andes_url + '/partial_variable_sync', 
            json={'model': model, 'var': var, 'idx': idx}
        )
        try:
            response_json = response.json()
        except Exception as e:
            raise ValueError(f"Failed to parse JSON from response: {response.text}") from e

        if 'value' not in response_json:
            raise KeyError(f"'value' key not found in response JSON: {response_json}")
        
        return response_json['value']
    
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
        except Exception as e:
            print(f"[Send] Failed to send setpoint: {e}")

    def change_parameter_value(self, role_change_dict: dict):
        try:
            response = requests.post(
                f"{self.andes_url}/change_parameter_value",
                json=role_change_dict
            )
        except Exception as e:
            print(f"[Send] Failed to send setpoint: {e}")
    
    def run_step(self):
        response = requests.post(
            f"{self.andes_url}/run_step"
        ) 
        if response.status_code == 200:
            new_time = response.json().get("time")
            return True, new_time
        else:
            print("Step failed:", response.text)
            return False, None
