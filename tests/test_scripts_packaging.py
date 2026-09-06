"""Adversarial tests of the packaging containment and wheel-inventory checks."""
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from scripts import _packaging_contract as contract
from scripts.verify_scripts_packaging import verify_wheel


@pytest.fixture
def boundary(tmp_path, monkeypatch):
    baseline, current = tmp_path / 'old', tmp_path / 'new'
    original = 'import sys\nfrom pathlib import Path\nREPO_ROOT = Path(__file__).parent.parent\nsys.path.insert(0, str(REPO_ROOT))\ndef calculate(x):\n    return x + 1\n'
    for root in (baseline, current):
        (root / 'scripts').mkdir(parents=True)
        (root / 'runtime').mkdir()
        (root / 'research').mkdir()
        (root / 'scripts/example.py').write_text(original)
        (root / 'runtime/frozen.py').write_text('WEIGHT = 0.25\n')
        (root / contract.ADAPTED_GATE).write_text('GATE = 1\n')
    changed = original.replace('sys.path.insert(0, str(REPO_ROOT))\n', '')
    (current / 'scripts/example.py').write_text(contract.PRELUDE + changed)
    for name in contract.NEW_SOURCE_FILES:
        (current / name).write_text('')
    (current / 'docs/engineering').mkdir(parents=True)
    manifest = {'baseline': contract.BASELINE_SHA, 'files': {'scripts/example.py': {}},
                'adapted_gate_sha256': hashlib.sha256((current / contract.ADAPTED_GATE).read_bytes()).hexdigest()}
    (current / 'docs/engineering/SCRIPTS_PACKAGING_MIGRATIONS.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(contract, 'EXPECTED_MIGRATION_FILES', 1)
    def git(args, **kwargs):
        if 'rev-parse' in args: return contract.BASELINE_SHA
        if 'status' in args: return ''
        return 'scripts/example.py\nruntime/frozen.py\n' + contract.ADAPTED_GATE + '\n'
    monkeypatch.setattr(contract.subprocess, 'check_output', git)
    contract.check_packaging_boundaries(baseline, current)
    return baseline, current


@pytest.mark.parametrize('drift', ['addition', 'missing_new', 'frozen', 'logic', 'signature', 'import', 'bootstrap', 'gate'])
def test_packaging_boundary_rejects_unapproved_drift(boundary, drift):
    baseline, current = boundary
    path = current / 'scripts/example.py'
    if drift == 'addition': (current / 'scripts/rogue.py').write_text('BAD = True\n')
    elif drift == 'missing_new': (current / 'scripts/__init__.py').unlink()
    elif drift == 'frozen': (current / 'runtime/frozen.py').write_text('WEIGHT = 0.5\n')
    elif drift == 'logic': path.write_text(path.read_text().replace('x + 1', 'x + 2'))
    elif drift == 'signature': path.write_text(path.read_text().replace('calculate(x)', 'calculate(x, y)'))
    elif drift == 'import': path.write_text(path.read_text() + 'import unrelated\n')
    elif drift == 'bootstrap': path.write_text(path.read_text().replace('_bootstrap_checkout(__file__)', '_bootstrap_checkout("elsewhere")'))
    else: (current / contract.ADAPTED_GATE).write_text('GATE = 0\n')
    with pytest.raises(AssertionError): contract.check_packaging_boundaries(baseline, current)


def test_only_equivalent_sibling_imports_normalize():
    assert contract.normalized_source('import download_equity_data as dl') == contract.normalized_source('from scripts import download_equity_data as dl')
    assert contract.normalized_source('from analyze_cot_positioning_signal import load_cot_market') == contract.normalized_source('from scripts.analyze_cot_positioning_signal import load_cot_market')
    assert contract.normalized_source('from unrelated import load_cot_market') != contract.normalized_source('from scripts.analyze_cot_positioning_signal import load_cot_market')


def test_empty_wheel_cannot_pass(tmp_path):
    wheel = tmp_path / 'empty.whl'
    with zipfile.ZipFile(wheel, 'w'): pass
    with pytest.raises(AssertionError, match='Wheel script inventory mismatch'):
        verify_wheel(wheel)


def test_bare_checkout_command_without_site_packages(tmp_path):
    import subprocess
    import sys
    source = contract.ROOT / 'scripts/inventory_campaign50_equity_sources.py'
    fixture = tmp_path / 'input'; fixture.write_bytes(b'abc')
    program = "import runpy,sys; from pathlib import Path; sys.path.insert(0,str(Path(sys.argv[1]).parent)); ns=runpy.run_path(sys.argv[1]); print(ns['sha256_file'](Path(sys.argv[2])))"
    result = subprocess.run([sys.executable, '-I', '-S', '-c', program, str(source), str(fixture)], cwd=tmp_path, text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
