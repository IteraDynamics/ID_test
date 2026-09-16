import numpy as np
import pandas as pd
import pytest
from research.volatility_incremental.study import FEATURES,MODELS,columns,predict,annual,compare


def fixture():
    rng=np.random.default_rng(44)
    idx=pd.date_range('2018-01-01',periods=740,freq='D',tz='UTC')
    f=pd.DataFrame(rng.normal(size=(len(idx),7)),index=idx,columns=FEATURES['augmented'])
    f['log_variance']=rng.normal(-6,.8,len(idx))
    f['label_end']=f.index+pd.Timedelta(days=1)
    return f


def test_matched_input_sets():
    for group in FEATURES:
        assert columns('linear_'+group)==columns('boosted_'+group)==FEATURES[group]


@pytest.mark.parametrize('model',MODELS)
def test_future_labels_and_unused_columns_cannot_change_predictions(model):
    f=fixture();train=f.iloc[:600];test=f.iloc[600:].copy()
    expected=predict(train,test,model)
    test['log_variance']=1e10;test['future_secret']=1e10
    np.testing.assert_array_equal(expected,predict(train,test,model))


def test_annual_maturity_and_common_population():
    f=fixture();forecasts=annual(f,'SYNTHETIC',4,years=[2020])
    cutoff=pd.Timestamp('2020-01-01',tz='UTC')
    assert (pd.to_datetime(forecasts.latest_training_label_end)<cutoff).all()
    assert forecasts.groupby('model').available_at.apply(list).apply(tuple).nunique()==1
    changed=f.copy();changed.loc[changed.index>=cutoff,'log_variance']+=100
    altered=annual(changed,'SYNTHETIC',4,years=[2020])
    np.testing.assert_array_equal(forecasts.prediction,altered.prediction)


def test_comparison_direction():
    rows=[dict(asset='X',timeframe=4,year='all',model=m,log_variance_mse=2.,variance_qlike=2.) for m in MODELS]
    rows[-1]['log_variance_mse']=1.
    c=compare(pd.DataFrame(rows))
    row=c[(c.candidate=='boosted_augmented')&(c.benchmark=='linear_augmented')&(c.metric=='log_variance_mse')].iloc[0]
    assert row.relative_improvement==.5
