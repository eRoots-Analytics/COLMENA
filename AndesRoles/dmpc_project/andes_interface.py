import requests

class AndesInterface:
    def __init__(self, andes_url):
        self.andes_url = andes_url

    def start_simulation(self):
        """
        Start the simulation by sending a POST request to the Andes server.
        """
        return requests.post(f"{self.andes_url}/start_simulation")

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

    def get_delta_equivalent(self, area: int = 1):
        response = requests.get(
            f"{self.andes_url}/delta_equivalent",
            params={"area": area}
        )
        return response.json()['value']

    def get_device_dict(self):
        response = requests.get(f"{self.andes_url}/assign_device", params={"agent": self.agent_id})
        return response.json()

    def send_setpoint(self, role_change_dict : dict):
        return requests.get(f"{self.andes_url}/add_set_point", params=role_change_dict)
