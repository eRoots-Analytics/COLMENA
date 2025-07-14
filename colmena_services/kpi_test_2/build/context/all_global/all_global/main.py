from .kpi_test_2 import GlobalError


__version__ = '0.0.0'
def main():
	device = None # Environment variable, JSON file, TBD.
	r = GlobalError().locate(device)
