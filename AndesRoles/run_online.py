import subprocess
import time

# Replace this with the script you want to run
script_to_run = "python3 mpc_theta_difference.py"  # or e.g., "./run_me.sh" for a shell script
pre_command = 'source /home/pablo/myenv/bin/activate'

# Full path to the venv's Python
python_venv = "/home/pablo/myenv/bin/python"

# Full path to the script you want to run
script_path = "/home/pablo/Desktop/eroots/COLMENA/AndesRoles/mpc_theta_difference.py"

while True:
    print("Starting the script...")
    try:
        subprocess.run([python_venv, script_path], check=False)
    except Exception as e:
        print(f"Error running script: {e}")

    print("Script finished. Restarting...\n")
    time.sleep(0.1)