import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
import glob
import os

notebooks = sorted(glob.glob('notebooks/*.ipynb'))

def run_notebook(path):
    print(f"\\n{'='*40}\\nRunning {path}...")
    with open(path) as f:
        nb = nbformat.read(f, as_version=4)
    ep = ExecutePreprocessor(timeout=600, kernel_name='python3')
    ep.preprocess(nb, {'metadata': {'path': 'notebooks/'}})
    return nb

for nb_path in notebooks:
    if 'exemplo' not in nb_path:
        continue
    try:
        nb = run_notebook(nb_path)
        for cell in nb.cells:
            if cell.cell_type == 'code':
                for output in cell.outputs:
                    if output.output_type == 'stream' and output.name == 'stdout':
                        lines = output.text.split('\\n')
                        for line in lines:
                            if 'Perda Esperada' in line or 'percentil' in line or 'VaR' in line or 'Total de Exposição' in line:
                                print(f"[{os.path.basename(nb_path)}] {line.strip()}")
    except Exception as e:
        print(f"[{os.path.basename(nb_path)}] FAILED TO RUN: {e}")
