import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

spec=importlib.util.spec_from_file_location('crop_learning',Path(__file__).parents[1]/'scripts/research_probes/crop_learning_test_20260910.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def release(date, years):
    rows=[]
    for asset in m.ASSETS:
        for year,stocks in years.items():
            for field,value in [('supply, total',100+stocks),('use, total',100),('ending stocks',stocks)]:
                rows.append(dict(source_file=date+'_test.xml',asset=asset,crop_year=f'{year}/{(year+1)%100:02d} Proj.',forecast_month=pd.Timestamp(date).strftime('%b'),report_month=pd.Timestamp(date).strftime('%B %Y'),field=field,value=value,unit='million_bushels'))
    return rows

def test_new_crop_does_not_subtract_old_crop():
    rows=release('2018-04-10',{2017:30})+release('2018-05-10',{2017:25,2018:40})+release('2018-06-12',{2017:20,2018:35})
    f=m.build_features(rows);new=f[f.release_date.str.startswith('2018-05')]
    assert new.revision.isna().all()
    june=f[f.release_date.str.startswith('2018-06')]
    assert np.allclose(june.revision,-.05)
    assert (june.crop_year==2018).all()

def test_conflicting_versions_fail():
    a=release('2018-04-10',{2017:30});b=release('2018-04-11',{2017:40})
    with pytest.raises(ValueError,match='Different selected'):m.build_features(a+b)

def test_future_release_canary():
    earlier=release('2018-04-10',{2017:30});future=release('2018-05-10',{2017:999})
    pd.testing.assert_frame_equal(m.build_features(earlier),m.build_features(earlier+future).iloc[:3].reset_index(drop=True))

def test_operator_matches_independent_sklearn_fit_and_ignores_future_targets():
    rng=np.random.default_rng(1);x=rng.normal(size=(90,7));y=rng.normal(size=90)
    tr=np.arange(60);te=np.arange(60,90);h=m.ridge_operator(x,tr,te)
    scaler=StandardScaler().fit(x[tr]);model=Ridge(alpha=10).fit(scaler.transform(x[tr]),y[tr])
    assert np.allclose(h@y[tr],model.predict(scaler.transform(x[te])),atol=1e-12)
    changed=y.copy();changed[te]=1e9
    assert np.array_equal(h@y[tr],h@changed[tr])

def test_fold_purge_and_full_release_groups():
    rng=np.random.default_rng(4);rows=[]
    for date in pd.date_range('2012-01-01','2024-12-01',freq='MS',tz='UTC'):
        for asset in m.ASSETS:
            rows.append(dict(release_date=date.isoformat(),exit_date=(date+pd.Timedelta(days=35)).isoformat(),asset=asset,
                             **{k:float(rng.normal()) for k in ['month_sin','month_cos','momentum21','momentum63','volatility63','stocks_use','revision']},revision_missing=0))
    panel=pd.DataFrame(rows);hs,ev,folds=m.operators(panel)
    releases=pd.to_datetime(panel.release_date);ends=pd.to_datetime(panel.exit_date)
    for h in hs:
        for i in ev:
            train=np.flatnonzero(h[i])
            assert (ends.iloc[train]<releases.iloc[i]).all()
        assert np.allclose(h[ev].sum(1),1)
    assert all(f['test_rows']%3==0 for f in folds)
