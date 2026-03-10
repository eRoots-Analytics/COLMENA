from .mpc_multiple_roles_kpi import AgentControl


__version__ = '0.0.0'
def main():
	r = AgentControl.GridFormingRole(AgentControl)
	r.execute()
