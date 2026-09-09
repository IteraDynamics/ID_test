"""Offline, calendar-quarter SEC feature pilot for TSLA/META/APC; no model fitting."""
from __future__ import annotations

import argparse
import calendar
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import csv
import io
import json
from pathlib import Path

from scripts.run_ml_data_acquisition_pilot import (
    CUTOFF, ENTITIES, START, digest, filing_rows, finite, verify_sources,
)

INSTANT = ('Assets', 'Liabilities', 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest')
CFO = 'NetCashProvidedByUsedInOperatingActivities'
CFO_CONTINUING = CFO + 'ContinuingOperations'
FLOWS = ('NetIncomeLoss', CFO, CFO_CONTINUING, 'Revenues',
         'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet', 'OperatingIncomeLoss')
END = datetime(2025, 1, 1, tzinfo=timezone.utc)


def stamp(value):
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def quarter_end(year, quarter):
    month = quarter * 3
    return date(year, month, calendar.monthrange(year, month)[1]).isoformat()


def shift_quarter(end, offset):
    d = date.fromisoformat(end)
    index = d.year * 4 + (d.month - 1) // 3 + offset
    return quarter_end(index // 4, index % 4 + 1)


def quarter_start(end):
    return (date.fromisoformat(shift_quarter(end, -1)) + timedelta(days=1)).isoformat()


def normalize(facts, filings, symbol, cik):
    """Keep independent filing versions; quarantine unmatched/ambiguous contexts."""
    if str(facts.get('cik', '')).zfill(10) != cik:
        raise ValueError('SEC_FACTS_CIK_MISMATCH')
    by_acc = {}
    for f in filings:
        acc = f['accessionNumber']
        if acc in by_acc and by_acc[acc] != f:
            raise ValueError('SEC_CONFLICTING_ACCESSION')
        by_acc[acc] = f
    groups, exclusions = defaultdict(list), Counter()
    for tag in INSTANT + FLOWS:
        for row in facts.get('facts', {}).get('us-gaap', {}).get(tag, {}).get('units', {}).get('USD', []):
            try:
                filed, end = date.fromisoformat(row['filed']), date.fromisoformat(row['end'])
                if filed.isoformat() > CUTOFF or end.isoformat() > CUTOFF:
                    exclusions['after_cutoff'] += 1
                    continue
                if filed.isoformat() < START or row.get('form') not in ('10-K', '10-Q', '10-K/A', '10-Q/A'):
                    exclusions['outside_filing_contract'] += 1
                    continue
                if end > filed or not finite(row.get('val')) or isinstance(row['val'], bool):
                    raise ValueError('BAD_VALUE_OR_END')
                f = by_acc.get(row.get('accn'))
                if not f or f['filingDate'] != row['filed'] or f['form'] != row['form']:
                    raise ValueError('UNMATCHED_ACCESSION')
                accepted = datetime.fromisoformat(f['acceptanceDateTime'].replace('Z', '+00:00'))
                if accepted.tzinfo is None:
                    raise ValueError('NAIVE_ACCEPTANCE')
                # Explicit conservative pilot latency, NOT an exchange-session timestamp.
                available = max(accepted.astimezone(timezone.utc) + timedelta(hours=24),
                                datetime.combine(filed + timedelta(days=1), datetime.min.time(), timezone.utc))
                if available >= END:
                    exclusions['availability_after_cutoff'] += 1
                    continue
                if accepted.date() < filed - timedelta(days=7) or accepted.date() > filed + timedelta(days=1):
                    raise ValueError('ACCEPTANCE_DATE_MISMATCH')
                if end.isoformat() != quarter_end(end.year, (end.month - 1) // 3 + 1):
                    raise ValueError('NON_CALENDAR_QUARTER_END')
                start = row.get('start', '')
                if tag in INSTANT:
                    if start:
                        raise ValueError('DURATION_FOR_INSTANT')
                elif start not in (f'{end.year}-01-01', quarter_start(end.isoformat())):
                    raise ValueError('UNSUPPORTED_DURATION')
                key = (tag, start, row['end'], row['accn'])
                groups[key].append(dict(symbol=symbol, cik=cik, tag=tag, start=start,
                                        end=row['end'], value=row['val'], accession=row['accn'],
                                        filed=row['filed'], accepted_at=stamp(accepted), available_at=stamp(available)))
            except (ValueError, KeyError, TypeError) as exc:
                reason = str(exc) if str(exc) in {'BAD_VALUE_OR_END', 'UNMATCHED_ACCESSION', 'NAIVE_ACCEPTANCE', 'ACCEPTANCE_DATE_MISMATCH', 'NON_CALENDAR_QUARTER_END', 'DURATION_FOR_INSTANT', 'UNSUPPORTED_DURATION'} else 'MALFORMED_CONTEXT'
                exclusions[reason] += 1
    versions = []
    for key, rows in sorted(groups.items()):
        item = rows[0].copy()
        # A conflicting latest filing poisons its context; never fall back to an older value.
        item['status'] = 'CONFLICT' if len({r['value'] for r in rows}) != 1 else 'OBSERVED'
        if item['status'] == 'CONFLICT':
            item['value'] = None
        item['source_rows'] = len(rows)
        item['fact_id'] = digest(json.dumps([symbol, *key], separators=(',', ':')).encode())[:24]
        versions.append(item)
    return versions, dict(sorted(exclusions.items()))


def select_asof(versions, asof):
    groups = defaultdict(list)
    for v in versions:
        if v['available_at'] <= asof:
            groups[(v['tag'], v['start'], v['end'])].append(v)
    selected = {}
    for key, rows in groups.items():
        latest = max(r['available_at'] for r in rows)
        same = [r for r in rows if r['available_at'] == latest]
        v = sorted(same, key=lambda r: r['fact_id'])[0].copy()
        if any(r['status'] == 'CONFLICT' for r in same) or len({r['value'] for r in same}) != 1:
            v.update(value=None, status='CONFLICT')
        selected[key] = v
    return selected


def result(value=None, method='MISSING', facts=()):
    facts = list(facts)
    return dict(value=value, method=method, fact_ids=sorted({r['fact_id'] for r in facts}),
                accessions=sorted({r['accession'] for r in facts}),
                available_at=max((r['available_at'] for r in facts), default=None))


def quarter(selected, tag, end):
    start = quarter_start(end)
    direct = selected.get((tag, start, end))
    cumulative = selected.get((tag, end[:4] + '-01-01', end))
    prior = selected.get((tag, end[:4] + '-01-01', shift_quarter(end, -1)))
    # Do not retain an old direct quarter after a newer cumulative revision.
    if direct and (not cumulative or direct['available_at'] >= cumulative['available_at']):
        return result(direct['value'], direct['status'], [direct])
    if cumulative and cumulative['status'] == 'CONFLICT':
        return result(None, 'CONFLICT', [cumulative])
    if cumulative and prior:
        if prior['status'] == 'CONFLICT':
            return result(None, 'CONFLICT', [cumulative, prior])
        method = 'YTD_DIFFERENCE_SAME_FILING' if cumulative['accession'] == prior['accession'] else 'YTD_DIFFERENCE_CROSS_FILING_REVIEW'
        return result(cumulative['value'] - prior['value'], method, [cumulative, prior])
    return result(None, 'MISSING_COMPATIBLE_PRIOR' if cumulative else 'MISSING')


def ttm(selected, tag, end):
    # Annual observations are stronger than summing quarters from mixed filing versions.
    annual = selected.get((tag, end[:4] + '-01-01', end)) if end.endswith('12-31') else None
    if annual:
        return result(annual['value'], 'ANNUAL_' + annual['status'], [annual])
    qs = [quarter(selected, tag, shift_quarter(end, -i)) for i in range(4)]
    if any(q['value'] is None for q in qs):
        return result(None, 'INCOMPLETE_FOUR_QUARTERS')
    ids = {fid for q in qs for fid in q['fact_ids']}
    facts = [v for v in selected.values() if v['fact_id'] in ids]
    # Cross-filing summation can mix accounting bases even though every input is timely.
    return result(sum(q['value'] for q in qs), 'FOUR_QUARTERS_CROSS_FILING_REVIEW', facts)


def snapshot(versions, asof, symbol):
    selected = select_asof(versions, asof)
    ends = [end for tag, start, end in selected if tag == 'Assets']
    if not ends:
        return [], []
    end = max(ends)
    quarters, features = [], []
    for tag in FLOWS:
        for i in range(8):
            qend = shift_quarter(end, -i)
            quarters.append(dict(symbol=symbol, snapshot_at=asof, tag=tag,
                                 start=quarter_start(qend), end=qend, **quarter(selected, tag, qend)))
        features.append(dict(symbol=symbol, snapshot_at=asof, end=end,
                             feature=tag + '_ttm', **ttm(selected, tag, end)))
    instants = {}
    for tag in INSTANT:
        v = selected.get((tag, '', end))
        instants[tag] = result(v['value'], v['status'], [v]) if v else result()
        features.append(dict(symbol=symbol, snapshot_at=asof, end=end, feature=tag, **instants[tag]))
    assets = instants['Assets']
    for tag, name in [('NetIncomeLoss', 'net_income_ttm_to_end_assets'),
                      (CFO, 'operating_cash_flow_ttm_to_end_assets'),
                      (CFO_CONTINUING, 'continuing_cash_flow_ttm_to_end_assets'),
                      ('Liabilities', 'liabilities_to_assets')]:
        numerator = instants[tag] if tag in INSTANT else ttm(selected, tag, end)
        value = numerator['value'] / assets['value'] if numerator['value'] is not None and assets['value'] is not None and assets['value'] > 0 else None
        ids = set(numerator['fact_ids'] + assets['fact_ids'])
        lineage = [v for v in selected.values() if v['fact_id'] in ids]
        features.append(dict(symbol=symbol, snapshot_at=asof, end=end, feature=name,
                             **result(value, 'PILOT_RATIO_REVIEW' if value is not None else 'MISSING_OR_NONPOSITIVE_ASSETS', lineage)))
    ni, cfo = ttm(selected, 'NetIncomeLoss', end), ttm(selected, CFO, end)
    ids = set(ni['fact_ids'] + cfo['fact_ids'] + assets['fact_ids'])
    accrual = (ni['value'] - cfo['value']) / assets['value'] if ni['value'] is not None and cfo['value'] is not None and assets['value'] is not None and assets['value'] > 0 else None
    features.append(dict(symbol=symbol, snapshot_at=asof, end=end, feature='accruals_ttm_to_end_assets',
                         **result(accrual, 'PILOT_RATIO_REVIEW' if accrual is not None else 'MISSING_OR_NONPOSITIVE_ASSETS',
                                  [v for v in selected.values() if v['fact_id'] in ids])))
    equity = instants[INSTANT[2]]
    a = selected.get(('Assets', '', end))
    e = selected.get((INSTANT[2], '', end))
    # Kept separate from liabilities: redeemable/mezzanine equity is not ruled out.
    derived = assets['value'] - equity['value'] if a and e and a['accession'] == e['accession'] and assets['value'] is not None and equity['value'] is not None else None
    features.append(dict(symbol=symbol, snapshot_at=asof, end=end, feature='assets_minus_total_equity_DIAGNOSTIC',
                         **result(derived, 'ACCOUNTING_IDENTITY_REVIEW' if derived is not None else 'MISSING_SAME_FILING_COMPONENTS', [v for v in (a, e) if v])))
    for r in quarters + features:
        if r['available_at'] is not None and r['available_at'] > asof:
            raise AssertionError('FUTURE_FACT_IN_SNAPSHOT')
    return quarters, features


# Independently read from Tesla's 2015 10-K cash-flow statement (USD thousands).
# This validates these six rows only; it does not approve a global tag alias.
SPOT_URL = 'https://www.sec.gov/Archives/edgar/data/1318605/000156459016013195/tsla-10k_20151231.htm'
SPOTS = [(CFO_CONTINUING, year, value) for year, value in
         [(2013, 264804000), (2014, -57337000), (2015, -524499000)]] + [
         ('NetIncomeLoss', year, value) for year, value in
         [(2013, -74014000), (2014, -294040000), (2015, -888663000)]]


def spot_checks(versions):
    checks = []
    for tag, year, expected in SPOTS:
        matches = [v for v in versions if v['symbol'] == 'TSLA' and v['tag'] == tag
                   and v['accession'] == '0001564590-16-013195'
                   and v['start'] == f'{year}-01-01' and v['end'] == f'{year}-12-31']
        status = 'PASS' if len(matches) == 1 and matches[0]['value'] == expected else 'MISSING_OR_MISMATCH'
        checks.append(dict(tag=tag, year=year, expected_usd=expected,
                           actual_usd=[v['value'] for v in matches], status=status, source=SPOT_URL))
    return checks


def csv_bytes(rows, fields):
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, separators=(',', ':')) if isinstance(v, (list, dict)) else v for k, v in row.items()})
    return out.getvalue().encode()


def build(root):
    manifest = verify_sources(root)
    all_versions, all_quarters, all_features, summaries = [], [], [], {}
    for symbol, cik, token in ENTITIES:
        raw = root / 'raw'
        sub = json.loads((raw / f'{symbol}_submissions.json').read_text(encoding='utf-8'))
        if str(sub['cik']).zfill(10) != cik or token not in sub['name'].lower():
            raise ValueError('SEC_ENTITY_IDENTITY_MISMATCH')
        filings = filing_rows(sub['filings']['recent'])
        for path in sorted(raw.glob(f'{symbol}_CIK*-submissions-*.json')):
            filings.extend(filing_rows(json.loads(path.read_text(encoding='utf-8'))))
        facts = json.loads((raw / f'{symbol}_companyfacts.json').read_text(encoding='utf-8'))
        versions, exclusions = normalize(facts, filings, symbol, cik)
        quarters, features = [], []
        for asof in sorted({v['available_at'] for v in versions}):
            q, f = snapshot(versions, asof, symbol)
            quarters.extend(q)
            features.extend(f)
        all_versions.extend(versions)
        all_quarters.extend(quarters)
        all_features.extend(features)
        # Deliberately extreme future revision: changing its value must have no effect.
        if versions:
            asof = max(v['available_at'] for v in versions)
            injected = [dict(v, value=1e30, available_at='2025-01-02T00:00:00Z', fact_id='future-' + v['fact_id']) for v in versions]
            if snapshot(versions, asof, symbol) != snapshot(versions + injected, asof, symbol):
                raise AssertionError('FUTURE_REVISION_CANARY_FAILED')
        counts = Counter(r['feature'] for r in features if r['value'] is not None)
        by_period = defaultdict(set)
        for v in versions:
            if v['value'] is not None:
                by_period[(v['tag'], v['start'], v['end'])].add(v['value'])
        summaries[symbol] = dict(versions=len(versions), conflict_versions=sum(v['status']=='CONFLICT' for v in versions),
                                 changed_value_periods=sum(len(v)>1 for v in by_period.values()),
                                 snapshots=len({r['snapshot_at'] for r in features}),
                                 populated_features=dict(sorted(counts.items())), exclusions=exclusions)
    payloads = {
        'fact_versions.csv': csv_bytes(all_versions, ['symbol','cik','tag','start','end','value','accession','filed','accepted_at','available_at','status','source_rows','fact_id']),
        'quarterly_snapshots.csv': csv_bytes(all_quarters, ['symbol','snapshot_at','tag','start','end','value','method','fact_ids','accessions','available_at']),
        'feature_snapshots.csv': csv_bytes(all_features, ['symbol','snapshot_at','end','feature','value','method','fact_ids','accessions','available_at']),
    }
    report = dict(version=1, status='PIT_FEATURE_PILOT_REVIEW_REQUIRED', ready_for_model=False, candidate_fits=0,
                  cutoff=CUTOFF, future_revision_canary_passed=True, filing_spot_checks=spot_checks(all_versions),
                  implementation_sha256={name: digest(Path(__file__).with_name(name).read_bytes().replace(b'\r\n', b'\n')) for name in ('run_ml_pit_feature_pilot.py', 'run_ml_data_acquisition_pilot.py')},
                  implementation_hash_policy='UTF-8 source bytes with CRLF normalized to LF',
                  availability_policy='Later of SEC acceptance UTC plus 24 hours and midnight UTC after filed date; consume only at a later actual decision timestamp',
                  fiscal_scope='Calendar quarters only; exact Jan/Apr/Jul/Oct starts, exact quarter ends; USD',
                  source_manifest_sha256=digest((root/'source_manifest.json').read_bytes()),
                  source_acquisition_errors=manifest['errors'], issuers=summaries,
                  artifact_sha256={k:digest(v) for k,v in payloads.items()},
                  limitations=['Companyfacts contexts and tag equivalence are not comprehensively filing-validated',
                               'Cross-filing differences and TTM sums may mix accounting bases; explicitly marked for review',
                               'Continuing operating cash flow is never silently substituted for total operating cash flow',
                               'Assets minus total equity is diagnostic only, not reconstructed liabilities',
                               'Snapshot time is not a trading session; price adjustment, identity, delistings and universe remain unresolved'])
    payloads['feature_pilot_report.json'] = (json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()
    return payloads


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-root', type=Path, required=True, help='Saved acquisition directory containing raw/ and source_manifest.json')
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args()
    # Verify and compute twice before publishing any files. Never overwrite an earlier run.
    first, second = build(args.input_root), build(args.input_root)
    if first != second:
        raise AssertionError('NONDETERMINISTIC_REPLAY')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for name, payload in first.items():
        (args.output_dir/name).write_bytes(payload)
    print(json.dumps(json.loads(first['feature_pilot_report.json']), indent=2))


if __name__ == '__main__':
    main()
