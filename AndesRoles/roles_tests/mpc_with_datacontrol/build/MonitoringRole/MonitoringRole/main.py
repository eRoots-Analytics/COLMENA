from .mpc_with_datacontrol import AgentControl


__version__ = '0.0.0'
def main():
	r = AgentControl.MonitoringRole(AgentControl)
	r.execute()
