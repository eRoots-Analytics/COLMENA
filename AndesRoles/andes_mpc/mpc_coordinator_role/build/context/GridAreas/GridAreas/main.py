from .mpc_coordinator_role import GridAreas


__version__ = '0.0.0'
def main():
	device = None # Environment variable, JSON file, TBD.
	r = GridAreas().locate(device)
