from .mpc_multiple_roles import AgentControl


__version__ = '0.0.0'
def main():
	r = AgentControl.GridFormingRole(AgentControl)
	r.execute()
