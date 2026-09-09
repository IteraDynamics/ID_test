"""Offline reconciliation of the supplied inventory and sample ZIP; no universe substitution."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

CUTOFF = '2024-12-31'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def csv_rows(data):
    return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))


def csv_bytes(rows, fields):
    out = io.StringIO(newline='')
    w = csv.DictWriter(out, fieldnames=fields, lineterminator='\n')
    w.writeheader(); w.writerows(rows)
    return out.getvalue().encode()


def reconcile(inventory_bytes, members):
    inventory = csv_rows(inventory_bytes)
    paths = {r['RelativePath'].replace('\\', '/') for r in inventory}
    events = csv_rows(members['sp500_reconstitution_events.csv'])
    eligible = []
    for row in events:
        day = date.fromisoformat(row['date']).isoformat()
        if row['action'] not in ('add', 'remove') or not row['ticker'].strip():
            raise ValueError('INVALID_EVENT')
        if day <= CUTOFF:
            eligible.append(row)
    if len({(r['date'],r['ticker'],r['action']) for r in eligible}) != len(eligible):
        raise ValueError('DUPLICATE_EVENT')
    manifests = {}
    for name, data in sorted(members.items()):
        if not name.endswith('_1D.csv.manifest.json'):
            continue
        m = json.loads(data)
        ticker = m['request']['asset']
        if name != ticker + '_1D.csv.manifest.json' or ticker in manifests:
            raise ValueError('MANIFEST_IDENTITY_CONFLICT')
        first, last = m['actual_start'][:10], m['actual_end'][:10]
        date.fromisoformat(first); date.fromisoformat(last)
        if first > last:
            raise ValueError('REVERSED_PRICE_RANGE')
        manifests[ticker] = m
    grouped = defaultdict(list)
    for e in eligible:
        grouped[e['ticker']].append(e)
    coverage = []
    samples = {}
    for ticker in sorted(grouped):
        m = manifests.get(ticker)
        first = m['actual_start'][:10] if m else ''
        last = m['actual_end'][:10] if m else ''
        es = sorted(grouped[ticker], key=lambda e:(e['date'],e['action']))
        name = ticker + '_1D.csv'
        observed = None
        if name in members:
            rows = csv_rows(members[name])
            days = [date.fromisoformat(r['timestamp'][:10]).isoformat() for r in rows]
            observed = {d for d in days if d <= CUTOFF}
            samples[ticker] = dict(rows_through_cutoff=sum(d<=CUTOFF for d in days),
                                   first=min(observed,default=None),last=max(observed,default=None),
                                   duplicate_dates=len(days)-len(set(days)),sha256=sha(members[name]))
        status = ('NO_MATCHING_MANIFEST' if not m else 'NO_PRE2025_RANGE' if first>CUTOFF
                  else 'STARTS_AFTER_EVENT' if any(e['date']<first for e in es)
                  else 'ENDS_BEFORE_EVENT' if any(e['date']>last for e in es)
                  else 'RANGE_OVERLAPS_EVENTS_ONLY')
        coverage.append(dict(ticker=ticker,first_event=es[0]['date'],last_event=es[-1]['date'],
                             adds=sum(e['action']=='add' for e in es),removes=sum(e['action']=='remove' for e in es),
                             root_price_in_inventory=f'data/{name}' in paths,
                             manifest_present=m is not None,actual_start=first,actual_end=last,
                             auto_adjust=m['request'].get('auto_adjust') if m else '',
                             coverage_status=status,identity_status='UNVERIFIED',
                             sample_rows_through_cutoff=len(observed) if observed is not None else '',
                             other_inventory_matches=';'.join(sorted(p for p in paths if p.rsplit('/',1)[-1]==name and p!=f'data/{name}'))))
    details = []
    for e in sorted(eligible,key=lambda r:(r['date'],r['ticker'],r['action'])):
        m=manifests.get(e['ticker'])
        first=m['actual_start'][:10] if m else ''
        last=m['actual_end'][:10] if m else ''
        status=('MISSING_MANIFEST' if not m else 'EVENT_BEFORE_HISTORY' if e['date']<first
                else 'EVENT_AFTER_HISTORY' if e['date']>last else 'WITHIN_RECORDED_RANGE_ONLY')
        details.append(dict(date=e['date'],ticker=e['ticker'],action=e['action'],
                            weekday=date.fromisoformat(e['date']).strftime('%A'),
                            actual_start=first,actual_end=last,range_status=status))
    by_day=defaultdict(list)
    for e in eligible: by_day[e['date']].append(e)
    pairs=[]
    for day, rows in sorted(by_day.items()):
        adds=[r['ticker'] for r in rows if r['action']=='add']
        removes=[r['ticker'] for r in rows if r['action']=='remove']
        if len(adds)==len(removes)==1:
            pairs.append(dict(date=day,removed=removes[0],added=adds[0],
                              status='PAIR_ONLY_NOT_PROOF_OF_RENAME'))
    missing=[r['ticker'] for r in coverage if not r['manifest_present']]
    report=dict(version=1,status='BROAD_UNIVERSE_UNSUPPORTED_BY_SUPPLIED_DATA',ready_for_model=False,candidate_fits=0,
                cutoff=CUTOFF,inventory_files=len(inventory),manifests=len(manifests),
                calendar=dict(total_rows=len(events),eligible_rows=len(eligible),tickers=len(grouped),
                              first=min((e['date'] for e in eligible),default=None),last=max((e['date'] for e in eligible),default=None),
                              weekend_events=sum(date.fromisoformat(e['date']).weekday()>=5 for e in eligible),
                              complete_membership_baseline_provided=False),
                ticker_coverage_counts=dict(sorted(Counter(r['coverage_status'] for r in coverage).items())),
                event_coverage_counts=dict(sorted(Counter(r['range_status'] for r in details).items())),
                missing_manifest_tickers=missing,
                missing_manifest_and_root_price_count=sum(not r['manifest_present'] and not r['root_price_in_inventory'] for r in coverage),
                samples=samples,source_sha256={'inventory':sha(inventory_bytes),**{n:sha(b) for n,b in sorted(members.items())}},
                decision=dict(original_2010_2024_design='NOT_SUPPORTED',
                              reduced_2019_2024_full_membership_design='NOT_ESTABLISHED',
                              approved_model_universe=None,approved_evaluation_period=None),
                limitations=['Exact ticker/filename reconciliation only; missing names may have aliases, never auto-joined',
                             'Most prices inspected via manifest endpoints only; no continuity, identity or action validation implied',
                             'Change-event tickers exclude unchanged constituents and depend on future changes; not a full historical universe',
                             'A first add/remove is insufficient to reconstruct all initial constituents',
                             'Weekend dates require verification; no date shifting or calendar repair performed',
                             'Top-100 nonfinancial operating-company selection additionally needs historical classifications, issuer/share-class IDs, liquidity and nominal prices',
                             'Later calendar events are excluded; source hashes cover complete supplied files without treating later observations as evaluation data'])
    payloads={'ticker_coverage.csv':csv_bytes(coverage,list(coverage[0]) if coverage else ['ticker']),
              'event_coverage.csv':csv_bytes(details,list(details[0]) if details else ['date','ticker','action']),
              'same_day_pairs.csv':csv_bytes(pairs,['date','removed','added','status'])}
    report['artifact_sha256']={n:sha(b) for n,b in payloads.items()}
    payloads['universe_coverage_report.json']=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode()
    return payloads


def build(inventory, samples_zip):
    with ZipFile(samples_zip) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):
            raise ValueError('DUPLICATE_ZIP_MEMBER')
        # Read only flat source filenames. Never extract ZIP paths.
        selected=[n for n in names if '/' not in n and '\\' not in n and
                  (n.endswith('_1D.csv.manifest.json') or n.endswith('_1D.csv') or n=='sp500_reconstitution_events.csv')]
        members={n:z.read(n) for n in selected}
    return reconcile(inventory.read_bytes(),members)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--samples-zip',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args()
    first,second=build(a.inventory,a.samples_zip),build(a.inventory,a.samples_zip)
    if first!=second:raise AssertionError('REPLAY_MISMATCH')
    a.output_dir.mkdir(parents=True,exist_ok=False)
    for name,data in first.items():(a.output_dir/name).write_bytes(data)
    report=json.loads(first['universe_coverage_report.json'])
    print(json.dumps({k:report[k] for k in ['status','calendar','ticker_coverage_counts','event_coverage_counts','decision']},indent=2))


if __name__=='__main__': main()
