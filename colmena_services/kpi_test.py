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
    @Data('Data_1', scope='all_global/id = .')
    @Context(class_ref = GlobalError, name = 'globalerror')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    class ActivationRole(Role):
        @Requirements('AREA')
        @Metric('frequency')
        @Metric('always_negative')
        @Context(class_ref = GlobalError, name='all_global')
        @Data('Data_1', scope='all_global/id = .')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.andes_url = andes_url

        @Persistent()
        def behavior(self):
            self.Data_1.publish({'error':1})
            area_frequency = self.andes.get_area_variable(model='GENROU', var='omega', area = self.area)
            area_M = self.andes.get_area_variable(model='GENROU', var='M', area = self.area)
            mean_freq = np.dot(area_frequency, area_M)
            self.frequency.publish(mean_freq)
            self.always_negative.publish(-1)
            return 1
        
    class Distributed_MPC(Role):
        @Requirements('AREA')
        @Metric('frequency')
        @Data('Data_1', scope='all_global/id = .')
        @Context(class_ref = GlobalError, name= 'all_global')
        @Data('Data_1', scope='all_global/id = .')
        @KPI('agentcontrol/frequency > 1', scope='all_global/id = .')
        def __init__(self, *args, **kwargs):
            time.sleep(12)
            super().__init__(*args, **kwargs)
            a = 0
            
        @Persistent()
        def behavior(self):
            print('running 1')
            
    class MonitoringRole(Role):
        @Requirements('AREA')
        @Metric('frequency')
        @Metric('always_negative')
        @Context(class_ref = GlobalError, name='all_global')
        @Data('Data_1', scope='all_global/id = .')
        @KPI('agentcontrol/always_negative[3s] > 1', scope='all_global/id = .')
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.andes_url = andes_url
            time.sleep(12)

        @Persistent()
        def behavior(self):
            area_frequency = self.andes.get_area_variable(model='GENROU', var='omega', area = self.area)
            area_M = self.andes.get_area_variable(model='GENROU', var='M', area = self.area)
            mean_freq = np.dot(area_frequency, area_M)
            self.frequency.publish(mean_freq)
            self.always_negative.publish(-1)
            return 1
        
