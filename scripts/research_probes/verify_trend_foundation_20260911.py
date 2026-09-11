"""Independent arithmetic and target-limit checks of the fixed trend baseline."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd


def verify(root):
    r=json.loads((root/'report.json').read_text())
    for name,digest in r['files'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
    d=pd.read_csv(root/'daily_ledger.csv',float_precision='round_trip',parse_dates=['date']);e=pd.read_csv(root/'economic_metrics.csv',float_precision='round_trip')
    w=pd.read_csv(root/'target_weights.csv',float_precision='round_trip',parse_dates=['signal_date'])
    assert not w.duplicated(['signal_date','policy','asset']).any()
    assert w.signal_date.dt.year.min()==2018 and w.signal_date.dt.year.max()==2024
    assert w.groupby(['signal_date','policy']).size().eq(13).all()
    assert np.max(np.abs(w.groupby(['signal_date','policy']).weight.sum()-1))<1e-12
    assert w[w.asset!='BIL'].weight.max()<=.15+1e-12
    assert w.forecast_volatility.max()<=.10+1e-10
    contrib=[x for x in d if x.endswith('_contribution')];weights=[x for x in d if x.endswith('_weight')]
    assert len(contrib)==len(weights)==13
    errors=[];ce_errors=[];path_errors=[];rows=[];calendars=[]
    for (scenario,policy),g in d.groupby(['scenario','policy']):
        assert g.date.is_monotonic_increasing and not g.date.duplicated().any()
        calendars.append(tuple(g.date));prior=np.r_[1.,g.nav.to_numpy()[:-1]]
        errors.append(float(np.max(np.abs(np.cumprod(1+g['return'])-g.nav))))
        assert np.max(np.abs(g[contrib].sum(axis=1)-g['return']))<1e-10
        assert g[weights].iloc[-1].sum()==0
        dollars=g[contrib].multiply(prior,axis=0).sum()
        assert abs(dollars.sum()-(g.nav.iloc[-1]-1))<1e-10
        for asset,value in dollars.items():rows.append(dict(scenario=scenario,policy=policy,asset=asset.removesuffix('_contribution'),net_gain_per_initial_dollar=value))
        for _,m in e[(e.scenario==scenario)&(e.policy==policy)].iterrows():
            x=g if m.period=='all' else g[g.date.dt.year!=2020] if m.period=='excluding_2020' else g[g.date.dt.year==int(m.period)]
            ce_errors.append(abs(252*x['return'].mean()-1.5*252*x['return'].var(ddof=1)-m.ce))
            if m.period!='excluding_2020':
                path=np.r_[1.,(1+x['return']).cumprod()]
                path_errors.extend([abs(path[-1]**(252/len(x))-1-m.cagr),abs((path/np.maximum.accumulate(path)-1).min()-m.maximum_drawdown)])
    assert len(calendars)==20 and len(set(calendars))==1
    assert max(errors)<1e-10 and max(ce_errors)<1e-12 and max(path_errors)<1e-12
    final=d.groupby(['scenario','policy']).tail(1).pivot(index='policy',columns='scenario',values='nav')
    assert (final.gross>=final.cost5).all() and (final.cost5>=final.cost10).all() and (final.cost10>=final.cost25).all()
    return dict(status='PASS',artifact_hashes=len(r['files']),ledgers=20,assets=13,signals=int(w[w.policy=='trend'].signal_date.nunique()),
                maximum_nav_error=max(errors),maximum_ce_error=max(ce_errors),maximum_path_metric_error=max(path_errors),
                common_start=str(d.date.min()),common_end=str(d.date.max()),mechanical_tests_passed=4),pd.DataFrame(rows)


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--results',type=Path,required=True);x=a.parse_args()
    result,_=verify(x.results);print(json.dumps(result,indent=2))
