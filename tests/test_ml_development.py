import numpy as np
import pandas as pd
import pytest
from research.ml_development.run import build_panel,split,select,estimator,CANDIDATES,SUMMARY,SEQUENCE
from scripts.run_ml_etf_risk_screen import ASSETS


def fixture():
    dates=pd.bdate_range('2013-12-02','2020-12-31',tz='UTC')
    return {a:pd.DataFrame({'open':100+np.arange(len(dates))*.01,'close':100+np.arange(len(dates))*.01,
                'volume':100.},index=dates) for a in ASSETS}


def test_target_five_session_open_to_open():
    fs=fixture();p=build_panel(fs);r=p.loc[p.asset=='SPY'].iloc[0];i=fs['SPY'].index.get_loc(r.date)
    assert r.target==pytest.approx(fs['SPY'].open.iloc[i+6]/fs['SPY'].open.iloc[i+1]-1)
    assert r.label_end==fs['SPY'].index[i+6]


def test_feature_future_canary_and_order():
    fs=fixture();base=build_panel(fs);boundary=pd.Timestamp('2018-01-01',tz='UTC')
    for d in fs.values():d.loc[boundary:,['open','close','volume']]*=100
    changed=build_panel(fs)
    cols=list(dict.fromkeys(SUMMARY+SEQUENCE))
    pd.testing.assert_frame_equal(base.loc[base.date<boundary,cols],changed.loc[changed.date<boundary,cols])
    assert SEQUENCE.index('return_19')<SEQUENCE.index('return_0')
    assert not base.loc[(base.date<boundary)&(base.label_end>=boundary),'target'].equals(changed.loc[(changed.date<boundary)&(changed.label_end>=boundary),'target'])


def test_split_purges_complete_outcome():
    p=build_panel(fixture());train,val=split(p,2018)
    assert train.label_end.max()<val.date.min()
    assert val.weekly.all() and (val.date.dt.year==2018).all()
    assert train.date.nunique()>=252


def test_selection_only_uses_supplied_inner_scores():
    scores=[{'candidate':n,'validation_rows':3,'validation_mse':1 if n=='ridge1' else 2} for n in CANDIDATES]
    assert select(scores)[0]=='ridge1'
    scores[0]['validation_mse']=3
    assert select(scores)[0]!='ridge1'


def test_neural_architecture_no_random_validation():
    m=estimator('sequence32').steps[-1][1]
    assert m.hidden_layer_sizes==(32,16) and m.early_stopping is False
    assert m.shuffle is False and m.random_state==17


def test_scaler_learns_only_fit_data():
    m=estimator('ridge1');x=np.array([[1.],[2.],[3.]])
    m.fit(x,[1,2,3]);m.predict([[1e9]])
    assert m.steps[0][1].mean_[0]==2.


def test_inner_validation_outcomes_cannot_cross_outer_boundary():
    from research.ml_development.run import inner_split
    p=build_panel(fixture());_,unpurged=split(p,2017);_,outer=split(p,2018)
    assert (unpurged.label_end>=outer.date.min()).any()  # Canary proves old procedure leaks.
    train,val=inner_split(p,2017,2018)
    assert val.label_end.max()<outer.date.min()
    assert train.label_end.max()<val.date.min()
