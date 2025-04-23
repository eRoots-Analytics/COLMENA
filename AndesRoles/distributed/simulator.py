class Simulator:
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.state_cache = {}

    def get_states(self):
        # Get data from the simulator
        self.state_cache = {"x": 1.0}

    def write_inputs(self, agent_id, control):
        # Write data to the simulator
        print(f"Agent {agent_id} sends control: {control}")
