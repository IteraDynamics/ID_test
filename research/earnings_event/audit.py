"""Read-only local feasibility audit; no downloads, returns, fits or orders."""
from __future__ import annotations
import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import zipfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def day(value):
    text = str(value).strip()
    if re.fullmatch(r'\d{10}(?:\.\d+)?', text):
        return datetime.fromtimestamp(float(text), timezone.utc).date()
    if re.fullmatch(r'\d{13}', text):
        return datetime.fromtimestamp(float(text)/1000, timezone.utc).date()
    if len(text) == 10:
        return date.fromisoformat(text)
    # Preserve the provider's displayed calendar date, never shift a midnight
    # daily label to the preceding New York date. Exchange mapping remains open.
    return datetime.fromisoformat(text.replace('Z', '+00:00')).date()


def read_rows(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        return fields, list(reader)


def events(path, cutoff):
    fields, rows = read_rows(path)
    if not {'ticker', 'date', 'reported_eps'}.issubset(fields):
        raise ValueError('Earnings CSV requires ticker, date, reported_eps')
    grouped, issues, counts = defaultdict(list), [], Counter()
    for i, r in enumerate(rows, 2):
        ticker = r.get('ticker', '').strip().upper()
        try:
            d = date.fromisoformat(r.get('date', '').strip())
            if not re.fullmatch(r'[A-Z0-9.^=-]+', ticker):
                raise ValueError('unsafe/empty ticker')
        except ValueError:
            counts['invalid_rows'] += 1
            issues.append(dict(row=i, ticker=ticker, date=r.get('date'), reason='invalid_key'))
            continue
        if d > cutoff:
            counts['after_cutoff_rows'] += 1
            continue
        grouped[ticker, d].append((i, r))
    clean = []
    for (ticker, d), group in sorted(grouped.items()):
        variants = {tuple((k, str(r.get(k, '')).strip()) for k in fields) for _, r in group}
        if len(group) > 1:
            counts['duplicate_groups'] += 1
            counts['duplicate_extra_rows'] += len(group)-1
        if len(variants) > 1:
            counts['conflicting_groups'] += 1
            for i, r in group:
                issues.append(dict(row=i, ticker=ticker, date=d.isoformat(), reason='conflicting_key'))
            continue
        if not finite(group[0][1]['reported_eps']):
            counts['missing_reported_eps_groups'] += 1
            issues.append(dict(row=group[0][0], ticker=ticker, date=d.isoformat(), reason='missing_reported_eps'))
            continue
        clean.append((ticker, d))
    counts.update(raw_rows=len(rows), dated_groups_through_cutoff=len(grouped),
                  structurally_clean_reported_events=len(clean),
                  clean_tickers=len({t for t, _ in clean}))
    return clean, dict(counts), issues


def price_inventory(path, cutoff):
    fields, rows = read_rows(path)
    columns = {f.strip().lower(): f for f in fields}
    dc = next((columns[k] for k in ('timestamp', 'date', 'datetime') if k in columns), None)
    result = dict(path=str(path.resolve()), sha256=digest(path), raw_rows=len(rows),
                  columns=fields, structural_ok=False)
    if not dc or not all(k in columns for k in ('open','high','low','close','volume')):
        return result | {'error':'unsupported_schema'}, []
    dates, bad, beyond = [], 0, 0
    for r in rows:
        try:
            d = day(r[dc])
            if d > cutoff:
                beyond += 1
                continue
            o,h,l,c,v = [float(r[columns[k]]) for k in ('open','high','low','close','volume')]
            if not all(math.isfinite(x) for x in (o,h,l,c,v)) or min(o,h,l,c)<=0 or v<0:
                raise ValueError('invalid prices')
            if l > min(o,c) or h < max(o,c) or l > h:
                raise ValueError('inconsistent OHLC')
            dates.append(d)
        except (ValueError, TypeError, KeyError, OverflowError, OSError):
            bad += 1
    duplicate = len(dates)-len(set(dates))
    ordered = dates == sorted(dates)
    weekends = sum(d.weekday()>4 for d in dates)
    ok = bool(dates) and not (bad or duplicate or weekends) and ordered
    result.update(valid_rows=len(dates), after_cutoff_rows=beyond, invalid_rows=bad,
                  duplicate_dates=duplicate, ascending=ordered, weekend_rows=weekends,
                  first_date=str(min(dates)) if dates else None,
                  last_date=str(max(dates)) if dates else None, structural_ok=ok)
    manifests = sorted(set(path.parent.glob(path.stem+'*manifest*.json')))
    result['manifests'] = [dict(path=str(p.resolve()),sha256=digest(p)) for p in manifests]
    result['adjustment_and_identity_verified'] = False
    return result, sorted(dates) if ok else []


def audit(data_root, earnings, cutoff):
    clean, counts, issues = events(earnings, cutoff)
    by_ticker = defaultdict(list)
    for t,d in clean:
        by_ticker[t].append(d)
    # Exact canonical basename only; ambiguous duplicates never auto-selected.
    index = defaultdict(list)
    for p in data_root.rglob('*'):
        if p.is_file() and p.name.lower().endswith('_1d.csv'):
            index[p.name.lower()].append(p)
    inventories, coverage = [], []
    for t in sorted(set(by_ticker) | {'SPY'}):
        candidates = sorted(index[t.lower()+'_1d.csv'])
        dates = []
        if len(candidates) == 1:
            try:
                inv, dates = price_inventory(candidates[0], cutoff)
            except (ValueError, UnicodeError, csv.Error, OSError) as exc:
                inv = dict(path=str(candidates[0]),structural_ok=False,error=str(exc))
            inventories.append(dict(ticker=t, **inv))
        row = dict(ticker=t, clean_events=len(by_ticker[t]), price_candidates=len(candidates),
                   price_paths=' | '.join(str(p) for p in candidates),
                   structurally_valid_prices=bool(dates), metadata_windows_1=0,
                   metadata_windows_3=0, metadata_windows_5=0)
        for d in by_ticker[t]:
            # Conservative proxy: first observed session strictly AFTER event date
            # is observation day; following open is earliest candidate entry.
            k = bisect_right(dates, d)
            for h in (1,3,5):
                # 60 prior observed rows and next open + h open-to-open sessions.
                if k>=60 and k+1+h<len(dates):
                    row[f'metadata_windows_{h}'] += 1
        coverage.append(row)
    report = dict(status='FEASIBILITY_ONLY_SOURCE_REVIEW_REQUIRED', ready_for_backtest=False,
                  cutoff=str(cutoff), earnings_sha256=digest(earnings), earnings_path=str(earnings.resolve()),
                  events=counts, structurally_valid_price_files=sum(bool(i.get('structural_ok')) for i in inventories),
                  verified_first_session_events=0,
                  blockers=['Announcement time/session and original publication evidence not verified',
                            'Historical security identity, universe selection and delistings unresolved',
                            'Price adjustment/corporate actions and exchange calendar gaps unresolved',
                            'Historical sector mapping and matched controls unresolved'],
                  interpretation='Metadata window counts are upper bounds, not tradable events or P&L. EPS presence is a data-quality filter, not a point-in-time trading feature.',
                  coverage_totals={f'metadata_windows_{h}':sum(r[f'metadata_windows_{h}'] for r in coverage) for h in (1,3,5)})
    return report, inventories, coverage, issues


def write_csv(path, rows, empty_fields):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else empty_fields)
        w.writeheader(); w.writerows(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--earnings-csv',type=Path)
    p.add_argument('--cutoff',type=date.fromisoformat,default=date(2024,12,31))
    p.add_argument('--output-dir',type=Path,default=Path('artifacts'))
    a=p.parse_args()
    if not a.data_root.is_dir():
        p.error('Data root does not exist')
    source=a.earnings_csv or a.data_root/'earnings_surprise_history.csv'
    if not source.is_file():
        p.error('Earnings CSV missing; supply --earnings-csv')
    report,inv,cov,issues=audit(a.data_root,source,a.cutoff)
    out=a.output_dir/('earnings_event_audit_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(parents=True,exist_ok=False)
    report['runner_sha256']=digest(Path(__file__))
    for name,obj in [('report.json',report),('price_inventory.json',inv)]:
        (out/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    write_csv(out/'coverage.csv',cov,['ticker','clean_events'])
    write_csv(out/'event_issues.csv',issues,['row','ticker','date','reason'])
    bundle=out.with_suffix('.zip')
    with zipfile.ZipFile(bundle,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.iterdir()): z.write(f,f.name)
    print(json.dumps(report,indent=2))
    print(f'SHARE AUDIT ZIP: {bundle.resolve()}')


if __name__=='__main__':
    main()
