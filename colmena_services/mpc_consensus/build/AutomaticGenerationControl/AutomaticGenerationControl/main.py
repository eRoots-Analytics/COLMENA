from .mpc_consensus import AgentControl


__version__ = '0.0.0'
def main():
	r = AgentControl.AutomaticGenerationControl(AgentControl)
	r.execute()
