from .mpc_with_ipopt import DistributedMPC


__version__ = '0.0.0'
def main():
	r = DistributedMPC.LayerOne(DistributedMPC)
	r.execute()
