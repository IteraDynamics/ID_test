import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import run_ml_data_acquisition_pilot as pilot


def test_rejects_history_after_event_and_duplicate_dates():
    data = b'timestamp,close\n2024-08-15,2\n2024-08-15,2\n2025-01-02,999\n'
    out = pilot.price_check(data, 'timestamp', ('close',), '2023-03-10')
    assert out['rows_through_2024'] == 2
    assert out['required_date_missing'] and out['duplicate_dates'] == 1
    assert out['coverage_status'] == 'REJECTED'


def test_price_schema_nan_and_holdout_canary():
    data = b'Date,Close\n2024-01-02,nan\n2025-01-02,999999999\n'
    out = pilot.price_check(data, 'Date', ('Close', 'Dividends'))
    assert out['invalid_numeric_rows'] == 1 and out['missing_columns'] == ['Dividends']
    assert out['last'] == '2024-01-02'
    assert out['identity_status'] == 'UNVERIFIED'


def test_rejects_empty_and_bad_dates():
    out = pilot.price_check(b'Date,Close\nbad,1\n2026-01-01,2\n', 'Date', ('Close',))
    assert out['invalid_dates'] == 1 and out['coverage_status'] == 'REJECTED'


def test_facts_late_restatement_and_missing_acceptance():
    rows = [dict(filed='2024-03-01', end='2023-12-31', val=10, accn='a', form='10-K'),
            dict(filed='2025-03-01', end='2023-12-31', val=1000000, accn='b', form='10-K'),
            dict(filed='2024-04-01', end='2024-03-31', val=12, accn='c', form='10-Q')]
    facts = dict(cik=1318605, facts={'us-gaap': {'Assets': {'units': {'USD': rows}}}})
    filings = [dict(accessionNumber='a', filingDate='2024-03-01', form='10-K', acceptanceDateTime='2024-03-01T20:00:00Z')]
    out = pilot.fact_check(facts, filings, '0001318605')['Assets']
    assert out['fact_versions'] == 2 and out['acceptance_timestamp_matches'] == 1
    assert out['filed_years'] == ['2024']
    with pytest.raises(ValueError, match='CIK_MISMATCH'):
        pilot.fact_check(facts, filings, '0000773910')


def test_malformed_sec_filing_arrays_rejected():
    with pytest.raises(ValueError, match='ARRAY_LENGTH'):
        pilot.filing_rows({'accessionNumber': ['a']})


def fixture_bundle(root):
    raw = root / 'raw'
    raw.mkdir(parents=True)
    data = b'Date,Open,High,Low,Close,Volume,Adj Close,Dividends,Stock Splits\n2019-01-02,1,1,1,1,100,1,0,0\n'
    (raw / 'TSLA_history.csv').write_bytes(data)
    manifest = dict(version=1, cutoff=pilot.CUTOFF, start=pilot.START, errors=[],
                    files=[dict(name='TSLA_history.csv', bytes=len(data), sha256=pilot.digest(data), source='synthetic')])
    pilot.write_json(root / 'source_manifest.json', manifest)
    return manifest


def test_replay_exact_report_no_network_and_no_overwrite(tmp_path):
    src = tmp_path / 'source'
    manifest = fixture_bundle(src)
    expected = pilot.analyze(src, manifest)
    out = tmp_path / 'replay'
    cmd = [sys.executable, '-m', 'scripts.run_ml_data_acquisition_pilot', '--replay-from', str(src), '--output-dir', str(out)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    assert json.loads((out / 'pilot_report.json').read_text()) == expected
    assert (src / 'source_manifest.json').read_bytes() == (out / 'source_manifest.json').read_bytes()
    assert not expected['ready_for_model'] and expected['candidate_fits'] == 0
    before = (out / 'pilot_report.json').read_bytes()
    assert subprocess.run(cmd, capture_output=True).returncode != 0
    assert (out / 'pilot_report.json').read_bytes() == before


def test_corrupt_source_rejected_before_output_creation(tmp_path):
    src = tmp_path / 'source'
    fixture_bundle(src)
    (src / 'raw/TSLA_history.csv').write_bytes(b'corrupt')
    out = tmp_path / 'replay'
    cmd = [sys.executable, '-m', 'scripts.run_ml_data_acquisition_pilot', '--replay-from', str(src), '--output-dir', str(out)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0 and 'SOURCE_HASH_MISMATCH' in result.stderr
    assert not out.exists()


def test_source_path_escape_and_extra_file_rejected(tmp_path):
    manifest = fixture_bundle(tmp_path)
    (tmp_path / 'raw/extra.csv').write_text('bad')
    with pytest.raises(ValueError, match='INVENTORY_MISMATCH'):
        pilot.verify_sources(tmp_path)
    manifest['files'][0]['name'] = '../escape'
    pilot.write_json(tmp_path / 'source_manifest.json', manifest)
    with pytest.raises(ValueError, match='INVALID_SOURCE_NAME'):
        pilot.verify_sources(tmp_path)


def test_live_requires_real_contact_before_output(tmp_path, monkeypatch):
    monkeypatch.delenv('SEC_USER_AGENT', raising=False)
    out = tmp_path / 'out'
    result = subprocess.run([sys.executable, '-m', 'scripts.run_ml_data_acquisition_pilot', '--output-dir', str(out)], capture_output=True, text=True)
    assert result.returncode != 0 and 'real contact email' in result.stderr
    assert not out.exists()


def test_acquisition_saves_actions_archives_and_source_failures(tmp_path, monkeypatch):
    import types
    import pandas as pd
    monkeypatch.setattr(pilot.time, 'sleep', lambda _: None)
    requests = []

    class Ticker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, **kwargs):
            requests.append(kwargs)
            if self.symbol in ('FB', 'APC'):
                raise ValueError('unavailable historical security')
            return pd.DataFrame({'Open': [1], 'High': [1], 'Low': [1], 'Close': [1],
                                 'Volume': [100], 'Adj Close': [1], 'Dividends': [0],
                                 'Stock Splits': [0]}, index=pd.to_datetime(['2019-01-02']))

        def get_history_metadata(self):
            return {'symbol': self.symbol, 'instrumentType': 'EQUITY'}

    monkeypatch.setitem(sys.modules, 'yfinance', types.SimpleNamespace(Ticker=Ticker))
    monkeypatch.setattr(pilot.importlib.metadata, 'version', lambda _: 'fixture')
    table = dict(accessionNumber=['a'], filingDate=['2019-02-01'],
                 acceptanceDateTime=['2019-02-01T21:00:00Z'], form=['10-K'])

    def get(url, agent):
        if '-submissions-' in url:
            return json.dumps(table).encode()
        if '/submissions/' in url:
            return json.dumps({'filings': {'recent': table, 'files': [
                dict(name='CIK0001318605-submissions-001.json', filingFrom='2010-01-01', filingTo='2019-12-31')]}}).encode()
        return b'{"facts": {}}'

    monkeypatch.setattr(pilot, 'sec_get', get)
    raw = tmp_path / 'raw'
    raw.mkdir()
    manifest = pilot.acquire(raw, 'Fixture test@example.invalid')
    pilot.write_json(tmp_path / 'source_manifest.json', manifest)
    assert pilot.verify_sources(tmp_path) == manifest
    assert {e['item'] for e in manifest['errors']} == {'FB', 'APC'}
    assert all(r['actions'] and not r['auto_adjust'] and not r['repair'] for r in requests)
    assert all(r['end'] == '2025-01-01' for r in requests)
    assert (raw / 'TSLA_CIK0001318605-submissions-001.json').exists()
    assert 'Dividends' in (raw / 'TSLA_history.csv').read_text()
