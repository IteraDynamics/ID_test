"""Boundary checks for packaged research and preserved historical entry points."""
import ast
import importlib
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from research.ml_lab import macro_v1
from research.ml_lab.experiments import experiment_011 as transfer

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('number', range(5, 12))
def test_legacy_entrypoint_resolves_to_packaged_implementation(number):
    legacy = importlib.import_module(f'scripts.run_ml_lab_experiment_{number:03}')
    implementation = importlib.import_module(f'research.ml_lab.experiments.experiment_{number:03}')
    assert legacy is implementation
    result = subprocess.run([sys.executable, str(ROOT / f'scripts/run_ml_lab_experiment_{number:03}.py'), '--help'], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert '--output-dir' in result.stdout


def forbidden_imports(source, *, runtime=False):
    imports = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or '')
            imports.extend(f'{node.module}.{alias.name}' for alias in node.names)
    return [name for name in imports if name.startswith(('scripts', 'run_ml_lab_experiment')) or runtime and name.startswith('research.ml_lab')]


def test_package_and_runtime_import_boundaries():
    assert forbidden_imports('from scripts import run_ml_lab_experiment_005')
    assert forbidden_imports('import research.ml_lab.experiments', runtime=True)
    assert forbidden_imports('from research import ml_lab', runtime=True)
    for base in ['research/ml_lab', 'runtime']:
        for path in (ROOT / base).rglob('*.py'):
            assert not forbidden_imports(path.read_text(), runtime=base == 'runtime'), path


def test_training_embargo_rejects_targets_crossing_test_boundary():
    start = pd.Timestamp('2022-01-03', tz='UTC')
    panel = pd.DataFrame({
        'timestamp': pd.to_datetime(['2018-01-01', '2021-12-01', '2021-12-02', '2022-01-03'], utc=True),
        'target_end_date': pd.to_datetime(['2018-02-01', '2022-01-02', '2022-01-03', '2022-02-01'], utc=True),
    })
    assert macro_v1.training_slice(panel, start, 3).index.tolist() == [1]
    assert macro_v1.training_slice(panel, start, None).index.tolist() == [0, 1]


def test_transfer_parity_gate_detects_score_and_row_corruption():
    sample = pd.DataFrame({'timestamp': pd.to_datetime(['2022-01-03'] * 2, utc=True), 'ticker': ['A', 'B']})
    saved = sample.assign(test_year=2022, memory_scheme='expanding', model='price_ridge', score=[.2, .8])
    assert transfer._parity_check(saved, sample, np.array([.2, .8]), 2022, 'expanding', 'price_ridge')['passed']
    with pytest.raises(ValueError, match='SOURCE_PARITY_FAILURE'):
        transfer._parity_check(saved, sample, np.array([.2, .9]), 2022, 'expanding', 'price_ridge')
    with pytest.raises(ValueError, match='SOURCE_PARITY_ROW_MISMATCH'):
        transfer._parity_check(saved.iloc[:1], sample, np.array([.2, .8]), 2022, 'expanding', 'price_ridge')
