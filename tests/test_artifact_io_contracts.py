"""Guard byte contracts and adversarial source-boundary/comparator failures."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from research.artifact_io import v1
from scripts import verify_artifact_io_parity as parity


def test_file_hash_known_vectors_and_chunk_boundary(tmp_path):
    for payload, expected in [(b'', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
                              (b'abc', 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')]:
        path = tmp_path / 'bytes'
        path.write_bytes(payload)
        assert v1.sha256_file_v1(path) == expected
    path.write_bytes(bytes(range(256)) * 4097)
    assert v1.sha256_file_v1(path) == v1.sha256_file_v1(path, chunk_size=1024) == hashlib.sha256(path.read_bytes()).hexdigest()


def test_legacy_read_size_and_constructor_target_are_preserved():
    reads = []
    class Reader:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size):
            reads.append(size)
            return b'abc' if len(reads) == 1 else b''
    path = SimpleNamespace(open=lambda mode: Reader())
    constructors = []
    def factory():
        constructors.append(True)
        return hashlib.sha256()
    assert v1.sha256_file_v1(path, chunk_size=1024, factory=factory) == hashlib.sha256(b'abc').hexdigest()
    assert reads == [1024, 1024]
    assert constructors == [True]


def test_independent_baseline_rejects_corrupt_shared_helper(tmp_path, monkeypatch):
    original = tmp_path / 'baseline.py'
    original.write_text('def digest(payload):\n    return hashlib.sha256(payload).hexdigest()\n')
    old = parity.baseline_function(original, 'digest')
    monkeypatch.setattr(v1, 'sha256_file_v1', lambda *args, **kwargs: 'corrupt')
    from scripts import prepare_ml_lab_experiment_009_sources as caller
    path = tmp_path / 'input'
    path.write_bytes(b'abc')
    with pytest.raises(AssertionError, match='I/O parity mismatch'):
        parity.require_equal(parity.outcome(old, b'abc'), parity.outcome(caller._sha256, path))


@pytest.mark.parametrize('drift', ['unlisted', 'logic', 'signature', 'missing'])
def test_source_boundary_rejects_changes_outside_extraction(tmp_path, monkeypatch, drift):
    old, new = tmp_path / 'old', tmp_path / 'new'
    for root in (old, new):
        (root / 'scripts').mkdir(parents=True)
        (root / 'scripts/a.py').write_text('def digest(path):\n    return 1\ndef logic():\n    return 2\n')
        (root / 'scripts/b.py').write_text('FROZEN = 3\n')
    monkeypatch.setattr(parity, 'ROOT', new)
    monkeypatch.setattr(parity.subprocess, 'check_output', lambda *args, **kwargs: 'scripts/a.py\nscripts/b.py\n')
    entries = [{'path': 'scripts/a.py', 'name': 'digest'}]
    parity.check_source_boundaries(old, entries)
    if drift == 'unlisted': (new / 'scripts/b.py').write_text('FROZEN = 4\n')
    elif drift == 'logic': (new / 'scripts/a.py').write_text('def digest(path):\n    return 1\ndef logic():\n    return 3\n')
    elif drift == 'signature': (new / 'scripts/a.py').write_text('def digest(other):\n    return 1\ndef logic():\n    return 2\n')
    else: (new / 'scripts/a.py').write_text('def logic():\n    return 2\n')
    with pytest.raises(AssertionError): parity.check_source_boundaries(old, entries)


def test_strict_json_golden_bytes_and_byte_digest():
    encoded = v1.strict_json_text_v1({'z': -0.0, 'a': 'é雪'}).encode('utf-8')
    assert encoded == '{\n  "a": "é雪",\n  "z": -0.0\n}\n'.encode('utf-8')
    assert v1.sha256_bytes_v1(b'abc') == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    assert v1.sha256_bytes_v1(encoded) == hashlib.sha256(encoded).hexdigest()


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
def test_strict_json_rejects_nonfinite_values(value):
    with pytest.raises(ValueError): v1.strict_json_text_v1({'value': value})


def test_strict_json_rejects_unsupported_values():
    with pytest.raises(TypeError): v1.strict_json_text_v1({'value': object()})


SCRIPT_ENTRIES = [e for e in json.loads((parity.ROOT / 'docs/engineering/ARTIFACT_IO_MIGRATIONS.json').read_text())['functions']
                  if e['path'].startswith('scripts/') and e['kind'] in ('file', 'bytes')]


@pytest.mark.parametrize('entry', SCRIPT_ENTRIES, ids=lambda e: e['path'])
def test_standalone_script_digest_import_contract(tmp_path, entry):
    import subprocess
    import sys
    source = parity.ROOT / entry['path']
    input_path = tmp_path / 'input.bin'
    input_path.write_bytes(b'abc')
    # Keep third-party site-packages, but remove the editable checkout/PYTHONPATH.
    # run_path must rely on the script's own standalone import compatibility.
    program = '''import sys, runpy
from pathlib import Path
repo, script, name, kind, source = sys.argv[1:]
sys.path[:] = [p for p in sys.path if Path(p).resolve() != Path(repo).resolve()]
sys.path.insert(0, str(Path(script).parent))
namespace = runpy.run_path(script)
value = Path(source) if kind == 'file' else b'abc'
print(namespace[name](value))
'''
    completed = subprocess.run([sys.executable, '-I', '-c', program, str(parity.ROOT), str(source), entry['name'], entry['kind'], str(input_path)], cwd=tmp_path, text=True, capture_output=True, timeout=30)
    # Packaging now supports both formerly failing Campaign 50/52 entry points.
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
