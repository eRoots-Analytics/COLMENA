import numpy as np
import subprocess
import shlex
import signal
import sys

pre_command = 'source /home/pablo/myenv/bin/activate'
build_command = {
        "cmd": "python3 -m colmena_build --colmena_path='/home/pablo/Desktop/Colmena/programming-model' "
               "--service_code_path='/home/pablo/Desktop/eroots/COLMENA/AndesRoles' "
               "--module_name='example_test' "
               "--service_name='ErootsUseCase' ",
        "cwd": "/home/pablo/Desktop/Colmena/programming-model/scripts"  
    }
deploy_command = {
        "cmd": "python3 -m colmena_deploy --build_path='/home/pablo/Desktop/eroots/COLMENA/AndesRoles/example_test/build' "
               "--platform='linux/amd64' "
               "--user=pablodejuan",
        "cwd": "/home/pablo/Desktop/Colmena/deployment-tool/deployment"  # Change to the correct directory
    }
zenoh_command = {
        "cmd": "docker compose -f compose-zenoh.yaml up --abort-on-container-exit",
        "cwd": "/home/pablo/Desktop/Colmena/agent"  # Change to the directory where compose.yaml is located
    }

agent_command= {
        "cmd": "DEVICE_HARDWARE={hardware} DEVICE_STRATEGY={strategy} DEVICE_NAME={agent_name} docker compose -p {agent_name} -f compose.yaml up --abort-on-container-exit",
        "cwd": "/home/pablo/Desktop/Colmena/agent", 
        'is_agent': True,
    }


agents = [{'hardware':'GENERATOR', 'strategy':'EAGER', 'agent_name':'agent_a'},
          {'hardware':'CAMERA', 'strategy':'EAGER', 'agent_name':'agent_b'}, 
          {'hardware':'CPU', 'strategy':'EAGER', 'agent_name':'agent_c'}] 
redeploy_commands = [build_command, zenoh_command, agent_command, agent_command, deploy_command]  
commands =  [zenoh_command, agent_command, agent_command, deploy_command]  
commands = redeploy_commands 
#commands = [zenoh_command, agent_command, agent_command, deploy_command]
commands = [zenoh_command, agent_command, agent_command, deploy_command]
processes = []
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
    print(f"Starting: {cmd_formatted['cmd']} in {cmd['cwd']}")
    terminal_cmd = f"terminator --working-directory={cmd_formatted['cwd']} -e 'bash -c \"{pre_command} && {cmd_formatted['cmd']}; exec bash\"'"
    process = subprocess.Popen(shlex.split(terminal_cmd))
    processes.append(process)

# Collect and print outputs
for process in processes:
    stdout, stderr = process.communicate()
    if stdout:
        print(f"OUTPUT:\n{stdout}")
    if stderr:
        print(f"ERROR:\n{stderr}")

# Ensure all processes have completed
for process in processes:
    process.wait()

