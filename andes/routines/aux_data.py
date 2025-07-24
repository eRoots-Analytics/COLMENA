def get_set_points(self, set_points = None, line_id = 8, line_toggle = True, idxs = None):
        set_point_changes = []
        line_n = self.system.Line.n
        line_resistance = False
        line_failure = False
        resistance = False
        change_turbine = False

        if set_points is None:
            return []

        if set_points == 'REDUAL':
            new_set_point = {}
            idxs = ['GENROU_1', 'GENROU_2']
            new_set_point['model'] = 'REDUAL'
            new_set_point['param'] = 'is_GFM'
            new_set_point['value'] = 0
            new_set_point['add'] = False
            new_set_point['t'] = 14
            if idxs is not None:
                for i, idx in enumerate(idxs):
                    idx_val = str('GENROU_') + str(i+1)    
                    new_set_point['idx'] = idx_val
                    set_point_changes.append(new_set_point)

        if set_points == 'intermittent':
            new_set_point = {}
            new_set_point['model'] = 'GENROU'
            new_set_point['param'] = 'gammap'
            new_set_point['value'] = -0.1
            new_set_point['idx'] = 1
            new_set_point['add'] = False
            new_set_point['t'] = 5
            set_point_changes.append(new_set_point)

        elif set_points == 'turbine':
            new_set_point = {}
            new_set_point['model'] = 'TGOV1'
            new_set_point['param'] = 'paux0'
            new_set_point['value'] = 0.1
            new_set_point['idx'] = 1
            new_set_point['add'] = True
            new_set_point['t'] = 5
            set_point_changes.append(new_set_point)
        
        elif set_points == 'fload':
            new_set_point = {}
            new_set_point['model'] = 'FLoad'
            new_set_point['param'] = 'kp'
            new_set_point['value'] = 50
            new_set_point['idx'] = 'FLoad_1'
            new_set_point['add'] = True
            new_set_point['t'] = 5
            set_point_changes.append(new_set_point)
        
        elif set_points == 'load_p0':
            new_set_point = {}
            new_set_point['model'] = 'PQ'
            new_set_point['param'] = 'p0'
            new_set_point['value'] = 1
            new_set_point['idx'] = 'PQ_1'
            new_set_point['add'] = True
            new_set_point['t'] = 5
            set_point_changes.append(new_set_point)
            new_set_point = {}
            new_set_point['model'] = 'PQ'
            new_set_point['param'] = 'Ppf'
            new_set_point['value'] = 15.7
            new_set_point['idx'] = 'PQ_1'
            new_set_point['add'] = False
            new_set_point['t'] = 5
            set_point_changes.append(new_set_point)
            new_set_point = {}
            new_set_point['model'] = 'PQ'
            new_set_point['param'] = 'p2p'
            new_set_point['value'] = 0.5
            new_set_point['idx'] = 'PQ_1'
            new_set_point['add'] = False
            new_set_point['t'] = 5
            #set_point_changes.append(new_set_point)
            new_set_point = {}
            new_set_point['model'] = 'PQ'
            new_set_point['param'] = 'p2i'
            new_set_point['value'] = 0
            new_set_point['idx'] = 'PQ_1'
            new_set_point['add'] = False
            new_set_point['t'] = 5
            #set_point_changes.append(new_set_point)

        elif set_points == 'droop':
            new_set_point = {}
            new_set_point['model'] = 'TGOV1'
            new_set_point['param'] = 'R'
            new_set_point['value'] = 0.1
            new_set_point['idx'] = 1
            new_set_point['add'] = False
            new_set_point['t'] = 5
            set_point_changes.append(new_set_point)

        elif set_points == 'converter':
            new_set_point = {}
            new_set_point['model'] = 'PVD1'
            new_set_point['param'] = 'gammap'
            new_set_point['value'] = 0.1
            new_set_point['idx'] = 1
            new_set_point['add'] = True
            new_set_point['t'] = 5
            set_point_changes.append(new_set_point)
        
        elif set_points == 'load':
            new_set_point = {}
            new_set_point['model'] = 'PQ'
            new_set_point['param'] = 'Ppf'
            new_set_point['value'] = 0.5
            new_set_point['idx'] = 'PQ_1'
            new_set_point['add'] = False
            new_set_point['t'] = 5
            set_point_changes.append(new_set_point)

        elif set_points == 'pref':
            new_set_point = {}
            new_set_point['model'] = 'TGOV1'
            new_set_point['param'] = 'pref0'
            new_set_point['value'] = 0.1
            new_set_point['idx'] = 1
            new_set_point['add'] = True
            new_set_point['t'] = 5
            set_point_changes.append(new_set_point)

        elif set_points == 'ZIP':
            new_set_point = {}
            new_set_point['model'] = 'ZIP'
            new_set_point['param'] = 'kpp'
            new_set_point['value'] = 10
            new_set_point['idx'] = 'ZIP_1'
            new_set_point['add'] = False
            new_set_point['t'] = 5
            set_point_changes.append(new_set_point)

        elif set_points == 'motor':
            new_set_point = {}
            new_set_point['model'] = 'Motor5'
            new_set_point['param'] = 'kpp'
            new_set_point['value'] = 10
            new_set_point['idx'] = 'ZIP_1'
            new_set_point['add'] = False
            new_set_point['t'] = 5
            set_point_changes.append(new_set_point)

        elif line_toggle:
            new_set_point = {}
            new_set_point['model'] = 'Toggle'
            new_set_point['param'] = 't'
            new_set_point['value'] = 5
            new_set_point['idx'] = 1
            new_set_point['add'] = False
            new_set_point['t'] = 5
            set_point_changes.append(new_set_point)
            return set_point_changes
        
        elif line_resistance:
            new_set_point = {}
            new_set_point['model'] = 'Line'
            new_set_point['param'] = 'b'
            new_set_point['value'] = 1e9
            new_set_point['idx'] = 'Line_8'
            new_set_point['add'] = False
            new_set_point['t'] = 5
            set_point_changes.append(new_set_point)
            new_set_point = {}
            new_set_point['model'] = 'Line'
            new_set_point['param'] = 'g'
            new_set_point['value'] = 1e9
            new_set_point['idx'] = 'Line_8'
            new_set_point['add'] = False
            new_set_point['t'] = 5
            set_point_changes.append(new_set_point)
        for i in range(line_n):
            if self.system.dae.t < 5 or line_id!=5:
                continue
            if set_points is None:
                break
            elif resistance:
                new_set_point = {}
                new_set_point['model'] = 'Line'
                new_set_point['param'] = 'u'
                new_set_point['value'] = 0
                new_set_point['idx'] = i
                new_set_point['add'] = False
                new_set_point['t'] = 5
            elif self.system.dae.t > 5:
                new_set_point = {}
                new_set_point['model'] = 'Line'
                new_set_point['param'] = 'u'
                new_set_point['value'] = 0
                new_set_point['idx'] = i
                new_set_point['t'] = 5
                new_set_point['add'] = False
            elif self.system.dae.t > 10:
                new_set_point['model'] = 'Line'
                new_set_point['param'] = 'u'
                new_set_point['value'] = 1
                new_set_point['idx'] = i
                new_set_point['t'] = 5
                new_set_point['add'] = False
            if 'new_set_point' in locals():        
                set_point_changes.append(new_set_point)
        if not line_failure and set_points is None:
            new_set_point = {}
            new_set_point['model'] = 'GENROU'
            new_set_point['param'] = 'u'
            new_set_point['value'] = 0
            new_set_point['idx'] = i
            new_set_point['add'] = False
            new_set_point['t'] = 5
            set_point_changes.append(new_set_point)
        return set_point_changes