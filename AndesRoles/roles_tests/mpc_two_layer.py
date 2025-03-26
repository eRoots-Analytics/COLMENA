import time
import numpy as np
import json
import time
import queue
from colmena import (
    Context,
    Service,
    Role,
    Channel,
    Requirements,
    Metric,
    Persistent,
    Async,
    KPI,
    Data
)

class GridAreas(Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.structure = {
            "floor1": ["reception"],
            "floor2": ["reception", "open_space"],
            "floor3": ["open_space", "manager_office"],
        }

    def locate(self, device):
        print(self.structure["floor1"][0])

        return

class AgentControl(Service):
    @Channel('', scope='')
    @Channel('layer_one_output', scope='')
    @Channel('layer_two_output', scope='')
    @Requirements('MAIN')
    @Requirements('AREA')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class LayerOne(Role):
        @Channel('layer_one_output')
        @Channel('layer_two_output')
        @Requirements('MAIN')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.n_areas = 2
            self.states = np.ones(self.n_areas)
            self.value = np.random.rand(1)

        def solve(self):
            return 0

        @Async(updated_state = "layer_two_output")
        def behavior(self, updated_state):
            print("we updated the state", updated_state)
            area = updated_state[0]
            value = updated_state[0]
            for i in range(self.n_areas):
                self.layer_one_output.publish(self.value)
            time.sleep(0.2)
            return

    class LayerTwo(Role):
        @Channel('layer_one_output')
        @Channel('layer_two_output')
        @Requirements('AREA')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            n_areas = 2
            self.states = np.ones(n_areas)
            self.value = np.random.rand(1)

        def solve(self):
            return 0

        @Async(updated_state = "layer_one_output")
        def behavior(self, updated_state):
            print("we updated the state", updated_state)
            area = updated_state[0]
            value = updated_state[0]
            self.layer_two_output.publish([self.area, self.value])
            time.sleep(0.2)
            return