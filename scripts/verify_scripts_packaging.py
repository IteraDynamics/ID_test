"""Verify the packaging source boundary and a wheel outside the checkout."""
from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)

import argparse
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from scripts._packaging_contract import ROOT, check_packaging_boundaries


def verify_wheel(wheel: Path):
    with tempfile.TemporaryDirectory(prefix='itera-installed-wheel-') as temp:
        root = Path(temp)
        target = root / 'installed'
        with zipfile.ZipFile(wheel) as archive:
            expected = {str(p.relative_to(ROOT)) for p in (ROOT / 'scripts').glob('*.py')}
            names = set(archive.namelist())
            if not expected or not expected <= names or any(n.endswith('.pyc') for n in names):
                raise AssertionError(f'Wheel script inventory mismatch: {expected - names}')
        install = subprocess.run(['uv', 'pip', 'install', '--no-deps', '--no-index', '--target', str(target), str(wheel)], text=True, capture_output=True)
        if install.returncode:
            raise AssertionError('Local wheel installation failed: ' + install.stderr)
        checks = '''import importlib, json, runpy, sys
from pathlib import Path
from unittest.mock import patch
installed, checkout = map(Path, sys.argv[1:3])
sys.path[:] = [str(installed)] + [p for p in sys.path if Path(p).resolve() != checkout.resolve()]
before = list(sys.path)
import scripts, research, runtime
assert sys.path == before, 'Package import changed sys.path'
for module in (scripts, research, runtime):
    assert Path(module.__file__).is_relative_to(installed), module.__file__
modules = ['run_campaign50_development_validation', 'run_campaign52_governed_equivalence',
           'prepare_ml_lab_experiment_011_sources', 'analyze_vrp_cash_secured_put',
           'run_vrp_structure_robustness_sweep', 'run_cot_cross_sectional_discovery',
           'backtest_low_volatility_factor', 'analyze_vrp_premium_distribution',
           'run_core_v1_paper_live', 'run_core_v1_jump_risk_replay']
with patch('urllib.request.urlopen', side_effect=AssertionError('Network forbidden in packaging verification')):
    for name in modules:
        module = importlib.import_module('scripts.' + name)
        assert Path(module.__file__).is_relative_to(installed), module.__file__
        assert sys.path == before, name + ' changed sys.path during package import'
    for number in range(5, 12):
        legacy = importlib.import_module(f'scripts.run_ml_lab_experiment_{number:03}')
        implementation = importlib.import_module(f'research.ml_lab.experiments.experiment_{number:03}')
        assert legacy is implementation
        assert Path(legacy.__file__).is_relative_to(installed), legacy.__file__
        assert sys.path == before
    from scripts import run_campaign50_development_validation as c50
    from scripts import run_campaign52_governed_equivalence as c52
    fixture = Path('fixture.bin'); fixture.write_bytes(b'abc')
    expected = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    assert c50._sha256_bytes(b'abc') == c52.sha256_file(fixture) == expected
    from scripts import verify_refactor_runtime_parity as parity
    import copy
    args = parity._args(Path('paper'), is_candidate=False)
    snapshot, provenance = parity.frozen_market_snapshot()
    with patch.object(parity.current, 'utc_now', return_value=parity.FIXED_NOW), patch.object(parity.current, 'load_market_data', return_value=(copy.deepcopy(snapshot), copy.deepcopy(provenance))):
        parity.current.run_cycle(args)
    parity.run_failure_cycle(parity.current, args, snapshot, provenance)
print(json.dumps({'status':'PASS', 'installed_imports':17, 'ml_alias_identities':7}))
'''
        completed = subprocess.run([sys.executable, '-I', '-c', checks, str(target), str(ROOT)], cwd=root, text=True, capture_output=True, timeout=90)
        if completed.returncode:
            raise AssertionError(completed.stderr + '\n' + completed.stdout[-2000:])
        result = json.loads(completed.stdout.splitlines()[-1])
        commands = ['run_campaign50_development_validation', 'run_campaign52_governed_equivalence',
                    'prepare_ml_lab_experiment_011_sources', 'analyze_vrp_cash_secured_put',
                    'run_vrp_structure_robustness_sweep', 'run_cot_cross_sectional_discovery',
                    'backtest_low_volatility_factor', 'analyze_vrp_premium_distribution',
                    'run_core_v1_paper_live', 'run_core_v1_jump_risk_replay']
        commands += [f'run_ml_lab_experiment_{n:03}' for n in range(5, 12)]
        command_runner = "import sys,runpy; from pathlib import Path; sys.path[:]=[sys.argv[1]]+[p for p in sys.path if Path(p).resolve()!=Path(sys.argv[2]).resolve()]; name=sys.argv[3]; sys.argv=[name,'--help']; runpy.run_module('scripts.'+name,run_name='__main__')"
        for name in commands:
            command = subprocess.run([sys.executable, '-I', '-c', command_runner, str(target), str(ROOT), name], cwd=root, text=True, capture_output=True, timeout=30)
            if command.returncode or 'usage:' not in command.stdout.lower():
                raise AssertionError(f'Installed module CLI failed: {name}: {command.stderr}')
        result['module_help_commands'] = len(commands)
        result['installed_paper_success_and_error_cycles'] = 2
        # Exercise actual artifact production, not only imports/help. The original
        # full ML gate separately proves checkout parity against the frozen baseline.
        from scripts import verify_refactor_ml_parity as ml
        fixture_root = root / 'ml-fixture'
        fixture_root.mkdir()
        ml.fixture(fixture_root)
        output = fixture_root / '005'
        execute = "import sys,runpy; from pathlib import Path; sys.path[:]=[sys.argv[1]]+[p for p in sys.path if Path(p).resolve()!=Path(sys.argv[2]).resolve()]; sys.argv=['experiment_005','--data-dir',sys.argv[3],'--output-dir',sys.argv[4]]; runpy.run_module('scripts.run_ml_lab_experiment_005',run_name='__main__')"
        inventories = []
        for code_root in (ROOT, target):
            command = subprocess.run([sys.executable, '-I', '-c', execute, str(code_root), str(ROOT), str(fixture_root / 'source'), str(output)], cwd=root, text=True, capture_output=True, timeout=120)
            if command.returncode:
                raise AssertionError('Packaged ML execution failed: ' + command.stderr)
            inventory = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob('*') if p.is_file()}
            if len(inventory) != 7:
                raise AssertionError(f'Expected 7 Experiment 005 files, got {len(inventory)}')
            inventories.append(inventory)
            shutil.rmtree(output)
        ml.check_outputs_equal(*inventories)
        result['installed_ml_artifacts_byte_identical'] = len(inventories[0])
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-root', required=True, type=Path)
    parser.add_argument('--wheel', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps({'source': check_packaging_boundaries(args.baseline_root.resolve()),
                      'wheel': verify_wheel(args.wheel.resolve())}, indent=2))
