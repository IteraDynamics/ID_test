"""Independent, synthetic-only parity for the explicitly inventoried I/O extractions."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any
from unittest.mock import patch
import warnings

BASELINE_SHA = 'f332255139b613af0ffa1d227585db47fb8a8fb4'
ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = '''# Keep standalone script execution working until the separate packaging migration.
import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
if str(_ArtifactPath(__file__).resolve().parents[1]) not in _artifact_sys.path:
    _artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parents[1]))
'''


def parse(source):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', SyntaxWarning)
        return ast.parse(source)


def baseline_function(path, name):
    # Original function body executes against stdlib dependencies only, never the new helper.
    node = next(n for n in parse(path.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {'Path': Path, 'Any': Any, 'hashlib': hashlib, 'sha256': hashlib.sha256, 'json': json}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), ns)
    return ns[name]


def outcome(fn, value):
    try:
        return ('return', fn(value))
    except Exception as exc:
        return ('raise', type(exc).__module__, type(exc).__qualname__, str(exc))


def require_equal(before, after):
    if before != after:
        raise AssertionError(f'I/O parity mismatch: {before!r} != {after!r}')


def check_source_boundaries(baseline, entries):
    """Constrain baseline-tracked existing Python files; additions need separate review."""
    grouped = {}
    for e in entries:
        grouped.setdefault(e['path'], set()).add(e['name'])
    bootstrap_nodes = [ast.dump(n) for n in parse(BOOTSTRAP).body]
    paths = subprocess.check_output(['git', '-C', str(baseline), 'ls-files', 'scripts', 'research', 'runtime'], text=True).splitlines()
    for rel in paths:
        if not rel.endswith('.py'):
            continue
        original = (baseline / rel).read_bytes()
        current = (ROOT / rel).read_bytes()
        if rel not in grouped:
            if original != current:
                raise AssertionError(f'Unlisted source changed: {rel}')
            continue
        old, new = parse(original.decode()), parse(current.decode())
        # Only the listed function bodies and this exact standalone import bootstrap may change.
        new.body = [n for n in new.body if ast.dump(n) not in bootstrap_nodes]
        for tree in (old, new):
            found = set()
            for n in tree.body:
                if isinstance(n, ast.FunctionDef) and n.name in grouped[rel]:
                    n.body = [ast.Pass()]
                    found.add(n.name)
            if found != grouped[rel]:
                raise AssertionError(f'Missing migration function: {rel}')
        if ast.dump(old) != ast.dump(new):
            raise AssertionError(f'Non-I/O source changed: {rel}')


def verify(baseline):
    sha = subprocess.check_output(['git', '-C', str(baseline), 'rev-parse', 'HEAD'], text=True).strip()
    if sha != BASELINE_SHA or subprocess.check_output(['git', '-C', str(baseline), 'status', '--porcelain', '--untracked-files=no'], text=True):
        raise AssertionError('Expected clean pinned I/O baseline')
    manifest = json.loads((ROOT / 'docs/engineering/ARTIFACT_IO_MIGRATIONS.json').read_text())
    entries = manifest['functions']
    if manifest['baseline'] != BASELINE_SHA or len(entries) != 23 or len({(e['path'], e['name']) for e in entries}) != 23:
        raise AssertionError('Expected frozen, non-empty 23-function inventory')
    check_source_boundaries(baseline, entries)
    results = {}
    modules = {}
    with tempfile.TemporaryDirectory(prefix='itera-io-parity-') as temp, patch('urllib.request.urlopen', side_effect=AssertionError('Network forbidden in I/O parity')):
        root = Path(temp)
        payloads = [b'', b'abc', bytes(range(256)), 'é\r\n雪\n'.encode(), b'x' * 1048575, b'y' * 1048576, b'z' * 1048577]
        paths = []
        for i, raw in enumerate(payloads):
            p = root / f'{i}.bin'
            p.write_bytes(raw)
            paths.append(p)
        paths += [root / 'missing', root]
        circular = []; circular.append(circular)
        json_values = [{}, {'z': -0.0, 'a': ['é', '雪', None, True, 1e-12]}, {'n': float('nan')}, {'n': float('inf')}, {'x': object()}, circular]
        for e in entries:
            rel, name = e['path'], e['name']
            if rel not in modules:
                spec = importlib.util.spec_from_file_location('io_candidate_' + Path(rel).stem, ROOT / rel)
                module = importlib.util.module_from_spec(spec)
                # Dataclass decorators inspect their defining module during import.
                import sys
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                modules[rel] = module
            old = baseline_function(baseline / rel, name)
            new = getattr(modules[rel], name)
            values = paths if e['kind'] == 'file' else payloads if e['kind'] == 'bytes' else json_values
            for i, value in enumerate(values):
                before, after = outcome(old, value), outcome(new, value)
                require_equal(before, after)
                # Exact serialized bytes and their digest are part of the checked result.
                if e['kind'] == 'strict_json' and before[0] == 'return':
                    require_equal(before[1].encode('utf-8'), after[1].encode('utf-8'))
                    require_equal(hashlib.sha256(before[1].encode()).hexdigest(), hashlib.sha256(after[1].encode()).hexdigest())
                results[f'{rel}:{name}:{i}'] = before
        if len(results) != 193:
            raise AssertionError(f'Expected 193 differential cases, got {len(results)}')
    # Prove that the comparator is capable of rejecting corruption.
    try:
        require_equal(('return', 'original'), ('return', 'corrupt'))
    except AssertionError:
        pass
    else:
        raise AssertionError('Comparator corruption canary failed')
    return {'status': 'PASS', 'baseline': sha, 'functions': len(entries), 'cases': len(results),
            'scope': 'Pure I/O outputs/errors and source boundaries; synthetic inputs only'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline-root', required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(verify(args.baseline_root.resolve()), indent=2))
