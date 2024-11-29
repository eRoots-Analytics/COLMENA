import openpyxl
import numpy as np

def add_sheet(workbook, sheet_name, data):

    # Create a new sheet
    if sheet_name in workbook.sheetnames:
        print(f'Sheet "{sheet_name}" already exists. It will be overwritten.')
        workbook.remove(workbook[sheet_name])
    new_sheet = workbook.create_sheet(title=sheet_name)

    # Write the header row
    for col_idx, key in enumerate(data.keys(), 1):
        new_sheet.cell(row=1, column=col_idx, value=key)

    # Write the data rows
    for row_idx in range(len(next(iter(data.values())))):  # Assuming all columns have the same length
        for col_idx, key in enumerate(data.keys(), 1):
            new_sheet.cell(row=row_idx + 2, column=col_idx, value=data[key][row_idx])

    return workbook

def set_config(system, setup=1, device_uid=0, toggle_model= None):
    tds_object = system.TDS_colmena
    def f_condition(mdl, device_idx, colmena_device =[1], epsilon = 0.003, dae_t = 0):
        uid = mdl.idx2uid(device_idx)
        if device_idx not in colmena_device:
            return False
        if mdl.omega.v[uid] > 1-epsilon and mdl.omega.v[uid]<1+epsilon:
            return False
        return True

    def f_condition2(mdl, device_idx, colmena_device =[1], epsilon = 0.003, dae_t=0):
        uid = mdl.idx2uid(device_idx)
        if device_idx not in colmena_device:
            return False
        if dae_t < 10:
            return False
        return True
    
    
    if getattr(tds_object.config, 'changes', None) is None:
        tds_object.config.changes = {}
    if setup == 1:
        tds_object.config.instructions = (f_condition, lambda x: 0*x + 13, lambda x: 0*x + 130)
        tds_object.config.instruction_msg = {}
        tds_object.config.instruction_msg["GENROU"] = (f_condition, lambda x: 0*x + 13, lambda x: 0*x + 130)
        tds_object.config.param = 'M'
        tds_object.config.device_uid = device_uid
        tds_object.config.changes[setup] = tds_object.config.instructions
    if setup == 2:
        tds_object.config.instructions = (f_condition2, lambda x: 0.1, lambda x: 0.2)
        tds_object.config.instruction_msg = {}
        tds_object.config.instruction_msg["PVD1"] = (f_condition2, lambda x: 0.1, lambda x: 0.2)
        tds_object.config.param = 'gammap'
        tds_object.config.device_uid = device_uid
        tds_object.config.changes[setup] = tds_object.config.instructions
    if setup == 3:
        tds_object.config.instructions = (f_condition2, lambda x: 1, lambda x: 0)
        tds_object.config.instruction_msg = {}
        tds_object.config.instruction_msg["Toggle_Line"] = (f_condition2, lambda x: 1, lambda x: 0)
        tds_object.config.param = 'connect'
        tds_object.config.device_uid = device_uid
        tds_object.config.changes[setup] = tds_object.config.instructions
    if setup == 4:
        tds_object.config.instructions = (f_condition2, lambda x: 1, lambda x: 0)
        tds_object.config.instruction_msg = {}
        tds_object.config.instruction_msg["GENROU_2"] = (f_condition2, lambda x: 1, lambda x: 0)
        tds_object.config.param = 'u'
        tds_object.config.device_uid = device_uid
        tds_object.config.changes[setup] = tds_object.config.instructions
    if setup == 5:
        tds_object.config.instructions = (f_condition2, lambda x: 0, lambda x: 999)
        tds_object.config.instruction_msg = {}
        tds_object.config.instruction_msg["Line"] = (f_condition2, lambda x: 0, lambda x: 999)
        tds_object.config.param = 'r'
        tds_object.config.device_uid = device_uid
        tds_object.config.changes[setup] = tds_object.config.instructions
    if setup == 6:
        tds_object.config.instructions = (f_condition2, lambda x: 1, lambda x: 0)
        tds_object.config.instruction_msg = {}
        tds_object.config.instruction_msg[toggle_model] = (f_condition2, lambda x: 1, lambda x: 0)
        tds_object.config.param = 'connect'
        tds_object.config.device_uid = device_uid
        tds_object.config.changes[setup] = tds_object.config.instructions
        
    if isinstance(setup, (list, np.ndarray)):
        for i, set in enumerate(setup):
            set_config(system, setup=set)
    return

def delete_last_row(workbook, sheet_name):
    sheet = workbook[sheet_name]
    
    # Get the maximum row number (last row)
    max_row = sheet.max_row
    max_column = sheet.max_column
    
    # Get the headers from the first row
    headers = [sheet.cell(row=1, column=i).value for i in range(1, max_column + 1)]
    
    # Get the data from the last row
    last_row_data = [sheet.cell(row=max_row, column=i).value for i in range(1, max_column + 1)]
    
    # Create the dictionary from headers and last row data
    last_row_dict = {headers[i]: [last_row_data[i]] for i in range(max_column)}
    
    # Delete the last row
    sheet.delete_rows(max_row)
    
    return last_row_dict

def transfer_grid_info(system_from, system_to):
    for model_from in system_from.models:
        model_from = getattr(system_from, model_from)
        if model_from.n == 0:
            continue
        model_name = model_from.class_name
        model_to = getattr(system_to, model_name)
        
        for var_name, var_from in model_from._states_and_ext().items():
            for i in range(model_from.n):
                var_to = getattr(model_to, var_name)
                var_to.v[i] = var_from.v[i]
                
        for var_name, var_from in model_from._algebs_and_ext().items():
            for i in range(model_from.n):
                var_to = getattr(model_to, var_name)
                var_to.v[i] = var_from.v[i]
        
        for var_name, var_from in model_from._all_params().items():
            for i in range(model_from.n):
                var_to = getattr(model_to, var_name)
                try:
                    var_to.v[i] = var_from.v[i]
                except:
                    _ = 0
        
        for var_name, var_from in model_from.discrete.items():
            for i in range(model_from.n):
                var_to = getattr(model_to, var_name)
                for flag in ['v', 'zu', 'zl', 'zi']:
                    try:
                        val = getattr(var_from, flag)[i]
                        getattr(var_to, flag)[i] = val
                    except:
                        _ = 0
    
    system_to.dae.t = system_from.dae.t
    return system_to
                