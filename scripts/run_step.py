# Move to one level up, i.e. project root folder (COLMENA). 
import sys
from pathlib import Path
import time
sys.path.append(str(Path(__file__).resolve().parents[1]))
from colmenasrc.simulator.andes_wrapper import AndesWrapper
from colmenasrc.controller.coordinator import Coordinator

andes = AndesWrapper(load = False)
v = andes.get_complete_variable(model='Bus', var='v')
print(v)
for t in range(500):
    success, new_time = andes.run_step()
    time.sleep(0.05)
    print(success, new_time)