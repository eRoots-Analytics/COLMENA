from .mpc_kpi_driven import AgentControl


__version__ = '0.0'
def main():
	r = AgentControl.SimulationManager(AgentControl)
	r.execute()
