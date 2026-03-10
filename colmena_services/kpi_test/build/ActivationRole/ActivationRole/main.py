from .kpi_test import AgentControl


__version__ = '0.0.0'
def main():
	r = AgentControl.ActivationRole(AgentControl)
	r.execute()
