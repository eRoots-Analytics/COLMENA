import numpy as np
import subprocess
import time
import os

#script_name = os.getenv('service_file')
script_name = 'mpc_multiple_areas'
#colmena_dir = os.getenv('colmena_dir')
colmena_dir = '/home/xcasas/gitlab/'
#python_dir  = os.getenv('python_dir')
python_dir = 'python3'
#docker_user = os.getenv('docker_user')
docker_user = 'xaviercasasbsc'
#grid_name   = os.getenv('grid_name')
grid_name = 'ieee39'

current_dir = os.getcwd()
folder_name = 'colmena_services'


build_command = {
        "cmd": f"{python_dir} -m colmena_build "
               f"--service_path='{current_dir}/{folder_name}/{script_name}.py' "
               f"--build_file='{colmena_dir}/programming-model/dist/colmena_swarm_pm-0.1.4.tar.gz' ",
        "cwd": f"{colmena_dir}/programming-model/colmena/building_tool"  
    }

deploy_command = {
        "cmd": f"{python_dir} -m colmena_deploy --build_path='{current_dir}/{folder_name}/{script_name}/build' "
               "--platform='linux/amd64' "
               f"--user={docker_user}",
        "cwd": f"{colmena_dir}/deployment-tool/deployment"  # Change to the correct directory
    }

zenoh_command = {
        "cmd": "docker compose -f compose-zenoh.yaml up --abort-on-container-exit",
        "cwd": f"{colmena_dir}/agent"  # Change to the directory where compose.yaml is located
    }
agent_command= {
        "cmd": "HARDWARE={hardware} AGENT_ID={agent_name} POLICY={strategy} ZENOH_ROUTER=172.18.0.1 docker compose -p {agent_name} -f compose.yaml up --abort-on-container-exit",
        "cwd": f"{colmena_dir}/agent", 
        'is_agent': True,
    }

compose_down = f" 'docker compose --file f'{colmena_dir}/agent/compose.yaml' --project-name 'area_1' down' "
if grid_name == 'ieee39':
    n_area = 2
    n_generators = 0
elif grid_name == 'npcc':
    n_area = 6
    n_generators = 5

agents = []
if n_area >= 2:
    for i in range(1, n_area+1):
        agents +=  [{'hardware':'AREA', 'strategy':'eager', 'agent_name':f'area_{i}'}] 
if n_generators >= 2:
    for i in range(1, n_generators+1):
        j = 20+3*i
        if grid_name == 'ieee39':
            j = max(j, 10)
        agents +=  [{'hardware':'GENERATOR', 'strategy':'eager', 'agent_name':f'genrou_{j}'}]

print(agents)
commands =  [zenoh_command] + [agent_command]*(n_area+n_generators) + [deploy_command]  
processes = []

cmd = zenoh_command['cmd']
cwd = zenoh_command['cwd']
terminal_cmd = f"gnome-terminal -- bash -c 'cd {zenoh_command['cwd']} && {zenoh_command['cmd']}; exec bash'"
build_cmd = f"gnome-terminal -- bash -c './{folder_name}/activate_env.sh {build_command['cwd']} \"{build_command['cmd']}\"; exec bash'"
subprocess.Popen(terminal_cmd,shell=True)
#subprocess.Popen(build_cmd,shell=True)

time.sleep(2)
agent_i = 0
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
