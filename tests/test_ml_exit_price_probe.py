import json
import subprocess
import sys
import urllib.error

import pytest

from scripts import run_ml_exit_price_probe as probe


def payload(dates):
    return ('Date,Open,High,Low,Close,Volume,Adj Close,Dividends,Stock Splits\n' +
            ''.join(f'{d},1,1,1,1,100,1,0,0\n' for d in dates)).encode()


def test_late_reused_ticker_cannot_pass_required_history():
    result = probe.inspect(payload(['2024-08-15']), 'yahoo', 'SBNY')
    assert result['coverage_status'] == 'REJECTED'
    assert '2023-03-10' in result['missing_check_dates']
    assert result['identity_status'] == 'UNVERIFIED'


def test_holdout_and_duplicate_canaries():
    dates = probe.CHECK_DATES['APC']
    assert probe.inspect(payload(dates), 'yahoo', 'APC')['coverage_status'] == 'STRUCTURE_ONLY'
    for extra in ('2025-01-02', dates[0]):
        assert probe.inspect(payload((*dates, extra)), 'yahoo', 'APC')['coverage_status'] == 'REJECTED'


def test_gap_is_reported_without_filling_or_approving_terminal_value():
    result = probe.inspect(payload(probe.CHECK_DATES['SBNY']), 'stooq', 'SBNY')
    assert {'before': '2023-03-10', 'after': '2023-03-28', 'days': 18} in result['gaps_over_7_calendar_days']
    assert result['terminal_outcome_status'] == result['adjustment_basis'] == 'UNVERIFIED'


def test_control_failure_stops_provider(tmp_path):
    calls = []
    def get(provider, symbol):
        calls.append(symbol)
        raise urllib.error.HTTPError('https://example.test', 404, 'missing', {}, None)
    manifest = probe.acquire(tmp_path, ('stooq',), get, lambda _: None)
    assert calls == ['SPY']
    assert sum(a['status'] == 'SKIPPED_PROVIDER_STOP' for a in manifest['attempts']) == 8
    assert probe.verify(tmp_path) == manifest


def test_rate_limit_stops_remaining_requests(tmp_path):
    calls = []
    def get(provider, symbol):
        calls.append(symbol)
        if symbol != 'SPY':
            raise urllib.error.HTTPError('https://example.test', 429, 'rate', {}, None)
        return payload(probe.CHECK_DATES[symbol])
    manifest = probe.acquire(tmp_path, ('stooq',), get, lambda _: None)
    assert calls == ['SPY', 'APC']
    assert manifest['attempts'][2]['reason'] == 'PROVIDER_ACCESS_OR_RATE_LIMIT'


def test_bad_control_body_is_preserved_and_stops(tmp_path):
    manifest = probe.acquire(tmp_path, ('stooq',), lambda *_: b'<html>not csv</html>', lambda _: None)
    assert (tmp_path / 'raw' / 'stooq_SPY.csv').read_bytes().startswith(b'<html>')
    assert manifest['attempts'][1]['status'] == 'SKIPPED_PROVIDER_STOP'
    report = probe.analyze(tmp_path, probe.verify(tmp_path))
    assert report['results'][0]['coverage_status'] == 'REJECTED'


def test_replay_and_hash_tamper(tmp_path):
    manifest = probe.acquire(tmp_path, ('stooq',), lambda _, s: payload(probe.CHECK_DATES[s]), lambda _: None)
    report = probe.encoded(probe.analyze(tmp_path, manifest))
    (tmp_path / 'exit_price_report.json').write_bytes(report)
    run = subprocess.run([sys.executable, '-m', 'scripts.run_ml_exit_price_probe', '--replay-from', str(tmp_path)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert (tmp_path / 'exit_price_report.json').read_bytes() == report
    (tmp_path / 'raw' / 'stooq_APC.csv').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='SOURCE_HASH_MISMATCH'):
        probe.verify(tmp_path)


@pytest.mark.parametrize('change', ['path', 'extra', 'attempt'])
def test_manifest_inventory_canaries(tmp_path, change):
    manifest = probe.acquire(tmp_path, ('stooq',), lambda _, s: payload(probe.CHECK_DATES[s]), lambda _: None)
    if change == 'path':
        manifest['attempts'][0]['name'] = '../unsafe.csv'
    elif change == 'extra':
        (tmp_path / 'raw' / 'extra.csv').write_bytes(b'x')
    else:
        manifest['attempts'].pop()
    (tmp_path / 'source_manifest.json').write_bytes(probe.encoded(manifest))
    with pytest.raises(ValueError):
        probe.verify(tmp_path)


def test_output_never_overwritten(tmp_path):
    run = subprocess.run([sys.executable, '-m', 'scripts.run_ml_exit_price_probe', '--output-dir', str(tmp_path)], capture_output=True, text=True)
    assert run.returncode != 0
    assert 'OUTPUT_ALREADY_EXISTS' in run.stderr
