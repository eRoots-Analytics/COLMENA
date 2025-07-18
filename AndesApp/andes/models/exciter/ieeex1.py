from andes.core.service import VarService
from andes.models.exciter.exdc2 import EXDC2Data, EXDC2Model
from andes.core.param import NumParam


class IEEEX1Model(EXDC2Model):

    def __init__(self, system, config):
        EXDC2Model.__init__(self, system, config)
        self.VRTMAX = VarService('VRMAX * v',
                                 tex_name='V_{RMAX}V_T')
        self.VRTMIN = VarService('VRMIN * v',
                                 tex_name='V_{RMIN}V_T')

        self.LA.upper = self.VRTMAX
        self.LA.lower = self.VRTMIN


class IEEEX1(EXDC2Data, IEEEX1Model):
    """
    IEEEX1 Type 1 exciter (DC)

    Derived from EXDC2 by varying the limiter bounds.
    """
    def __init__(self, system, config):
        EXDC2Data.__init__(self)
        IEEEX1Model.__init__(self, system, config)

        self.vout.e_str = 'ue * vp - vout'
        self.v_aux = NumParam(default=0)
        self.vi.e_str = self.vi.e_str + '+ v_aux'
        self.vi.v_str = self.vi.v_str + '+ v_aux'
