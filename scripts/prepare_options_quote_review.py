"""Offline quote inspection package. No model fitting, trade P&L, or 2025 files.

Five deliberately selected calm/stress windows diagnose data quality; they are
NOT a representative performance sample or a new out-of-sample test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

WINDOWS = {
    2017: ('2017-11-01', '2017-11-15'),
    2018: ('2018-02-01', '2018-02-15'),
    2020: ('2020-03-02', '2020-03-16'),
    2022: ('2022-06-01', '2022-06-15'),
    2024: ('2024-08-01', '2024-08-15'),
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def package(input_root, output_dir):
    source = input_root / 'artifacts/free_options_history_probe'
    # Refuse reuse: stale files must never enter a review package.
    output_dir.mkdir(parents=True, exist_ok=False)
    report = {
        'purpose': 'QUOTE_DATA_AUDIT_ONLY_NOT_PERFORMANCE',
        'windows': WINDOWS,
        'limitations': [
            'Purposively selected windows; no return inference permitted.',
            'A date field alone does not establish quote availability or fill time.',
            'Daily bid/ask snapshots do not establish simultaneous executable fills.',
            'Underlying adjustment, contract deliverables, dividends and assignment remain unverified.',
        ],
        'sources': [],
    }
    for year, (start, end) in WINDOWS.items():
        path = source / f'spy_options_{year}.parquet'
        if not path.exists():
            report['sources'].append({'file': path.name, 'status': 'MISSING'})
            continue
        entry = {'file': path.name, 'bytes': path.stat().st_size,
                 'sha256': digest(path)}
        parquet = pq.ParquetFile(path)
        entry['schema'] = str(parquet.schema_arrow)
        entry['file_rows'] = parquet.metadata.num_rows
        frame = parquet.read().to_pandas()
        required = {'date', 'expiration', 'strike', 'type', 'bid', 'ask'}
        missing = sorted(required - set(frame.columns))
        if missing:
            entry.update(status='MISSING_COLUMNS', missing_columns=missing)
            report['sources'].append(entry)
            continue
        dates = pd.to_datetime(frame['date'], errors='coerce', utc=True)
        entry['unparseable_date_rows'] = int(dates.isna().sum())
        # Any later rows in a mislabeled yearly file are excluded from analysis.
        mask = dates.ge(pd.Timestamp(start, tz='UTC')) & dates.lt(
            pd.Timestamp(end, tz='UTC') + pd.Timedelta(days=1))
        sample = frame.loc[mask].copy()
        sample_dates = dates.loc[mask]
        expiration = pd.to_datetime(sample['expiration'], errors='coerce', utc=True)
        dte = (expiration.dt.normalize() - sample_dates.dt.normalize()).dt.days
        # Retain bad/unknown expirations for review, and all 0--90 day chains.
        selected = dte.between(0, 90) | dte.isna() | dte.lt(0)
        sample = sample.loc[selected].copy()
        sample_dates = sample_dates.loc[selected]
        expiration = expiration.loc[selected]
        bid = pd.to_numeric(sample['bid'], errors='coerce')
        ask = pd.to_numeric(sample['ask'], errors='coerce')
        strike = pd.to_numeric(sample['strike'], errors='coerce')
        kind = sample['type'].astype(str).str.lower().replace({'c': 'call', 'p': 'put'})
        key = pd.DataFrame({'date': sample_dates.dt.normalize(),
                            'expiration': expiration.dt.normalize(),
                            'strike': strike, 'type': kind})
        finite = np.isfinite(bid) & np.isfinite(ask)
        entry.update(
            status='EXPORTED' if len(sample) else 'EMPTY_WINDOW',
            exported_rows=len(sample),
            observation_days=int(sample_dates.dt.normalize().nunique()),
            all_observation_times_midnight=bool((sample_dates == sample_dates.dt.normalize()).all()) if len(sample) else None,
            duplicate_contract_day_rows=int(key.duplicated(keep=False).sum()),
            invalid_type_rows=int((~kind.isin(['call', 'put'])).sum()),
            invalid_strike_rows=int((~np.isfinite(strike) | strike.le(0)).sum()),
            unparseable_expiration_rows=int(expiration.isna().sum()),
            nonfinite_quote_rows=int((~finite).sum()),
            negative_quote_rows=int((bid.lt(0) | ask.lt(0)).sum()),
            zero_bid_rows=int(bid.eq(0).sum()),
            crossed_quote_rows=int((finite & ask.lt(bid)).sum()),
        )
        # Export original columns/values. Do not silently filter bad quotes or deduplicate.
        sample.to_csv(output_dir / f'quotes_{year}.csv', index=False)
        report['sources'].append(entry)
    report['status'] = 'REVIEW_REQUIRED'
    report['export_sha256'] = {p.name: digest(p) for p in sorted(output_dir.glob('*.csv'))}
    (output_dir / 'quote_review_report.json').write_text(
        json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    zip_path = output_dir.with_name(output_dir.name + '.zip')
    with zipfile.ZipFile(zip_path, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output_dir.iterdir()):
            bundle.write(path, path.name)
    print(f'Upload this file: {zip_path.resolve()}')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    package(args.input_root.resolve(), args.output_dir.resolve())
