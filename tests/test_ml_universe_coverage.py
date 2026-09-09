import json
import pytest
from scripts import reconcile_ml_universe_coverage as p


def sources():
    inventory=b'RelativePath,Length,LastWriteTimeUtc\ndata\\AAA_1D.csv,10,unknown\n'
    events=b'date,ticker,action,reason\n2020-01-02,AAA,remove,\n2020-01-02,BBB,add,\n2025-01-02,LATE,add,\n'
    m=dict(request={'asset':'AAA','auto_adjust':False},actual_start='2020-02-01',actual_end='2024-12-31')
    return inventory,{'sp500_reconstitution_events.csv':events,'AAA_1D.csv.manifest.json':json.dumps(m).encode()}


def test_missing_and_late_start_are_not_approved_or_aliased():
    inv,members=sources();out=p.reconcile(inv,members);r=json.loads(out['universe_coverage_report.json'])
    assert r['calendar']['tickers']==2 and r['calendar']['eligible_rows']==2
    assert r['ticker_coverage_counts']=={'NO_MATCHING_MANIFEST':1,'STARTS_AFTER_EVENT':1}
    assert r['missing_manifest_tickers']==['BBB']
    assert r['decision']['approved_model_universe'] is None
    assert b'PAIR_ONLY_NOT_PROOF_OF_RENAME' in out['same_day_pairs.csv']


def test_future_calendar_canary_does_not_change_coverage():
    inv,members=sources();before=p.reconcile(inv,members)
    members['sp500_reconstitution_events.csv']+=b'2026-01-01,FUTURE,remove,\n'
    after=p.reconcile(inv,members)
    for name in ['ticker_coverage.csv','event_coverage.csv','same_day_pairs.csv']:assert before[name]==after[name]


def test_manifest_overlap_is_only_range_evidence():
    inv,members=sources();m=json.loads(members['AAA_1D.csv.manifest.json']);m['actual_start']='2019-01-01'
    members['AAA_1D.csv.manifest.json']=json.dumps(m).encode()
    members['AAA_1D.csv']=b'timestamp,close\n2024-01-01,10\n'
    r=json.loads(p.reconcile(inv,members)['universe_coverage_report.json'])
    assert r['ticker_coverage_counts']['RANGE_OVERLAPS_EVENTS_ONLY']==1
    assert r['samples']['AAA']['rows_through_cutoff']==1
    assert not r['ready_for_model']


@pytest.mark.parametrize('kind',['duplicate','bad_action','bad_manifest'])
def test_bad_inputs_fail(kind):
    inv,members=sources()
    if kind=='duplicate':members['sp500_reconstitution_events.csv']+=b'2020-01-02,BBB,add,\n'
    if kind=='bad_action':members['sp500_reconstitution_events.csv']+=b'2020-01-02,CCC,rename,\n'
    if kind=='bad_manifest':members['BBB_1D.csv.manifest.json']=members['AAA_1D.csv.manifest.json']
    with pytest.raises(ValueError):p.reconcile(inv,members)


def test_replay_order_and_nested_inventory_match():
    inv,members=sources();inv+=b'data\\archive\\BBB_1D.csv,20,unknown\n'
    first=p.reconcile(inv,members)
    assert first==p.reconcile(inv,dict(reversed(list(members.items()))))
    assert b'data/archive/BBB_1D.csv' in first['ticker_coverage.csv']
    r=json.loads(first['universe_coverage_report.json'])
    assert r['missing_manifest_and_root_price_count']==1
