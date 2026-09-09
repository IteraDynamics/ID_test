"""Bounded source feasibility probe. No fitting, portfolio returns, or promotion."""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path
import re
import shutil
import time
import urllib.error
import urllib.request

START = '2005-01-01'
CUTOFF = '2024-12-31'
# CIKs identify filing entities, not share classes or Yahoo securities.
ENTITIES = (
    ('TSLA', '0001318605', 'tesla'),
    ('META', '0001326801', 'meta'),
    ('APC', '0000773910', 'anadarko'),
)
SYMBOLS = ('TSLA', 'META', 'FB', 'APC')
TAGS = ('Assets', 'Liabilities', 'NetIncomeLoss',
        'NetCashProvidedByUsedInOperatingActivities',
        'Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet', 'OperatingIncomeLoss')


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8', newline='\n')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def failure_code(exc):
    message = str(exc)
    return message if re.fullmatch(r'[A-Z][A-Z0-9_]+', message) else None


def finite(value):
    try:
        return math.isfinite(float(value))
    except (ValueError, TypeError):
        return False


def price_check(payload, date_column, columns, required_date=None):
    reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
    fields = reader.fieldnames or []
    if date_column not in fields:
        raise ValueError('PRICE_DATE_COLUMN_MISSING')
    eligible = []
    invalid_dates = 0
    for row in reader:
        day = row[date_column][:10]
        try:
            date.fromisoformat(day)
        except ValueError:
            invalid_dates += 1
            continue
        if START <= day <= CUTOFF:
            eligible.append((day, row))
    dates = [d for d, _ in eligible]
    event_missing = required_date is not None and required_date not in dates
    missing = sorted(set(columns) - set(fields))
    bad = sum(any(not finite(row.get(c)) for c in columns) for _, row in eligible)
    return dict(rows_through_2024=len(dates), first=min(dates, default=None),
                last=max(dates, default=None), duplicate_dates=len(dates)-len(set(dates)),
                invalid_dates=invalid_dates, missing_columns=missing, invalid_numeric_rows=bad,
                years=dict(sorted(Counter(d[:4] for d in dates).items())),
                required_date=required_date, required_date_missing=event_missing,
                coverage_status='REJECTED' if not dates or missing or bad or invalid_dates or event_missing or len(dates)!=len(set(dates)) else 'STRUCTURE_ONLY',
                identity_status='UNVERIFIED', columns=fields)


def filing_rows(table):
    keys = ('accessionNumber', 'filingDate', 'acceptanceDateTime', 'form')
    n = len(table.get('accessionNumber', []))
    if any(len(table.get(k, [])) != n for k in keys):
        raise ValueError('SEC_FILING_ARRAY_LENGTH_MISMATCH')
    return [dict(zip(keys, values)) for values in zip(*(table[k] for k in keys))]


def fact_check(facts, filings, cik):
    if str(facts.get('cik', '')).zfill(10) != cik:
        raise ValueError('SEC_FACTS_CIK_MISMATCH')
    by_acc = {}
    for row in filings:
        acc = row['accessionNumber']
        if acc in by_acc and by_acc[acc] != row:
            raise ValueError('SEC_CONFLICTING_ACCESSION')
        by_acc[acc] = row
    result = {}
    for tag in TAGS:
        kept = []
        matched = 0
        for row in facts.get('facts', {}).get('us-gaap', {}).get(tag, {}).get('units', {}).get('USD', []):
            # Later restatements of older periods do not become historical observations.
            try:
                filed, end = date.fromisoformat(row['filed']), date.fromisoformat(row['end'])
            except (KeyError, ValueError, TypeError):
                continue
            if not (START <= filed.isoformat() <= CUTOFF and end.isoformat() <= CUTOFF):
                continue
            if not finite(row.get('val')) or row.get('form') not in ('10-K', '10-Q', '10-K/A', '10-Q/A'):
                continue
            kept.append(row)
            f = by_acc.get(row.get('accn'))
            if f and f['filingDate'] == row['filed'] and f['form'] == row['form']:
                try:
                    accepted = datetime.fromisoformat(f['acceptanceDateTime'].replace('Z', '+00:00'))
                    if accepted.tzinfo is not None and accepted.astimezone(timezone.utc).date().isoformat() <= CUTOFF:
                        matched += 1
                except (ValueError, TypeError):
                    pass
        result[tag] = dict(fact_versions=len(kept), acceptance_timestamp_matches=matched,
                           first_filed=min((r['filed'] for r in kept), default=None),
                           last_filed=max((r['filed'] for r in kept), default=None),
                           filed_years=sorted({r['filed'][:4] for r in kept}))
    return result


def sec_get(url, user_agent):
    for attempt in range(3):
        time.sleep(0.35)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': user_agent, 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = response.read()
            json.loads(payload)
            return payload
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError('SEC_RETRIES_EXHAUSTED')


def acquire(raw, user_agent):
    import yfinance as yf
    entries, errors = [], []

    def save(name, payload, source):
        (raw / name).write_bytes(payload)
        entries.append(dict(name=name, sha256=digest(payload), bytes=len(payload), source=source))

    for symbol in SYMBOLS:
        print('Yahoo history:', symbol, flush=True)
        ticker = yf.Ticker(symbol)
        try:
            # Provider-returned OHLC may already be split-adjusted. Never call it raw exchange prices.
            frame = ticker.history(start=START, end='2025-01-01', interval='1d',
                                   auto_adjust=False, back_adjust=False, actions=True,
                                   repair=False, keepna=True, rounding=False, timeout=30,
                                   raise_errors=True)
            if frame.empty:
                raise ValueError('EMPTY_HISTORY')
            frame.index.name = 'Date'
            save(symbol + '_history.csv', frame.to_csv(lineterminator='\n').encode(),
                 {'provider': 'yfinance', 'symbol': symbol, 'start': START, 'end_exclusive': '2025-01-01',
                  'auto_adjust': False, 'back_adjust': False, 'actions': True, 'repair': False})
            metadata = ticker.get_history_metadata()
            # Current identity hints are not proof of historical identity.
            hints = {k: metadata.get(k) for k in ('symbol', 'shortName', 'longName', 'instrumentType', 'exchangeName', 'currency', 'exchangeTimezoneName')}
            save(symbol + '_identity_hints.json', json.dumps(hints, sort_keys=True).encode(), 'yfinance.history_metadata')
        except Exception as exc:
            errors.append(dict(source='yfinance', item=symbol, error_type=type(exc).__name__,
                               http_status=getattr(exc, 'code', None), reason_code=failure_code(exc)))
        time.sleep(1)
    for symbol, cik, _ in ENTITIES:
        print('SEC filing entity:', symbol, cik, flush=True)
        for kind, url in (
            ('submissions', f'https://data.sec.gov/submissions/CIK{cik}.json'),
            ('companyfacts', f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'),
        ):
            try:
                payload = sec_get(url, user_agent)
                save(symbol + '_' + kind + '.json', payload, url)
                if kind == 'submissions':
                    archives = [f for f in json.loads(payload)['filings'].get('files', [])
                                if f['filingTo'] >= START and f['filingFrom'] <= CUTOFF]
                    if len(archives) > 20:
                        raise ValueError('SEC_ARCHIVE_BUDGET_EXCEEDED')
                    for f in archives:
                        name = f['name']
                        if not re.fullmatch(r'CIK\d{10}-submissions-\d+\.json', name):
                            raise ValueError('INVALID_SEC_ARCHIVE_NAME')
                        archive_url = 'https://data.sec.gov/submissions/' + name
                        save(symbol + '_' + name, sec_get(archive_url, user_agent), archive_url)
            except Exception as exc:
                errors.append(dict(source='sec', item=symbol + '_' + kind, error_type=type(exc).__name__,
                               http_status=getattr(exc, 'code', None), reason_code=failure_code(exc)))
    return dict(version=1, cutoff=CUTOFF, start=START, acquired_at_utc=datetime.now(timezone.utc).isoformat(),
                yfinance=importlib.metadata.version('yfinance'),
                runner_sha256=digest(Path(__file__).read_bytes()), files=entries, errors=errors)


def verify_sources(root):
    manifest = json.loads((root / 'source_manifest.json').read_text(encoding='utf-8'))
    if manifest['version'] != 1 or manifest['cutoff'] != CUTOFF or manifest['start'] != START:
        raise ValueError('SOURCE_CONTRACT_MISMATCH')
    names = set()
    for entry in manifest['files']:
        name = entry['name']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name in names or name in ('.', '..'):
            raise ValueError('INVALID_SOURCE_NAME')
        names.add(name)
        p = root / 'raw' / name
        if p.is_symlink():
            raise ValueError('SOURCE_SYMLINK')
        payload = p.read_bytes()
        if digest(payload) != entry['sha256'] or len(payload) != entry['bytes']:
            raise ValueError('SOURCE_HASH_MISMATCH:' + name)
    actual = {p.name for p in (root / 'raw').iterdir()}
    if actual != names:
        raise ValueError('SOURCE_INVENTORY_MISMATCH')
    return manifest


def analyze(root, manifest):
    raw = root / 'raw'
    prices, entities, errors = {}, {}, []
    for symbol in SYMBOLS:
        path = raw / (symbol + '_history.csv')
        if not path.exists():
            prices[symbol] = {'coverage_status': 'MISSING', 'identity_status': 'UNVERIFIED'}
            continue
        try:
            prices[symbol] = price_check(path.read_bytes(), 'Date',
                                        ('Open', 'High', 'Low', 'Close', 'Volume', 'Adj Close', 'Dividends', 'Stock Splits'),
                                        {'TSLA': '2019-01-02', 'META': '2022-06-08',
                                         'FB': '2022-06-08', 'APC': '2019-08-08'}[symbol])
        except Exception as exc:
            errors.append(dict(item=symbol, error_type=type(exc).__name__,
                               http_status=getattr(exc, 'code', None), reason_code=failure_code(exc)))
            prices[symbol] = {'coverage_status': 'REJECTED', 'identity_status': 'UNVERIFIED'}
    for symbol, cik, token in ENTITIES:
        try:
            sub = json.loads((raw / (symbol + '_submissions.json')).read_text())
            facts = json.loads((raw / (symbol + '_companyfacts.json')).read_text())
            if str(sub.get('cik', '')).zfill(10) != cik or token not in sub.get('name', '').lower():
                raise ValueError('SEC_ENTITY_IDENTITY_MISMATCH')
            filings = filing_rows(sub['filings']['recent'])
            for path in sorted(raw.glob(symbol + '_CIK*-submissions-*.json')):
                filings.extend(filing_rows(json.loads(path.read_text())))
            entities[symbol] = dict(cik=cik, name=sub['name'], status='FILING_ENTITY_MATCH_ONLY',
                                    concepts=fact_check(facts, filings, cik))
        except Exception as exc:
            errors.append(dict(item=symbol + '_sec', error_type=type(exc).__name__,
                               http_status=getattr(exc, 'code', None), reason_code=failure_code(exc)))
            entities[symbol] = dict(cik=cik, status='MISSING_OR_INVALID')
    return dict(status='ACQUISITION_INCOMPLETE' if errors or manifest['errors'] or any(v['coverage_status'] != 'STRUCTURE_ONLY' for v in prices.values()) else 'SOURCE_REVIEW_REQUIRED',
                ready_for_model=False, candidate_fits=0, cutoff=CUTOFF, prices=prices, sec_entities=entities,
                acquisition_errors=manifest['errors'], validation_errors=errors,
                source_manifest_sha256=digest((root / 'source_manifest.json').read_bytes()),
                unresolved=['Historical security-to-issuer mapping and share classes',
                            'Delisted security terminal outcomes and full historical universe',
                            'Corporate-action reconciliation and unadjusted execution prices',
                            'Fact contexts, fiscal periods, revisions, dissemination and session availability',
                            '2005 training coverage and independent confirmation route'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--replay-from', type=Path, help='Verify and reanalyze a saved pilot; no network')
    p.add_argument('--sec-user-agent', help='Real organization/name and contact email; alternatively SEC_USER_AGENT environment variable')
    a = p.parse_args()
    import os
    agent = a.sec_user_agent or os.environ.get('SEC_USER_AGENT', '')
    if not a.replay_from and not re.search(r'\S+@\S+\.\S+', agent):
        p.error('Live SEC requests require SEC_USER_AGENT with your real contact email.')
    # Exclusive new directory: no overwrite or mutation of prior datasets.
    if a.replay_from:
        manifest = verify_sources(a.replay_from)
    a.output_dir.mkdir(parents=True, exist_ok=False)
    raw = a.output_dir / 'raw'
    raw.mkdir()
    if a.replay_from:
        for entry in manifest['files']:
            shutil.copyfile(a.replay_from / 'raw' / entry['name'], raw / entry['name'])
        shutil.copyfile(a.replay_from / 'source_manifest.json', a.output_dir / 'source_manifest.json')
    else:
        manifest = acquire(raw, agent)
        write_json(a.output_dir / 'source_manifest.json', manifest)
    manifest = verify_sources(a.output_dir)
    report = analyze(a.output_dir, manifest)
    write_json(a.output_dir / 'pilot_report.json', report)
    print(json.dumps({'status': report['status'], 'ready_for_model': False,
                      'report': str(a.output_dir / 'pilot_report.json')}, indent=2))
    # Completed diagnostic reports can contain source failures; infrastructure exceptions still fail.


if __name__ == '__main__':
    main()
