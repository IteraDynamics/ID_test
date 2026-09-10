import numpy as np
import pandas as pd
from research.ml_development.design_audit import transformed,risk


def test_risk_transform_uses_only_known_volatility_and_roundtrips():
    p=pd.DataFrame({'target':[.02,-.01],'rv60':[.2,0.]})
    x=transformed(p,'risk')
    np.testing.assert_allclose(x.target/.01*risk(p),p.target)
    q=p.copy();q.target*=100
    np.testing.assert_array_equal(risk(q),risk(p))
    assert risk(p)[1]==.005


def test_rank_target_order_ties_and_date_isolation():
    p=pd.DataFrame({'date':[1]*8+[2]*8,'target':list(range(8))+[1]*8})
    t=transformed(p,'rank')
    assert t.target.iloc[0]==-.01 and t.target.iloc[7]==.01
    assert (t.target.iloc[8:]==0).all()
    p.loc[p.date==2,'target']=np.arange(8)*100
    np.testing.assert_array_equal(transformed(p,'rank').target.iloc[:8],t.target.iloc[:8])


def test_metadata_is_not_treated_as_a_model():
    from research.ml_development.design_audit import evaluate,MODELS
    dates=pd.to_datetime([f'{y}-01-08' for y in range(2018,2025)],utc=True)
    f=pd.DataFrame({'date':np.repeat(dates,8),'target':list(np.arange(8)*.001)*7,'risk_scale':.01,'past_mean':.001,'zero':0.})
    for kind in ['raw','risk','rank']:
        for m in MODELS:f[kind+'_'+m]=f.target
    f['fine_mlp16']=f.target
    m,ic=evaluate(f)
    assert 'risk_scale' not in set(m.variant)
    assert len(set(ic.variant))==12
    assert m.loc[(m.scope=='all')&(m.variant=='rank_ridge100'),'rank_ic'].iloc[0]==1.
