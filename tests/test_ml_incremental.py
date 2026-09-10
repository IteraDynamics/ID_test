import numpy as np
import pandas as pd
import pytest
from research.ml_development.incremental import gated,slope,residual_fit,b


def test_gate_abstains_and_handles_costs_and_ties():
    assert gated(np.full(8,.004),.001).sum()==0
    assert gated(np.full(8,.009),.0025).sum()==0
    np.testing.assert_allclose(gated(np.full(8,.009),.001),np.full(8,.75/8))
    w=gated(np.array([.01,.009,.008,0,0,0,0,0]),.001)
    np.testing.assert_array_equal(w,np.r_[np.full(3,.25),np.zeros(5)])
    with pytest.raises(ValueError):gated(np.full(8,np.nan),.001)


def test_calibration_shrinks_or_disables_without_sign_flip():
    assert slope([1,2],[2,4])==1
    assert slope([1,2],[-1,-2])==0
    assert slope([1,2],[.5,1])==.5
    assert slope([0,0],[1,2])==0


def synthetic():
    rng=np.random.default_rng(77);dates=pd.bdate_range('2010-01-01',periods=410,tz='UTC');rows=[]
    for i in range(400):
        for j,a in enumerate(b.ASSETS):
            r={c:rng.normal() for c in b.SUMMARY[:8]};r.update({x:float(x==a) for x in b.ASSETS});r.update(asset=a,date=dates[i],label_end=dates[i+6],target=.001*j+.02*r['ret5']);rows.append(r)
    q=pd.DataFrame(rows);return q[q.label_end<dates[300]],q[q.date>=dates[300]]


def test_planted_incremental_signal_and_validation_outcome_canary():
    tr,va=synthetic();mean,res,static=residual_fit('ridge100',tr,va)
    assert np.mean((mean+res-va.target)**2)<.1*np.mean((mean-va.target)**2)
    assert np.mean((mean+res-va.target)**2)<np.mean((mean+static-va.target)**2)
    changed=va.copy();changed.target=1000
    actual=residual_fit('ridge100',tr,changed)
    for x,y in zip((mean,res,static),actual):np.testing.assert_array_equal(x,y)
    bad=tr.copy();bad.label_end=va.date.max()
    with pytest.raises(ValueError):residual_fit('ridge100',bad,va)
