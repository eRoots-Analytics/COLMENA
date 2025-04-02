import numpy as np
import subprocess
import time

pre_command = 'source /home/pablo/myenv/bin/activate'
build_command = {
        "cmd": "/home/pablo/myenv/bin/python -m colmena_build "
               "--service_path='/home/pablo/Desktop/eroots/COLMENA/AndesRoles/example_test2.py' "
               "--build_file='/home/pablo/Desktop/Colmena/programming-model/dist/colmena_swarm_pm-0.1.4.tar.gz' ",
        "cwd": "/home/pablo/Desktop/Colmena/programming-model/colmena/building_tool"  
    }
deploy_command = {
        "cmd": "/home/pablo/myenv/bin/python -m colmena_deploy --build_path='/home/pablo/Desktop/eroots/COLMENA/AndesRoles/example_test2/build' "
               "--platform='linux/amd64' "
               "--user=pablodejuan",
        "cwd": "/home/pablo/Desktop/Colmena/deployment-tool/deployment"  # Change to the correct directory
    }
zenoh_command = {
        "cmd": "docker compose -f compose-zenoh.yaml up --abort-on-container-exit",
        "cwd": "/home/pablo/Desktop/Colmena/agent"  # Change to the directory where compose.yaml is located
    }
agent_command= {
        "cmd": "DEVICE_HARDWARE={hardware} DEVICE_STRATEGY={strategy} docker compose -p {agent_name} -f compose.yaml up --abort-on-container-exit",
        "cwd": "/home/pablo/Desktop/Colmena/agent", 
        'is_agent': True,
    }

agents = [{'hardware':'GENERATOR', 'strategy':'LAZY', 'agent_name':'agent_a'},
          {'hardware':'GENERATOR', 'strategy':'LAZY', 'agent_name':'agent_b'}, 
          {'hardware':'TRANSFORMER', 'strategy':'LAZY', 'agent_name':'agent_c'}, 
          {'hardware':'TRANSFORMER', 'strategy':'LAZY', 'agent_name':'agent_d'},] 

mpc_agents = False
if mpc_agents:
    agents = [{'hardware':'AREA', 'strategy':'EAGER', 'agent_name':'area1'},{'hardware':'AREA', 'strategy':'EAGER', 'agent_name':'area2'}] 
    agents += [{'hardware':'DEVICE', 'strategy':'EAGER', 'agent_name':'device1'},{'hardware':'DEVICE', 'strategy':'EAGER', 'agent_name':'device2'}] 

redeploy_commands = [build_command, zenoh_command, agent_command, agent_command, agent_command, agent_command, deploy_command]  
commands =  [zenoh_command, agent_command, agent_command, deploy_command]  
commands = redeploy_commands 
commands = [agent_command, agent_command, agent_command, agent_command, deploy_command]
#commands = [build_command]
processes = []
agent_i = 0


cmd = zenoh_command['cmd']
cwd = zenoh_command['cwd']
terminal_cmd = f"gnome-terminal -- bash -c './AndesRoles/colmena_deploy/activate_env.sh {zenoh_command['cwd']} \"{zenoh_command['cmd']}\"; exec bash'"
build_cmd = f"gnome-terminal -- bash -c './AndesRoles/colmena_deploy/activate_env.sh {build_command['cwd']} \"{build_command['cmd']}\"; exec bash'"
subprocess.Popen(terminal_cmd, shell=True)
subprocess.Popen(build_cmd, shell=True)

time.sleep(4)
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
    terminal_cmd = f"gnome-terminal -- bash -c './AndesRoles/colmena_deploy/activate_env.sh {cmd_formatted['cwd']} \"{cmd_formatted['cmd']}\"; exec bash'"
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

