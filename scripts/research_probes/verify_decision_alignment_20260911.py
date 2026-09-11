"""Read-only independent reconciliation of the corrected decision experiment."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd


def verify(root,inputs):
    report=json.loads((root/'report.json').read_text())
    for name,digest in report['files'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
    f=pd.read_csv(root/'forecasts.csv',float_precision='round_trip',parse_dates=['date','label_end'])
    fits=pd.read_csv(root/'fits.csv',parse_dates=['last_training_outcome','first_validation_signal','last_validation_outcome','outer_first_signal'])
    assert len(fits)==42 and (fits.last_training_outcome<fits.first_validation_signal).all()
    inner=fits[fits.stage=='inner'];assert (inner.last_validation_outcome<inner.outer_first_signal).all()
    assert not f.duplicated(['date','asset']).any() and (f.groupby('date').size()==8).all()
    frames={}
    for asset in [*sorted(f.asset.unique()),'BIL']:
        x=pd.read_csv(inputs/f'{asset}_1D.csv');x.index=pd.to_datetime(x.timestamp,utc=True)
        frames[asset]=x.loc['2013-12-02':'2024-12-31']
    dates=frames['BIL'].index
    assert (np.diff(dates.get_indexer(sorted(f.date.unique())))==5).all()
    assert (dates.get_indexer(f.label_end)-dates.get_indexer(f.date)==6).all()
    target_errors=[]
    for asset,g in f.groupby('asset'):
        entry=dates.get_indexer(g.date)+1;exit_=dates.get_indexer(g.label_end)
        price=frames[asset].open.to_numpy();bil=frames['BIL'].open.to_numpy()
        y=price[exit_]/price[entry]-bil[exit_]/bil[entry]
        target_errors.extend(np.abs(y-g.target))
    assert max(target_errors)<1e-12
    fm=pd.read_csv(root/'forecast_metrics.csv');mse_errors=[]
    for _,r in fm.iterrows():
        g=f if r.scope=='all' else f[f.date.dt.year!=2020] if r.scope=='excluding_2020' else f[f.date.dt.year==int(r.scope)]
        if r.asset!='pooled':g=g[g.asset==r.asset]
        mse_errors.append(abs(((g[r.variant]-g.target)**2).mean()-r.mse))
    assert max(mse_errors)<1e-12
    daily=pd.read_csv(root/'daily_ledger.csv',float_precision='round_trip',parse_dates=['date'])
    em=pd.read_csv(root/'economic_metrics.csv');ce_errors=[];nav_errors=[]
    for (scenario,policy),g in daily.groupby(['scenario','policy']):
        nav_errors.append(float(np.max(np.abs((1+g['return']).cumprod()-g.nav))))
        contribution=g.filter(like='_contribution').sum(axis=1)
        assert np.max(np.abs(contribution-g['return']))<1e-10
        assert g.date.max()==f.label_end.max() and g.exposure.iloc[-1]==0
        for _,r in em[(em.scenario==scenario)&(em.policy==policy)].iterrows():
            s=g if r.period=='all' else g[g.date.dt.year!=2020] if r.period=='excluding_2020' else g[g.date.dt.year==int(r.period)]
            ce=252*s['return'].mean()-1.5*252*s['return'].var(ddof=1)
            ce_errors.append(abs(ce-r.ce))
    assert len(daily.groupby(['scenario','policy']))==68
    assert max(nav_errors)<1e-10 and max(ce_errors)<1e-12
    final=daily.groupby(['scenario','policy']).tail(1).pivot(index='policy',columns='scenario',values='nav')
    assert (final.fixed_gross>=final.cost10-1e-10).all()
    assert (final.cost10>=final.fixed_cost25-1e-10).all()
    w=pd.read_csv(root/'target_weights.csv')
    selected=w[w.policy.str.startswith('opt:')]
    assert selected.forecast_volatility.max()<=.10000001
    asset_cols=[*sorted(f.asset.unique()),'BIL']
    assert np.max(np.abs(selected[asset_cols].sum(axis=1)-1))<1e-8
    assert selected[asset_cols[:-1]].max().max()<=.25000001
    assert (selected[asset_cols[:-1]].sum(axis=1)<=.75000001).all()
    return dict(status='PASS',artifact_hashes=len(report['files']),fit_boundaries=42,
                signals=f.date.nunique(),five_session_targets=len(f),ledgers=68,
                maximum_target_error=max(target_errors),maximum_mse_error=max(mse_errors),
                maximum_ce_error=max(ce_errors),maximum_nav_error=max(nav_errors),
                max_optimized_signal_volatility=selected.forecast_volatility.max())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--input-root',type=Path,required=True)
    a=p.parse_args();print(json.dumps(verify(a.results,a.input_root),indent=2))
