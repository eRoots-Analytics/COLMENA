from .mpc_coordinator_role import AgentControl


__version__ = '0.0.0'
def main():
	r = AgentControl.LayerOne(AgentControl)
	r.execute()
