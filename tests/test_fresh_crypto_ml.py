"""Causal fitting, counterfactual economics and continuous-inventory checks."""
from __future__ import annotations

import hashlib
import json
import zipfile

import numpy as np
import pandas as pd
import pytest

from research.fresh_crypto import engine as baseline
from research.fresh_crypto.data import WARMUP
from research.fresh_discovery.accounting import rebalance
from research.fresh_crypto_ml import data, design, labels, models, portfolio, run
from research.fresh_crypto_ml.features import Panel


def market(end="2020-03-31"):
    dates = pd.date_range("2017-01-01", end, tz="UTC")
    t = np.arange(len(dates))
    result = {}
    for asset, phase in (("BTC", 0.), ("ETH", .6)):
        close = 100*np.exp(.0003*t+.25*np.sin(t/53+phase)+.04*np.sin(t/7+phase))
        opening = np.r_[close[0], close[:-1]]*(1+.001*np.cos(t/13))
        result[asset] = pd.DataFrame(dict(open=opening, high=np.maximum(opening, close)*1.002,
                                        low=np.minimum(opening, close)*.998, close=close,
                                        volume=10+np.cos(t/11+phase)), index=dates)
        result[asset].index.name = "timestamp"
    return result


@pytest.fixture(scope="module")
def panel():
    return Panel(market())


@pytest.fixture(scope="module")
def label_frame(panel):
    return labels.make_labels(panel)


def test_features_and_experts_are_causal_and_match_existing_rules(panel):
    frames = market()
    old, _ = baseline.schedules(frames)
    for profile in design.PROFILES:
        for family, path in (("trend_ensemble", panel.trend[profile]), ("equal_weight", panel.allocation[profile])):
            for t, weights in old[f"{family}_vol{int(profile*100)}"].items():
                np.testing.assert_allclose(path[t], weights, atol=1e-14, rtol=1e-13)
    boundary = 800
    changed = market()
    for frame in changed.values():
        frame.iloc[boundary:, :4] *= 3
        frame.iloc[boundary:, 4] *= 100
    perturbed = Panel(changed)
    np.testing.assert_array_equal(panel.x[:boundary], perturbed.x[:boundary])
    for p in design.PROFILES:
        np.testing.assert_array_equal(panel.trend[p][:boundary], perturbed.trend[p][:boundary])
    assert panel.x.shape[1]==15 and np.isfinite(panel.x[WARMUP:]).all()


@pytest.mark.parametrize("rate", [0., .003, .0075])
def test_vectorized_fee_solver_against_scalar_inventory_accounting(rate):
    rng = np.random.default_rng(37)
    values = rng.uniform(.05,.3,size=(40,2))
    cash = 1-values.sum(axis=1)
    weights = rng.uniform(0,.45,size=(40,2))
    positions, remaining = labels.rebalance_many(values,cash,weights,rate)
    for i in range(len(cash)):
        target,new_cash,_,_ = rebalance(values[i],cash[i],weights[i],rate)
        np.testing.assert_allclose(positions[i],target,atol=1e-13)
        assert remaining[i]==pytest.approx(new_cash,abs=1e-13)


@pytest.mark.parametrize("rate", [0., .003, .0075])
def test_counterfactual_label_independent_growth_and_round_trip_fee_identity(rate):
    frames = market()
    for frame in frames.values():
        price = 100*1.001**np.arange(len(frame))
        frame[["open","high","low","close"]] = np.repeat(price[:,None],4,axis=1)
    p = Panel(frames)
    targets = np.tile([.5,.5],(len(p.dates),1))
    result = labels.terminal_wealth(p,targets,np.array([365,500,900]),rate)
    expected = 1.001**14*(1-rate)/(1+rate)
    np.testing.assert_allclose(result,expected,atol=2e-12)
    with pytest.raises(ValueError):
        labels.terminal_wealth(p,targets,np.array([len(p.dates)-10]),rate)


def test_labels_have_exact_execution_and_availability_boundaries(panel,label_frame):
    for row in label_frame.itertuples():
        assert pd.Timestamp(row.entry_time)==panel.dates[row.signal_index+2]
        assert pd.Timestamp(row.label_available)==panel.dates[row.signal_index+16]
        assert row.target==pytest.approx(np.log(row.trend_terminal_nav/row.allocation_terminal_nav),abs=1e-15)
    last = label_frame.signal_index.max()
    assert last+16==len(panel.dates)-1


def test_maturity_rejects_boundary_ties_and_future_outcomes(label_frame):
    cutoff = pd.Timestamp("2019-12-31",tz="UTC")
    selected = models.eligible_labels(label_frame[label_frame.profile==.2],cutoff)
    assert (pd.to_datetime(selected.label_available,utc=True)<cutoff).all()
    tied = label_frame[pd.to_datetime(label_frame.label_available,utc=True)==cutoff]
    assert len(tied)>0 and not set(tied.signal_index)&set(selected.signal_index)
    with pytest.raises(ValueError,match="matured training"):
        models.eligible_labels(tied,cutoff,minimum=1)


def test_future_labels_do_not_change_fits_or_predictions(panel,label_frame):
    predictions, fits = models.walk_forward(panel,label_frame)
    altered = label_frame.copy()
    cutoff = pd.Timestamp(fits[0]["fit_time"])
    altered.loc[pd.to_datetime(altered.label_available,utc=True)>=cutoff,"target"] += 1000
    replay, replay_fits = models.walk_forward(panel,altered)
    pd.testing.assert_frame_equal(predictions,replay)
    assert fits==replay_fits
    for fit in fits:
        assert pd.Timestamp(fit["latest_label_available"])<pd.Timestamp(fit["fit_time"])


def test_train_only_preprocessing_and_future_price_perturbation(panel,label_frame):
    predictions, fits = models.walk_forward(panel,label_frame)
    changed = market()
    boundary = pd.Timestamp("2020-02-01",tz="UTC")
    for frame in changed.values():
        frame.loc[boundary:, ["open","high","low","close"]] *= 10000
    altered = Panel(changed)
    second, other_fits = models.walk_forward(altered,labels.make_labels(altered))
    before = pd.to_datetime(predictions.feature_available,utc=True)<boundary
    pd.testing.assert_frame_equal(predictions[before],second[before])
    assert fits==other_fits
    transform = models.Transform().fit(np.arange(1500,dtype=float).reshape(100,15))
    saved = transform.record()
    transform.apply(np.full((2,15),1e12))
    assert saved==transform.record()


def test_quarterly_refits_admit_newly_matured_outcomes():
    p=Panel(market("2020-06-30"))
    target=labels.make_labels(p)
    original,fits=models.walk_forward(p,target)
    q1=pd.Timestamp(next(f["fit_time"] for f in fits if f["quarter"]=="2020Q1"))
    q2=pd.Timestamp(next(f["fit_time"] for f in fits if f["quarter"]=="2020Q2"))
    altered=target.copy()
    available=pd.to_datetime(altered.label_available,utc=True)
    altered.loc[(available>=q1)&(available<q2),"target"] += .1
    changed,records=models.walk_forward(p,altered)
    first=original.fit_id.str.endswith("2020Q1")
    pd.testing.assert_frame_equal(original[first],changed[first])
    later=(original.model=="constant")&original.fit_id.str.endswith("2020Q2")
    assert (changed[later].predicted_relative_log_return.to_numpy()>original[later].predicted_relative_log_return.to_numpy()).all()
    assert all(pd.Timestamp(f["latest_label_available"])<pd.Timestamp(f["fit_time"]) for f in records)


@pytest.mark.parametrize("kind", ["ridge","boosted"])
def test_models_recover_planted_predictive_information(kind):
    rng = np.random.default_rng(209)
    x = rng.normal(size=(1200,15))
    y = .03*x[:,0]+rng.normal(scale=.001,size=1200)
    pred,_ = models.fit_predict(kind,x[:900],y[:900],x[900:])
    null = np.full(300,y[:900].mean())
    assert np.mean((pred-y[900:])**2)<.25*np.mean((null-y[900:])**2)
    # Constant outcomes must not generate synthetic market-predictive variation.
    flat,_ = models.fit_predict(kind,x[:900],np.zeros(900),x[900:])
    np.testing.assert_allclose(flat,0.,atol=1e-12)


def test_cost_hurdle_retains_uncertain_mixture():
    assert portfolio.select_mixture(.0001,.5,1.)[0]==.5
    assert portfolio.select_mixture(.02,.5,1.)[0]==1.
    assert portfolio.select_mixture(-.02,1.,1.)[0]==0.
    assert portfolio.select_mixture(.002,.5,1.)[0]==.5


def test_execution_band_skips_small_changes_but_preserves_risk_reductions():
    assert portfolio.should_trade(np.array([.1,.1]),np.array([.105,.1]),np.eye(2),.4,.02)==(False,"inside_band")
    assert portfolio.should_trade(np.array([.3,.1]),np.array([.29,.1]),np.eye(2),.2,.02)==(True,"risk_reduction")
    assert portfolio.should_trade(np.array([.005,0.]),np.array([0.,0.]),np.eye(2),.2,.02)==(True,"full_exit")


@pytest.mark.parametrize("delay", [0,1])
def test_continuous_ledger_matches_audited_engine_and_includes_weekends(panel,delay):
    first = models.first_signal(panel)
    policy = next(p for p in design.policies() if p.name=="trend_vol20_exact")
    schedule = {t:(panel.trend[.2][t],1.) for t in range(first,len(panel.dates)-3)}
    result = portfolio.simulate(panel,schedule,policy,30.,delay,first)
    reference = baseline.simulate(market(),{t:w for t,(w,m) in schedule.items()},30.,delay,first)
    for column in ("nav","return","execution_cost","BTC_weight","ETH_weight","USD_weight"):
        np.testing.assert_allclose(result[column],reference[column],atol=2e-12,rtol=2e-12)
    assert (pd.to_datetime(result.date).diff().dropna()==pd.Timedelta(days=1)).all()
    assert result.risky_exposure.iloc[-1]==0
    assert np.prod(1+result["return"])==pytest.approx(result.nav.iloc[-1],abs=1e-12)
    actual=result[(result.signal_bar_start!="") & result.executed]
    assert (pd.to_datetime(actual.fill_time,utc=True)-pd.to_datetime(actual.feature_available,utc=True)==pd.Timedelta(days=1+delay)).all()


def test_band_first_delayed_entry_executes_even_when_tiny(panel):
    first=models.first_signal(panel)
    policy=next(p for p in design.policies() if p.name=="trend_vol20_band2")
    ledger=portfolio.simulate(panel,{first:(np.array([.001,0.]),1.)},policy,30.,1,first)
    assert ledger.iloc[1].executed and ledger.iloc[1].BTC_weight>0


def test_input_reuse_is_hash_pinned_and_rejects_corruption(tmp_path,monkeypatch):
    source,out=tmp_path/"source",tmp_path/"out"
    source.mkdir();out.mkdir()
    frames=market("2024-12-31")
    expected={}
    for asset,frame in frames.items():
        path=source/f"{asset}-USD.csv"
        frame.to_csv(path,lineterminator="\n",float_format="%.17g")
        expected[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(data,"EXPECTED_INPUTS",expected)
    (source/"report.json").write_text(json.dumps(dict(synthetic_data_used=False,commit=design.SOURCE_COMMIT,reserved_2025_used=False,files=expected)))
    loaded,identity=data.load_source(source,out)
    assert identity["downloads"]==0 and len(loaded["BTC"])==2922
    (source/"BTC-USD.csv").write_text("corrupt")
    with pytest.raises(ValueError,match="differs from"):
        data.load_source(source,out)


def test_complete_synthetic_pipeline_replays_models_and_portfolios(tmp_path):
    report=run.evaluate(market(),tmp_path,dict(synthetic_data_used=True))
    assert report["status"]=="SYNTHETIC_MECHANICS_ONLY"
    assert report["policy_count"]==32 and report["ledger_count"]==128
    assert report["distinct_learned_fits"]==4 and report["learned_fit_executions_including_replay"]==8
    assert report["exact_replay_passed"] and report["immature_label_canary_passed"]
    decisions=pd.read_csv(tmp_path/"mixture_decisions.csv")
    for profile in (20,40):
        left=decisions[decisions.policy==f"ridge_vol{profile}_exact"].mixture.to_numpy()
        right=decisions[decisions.policy==f"ridge_vol{profile}_band2"].mixture.to_numpy()
        np.testing.assert_array_equal(left,right)
    archive=run.bundle(tmp_path)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and "fit_records.json" in z.namelist()
