import time, os
import numpy as np
import json
import time
import sys
sys.path.append('/home/pablo/Desktop/eroots/COLMENA')
from copy import deepcopy
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
    Data,
    Dependencies
)

#Service to deploy a one layer control
andes_url = 'http://127.0.0.1:5000'

class GlobalError(Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def locate(self, device):
        id = {'id':1}
        print(json.dumps(id))

class AgentControl(Service):
    @Metric('frequency')
    @Metric('always_negative')
    @Context(class_ref=GlobalError, name='all_global')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class ActivationRole(Role):
        @Requirements('AREA')
        @Metric('frequency')
        @Context(class_ref=GlobalError, name='all_global')
        @Metric('always_negative')
        @KPI('min((min_over_time(agentcontrol_frequency[30s])>=0)) < 1')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.andes_url = andes_url

        @Persistent()
        def behavior(self):
            #area_frequency = self.andes.get_area_variable(model='GENROU', var='omega', area = self.area)
            #area_M = self.andes.get_area_variable(model='GENROU', var='M', area = self.area)
            #mean_freq = np.dot(area_frequency, area_M)
            self.frequency.publish(2)
            self.always_negative.publish(-1)
            return 1