import numpy as np
import subprocess
import time

pre_command = 'source /home/pablo/myenv/bin/activate'
script_name = "mpc_multiple_areas"
folder_name = 'colmena_services'

colmena_command = f"""
/home/pablo/myenv/bin/python -m colmena_build \
--service_path='/home/pablo/Desktop/eroots/COLMENA/{folder_name}/mpc_multiple_areas.py' \
--build_file='/home/pablo/Desktop/Colmena/programming-model/dist/colmena_swarm_pm-0.1.4.tar.gz' 
"""

build_command = {
        "cmd": "/home/pablo/myenv/bin/python -m colmena_build "
               f"--service_path='/home/pablo/Desktop/eroots/COLMENA/{folder_name}/{script_name}.py' "
               "--build_file='/home/pablo/Desktop/Colmena/programming-model/dist/colmena_swarm_pm-0.1.4.tar.gz' ",
        "cwd": "/home/pablo/Desktop/Colmena/programming-model/colmena/building_tool"  
    }
deploy_command = {
        "cmd": f"/home/pablo/myenv/bin/python -m colmena_deploy --build_path='/home/pablo/Desktop/eroots/COLMENA/{folder_name}/{script_name}/build' "
               "--platform='linux/amd64' "
               "--user=pablodejuan",
        "cwd": "/home/pablo/Desktop/Colmena/deployment-tool/deployment"  # Change to the correct directory
    }
zenoh_command = {
        "cmd": "docker compose -f compose-zenoh.yaml up --abort-on-container-exit",
        "cwd": "/home/pablo/Desktop/Colmena/agent"  # Change to the directory where compose.yaml is located
    }
agent_command= {
        "cmd": "HARDWARE={hardware} AGENT_ID={agent_name} POLICY={strategy} docker compose -p {agent_name} -f compose.yaml up --abort-on-container-exit",
        "cwd": "/home/pablo/Desktop/Colmena/agent", 
        'is_agent': True,
    }

compose_down = " 'docker compose --file '/home/pablo/Desktop/Colmena/agent/compose.yaml' --project-name 'area_1' down' "

agents = [{'hardware':'GENERATOR', 'strategy':'eager', 'agent_name':'device_a'},
          {'hardware':'TRANSFORMER', 'strategy':'eager', 'agent_name':'device_b'}, 
          {'hardware':'GENERATOR', 'strategy':'eager', 'agent_name':'device_c'}, 
          {'hardware':'GENERATOR', 'strategy':'eager', 'agent_name':'device_d'}] 

mpc_agents = True
n_area = 6
if mpc_agents:
    agents = [{'hardware':'AREA', 'strategy':'eager', 'agent_name':'area_1'},{'hardware':'AREA', 'strategy':'eager', 'agent_name':'area_2'}] 

agents = []
if n_area >= 2:
    for i in range(1, n_area+1):
        agents +=  [{'hardware':'AREA', 'strategy':'eager', 'agent_name':f'area_{i}'}]
        
commands =  [zenoh_command] + [agent_command]*n_area + [deploy_command]  
#commands = [build_command]
#commands = [deploy_command]
processes = []
agent_i = 0

cmd = zenoh_command['cmd']
cwd = zenoh_command['cwd']
terminal_cmd = f"gnome-terminal -- bash -c './{folder_name}/activate_env.sh {zenoh_command['cwd']} \"{zenoh_command['cmd']}\"; exec bash'"
build_cmd = f"gnome-terminal -- bash -c './{folder_name}/activate_env.sh {build_command['cwd']} \"{build_command['cmd']}\"; exec bash'"
#terminal_cmd = f"gnome-terminal -- bash -c './AndesRoles/colmena_deploy/activate_env.sh {build_command['cwd']} \"{build_command['cmd']}\"; exec bash'"
#process = subprocess.Popen(terminal_cmd, shell=True)
subprocess.Popen(terminal_cmd,shell=True)
#subprocess.Popen(build_cmd,shell=True)

time.sleep(6)
for cmd in commands:
    if cmd.get('is_agent', False):  # Check if it's the agent command
        agent_data = agents[agent_i]
        cmd_formatted = {
            "cmd": cmd["cmd"].format(**agent_data),  # Inject agent values
            "cwd": cmd["cwd"]
        }
        agent_i += 1  # Move to the next agent
    else:
        cmd_formatted = cmd.copy()

    print(f"Starting: {cmd_formatted['cmd']} in {cmd_formatted['cwd']}")
    # Open a new terminal and source the environment before running the command
    terminal_cmd = f"gnome-terminal -- bash -c './{folder_name}/activate_env.sh {cmd_formatted['cwd']} \"{cmd_formatted['cmd']}\"; exec bash'"
    process = subprocess.Popen(terminal_cmd, shell=True)
    processes.append(process)

for process in processes:
    stdout, stderr = process.communicate()
    if stdout:
        print(f"OUTPUT:\n{stdout}")
    if stderr:
        print(f"ERROR:\n{stderr}")

# Ensure all processes have completed
for process in processes:
    process.wait()
