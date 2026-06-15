import pandas as pd
import numpy as np

xls = pd.ExcelFile('references/CreditRisk+.xls')
sheets = ['Example1A', 'Example1B', 'Example1C', 'Example2', 'Example3']

results = {}

for sheet in sheets:
    df = pd.read_excel(xls, sheet_name=sheet)
    # The columns 15 and 16 (0-indexed) are typically 'Credit Loss Amount' and 'Probability'
    # but the exact names might be different. Let's find columns that have 'Probability' in row 8
    
    # We can just iterate through columns to find 'Credit' and 'Probability'
    for c in range(df.shape[1] - 1):
        if str(df.iloc[8, c]).strip() == 'Amount' and str(df.iloc[8, c+1]).strip() == 'Probability':
            # It's an Amount and Probability
            amounts = pd.to_numeric(df.iloc[9:, c], errors='coerce').fillna(0).values
            probs = pd.to_numeric(df.iloc[9:, c+1], errors='coerce').fillna(0).values
            
            # Filter where prob > 0 or amounts are valid
            valid = (probs >= 0) & (~np.isnan(probs)) & (~np.isnan(amounts))
            amounts = amounts[valid]
            probs = probs[valid]
            
            if len(amounts) > 0:
                el = np.sum(amounts * probs)
                
                # compute cdf
                cdf = np.cumsum(probs)
                
                # For VaR99, we interpolate or just find the first amount where cdf >= 0.99
                # Let's find exactly how the spreadsheet does it or just take the exact percentile
                idx = np.searchsorted(cdf, 0.99)
                if idx < len(cdf):
                    # Linear interpolation like in the notebook
                    if idx == 0:
                        var_99 = 0
                    else:
                        p_lo, p_hi = cdf[idx - 1], cdf[idx]
                        unit_size = amounts[idx] - amounts[idx-1] if idx > 0 else amounts[0]
                        frac = (0.99 - p_lo) / (p_hi - p_lo) if p_hi > p_lo else 0.0
                        var_99 = amounts[idx - 1] + frac * unit_size
                else:
                    var_99 = amounts[-1]
                
                results[sheet] = {'EL': el, 'VaR99': var_99}
            break

print("Theoretical values from Spreadsheet:")
for sheet, vals in results.items():
    print(f"{sheet}: EL = {vals['EL']:.0f}, VaR99 = {vals['VaR99']:.0f}")

