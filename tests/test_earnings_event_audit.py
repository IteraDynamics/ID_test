import csv
from datetime import date, timedelta
from research.earnings_event.audit import audit, events, price_inventory, day


def save(path, fields, rows):
    with path.open('w',newline='') as f:
        w=csv.writer(f); w.writerow(fields); w.writerows(rows)


def event_file(root, rows):
    p=root/'earnings_surprise_history.csv'
    save(p,['ticker','date','reported_eps','eps_estimate'],rows)
    return p


def prices(root, dates):
    p=root/'ABC_1D.csv'
    save(p,['timestamp','open','high','low','close','volume'],
         [[str(d),10,12,9,11,100] for d in dates])
    return p


def test_conflicts_exclude_whole_event_and_exact_duplicates_collapse(tmp_path):
    p=event_file(tmp_path,[['ABC','2020-01-01',1,1]]*2+
                 [['ABC','2020-02-01',1,1],['ABC','2020-02-01',2,1],
                  ['ABC','2020-03-01','nan',1],['ABC','2025-01-01',3,1]])
    clean,c,_=events(p,date(2024,12,31))
    assert clean==[('ABC',date(2020,1,1))]
    assert c['conflicting_groups']==1 and c['after_cutoff_rows']==1
    assert c['missing_reported_eps_groups']==1


def test_invalid_ticker_never_becomes_a_path(tmp_path):
    p=event_file(tmp_path,[['../ABC','2020-01-01',1,1],['ABC','bad',1,1]])
    clean,c,_=events(p,date(2024,12,31))
    assert not clean and c['invalid_rows']==2


def test_duplicate_or_unsorted_price_dates_fail_closed(tmp_path):
    for dates in [['2020-01-02','2020-01-02'],['2020-01-03','2020-01-02']]:
        inv,ds=price_inventory(prices(tmp_path,dates),date(2024,12,31))
        assert not inv['structural_ok'] and not ds


def test_impossible_ohlc_and_weekend_fail(tmp_path):
    p=prices(tmp_path,['2020-01-04'])
    assert not price_inventory(p,date(2024,12,31))[1]
    save(p,['date','open','high','low','close','volume'],[['2020-01-02',10,9,8,11,100]])
    assert not price_inventory(p,date(2024,12,31))[1]


def test_horizon_requires_entry_and_exit_and_keeps_unknown_timing(tmp_path):
    ds=[date(2020,1,1)+timedelta(days=i) for i in range(150)]
    ds=[d for d in ds if d.weekday()<5][:70]
    prices(tmp_path,ds)
    p=event_file(tmp_path,[['ABC',str(ds[62]),1,1]])
    report,_,cov,_=audit(tmp_path,p,date(2024,12,31))
    row=next(r for r in cov if r['ticker']=='ABC')
    assert row['metadata_windows_5']==1
    assert not report['ready_for_backtest'] and report['verified_first_session_events']==0
    p=event_file(tmp_path,[['ABC',str(ds[63]),1,1]])
    report,_,cov,_=audit(tmp_path,p,date(2024,12,31))
    assert cov[0]['metadata_windows_3']==1 and cov[0]['metadata_windows_5']==0


def test_ambiguous_price_files_not_selected(tmp_path):
    p=event_file(tmp_path,[['ABC','2020-01-01',1,1]])
    prices(tmp_path,['2020-01-02'])
    other=tmp_path/'backup';other.mkdir();prices(other,['2020-01-02'])
    _,_,cov,_=audit(tmp_path,p,date(2024,12,31))
    assert cov[0]['price_candidates']==2 and not cov[0]['structurally_valid_prices']


def test_numeric_timestamp_and_no_timezone_date_shift():
    assert day('1577923200')==date(2020,1,2)
    assert day('1577923200000')==date(2020,1,2)
    assert day('2020-01-02T00:00:00+00:00')==date(2020,1,2)


def test_source_sample_is_reproducible_and_not_ranked_by_price_outcome(tmp_path):
    from research.earnings_event.review import select_sample
    ds=[date(2020,1,1)+timedelta(days=i) for i in range(160)]
    ds=[d for d in ds if d.weekday()<5]
    stock=prices(tmp_path,ds)
    spy=tmp_path/'SPY_1D.csv';spy.write_bytes(stock.read_bytes())
    event_file(tmp_path,[['ABC',str(ds[i]),1,1] for i in range(62,85)])
    first=select_sample(tmp_path,size=5)
    assert len(first['sample'])==5 and first['candidate_windows']==23
    save(stock,['timestamp','open','high','low','close','volume'],
         [[str(d),100,120,90,110,1000] for d in ds])
    assert select_sample(tmp_path,size=5)['sample']==first['sample']
    assert first['performance'] is None and not first['source_review_complete']


def test_calendar_proxy_reports_missing_session(tmp_path):
    from research.earnings_event.review import select_sample
    ds=[date(2020,1,1)+timedelta(days=i) for i in range(160)]
    ds=[d for d in ds if d.weekday()<5]
    stock=prices(tmp_path,ds)
    (tmp_path/'SPY_1D.csv').write_bytes(stock.read_bytes())
    missing=ds.pop(10);prices(tmp_path,ds)
    event_file(tmp_path,[['ABC',str(ds[65]),1,1]])
    r=select_sample(tmp_path)
    assert r['calendar_proxy_discrepancies'][0]['missing_spy_dates']==[str(missing)]
