from .mpc_with_ipopt import FirstLayer


__version__ = '0.0.0'
def main():
	device = None # Environment variable, JSON file, TBD.
	r = FirstLayer().locate(device)
