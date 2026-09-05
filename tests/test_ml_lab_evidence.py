import hashlib
import json
import numpy as np
import pandas as pd
import pytest

from research.ml_lab import acquisition_v1, evidence


def test_cached_acquisition_never_downloads(tmp_path, monkeypatch):
    path = tmp_path / 'DGS2.csv'
    path.write_bytes(b'frozen source\n')
    def fail(*args, **kwargs):
        raise AssertionError('cached data must not be refreshed')
    monkeypatch.setattr(acquisition_v1.urllib.request, 'urlopen', fail)
    assert acquisition_v1.download_once('DGS2', tmp_path) == path
    assert path.read_bytes() == b'frozen source\n'


def test_failed_acquisition_cannot_publish_source(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError('synthetic network failure')
    monkeypatch.setattr(acquisition_v1.urllib.request, 'urlopen', fail)
    with pytest.raises(RuntimeError, match='FRED_ACQUISITION_FAILURE'):
        acquisition_v1.download_once('DGS2', tmp_path)
    assert not (tmp_path / 'DGS2.csv').exists()


def test_hash_and_scalar_serialization_preserve_values(tmp_path):
    path = tmp_path / 'source'
    payload = b'\x00\r\n' * 400_000
    path.write_bytes(payload)
    assert evidence.sha256_file(path) == hashlib.sha256(payload).hexdigest()
    values = [np.int64(7), np.float64(.125), np.bool_(False), pd.Timestamp('2024-01-01', tz='UTC')]
    assert json.loads(json.dumps(values, default=evidence.json_scalar)) == [7, .125, False, '2024-01-01 00:00:00+00:00']
    with pytest.raises(TypeError):
        json.dumps(object(), default=evidence.json_scalar)
