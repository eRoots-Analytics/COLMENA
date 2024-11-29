"""
Package for ANDES analysis routines.
"""

from collections import OrderedDict
from andes.utils.func import list_flatten

# all_routines: file name: class name
all_routines = OrderedDict([('pflow', ['PFlow']),
                            ('tds', ['TDS']),
                            ('eig', ['EIG']),
                            ('tds_colmena', ['TDS_colmena']),
                            ('tds_stepwise', ['TDS_stepwise'])
                            ])

class_names = list_flatten(list(all_routines.values()))
routine_cli = OrderedDict([(item.lower(), item) for item in class_names])

from andes.routines import daeint    # NOQA
