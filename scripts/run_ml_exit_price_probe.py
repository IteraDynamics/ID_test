"""Small free-source history probe; no fitting or automatic security joins."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import zipfile

from scripts.run_ml_data_acquisition_pilot import price_check

START = '2018-01-01'
END = '2025-01-01'  # exclusive
# These are diagnostic observations, not assumed executable liquidation dates.
CHECK_DATES = {
    'SPY': ('2019-01-02', '2024-12-31'),
    'APC': ('2019-01-02', '2019-08-08'),
    'NFX': ('2019-01-02', '2019-02-13'),
    'FRC': ('2019-01-02', '2023-04-28'),
    'FRCB': ('2023-04-28', '2023-05-03'),
    'SBNY': ('2021-12-20', '2023-03-10', '2023-03-28'),
    'HRS': ('2019-01-02', '2019-06-28'),
    'LHX': ('2019-06-28', '2019-07-01'),
    'LLL': ('2019-01-02', '2019-06-28'),
}
LIMIT = 10_000_000


def encoded(obj):
    return (json.dumps(obj, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inspect(payload, provider, symbol):
    columns = ('Open', 'High', 'Low', 'Close', 'Volume')
    if provider == 'yahoo':
        columns += ('Adj Close', 'Dividends', 'Stock Splits')
    result = price_check(payload, 'Date', columns)
    rows = list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
    dates = [r['Date'][:10] for r in rows]
    outside = sum(not START <= d < END for d in dates)
    result['rows_outside_requested_window'] = outside
    result['missing_check_dates'] = [d for d in CHECK_DATES[symbol] if d not in dates]
    result['adjustment_basis'] = 'UNVERIFIED'
    result['terminal_outcome_status'] = 'UNVERIFIED'
    if outside or result['missing_check_dates']:
        result['coverage_status'] = 'REJECTED'
    # Retain actual gaps for review: a long halt is not filled or priced as zero.
    valid = sorted(set(d for d in dates if START <= d < END))
    result['gaps_over_7_calendar_days'] = [
        dict(before=a, after=b, days=(datetime.fromisoformat(b)-datetime.fromisoformat(a)).days)
        for a, b in zip(valid, valid[1:])
        if (datetime.fromisoformat(b)-datetime.fromisoformat(a)).days > 7
    ]
    return result


def fetch(provider, symbol):
    if provider == 'stooq':
        url = f'https://stooq.com/q/d/l/?s={symbol.lower()}.us&i=d&d1=20180101&d2=20241231'
        with urllib.request.urlopen(url, timeout=25) as response:
            payload = response.read(LIMIT + 1)
        return payload
    import yfinance as yf
    frame = yf.Ticker(symbol).history(
        start=START, end=END, interval='1d', auto_adjust=False,
        back_adjust=False, actions=True, repair=False, keepna=True,
        rounding=False, timeout=25, raise_errors=True)
    if frame.empty:
        raise ValueError('EMPTY_HISTORY')
    return frame.to_csv(index=True, index_label='Date', lineterminator='\n').encode()


def acquire(root, providers, fetcher=fetch, pause=time.sleep):
    raw = root / 'raw'
    raw.mkdir()
    attempts = []
    for provider in providers:
        stopped = None
        for symbol in CHECK_DATES:
            item = dict(provider=provider, symbol=symbol)
            if stopped:
                item.update(status='SKIPPED_PROVIDER_STOP', reason=stopped)
                attempts.append(item)
                continue
            print(f'{provider}: {symbol}', flush=True)
            try:
                data = fetcher(provider, symbol)
                if len(data) > LIMIT:
                    raise ValueError('RESPONSE_SIZE_LIMIT')
                name = f'{provider}_{symbol}.csv'
                (raw / name).write_bytes(data)
                item.update(status='RESPONSE_SAVED', name=name, bytes=len(data), sha256=sha(data))
                # Do not continue a provider if a known-good history cannot be read.
                if symbol == 'SPY' and inspect(data, provider, symbol)['coverage_status'] != 'STRUCTURE_ONLY':
                    stopped = 'CONTROL_HISTORY_REJECTED'
            except Exception as exc:
                item.update(status='ERROR', error_type=type(exc).__name__, http_status=getattr(exc, 'code', None))
                if symbol == 'SPY':
                    stopped = 'CONTROL_REQUEST_FAILED'
                elif getattr(exc, 'code', None) in (401, 403, 429) or 'RateLimit' in type(exc).__name__:
                    stopped = 'PROVIDER_ACCESS_OR_RATE_LIMIT'
            attempts.append(item)
            pause(1)
    manifest = dict(version=1, start=START, end_exclusive=END,
                    providers=list(providers), symbols=list(CHECK_DATES),
                    acquired_at_utc=datetime.now(timezone.utc).isoformat(),
                    yfinance=importlib.metadata.version('yfinance') if 'yahoo' in providers else None,
                    attempts=attempts)
    (root / 'source_manifest.json').write_bytes(encoded(manifest))
    return manifest


def verify(root):
    manifest = json.loads((root / 'source_manifest.json').read_bytes())
    if (manifest['version'], manifest['start'], manifest['end_exclusive'], manifest['symbols']) != (1, START, END, list(CHECK_DATES)):
        raise ValueError('PROBE_CONTRACT_MISMATCH')
    providers = manifest['providers']
    if not providers or len(set(providers)) != len(providers) or not set(providers) <= {'yahoo', 'stooq'}:
        raise ValueError('PROVIDERS_INVALID')
    expected = [(p, s) for p in providers for s in CHECK_DATES]
    if [(a['provider'], a['symbol']) for a in manifest['attempts']] != expected:
        raise ValueError('ATTEMPT_INVENTORY_MISMATCH')
    files = set()
    for item in manifest['attempts']:
        if 'name' not in item:
            if item['status'] not in ('ERROR', 'SKIPPED_PROVIDER_STOP'):
                raise ValueError('ATTEMPT_STATUS_INVALID')
            continue
        name = f"{item['provider']}_{item['symbol']}.csv"
        if item['name'] != name:
            raise ValueError('SOURCE_NAME_INVALID')
        path = root / 'raw' / name
        if path.is_symlink():
            raise ValueError('SOURCE_SYMLINK')
        data = path.read_bytes()
        if len(data) != item['bytes'] or sha(data) != item['sha256']:
            raise ValueError('SOURCE_HASH_MISMATCH')
        files.add(name)
    if {p.name for p in (root / 'raw').iterdir()} != files:
        raise ValueError('SOURCE_INVENTORY_MISMATCH')
    return manifest


def analyze(root, manifest):
    results = []
    for item in manifest['attempts']:
        result = dict(provider=item['provider'], symbol=item['symbol'], request_status=item['status'])
        if 'name' in item:
            try:
                result.update(inspect((root / 'raw' / item['name']).read_bytes(), item['provider'], item['symbol']))
            except (ValueError, KeyError, UnicodeError, csv.Error) as exc:
                result.update(coverage_status='REJECTED', error_type=type(exc).__name__)
        else:
            result['coverage_status'] = 'NOT_RETRIEVED'
        results.append(result)
    return dict(status='SOURCE_PROBE_REVIEW_REQUIRED', ready_for_modeling=False,
                model_fits=0, source_manifest_sha256=sha((root / 'source_manifest.json').read_bytes()),
                implementation_sha256={name: sha(Path(__file__).with_name(name).read_bytes().replace(b'\r\n', b'\n'))
                                       for name in ('run_ml_exit_price_probe.py', 'run_ml_data_acquisition_pilot.py')},
                results=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--replay-from', type=Path)
    parser.add_argument('--provider', choices=('both', 'yahoo', 'stooq'), default='both')
    args = parser.parse_args()
    if args.replay_from:
        if args.output_dir:
            parser.error('Replay verifies in place; omit --output-dir')
        root = args.replay_from
        report = encoded(analyze(root, verify(root)))
        if report != (root / 'exit_price_report.json').read_bytes():
            raise ValueError('REPLAY_MISMATCH')
        print('PASS: raw hashes verified; report reproduced without network.')
        return
    if not args.output_dir:
        parser.error('--output-dir is required')
    root = args.output_dir
    archive = root.with_name(root.name + '_review.zip')
    if root.exists() or archive.exists():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    root.mkdir(parents=True)
    providers = ('yahoo', 'stooq') if args.provider == 'both' else (args.provider,)
    acquire(root, providers)
    manifest = verify(root)
    report = encoded(analyze(root, manifest))
    if report != encoded(analyze(root, manifest)):
        raise ValueError('NONDETERMINISTIC_REPORT')
    (root / 'exit_price_report.json').write_bytes(report)
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(root).as_posix())
    print(f'Probe finished; missing histories are recorded in the report.\nShare: {archive}')


if __name__ == '__main__':
    main()
