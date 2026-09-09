import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

from scripts import run_ml_pit_feature_pilot as p


def version(tag, start, end, value, acc='a', available='2024-05-02T20:00:00Z', status='OBSERVED'):
    return dict(tag=tag, start=start, end=end, value=value, accession=acc,
                available_at=available, fact_id=f'{tag}:{start}:{end}:{acc}', status=status)


def table(rows):
    return p.select_asof(rows, '2024-12-31T23:59:59Z')


def test_revision_canary_does_not_rewrite_prior_snapshot():
    old = version('Assets', '', '2024-03-31', 10)
    revised = version('Assets', '', '2024-03-31', 999999, 'b', '2024-08-02T20:00:00Z')
    assert p.select_asof([old, revised], '2024-06-01T00:00:00Z')[('Assets','','2024-03-31')]['value'] == 10
    assert p.select_asof([old, revised], revised['available_at'])[('Assets','','2024-03-31')]['value'] == 999999
    # Explicitly demonstrate the latest-only bug this test guards against.
    assert table([old, revised])[('Assets','','2024-03-31')]['value'] != 10


def test_quarter_ytd_subtraction_q4_and_no_tag_splicing():
    rows = [version(p.CFO,'2024-01-01','2024-03-31',10),
            version(p.CFO,'2024-01-01','2024-06-30',25,'b'),
            version(p.CFO,'2024-01-01','2024-09-30',45,'c'),
            version(p.CFO,'2024-01-01','2024-12-31',80,'d')]
    selected=table(rows)
    assert [p.quarter(selected,p.CFO,e)['value'] for e in ('2024-03-31','2024-06-30','2024-09-30','2024-12-31')] == [10,15,20,35]
    assert 'CROSS_FILING_REVIEW' in p.quarter(selected,p.CFO,'2024-06-30')['method']
    assert p.ttm(selected,p.CFO,'2024-12-31')['value'] == 80
    rows[0]['tag'] = p.CFO_CONTINUING
    assert p.quarter(table(rows),p.CFO,'2024-06-30')['value'] is None


def test_ttm_requires_four_contiguous_quarters():
    ends = ['2023-06-30','2023-09-30','2023-12-31','2024-03-31']
    rows=[version('Revenues',p.quarter_start(e),e,v) for e,v in zip(ends,[10,20,30,40])]
    assert p.ttm(table(rows),'Revenues',ends[-1])['value'] == 100
    assert p.ttm(table(rows[1:]),'Revenues',ends[-1])['value'] is None


def test_latest_conflict_blocks_older_fact():
    old=version('Assets','','2024-03-31',10)
    conflict=version('Assets','','2024-03-31',None,'b','2024-08-01T20:00:00Z','CONFLICT')
    assert table([old,conflict])[('Assets','','2024-03-31')]['value'] is None
    twin=version('Assets','','2024-03-31',20,'z')
    assert table([old,twin])[('Assets','','2024-03-31')]['status'] == 'CONFLICT'


def test_new_cumulative_revision_does_not_keep_stale_direct_quarter():
    rows=[version(p.CFO,'2024-04-01','2024-06-30',15),
          version(p.CFO,'2024-01-01','2024-03-31',10),
          version(p.CFO,'2024-01-01','2024-06-30',30,'b','2024-09-01T00:00:00Z')]
    assert p.quarter(table(rows),p.CFO,'2024-06-30')['value'] == 20


def raw_fixture():
    row=dict(filed='2024-05-01',end='2024-03-31',val=10,accn='a',form='10-Q')
    facts=dict(cik=1318605,facts={'us-gaap':{'Assets':{'units':{'USD':[row]}}}})
    filings=[dict(accessionNumber='a',filingDate='2024-05-01',form='10-Q',acceptanceDateTime='2024-05-01T20:00:00Z')]
    return facts,filings


def test_normalization_availability_duplicates_conflicts_and_cutoff():
    facts,filings=raw_fixture()
    facts['facts']['us-gaap']['Assets']['units']['USD'] *= 2
    rows, excluded=p.normalize(facts,filings,'TSLA','0001318605')
    assert len(rows)==1 and rows[0]['source_rows']==2
    assert rows[0]['available_at']=='2024-05-02T20:00:00Z'
    assert p.select_asof(rows,'2024-05-02T19:59:59Z') == {}
    late=copy.deepcopy(facts['facts']['us-gaap']['Assets']['units']['USD'][0])
    late.update(filed='2025-03-01',val=999999,accn='late')
    facts['facts']['us-gaap']['Assets']['units']['USD'].append(late)
    new,excluded=p.normalize(facts,filings,'TSLA','0001318605')
    assert new==rows and excluded['after_cutoff']==1
    conflict=copy.deepcopy(late); conflict.update(filed='2024-05-01',accn='a',val=20)
    facts['facts']['us-gaap']['Assets']['units']['USD'].append(conflict)
    assert p.normalize(facts,filings,'TSLA','0001318605')[0][0]['status']=='CONFLICT'


@pytest.mark.parametrize('change', ['missing_accession','naive_time','noncalendar','nonfinite','wrong_duration'])
def test_invalid_facts_quarantined(change):
    facts,filings=raw_fixture()
    row=facts['facts']['us-gaap']['Assets']['units']['USD'][0]
    if change=='missing_accession': row['accn']='absent'
    if change=='naive_time': filings[0]['acceptanceDateTime']='2024-05-01T20:00:00'
    if change=='noncalendar': row['end']='2024-03-30'
    if change=='nonfinite': row['val']=float('nan')
    if change=='wrong_duration': row['start']='2024-01-01'
    rows,exclusions=p.normalize(facts,filings,'TSLA','0001318605')
    assert not rows and sum(exclusions.values())==1


def test_balance_components_not_substituted_for_liabilities():
    rows=[version('Assets','','2024-03-31',100),version(p.INSTANT[2],'','2024-03-31',40)]
    _, features=p.snapshot(rows,'2024-06-01T00:00:00Z','APC')
    f={r['feature']:r for r in features}
    assert f['assets_minus_total_equity_DIAGNOSTIC']['value']==60
    assert f['Liabilities']['value'] is None and f['liabilities_to_assets']['value'] is None
    rows[1]['accession']='other'
    f={r['feature']:r for r in p.snapshot(rows,'2024-06-01T00:00:00Z','APC')[1]}
    assert f['assets_minus_total_equity_DIAGNOSTIC']['value'] is None


def test_snapshot_replay_and_future_injection():
    rows=[version('Assets','','2024-03-31',100),version('NetIncomeLoss','2024-01-01','2024-03-31',5)]
    asof='2024-06-01T00:00:00Z'
    before=p.snapshot(rows,asof,'TSLA')
    rows.append(version('Assets','','2024-03-31',1e10,'future','2025-01-01T00:00:00Z'))
    assert p.snapshot(rows,asof,'TSLA') == before
    assert p.snapshot(list(reversed(rows)),asof,'TSLA') == before


def test_friday_acceptance_monday_filed_uses_later_availability():
    facts, filings = raw_fixture()
    row=facts['facts']['us-gaap']['Assets']['units']['USD'][0]
    row['filed']='2024-05-06'
    filings[0].update(filingDate='2024-05-06', acceptanceDateTime='2024-05-03T22:43:11Z')
    rows, exclusions=p.normalize(facts,filings,'TSLA','0001318605')
    assert not exclusions and rows[0]['available_at']=='2024-05-07T00:00:00Z'
    assert not p.select_asof(rows,'2024-05-06T23:59:59Z')


def test_independent_statement_expectation_can_fail():
    rows=[]
    for tag,year,value in p.SPOTS:
        rows.append(dict(symbol='TSLA', tag=tag, accession='0001564590-16-013195',
                         start=f'{year}-01-01',end=f'{year}-12-31',value=value))
    assert all(c['status']=='PASS' for c in p.spot_checks(rows))
    rows[0]['value']+=1
    assert p.spot_checks(rows)[0]['status']=='MISSING_OR_MISMATCH'


def test_cli_replay_and_corruption_before_output(tmp_path):
    import subprocess
    import sys
    raw=tmp_path/'source'/'raw'; raw.mkdir(parents=True)
    manifest=dict(version=1,start=p.START,cutoff=p.CUTOFF,errors=[],files=[])
    for symbol,cik,token in p.ENTITIES:
        facts,filings=raw_fixture();facts['cik']=int(cik)
        sub=dict(cik=int(cik),name=token,filings={'recent':{k:[r[k] for r in filings] for k in filings[0]}})
        for kind,payload in [('submissions',sub),('companyfacts',facts)]:
            name=f'{symbol}_{kind}.json'; data=json.dumps(payload).encode()
            (raw/name).write_bytes(data)
            manifest['files'].append(dict(name=name,bytes=len(data),sha256=p.digest(data)))
    (raw.parent/'source_manifest.json').write_text(json.dumps(manifest))
    def command(out):
        return [sys.executable,'-m','scripts.run_ml_pit_feature_pilot','--input-root',str(raw.parent),'--output-dir',str(out)]
    one,two=tmp_path/'one',tmp_path/'two'
    subprocess.run(command(one),check=True,capture_output=True)
    subprocess.run(command(two),check=True,capture_output=True)
    assert {f.name:f.read_bytes() for f in one.iterdir()}=={f.name:f.read_bytes() for f in two.iterdir()}
    assert subprocess.run(command(one),capture_output=True).returncode!=0
    (raw/'TSLA_companyfacts.json').write_bytes(b'corrupt')
    third=tmp_path/'third'
    assert subprocess.run(command(third),capture_output=True).returncode!=0
    assert not third.exists()
