"""Pinned structural contract for the scripts packaging migration."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import warnings

BASELINE_SHA = 'e75fb88808ed9c7bc45cf2f8bc04a2a9e43ce8d9'
ROOT = Path(__file__).resolve().parents[1]
PRELUDE = '''# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)
'''
PATH_STATEMENTS = (
    'sys.path.insert(0, str(REPO_ROOT))',
    'sys.path.insert(0, str(Path(__file__).resolve().parent.parent))',
    'sys.path.insert(0, str(Path(__file__).parent.parent))',
    'sys.path.insert(0, str(REPO_ROOT / "scripts"))',
    'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))',
    'if str(REPOSITORY_ROOT) not in sys.path:\n    sys.path.insert(0, str(REPOSITORY_ROOT))',
    'if str(REPO_ROOT) not in sys.path:\n    sys.path.insert(0, str(REPO_ROOT))',
    'if __package__ in (None, ""):\n    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))',
    'if __package__ in (None, ""):\n    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))',
    'if str(_ArtifactPath(__file__).resolve().parents[1]) not in _artifact_sys.path:\n    _artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parents[1]))',
    'import sys as _artifact_sys',
    'from pathlib import Path as _ArtifactPath',
)
SIBLINGS = {'analyze_vrp_defined_risk_backtest', 'download_equity_data',
            'analyze_cot_positioning_signal', 'backtest_pairs_distance_method'}
NEW_SOURCE_FILES = {'scripts/__init__.py', 'scripts/_checkout_bootstrap.py',
                    'scripts/_packaging_contract.py', 'scripts/verify_scripts_packaging.py'}
ADAPTED_GATE = 'scripts/verify_artifact_io_parity.py'
EXPECTED_MIGRATION_FILES = 111


def parse(source):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', SyntaxWarning)
        return ast.parse(source)


REMOVABLE = {ast.dump(parse(s).body[0]) for s in (*PATH_STATEMENTS, PRELUDE)}


def normalized_source(source):
    tree = parse(source)
    body = []
    for node in tree.body:
        if ast.dump(node) in REMOVABLE:
            continue
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module in SIBLINGS:
            node.module = 'scripts.' + node.module
        elif isinstance(node, ast.Import) and len(node.names) == 1 and node.names[0].name == 'download_equity_data':
            node = ast.ImportFrom(module='scripts', names=node.names, level=0)
        body.append(node)
    tree.body = body
    return ast.dump(tree)


def check_packaging_boundaries(baseline: Path, current: Path = ROOT):
    sha = subprocess.check_output(['git', '-C', str(baseline), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(baseline), 'status', '--porcelain', '--untracked-files=no'], text=True)
    if sha != BASELINE_SHA or dirty:
        raise AssertionError('Expected clean pinned packaging baseline')
    manifest = json.loads((current / 'docs/engineering/SCRIPTS_PACKAGING_MIGRATIONS.json').read_text())
    files = manifest['files']
    if manifest['baseline'] != BASELINE_SHA or len(files) != EXPECTED_MIGRATION_FILES:
        raise AssertionError('Expected frozen 111-file packaging inventory')
    old_paths = set(subprocess.check_output(['git', '-C', str(baseline), 'ls-files', 'scripts', 'research', 'runtime'], text=True).splitlines())
    new_paths = {str(p.relative_to(current)) for folder in ('scripts', 'research', 'runtime')
                 for p in (current / folder).rglob('*.py') if '__pycache__' not in p.parts}
    if not set(files) <= old_paths:
        raise AssertionError("Packaging inventory contains unknown baseline files")
    additions = new_paths - old_paths
    if additions != NEW_SOURCE_FILES:
        raise AssertionError(f'Unexpected new/missing packaging source files: {additions ^ NEW_SOURCE_FILES}')
    for rel in sorted(p for p in old_paths if p.endswith('.py')):
        before, after = (baseline / rel).read_bytes(), (current / rel).read_bytes()
        if rel == ADAPTED_GATE:
            if hashlib.sha256(after).hexdigest() != manifest['adapted_gate_sha256']:
                raise AssertionError('I/O gate adaptation changed outside reviewed manifest')
        elif rel in files:
            if normalized_source(before.decode()) != normalized_source(after.decode()):
                raise AssertionError(f'Non-packaging source changed: {rel}')
        elif before != after:
            raise AssertionError(f'Unlisted existing source changed: {rel}')
    return {'existing_files_checked': sum(p.endswith('.py') for p in old_paths),
            'packaging_files': len(files), 'new_source_files': len(additions)}
