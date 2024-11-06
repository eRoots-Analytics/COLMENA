import time
import numpy as np
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
)


class CompanyPremises(Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.structure = {
            "floor1": ["reception"],
            "floor2": ["reception", "open_space"],
            "floor3": ["open_space", "manager_office"],
        }

    def locate(self, device):
        print(self.structure["floor1"][0])


class ExampleApplication(Service):
    @Context(class_ref=CompanyPremises, name="company_premises")
    @Channel(name="buffer", scope=" ")
    @Channel(name="result", scope=" ")
    @Metric(name="sensed")
    @Metric(name="processed")
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class Sensing(Role):
        @Context(name="company_premises", scope="*.*.lobby")
        @Channel(name="buffer")
        @Metric(name="sensed")
        @Requirements("CAMERA")
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.dims = [512, 512]

        @Persistent()
        def behavior(self):
            image = np.random.randn(*self.dims)
            self.buffer.publish(image)
            self.sensed.publish(1)
            time.sleep(1)

    class Processing(Role):
        @Channel(name="result")
        @Channel(name="buffer")
        @Metric(name="processed")
        @Requirements("meteologix")
        @KPI("buffer_queue_size[100000000s] < 10")
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        @Async(image="buffer")
        def behavior(self, image):
            res = np.sum(image)
            self.result.publish(res)
            self.processed.publish(1)
            time.sleep(0.75)