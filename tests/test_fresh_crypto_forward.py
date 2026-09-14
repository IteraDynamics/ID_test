"""Synthetic checks of forward timing, input integrity and portfolio accounting."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

import numpy as np
import pandas as pd
import pytest

from research import fresh_crypto_forward as run
from research import fresh_crypto_forward_data as data
from research import fresh_crypto_long_history as prior
from research.fresh_crypto_ml import models
from research.fresh_crypto_ml.features import Panel
from research.fresh_crypto_ml.portfolio import simulate


def market(end="2026-01-31"):
    dates = pd.date_range("2017-01-01",end,tz="UTC")
    t = np.arange(len(dates))
    frames = {}
    for asset,phase in (("BTC",0.),("ETH",.6)):
        close = 100*np.exp(.0003*t+.25*np.sin(t/53+phase)+.04*np.sin(t/7+phase))
        opening = np.r_[close[0],close[:-1]]*(1+.001*np.cos(t/13))
        frames[asset] = pd.DataFrame(dict(open=opening,high=np.maximum(opening,close)*1.002,
                                        low=np.minimum(opening,close)*.998,close=close,
                                        volume=10+np.cos(t/11+phase)),index=dates)
        frames[asset].index.name = "timestamp"
    return frames


@pytest.fixture(scope="module")
def panel():
    return Panel(market())


@pytest.fixture(scope="module")
def schedules(panel):
    return run.make_schedules(panel)


def test_forward_targets_equal_original_continuation_and_initial_state_is_carried(panel,schedules):
    orders,targets,decisions,first = schedules
    original,_,_ = prior.make_schedules(panel)
    assert panel.dates[first]==pd.Timestamp("2024-12-30",tz="UTC")
    assert len(orders)==20
    for policy in prior.policies():
        if policy.role=="benchmark":
            assert list(orders[policy.name])==[first]
        else:
            for t,(weights,mixture) in orders[policy.name].items():
                np.testing.assert_array_equal(weights,original[policy.name][t][0])
                assert mixture==original[policy.name][t][1]
    state = decisions[decisions.policy==run.CANDIDATES[0]]
    assert state.iloc[0].signal_bar_start=="2024-12-28 00:00:00+00:00"
    assert state.iloc[0].carried_before_initial_entry
    assert state.iloc[1].base_fill_time=="2025-01-06 00:00:00+00:00"
    assert not state.signal_index.eq(first).any()
    assert (pd.to_datetime(state.base_fill_time,utc=True).dt.weekday==0).all()
    first_targets = targets[targets.signal_index==first]
    assert len(first_targets)==20
    assert first_targets.feature_available.eq("2024-12-31 00:00:00+00:00").all()
    assert first_targets.base_fill_time.eq("2025-01-01 00:00:00+00:00").all()


def test_future_perturbation_changes_later_targets_but_not_earlier_targets_or_pnl(panel,schedules):
    boundary = panel.dates.get_loc(pd.Timestamp("2025-06-01",tz="UTC"))
    changed = market()
    for frame in changed.values():
        frame.iloc[boundary:,:4] *= 3
        frame.iloc[boundary:,4] *= 100
    other_panel = Panel(changed)
    orders,targets,decisions,first = schedules
    altered,new_targets,new_decisions,_ = run.make_schedules(other_panel)
    pd.testing.assert_frame_equal(targets[targets.signal_index<boundary],new_targets[new_targets.signal_index<boundary])
    pd.testing.assert_frame_equal(decisions[decisions.signal_index<boundary],new_decisions[new_decisions.signal_index<boundary])
    assert not targets[targets.signal_index>=boundary].equals(new_targets[new_targets.signal_index>=boundary])
    policy = next(p for p in prior.policies() if p.name==run.CANDIDATES[0])
    original_ledger = simulate(panel,orders[policy.name],policy,30.,0,first)
    altered_ledger = simulate(other_panel,altered[policy.name],policy,30.,0,first)
    pd.testing.assert_frame_equal(original_ledger[original_ledger.date<"2025-06-01"],
                                  altered_ledger[altered_ledger.date<"2025-06-01"])


@pytest.mark.parametrize("delay",[0,1])
def test_cash_start_benchmark_fee_identity_and_no_2026_reset(panel,schedules,delay):
    orders,_,_,first = schedules
    policy = next(p for p in prior.policies() if p.family=="btc_buy_hold")
    ledger = simulate(panel,orders[policy.name],policy,30.,delay,first)
    assert run.verify_ledger(ledger,panel,policy,30.,delay,first) is not None
    assert ledger.date.iloc[0]=="2025-01-01"
    assert ledger.executed.sum()==2
    assert not ledger[ledger.date=="2026-01-01"].executed.iloc[0]
    if delay:
        assert ledger.iloc[0]["return"]==0 and ledger.iloc[0].USD_weight==1
    before = ledger[ledger.date=="2025-12-31"].nav.iloc[0]
    after = ledger[ledger.date=="2026-01-01"].nav.iloc[0]
    day = panel.dates.get_loc(pd.Timestamp("2026-01-01",tz="UTC"))
    assert after/before==pytest.approx(panel.closes[day,0]/panel.closes[day-1,0])


@pytest.fixture
def local_inputs(tmp_path,monkeypatch):
    source,raw = tmp_path/"prior results",tmp_path/"raw local data"
    source.mkdir()
    raw.mkdir()
    pins,paths = {},{}
    for asset,frame in market().items():
        name = f"{asset}-USD.csv"
        frame.loc[:"2024-12-31"].to_csv(source/name,lineterminator="\n",float_format="%.17g")
        pins[name] = hashlib.sha256((source/name).read_bytes()).hexdigest()
        paths[asset] = raw/data.FILENAMES[asset]
        frame.to_csv(paths[asset],lineterminator="\n",float_format="%.17g")
    monkeypatch.setattr(prior,"EXPECTED_INPUTS",pins)
    (source/"report.json").write_text(json.dumps(dict(synthetic_data_used=False,reserved_2025_used=False,
                                                  commit="synthetic_source_fixture",files=pins)))
    identity = dict(commit="synthetic_fixture",code_sha256={},environment={},synthetic_data_used=True,protocol=run.protocol())
    return source,paths,identity


def test_preparation_locks_metadata_before_prices_and_preserves_reviewed_values(local_inputs,tmp_path,monkeypatch):
    source,paths,identity = local_inputs
    out = tmp_path/"prepared"
    out.mkdir()
    original_read = data.read_daily
    calls = []
    def check_plan(path,end):
        assert (out/"run_plan.json").is_file()
        assert json.loads((out/"run_plan.json").read_text())["last_evaluation_date"]=="2026-01-31"
        calls.append(path)
        return original_read(path,end)
    monkeypatch.setattr(data,"read_daily",check_plan)
    manifest = data.snapshot(source,paths,out,identity)
    frames,prepared = data.load_prepared(out,identity)
    original,_ = prior.load_source(source)
    assert len(calls)==2 and prepared==manifest
    assert prepared["prior_access_2026"]=="unknown" and not prepared["globally_pristine_oos_claim"]
    for asset in paths:
        pd.testing.assert_frame_equal(frames[asset].loc[:"2024-12-31"],original[asset],check_freq=False)
        assert prepared["inputs"][asset]["overlap_rows"]==2922


@pytest.mark.parametrize("field",["open","volume"])
def test_conflicting_development_history_is_rejected(local_inputs,tmp_path,field):
    source,paths,identity = local_inputs
    raw = pd.read_csv(paths["BTC"])
    raw.loc[400,field] *= 1.00001
    raw.to_csv(paths["BTC"],index=False)
    out = tmp_path/"out"
    out.mkdir()
    with pytest.raises(ValueError,match="disagrees with reviewed"):
        data.snapshot(source,paths,out,identity)
    assert (out/"run_plan.json").exists() and not (out/"prepared.json").exists()


@pytest.mark.parametrize("problem",["missing","duplicate","intraday","short_2025"])
def test_calendar_failures_stop_before_price_evaluation(local_inputs,problem):
    _,paths,_ = local_inputs
    path = paths["BTC"]
    raw = pd.read_csv(path)
    if problem=="missing": raw = raw.drop(index=3000)
    if problem=="duplicate": raw = pd.concat([raw,raw.iloc[[3000]]])
    if problem=="intraday": raw.loc[3000,"timestamp"] = "2025-03-20 12:00:00+00:00"
    if problem=="short_2025": raw = raw[raw.timestamp<"2025-12-31"]
    raw.to_csv(path,index=False)
    with pytest.raises(ValueError,match="complete"):
        data.scan(path)


def test_fixed_cap_and_future_bad_prices_ignored(tmp_path):
    frame = market("2026-09-10")["BTC"]
    frame.loc["2026-08-27":,:] = np.nan
    path = tmp_path/"BTC.csv"
    frame.to_csv(path)
    assert data.scan(path)["eligible_last_date"]=="2026-08-26"
    assert data.scan(path)["rows_after_fixed_cap"]==15
    actual = data.read_daily(path,data.END_CAP)
    assert actual.index[-1]==data.END_CAP and not actual.isna().any().any()


def test_common_end_is_earlier_file_and_no_interior_day_trimming(local_inputs,tmp_path):
    source,paths,identity = local_inputs
    raw = pd.read_csv(paths["ETH"])
    raw[raw.timestamp<="2026-01-20 00:00:00+00:00"].to_csv(paths["ETH"],index=False)
    out = tmp_path/"out"
    out.mkdir()
    manifest = data.snapshot(source,paths,out,identity,"already_inspected")
    frames,_ = data.load_prepared(out,identity)
    assert manifest["last_evaluation_date"]=="2026-01-20"
    assert manifest["inputs"]["BTC"]["rows_after_common_end_not_evaluated"]==11
    assert frames["BTC"].index.equals(frames["ETH"].index)
    assert manifest["prior_access_2026"]=="already_inspected"


@pytest.mark.parametrize("unit",["s","ms"])
def test_epoch_dates_supported(local_inputs,unit):
    _,paths,_ = local_inputs
    path = paths["BTC"]
    raw = pd.read_csv(path)
    dates = pd.to_datetime(raw.timestamp,utc=True)
    raw["timestamp"] = dates.map(lambda d:int(d.timestamp()*(1000 if unit=="ms" else 1)))
    raw.to_csv(path,index=False)
    assert data.scan(path)["eligible_last_date"]=="2026-01-31"


@pytest.mark.parametrize("column,value",[("close",0.),("volume",-1.),("high",.01)])
def test_invalid_forward_ohlcv_rejected(local_inputs,column,value):
    _,paths,_ = local_inputs
    raw = pd.read_csv(paths["BTC"])
    raw.loc[3000,column] = value
    raw.to_csv(paths["BTC"],index=False)
    with pytest.raises(ValueError,match="Invalid"):
        data.read_daily(paths["BTC"],pd.Timestamp("2026-01-31",tz="UTC"))


@pytest.mark.parametrize("name",["BTC-USD.csv","run_plan.json","source_report.json"])
def test_prepared_artifact_tampering_rejected(local_inputs,tmp_path,name):
    source,paths,identity = local_inputs
    out = tmp_path/"out"
    out.mkdir()
    data.snapshot(source,paths,out,identity)
    path = out/name
    path.write_bytes(path.read_bytes()+b"\n")
    with pytest.raises(ValueError,match="Prepared artifact changed"):
        data.load_prepared(out,identity)


def test_raw_file_changed_during_preparation_rejected(local_inputs,tmp_path,monkeypatch):
    source,paths,identity = local_inputs
    out = tmp_path/"out"
    out.mkdir()
    original = data.read_daily
    def mutate(path,end):
        frame = original(path,end)
        path.write_bytes(path.read_bytes()+b"\n")
        return frame
    monkeypatch.setattr(data,"read_daily",mutate)
    with pytest.raises(ValueError,match="changed during"):
        data.snapshot(source,paths,out,identity)


def test_prepared_code_identity_mismatch_rejected(local_inputs,tmp_path):
    source,paths,identity = local_inputs
    out = tmp_path/"out"
    out.mkdir()
    data.snapshot(source,paths,out,identity)
    with pytest.raises(ValueError,match="Prepared identity changed: commit"):
        data.load_prepared(out,dict(identity,commit="other_commit"))


def test_source_lookup_directory_zip_fallback_and_explicit_missing(tmp_path):
    artifacts = tmp_path/"artifacts"
    artifacts.mkdir()
    archive = artifacts/(data.SOURCE_RUNS[0]+".zip")
    archive.touch()
    assert data.resolve_source(None,tmp_path)==archive.resolve()
    assert data.resolve_source(archive.with_suffix(""),tmp_path)==archive.resolve()
    with pytest.raises(FileNotFoundError,match="Checked"):
        data.resolve_source(tmp_path/"missing",tmp_path)


def test_original_dependency_and_freeze_tampering_rejected(tmp_path,monkeypatch):
    run.verify_frozen_strategy()
    freeze = json.loads(run.FREEZE.read_text())
    for name in freeze["source_code_sha256"]:
        target = tmp_path/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(run.ROOT/name,target)
    monkeypatch.setattr(run,"ROOT",tmp_path)
    path = tmp_path/"research/fresh_crypto_ml/features.py"
    path.write_bytes(path.read_bytes()+b"\n# changed\n")
    with pytest.raises(ValueError,match="Frozen strategy dependency changed"):
        run.verify_frozen_strategy()
    new_freeze = tmp_path/"freeze.json"
    new_freeze.write_bytes(run.FREEZE.read_bytes()+b"\n")
    monkeypatch.setattr(run,"FREEZE",new_freeze)
    with pytest.raises(ValueError,match="Candidate freeze changed"):
        run.verify_frozen_strategy()


def test_full_synthetic_workflow_all_scenarios_no_models_and_zip_hashes(local_inputs,tmp_path,monkeypatch):
    def forbidden(*args,**kwargs):
        raise AssertionError("No ML fit permitted")
    monkeypatch.setattr(models,"fit_predict",forbidden)
    source,paths,identity = local_inputs
    out = tmp_path/"synthetic_forward"
    monkeypatch.setattr(run,"identity",lambda:identity)
    monkeypatch.setattr(sys,"argv",["forward","--prepare","--source-run",str(source),
                                    "--btc-csv",str(paths["BTC"]),"--eth-csv",str(paths["ETH"]),"--output-dir",str(out)])
    run.main()
    assert not (out/"report.json").exists()
    monkeypatch.setattr(sys,"argv",["forward","--evaluate-prepared","--output-dir",str(out)])
    run.main()
    report = json.loads((out/"report.json").read_text())
    assert report["status"]=="SYNTHETIC_MECHANICS_ONLY"
    assert (report["policy_count"],report["ledger_count"],report["model_fits"])==(20,80,0)
    assert report["first_evaluation_date"]=="2025-01-01" and report["last_evaluation_date"]=="2026-01-31"
    assert report["independent_buy_hold_checks"]==12 and report["corruption_canary_passed"]
    assert report["reserved_2025_used"] is False and report["monte_carlo_run"] is False
    metrics = pd.read_csv(out/"metrics.csv")
    assert set(metrics.period)=={"full_forward","2025","2026"}
    assert set(metrics[metrics.role=="candidate"].policy)==set(run.CANDIDATES)
    annual = pd.read_csv(out/"annual_returns.csv")
    assert set(annual[annual.year==2026].days)=={31}
    archive = Path(str(out)+".zip")
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,digest in report["files"].items():
            assert hashlib.sha256(z.read(name)).hexdigest()==digest
    with pytest.raises(FileExistsError):
        run.bundle(out)
    with pytest.raises(FileExistsError,match="new run"):
        run.evaluate(market(),out,dict(synthetic_data_used=True))


def test_market_requires_prepared_inputs_and_calendar_bounds(tmp_path):
    with pytest.raises(ValueError,match="Explicit"):
        run.evaluate(market(),tmp_path,{})
    with pytest.raises(ValueError,match="verified prepared"):
        run.evaluate(market(),tmp_path,dict(synthetic_data_used=False))
    with pytest.raises(ValueError,match="calendar bounds"):
        run.evaluate(market("2026-08-27"),tmp_path,dict(synthetic_data_used=True))
