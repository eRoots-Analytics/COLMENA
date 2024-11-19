import requests
import json

def post_service_description(service_description):
    body = json.load(open(service_description))
    agent_host_port = "http://127.0.0.1:50551"
    response = requests.post(agent_host_port, json=body)
    print(response.status_code)

if __name__ == "__main__":
    post_service_description(r"C:\Users\pablo\OneDrive\Escritorio\Proyectos\COLMENA\AndesRoles\example_eroots\build\service_description.json")