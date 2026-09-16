import numpy as np
import pandas as pd
import pytest
from research.regime_engine_ml.study import feature_frame,build_panel,train_mask,predict_fold,MODELS
from research.regime_engine_ml.run import filter_orders
from research.crypto_reversal.experiment import HOUR


def fixture(n=3000):
    rng=np.random.default_rng(123)
    c=100*np.exp(np.cumsum(rng.normal(0,.005,n)))
    return pd.DataFrame(dict(open=c,high=c*1.01,low=c*.99,close=c,volume=1.),
        index=pd.date_range('2018-01-01',periods=n,freq='h',tz='UTC'))


def test_feature_prefix_invariance():
    frame=fixture()
    full=feature_frame(frame,4)
    short=feature_frame(frame.iloc[:2800],4)
    pd.testing.assert_frame_equal(full.loc[short.index],short)
    changed=frame.copy()
    changed.iloc[2800:,:4]*=3
    pd.testing.assert_frame_equal(full.loc[short.index],feature_frame(changed,4).loc[short.index])


def test_target_alignment_and_future_gap_only_removes_label():
    frame=fixture()
    panel=build_panel(frame,4)
    t=panel.dropna().index[0]
    prior=frame.loc[t-HOUR,'close']
    values=frame.loc[t:t+23*HOUR,'close'].to_numpy()
    expected=np.log(np.square(np.diff(np.log(np.r_[prior,values]))).sum())
    assert panel.loc[t,'log_variance']==pytest.approx(expected)
    assert panel.loc[t,'downside']==float((values/prior-1).min()<=-.03)
    gapped=build_panel(frame.drop(t+5*HOUR),4)
    assert t in gapped.index
    assert pd.isna(gapped.loc[t,'downside'])
    assert pd.isna(gapped.loc[t,'log_variance'])


def test_training_label_maturity():
    panel=build_panel(fixture(),4)
    cutoff=panel.index[-5]
    selected=panel.loc[train_mask(panel,cutoff,'downside')]
    assert (selected.label_end<cutoff).all()
    assert cutoff-24*HOUR not in selected.index


@pytest.mark.parametrize('model',MODELS)
def test_model_predictions_ignore_test_labels(model):
    panel=build_panel(fixture(10000),4).dropna()
    train,test=panel.iloc[:250],panel.iloc[250:260].copy()
    p=predict_fold(train,test,model,'downside')
    test['downside']=1000.
    np.testing.assert_array_equal(p,predict_fold(train,test,model,'downside'))
    assert ((p>=0)&(p<=1)).all()


def test_trading_filter_no_future_or_stale_forecasts():
    t=pd.Timestamp('2020-01-03',tz='UTC')
    predictions=pd.DataFrame([dict(available_at=str(t),fit_at='2020-01-01T00:00:00Z',
        latest_training_label_end='2019-12-31T00:00:00Z',prediction=.1,training_mean=.2)])
    orders={t+HOUR:dict(available_at=str(t),signal_start=str(t-4*HOUR)),
            t:dict(available_at=str(t-HOUR),signal_start=str(t-5*HOUR)),
            t+25*HOUR:dict(available_at=str(t+24*HOUR),signal_start=str(t+20*HOUR))}
    assert list(filter_orders(orders,predictions))==[t+HOUR]
