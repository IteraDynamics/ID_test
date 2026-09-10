import numpy as np
import pandas as pd
from research.ml_development import breadth as b
from tests.test_ml_development import fixture


def test_eight_asset_identity_and_target():
    fs=fixture();base=fs['SPY']
    for a in b.ASSETS:fs[a]=base.copy()
    p=b.build_panel(fs)
    assert set(p.asset)==set(b.ASSETS)
    assert (p[list(b.ASSETS)].sum(axis=1)==1).all()
    for a in b.ASSETS:assert (p.loc[p.asset==a,a]==1).all()


def test_stopping_purge_and_outer_exclusion():
    p=b.build_panel(fixture());train,val=b.inner_split(p,2016,2018)
    sub,stop=b.stopping_split(train)
    assert sub.label_end.max()<stop.date.min()
    assert stop.label_end.max()<val.date.min()
    assert sub.date.nunique()>=252
    assert (train.label_end>=stop.date.min()).any()


def test_outer_targets_do_not_select_neural_epochs():
    # Synthetic small feature matrix with sufficient dates; no real-data fits.
    dates=pd.bdate_range('2010-01-01',periods=400,tz='UTC')
    t=pd.DataFrame({c:np.sin(np.arange(400)/20) for c in b.SUMMARY})
    t['date']=dates;t['label_end']=dates+pd.Timedelta(days=8)
    t['weekly']=np.arange(400)%5==0;t['target']=.001
    v=t.iloc[-10:].copy();v['date']=v.date+pd.Timedelta(days=100)
    x,s=b.fit('mlp16',t,v)
    v['target']=1000
    y,u=b.fit('mlp16',t,v)
    np.testing.assert_array_equal(x,y)
    assert s['selected_epoch']==u['selected_epoch']
    assert s['training_curve']==u['training_curve']
