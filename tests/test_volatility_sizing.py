import numpy as np
import pandas as pd
import pytest
from research.volatility_sizing.study import add_benchmarks,size_at,DAILY_RISK
from research.volatility_sizing.replay import replay
from research.crypto_reversal.experiment import simulate,HOUR


def fixture():
    idx=pd.date_range('2020-01-01',periods=400,freq='h',tz='UTC')
    c=100*np.exp(np.sin(np.arange(400)/20)/20)
    return pd.DataFrame(dict(open=c,high=c*1.01,low=c*.99,close=c,volume=1.),index=idx)


def original(frame,cost=30):
    t=frame.index[300]
    orders={t:dict(available_at=str(t-HOUR),signal_start=str(t-5*HOUR))}
    return simulate(frame,orders,24,cost,frame.index[280],frame.index[-1])


def test_benchmark_formula_and_prefix_invariance():
    f=fixture();index=f.index+HOUR
    full=add_benchmarks(f,pd.DataFrame(index=index))
    short=add_benchmarks(f.iloc[:350],pd.DataFrame(index=index[:350]))
    pd.testing.assert_frame_equal(full.loc[short.index],short)
    t=full.index[-1]
    r=np.diff(np.log(f.close.iloc[-25:].to_numpy()))
    assert full.loc[t,'recent24']==pytest.approx(np.log(np.sum(r*r)))


@pytest.mark.parametrize('cost',[0,30,75])
def test_unit_weight_exact_original_curve(cost):
    f=fixture();o=original(f,cost)
    r=replay(f,o,{pd.Timestamp(t['entry_time']):1. for t in o.trades},cost)
    np.testing.assert_allclose(r.curve,o.curve,rtol=1e-10,atol=1e-10)


def test_half_weight_single_trade_math_and_zero_cash():
    f=fixture();o=original(f);entry=pd.Timestamp(o.trades[0]['entry_time'])
    r=replay(f,o,{entry:.5},30)
    assert r.curve.nav.iloc[-1]==pytest.approx(1+.5*o.trades[0]['net_return'])
    z=replay(f,o,{entry:0.},30)
    assert (z.curve.nav==1).all()
    assert not z.fills
    with pytest.raises(ValueError):replay(f,o,{entry:2.},30)


def test_future_missing_exit_defers_without_changing_entry():
    f=fixture().drop(pd.Timestamp('2020-01-14T12:00:00Z'))
    o=original(f)
    assert o.trades[0]['exit_delay_hours']==1
    r=replay(f,o,{pd.Timestamp(t['entry_time']):1. for t in o.trades},30)
    np.testing.assert_allclose(r.curve,o.curve,rtol=1e-10,atol=1e-10)


def test_size_timing_and_cap():
    t=pd.Timestamp('2020-01-03',tz='UTC')
    p=pd.DataFrame([dict(prediction=np.log((DAILY_RISK*2)**2),fit_at='2020-01-01T00:00:00Z',
        latest_training_label_end='2019-12-31T00:00:00Z')],index=[t])
    assert size_at(p,t)[0]==pytest.approx(.5)
    assert size_at(p,t-HOUR)[0]==0
    assert size_at(p,t+24*HOUR)[0]==0
    p['prediction']=np.log((DAILY_RISK/2)**2)
    assert size_at(p,t)[0]==1.
