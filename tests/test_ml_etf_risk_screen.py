"""Accounting and temporal invariants for the fixed ETF screen."""
import numpy as np
import pandas as pd
import pytest
from scripts.run_ml_etf_risk_screen import (ASSETS, FEATURES, features, panel, weekly_sessions,
    training_rows, rebalance, ledger, metrics, classify)


def frames(n=300):
    dates = pd.bdate_range('2017-01-02', periods=n, tz='UTC')
    d = pd.DataFrame({'open': 100., 'high': 101., 'low': 99., 'close': 100., 'volume': 1.}, index=dates)
    return {a: d.copy() for a in ASSETS}


def predictions(signals=(210,215,220)):
    return pd.DataFrame([{'asset': a, 'session': s, 'logistic': .2, 'gbm': .3,
                         'trend': 1., 'rv60': .2} for s in signals for a in ASSETS])


def test_label_entry_and_last_boundary():
    fs=frames()
    fs['SPY'].loc[fs['SPY'].index[211], 'open']=200.
    fs['SPY'].loc[fs['SPY'].index[231], 'close']=189.
    p=panel(fs)
    assert p.loc[(p.asset=='SPY') & (p.session==210), 'label'].item()==1
    assert p.loc[(p.asset=='SPY') & (p.session==209), 'label'].item()==0
    assert p.loc[p.session>=279, 'label'].isna().all()
    assert p.loc[p.session<200, FEATURES[:8]].isna().all().all()


def test_features_do_not_see_future():
    a=frames()['SPY']; b=a.copy(); b.iloc[240:, :4]*=10
    pd.testing.assert_frame_equal(features(a).iloc[:240], features(b).iloc[:240])


def test_training_label_purge_is_strict():
    fs=frames(); p=panel(fs); boundary=fs['SPY'].index[260]
    t=training_rows(p,boundary)
    assert t.session.max()==238
    assert (t.label_end<boundary).all()


def test_holiday_week_and_next_session():
    dates=pd.to_datetime(['2024-03-27','2024-03-28','2024-04-01','2024-04-02'],utc=True)
    assert weekly_sessions(dates).tolist()==[1]


def test_flat_full_exposure_round_trip():
    d=ledger(frames(), predictions(), 'constant100', .001)
    assert d.nav.iloc[-1] == pytest.approx((1-.001)/(1+.001), abs=1e-12)
    assert d.turnover.iloc[1:-1].sum()<1e-12
    assert d.exposure.iloc[-1]==0 and d.cash_fraction.iloc[-1]==1


def test_post_cost_solution_sells_drifted_holdings():
    h,c,fees,traded,before=rebalance(np.array([.6,.2,.2]),0.,np.array([2.,1.,1.]), np.ones(3)/3,.001)
    after=(h*np.array([2.,1.,1.])).sum()+c
    assert after==pytest.approx(before-fees.sum())
    assert np.allclose(h*np.array([2.,1.,1.]),after/3)
    assert traded[0]>.6 and c<1e-12


def test_gap_return_and_delayed_execution():
    fs=frames()
    for d in fs.values():
        d.loc[d.index[212]:, ['open','close']]=110.
    standard=ledger(fs,predictions(),'constant100',0)
    delayed=ledger(fs,predictions(),'constant100',0,1)
    assert standard.nav.iloc[-1]==pytest.approx(1.1)
    assert delayed.nav.iloc[-1]==pytest.approx(1.)
    assert standard.date.iloc[0]==fs['SPY'].index[211]
    assert delayed.date.iloc[0]==fs['SPY'].index[212]
    assert np.allclose(standard[[a+'_contribution' for a in ASSETS]].sum(axis=1),standard['return'])


def test_exclusion_omits_path_metrics():
    d=ledger(frames(),predictions(),'constant50')
    m=metrics(d.iloc[[0,3,5]],False)
    assert 'cagr' not in m and 'maximum_drawdown' not in m


def test_secondary_cannot_rescue_primary():
    from scripts.run_ml_etf_risk_screen import CONTROLS
    fm=pd.DataFrame([{'asset':'pooled','model':'logistic','period':p,'brier_skill':s}
        for p,s in [('2018_2020',-.01),('2021_2024',.1),('exclude_2020',.1)]])
    ec=pd.DataFrame([{'scenario':s,'period':p,'policy':m,'ce':.2 if m in ['logistic','gbm'] else .1}
        for s in ['cost10','cost25','delay1'] for p in ['all','2018_2020','2021_2024','exclude_2020']
        for m in [*CONTROLS,'logistic','gbm']])
    assert classify(fm,ec)[0]=='SCREEN_NEGATIVE'


def write_inputs(root):
    import json
    dates=pd.bdate_range('2013-12-02','2025-01-02',tz='UTC')
    for a in ASSETS:
        d=pd.DataFrame({'timestamp':dates,'open':100.,'high':101.,'low':99.,'close':100.,'volume':1.})
        path=root/f'{a}_1D.csv'; d.to_csv(path,index=False)
        m={'rows':len(d),'schema':list(d.columns),'request':{'asset':a,'interval':'1d','auto_adjust':True},
           'actual_start':str(dates[0]),'actual_end':str(dates[-1])}
        (root/f'{a}_1D.csv.manifest.json').write_text(json.dumps(m))


def test_quarantine_before_numeric_price_validation(tmp_path):
    from scripts.run_ml_etf_risk_screen import load_inputs
    write_inputs(tmp_path)
    p=tmp_path/'QQQ_1D.csv';d=pd.read_csv(p);d.loc[len(d)-1,'close']=-1;d.to_csv(p,index=False)
    fs,_=load_inputs(tmp_path)
    assert fs['QQQ'].index[-1].year==2024
    assert (fs['QQQ'].close==100).all()


def test_missing_session_fails_not_inner_join(tmp_path):
    import json
    from scripts.run_ml_etf_risk_screen import load_inputs
    write_inputs(tmp_path)
    p=tmp_path/'GLD_1D.csv';d=pd.read_csv(p).drop(index=300);d.to_csv(p,index=False)
    mpath=tmp_path/'GLD_1D.csv.manifest.json';m=json.loads(mpath.read_text());m['rows']-=1;mpath.write_text(json.dumps(m))
    with pytest.raises(AssertionError,match='session mismatch'):
        load_inputs(tmp_path)


def test_bad_execution_price_fails(tmp_path):
    from scripts.run_ml_etf_risk_screen import load_inputs
    write_inputs(tmp_path)
    p=tmp_path/'QQQ_1D.csv';d=pd.read_csv(p);d.loc[300,'open']=200;d.to_csv(p,index=False)
    with pytest.raises(AssertionError): load_inputs(tmp_path)
