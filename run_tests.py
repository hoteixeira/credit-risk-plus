import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
import pandas as pd
import numpy as np
import glob
import os

# 1. Extract Theoretical Values from XLS
xls_path = 'references/CreditRisk+.xls'
xls = pd.ExcelFile(xls_path)
sheets = ['Example1A', 'Example1B', 'Example2', 'Example3']
theory_values = {}

for sheet in sheets:
    df = pd.read_excel(xls, sheet_name=sheet)
    for c in range(df.shape[1] - 1):
        if str(df.iloc[8, c]).strip() == 'Amount' and str(df.iloc[8, c+1]).strip() == 'Probability':
            amounts = pd.to_numeric(df.iloc[9:, c], errors='coerce').fillna(0).values
            probs = pd.to_numeric(df.iloc[9:, c+1], errors='coerce').fillna(0).values
            
            valid = (probs > 0) & (~np.isnan(probs)) & (~np.isnan(amounts))
            valid_idx = np.where(valid)[0]
            if len(valid_idx) == 0:
                continue
                
            first_idx, last_idx = valid_idx[0], valid_idx[-1]
            amounts = amounts[first_idx:last_idx+1]
            probs = probs[first_idx:last_idx+1]
            
            el = np.sum(amounts * probs)
            cdf = np.cumsum(probs)
            
            idx = np.searchsorted(cdf, 0.99)
            if idx < len(cdf):
                if idx == 0:
                    var_99 = 0
                else:
                    p_lo, p_hi = cdf[idx - 1], cdf[idx]
                    unit_size = amounts[idx] - amounts[idx-1] if idx > 0 else amounts[0]
                    frac = (0.99 - p_lo) / (p_hi - p_lo) if p_hi > p_lo else 0.0
                    var_99 = amounts[idx - 1] + frac * unit_size
            else:
                var_99 = amounts[-1]
                
            theory_values[sheet] = {'EL': el, 'VaR99': var_99}
            break

# Exemplo 1C multi-year is theoretically 3x EL of 1 year, and VaR99 is around 111,450,000.
# We will use the notebook 1A expected values to infer 1C if needed, or skip strict test.

theory_mapping = {
    '04_exemplo_1A.ipynb': 'Example1A',
    '05_exemplo_1B.ipynb': 'Example1B',
    '07_exemplo_2_setores_geo.ipynb': 'Example2',
    '08_exemplo_3_setores_fracionarios.ipynb': 'Example3'
}

# 2. Run Notebooks and Extract Variables
notebooks = sorted(glob.glob('notebooks/*.ipynb'))

def extract_globals_from_notebook(nb_path):
    print(f"\\n{'='*60}\\nRunning {nb_path}...")
    with open(nb_path) as f:
        nb = nbformat.read(f, as_version=4)
        
    # Inject a cell to dump variables
    injection = """
import json
import numpy as np

def _safe_float(v):
    try:
        return float(v)
    except:
        return None

out = {}
g = globals()
out['el'] = _safe_float(g.get('el', g.get('el_1b', g.get('total_el_3years', g.get('total_el_example2', g.get('total_el_ex3'))))))
out['var_99'] = _safe_float(g.get('var_99', g.get('loss_99_1b', g.get('loss_99_3y', g.get('loss_99_example2', g.get('loss_99_ex3'))))))

with open('nb_vars.json', 'w') as f:
    json.dump(out, f)
"""
    new_cell = nbformat.v4.new_code_cell(source=injection)
    nb.cells.append(new_cell)
    
    ep = ExecutePreprocessor(timeout=600, kernel_name='python3')
    ep.preprocess(nb, {'metadata': {'path': 'notebooks/'}})
    
    import json
    with open('notebooks/nb_vars.json') as f:
        vars = json.load(f)
    os.remove('notebooks/nb_vars.json')
    return vars

all_passed = True

for nb_path in notebooks:
    if 'exemplo' not in nb_path:
        continue
        
    nb_name = os.path.basename(nb_path)
    try:
        res = extract_globals_from_notebook(nb_path)
        el = res.get('el')
        var_99 = res.get('var_99')
        
        print(f"Results from {nb_name}:")
        print(f"  EL:     {el}")
        print(f"  VaR_99: {var_99}")
        
        if nb_name in theory_mapping:
            sheet = theory_mapping[nb_name]
            theory = theory_values[sheet]
            
            t_el = theory['EL']
            t_var = theory['VaR99']
            
            el_err = abs(el - t_el) / t_el if t_el else 0
            
            print(f"Theory ({sheet}):")
            print(f"  EL:     {t_el} (Error: {el_err*100:.2f}%)")
            
            if el_err > 0.01:
                print(f"  [!] EL Error > 1%!")
                all_passed = False
                
            if var_99 is not None and t_var is not None:
                var_err = abs(var_99 - t_var) / t_var if t_var else 0
                print(f"  VaR_99: {t_var} (Error: {var_err*100:.2f}%)")
                if var_err > 0.01:
                    print(f"  [!] VaR_99 Error > 1%!")
                    all_passed = False
            else:
                print(f"  VaR_99: {t_var} (Not compared)")
        else:
            print(f"  No explicit spreadsheet sheet to compare.")
            
    except Exception as e:
        print(f"FAILED TO RUN {nb_name}: {e}")
        all_passed = False

if all_passed:
    print("\\nSUCCESS: All notebooks passed the theory validation within 1% tolerance.")
else:
    print("\\nFAILURE: Some notebooks failed the theory validation.")
    exit(1)
