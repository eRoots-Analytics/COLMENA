from .mpc_multiple_areas import AgentControl

__version__ = '0.0.0'

def main():
    r = AgentControl.LayerOne(AgentControl)
    r.execute()
