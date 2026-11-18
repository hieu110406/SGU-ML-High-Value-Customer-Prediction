from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import joblib
from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.capture import capture_output

path = Path('project/notebooks/03_clustering_eval/17-11-2026-hieu-dbscan-b03/dbscan.ipynb')
nb = json.loads(path.read_text(encoding='utf-8'))
shell = InteractiveShell.instance()
namespace = {'__name__': '__main__'}
count = 0
started = time.monotonic()
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    count += 1
    print(f'Executing cell {i}', flush=True)
    with capture_output() as captured:
        exec(compile(''.join(cell['source']), f'{path.name}:cell-{i}', 'exec'), namespace)
    cell['execution_count'] = count
    cell['outputs'] = []
    if captured.stdout:
        cell['outputs'].append({'output_type': 'stream', 'name': 'stdout', 'text': captured.stdout.splitlines(keepends=True)})
    if captured.stderr:
        cell['outputs'].append({'output_type': 'stream', 'name': 'stderr', 'text': captured.stderr.splitlines(keepends=True)})
    for output in captured.outputs:
        cell['outputs'].append({'output_type':'display_data','data':output.data,'metadata':output.metadata})
    if captured.stdout:
        print(captured.stdout[:1000], flush=True)
    plt.close('all')

loaded = joblib.load(namespace['artifact_path'])
assert loaded['preprocessor']['power'].standardize is False
assert loaded['preprocessor']['power'].method == 'yeo-johnson'
assert namespace['PCA_VAR'] == .9
assert len(namespace['grid']) == 72
assert set(loaded['params']['lambda_by_feature']) == set(namespace['FEATURES'])
assert np.allclose(loaded['preprocessor'].transform(namespace['X']), namespace['Z'])
assert np.allclose(loaded['preprocessor']['power'].inverse_transform(namespace['X_power']), namespace['X'])
assert np.allclose(namespace['X_scaled'].mean(axis=0), 0, atol=1e-10)
assert np.allclose(namespace['X_scaled'].std(axis=0), 1, atol=1e-10)
assert loaded['params']['pca_variance_kept'] >= .9-1e-12
assert not any('log1p' in name for name,_ in loaded['preprocessor'].steps)

# Exercise the empty-selection path without writing over actual run artifacts.
guard = next(c for c in nb['cells'] if c['cell_type']=='code' and ''.join(c['source']).startswith('valid = grid.loc[eligible]'))
empty_ns = namespace.copy()
empty_ns['eligible'] = namespace['eligible'] & False
with capture_output():
    exec(''.join(guard['source']), empty_ns)
assert empty_ns['best'] is None and empty_ns['labels'] is None and empty_ns['selected_model'] is None

path.write_text(json.dumps(nb,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
print('PASS: executed all cells, 72 configurations, lambda persistence, transform reload, inverse transform, standardization, PCA threshold and no-eligible guard.')
print('Elapsed seconds:', round(time.monotonic()-started,1))
