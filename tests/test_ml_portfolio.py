import numpy as np
import pandas as pd
import pytest
from research.ml_development.portfolio import top_weights,limit_risk,covariance,ledger,ALL_ASSETS


def test_ties_have_no_asset_order_bias():
    np.testing.assert_allclose(top_weights(np.zeros(8)),np.full(8,.75/8))
    scores=np.array([3,2,2,2,0,0,0,0]);w=top_weights(scores)
    assert w[0]==.25
    np.testing.assert_allclose(w[1:4],np.full(3,.5/3))
    np.testing.assert_allclose(top_weights(scores[::-1]),w[::-1])


def test_total_risk_includes_cash_proxy_and_limits():
    cov=np.diag([.09]*8+[.0001]);w=limit_risk(top_weights(np.arange(8)),cov)
    assert np.sqrt(w@cov@w)<=.1+1e-12 and w[:8].sum()<.75
    assert w.sum()==pytest.approx(1) and w.min()>=0
    with pytest.raises(ValueError):limit_risk(np.ones(8)*.09375,np.eye(9))


def test_covariance_does_not_use_future_prices():
    rng=np.random.default_rng(4);x=np.exp(np.cumsum(rng.normal(0,.01,(400,9)),axis=0));y=x.copy();y[301:]*=100
    np.testing.assert_array_equal(covariance(x,300),covariance(y,300))
    assert not np.allclose(covariance(x,302),covariance(y,302))


def frames():
    ix=pd.bdate_range('2020-01-01',periods=20,tz='UTC');d=pd.DataFrame({'open':100.,'close':100.},index=ix)
    return {a:d.copy() for a in ALL_ASSETS}


def test_nine_asset_round_trip_and_liquidation_cost():
    fs=frames();w=np.r_[np.full(8,.75/8),.25]
    d=ledger(fs,{2:w,7:w},12,.001,0)
    assert d.nav.iloc[-1]==pytest.approx((1-.001)/(1+.001),abs=1e-12)
    assert d.bil_fraction.iloc[-1]==0 and d.cash_fraction.iloc[-1]==1
    np.testing.assert_allclose(d[[a+'_contribution' for a in ALL_ASSETS]].sum(axis=1),d['return'],atol=1e-12)


def test_bil_returns_and_gap_execution_are_booked():
    fs=frames();fs['BIL'].iloc[4:]=110.;w=np.r_[np.zeros(8),1.]
    normal=ledger(fs,{2:w},12,0,0);delayed=ledger(fs,{2:w},12,0,1)
    assert normal.nav.iloc[-1]==pytest.approx(1.1)
    assert delayed.nav.iloc[-1]==pytest.approx(1.)
    assert normal.exposure.max()==0
