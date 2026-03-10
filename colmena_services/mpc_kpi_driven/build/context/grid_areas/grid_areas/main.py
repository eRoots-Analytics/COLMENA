from .mpc_kpi_driven import GridAreas


__version__ = '0.1'
def main():
	device = None # Environment variable, JSON file, TBD.
	r = GridAreas().locate(device)
