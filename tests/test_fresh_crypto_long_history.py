"""Fixed-rule equivalence, causal timing and reusable result inputs on synthetic data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
import pytest

from research import fresh_crypto_long_history as run
from research.fresh_crypto_ml import models, portfolio
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


@pytest.mark.parametrize("first", [365, 1093])
def test_all_fixed_targets_and_decisions_match_previous_builder(panel, first, monkeypatch):
    selected = run.policies()
    assert len(selected)==20
    assert sum(p.role=="candidate" for p in selected)==8
    assert sum(p.role=="control" for p in selected)==8
    assert sum(p.role=="benchmark" for p in selected)==4
    monkeypatch.setattr(portfolio, "policies", lambda:selected)
    _, reference, reference_decisions = portfolio.make_schedules(panel, pd.DataFrame(), first)
    _, actual, actual_decisions = run.make_schedules(panel, first)
    pd.testing.assert_frame_equal(actual, reference)
    columns = ["policy", "signal_index", "signal_bar_start", "mixture"]
    pd.testing.assert_frame_equal(actual_decisions[columns], reference_decisions[columns])


@pytest.mark.parametrize("agreement,ratio,expected", [
    (2/3,1.25,0.), (2/3-1e-12,1.25,1.), (2/3,1.25+1e-12,1.),
    (1.,1.1,0.), (0.,1.,1.), (1.,2.,1.)])
def test_state_rule_preserves_exact_threshold_boundaries(agreement, ratio, expected):
    assert run.state_mixture(agreement, ratio)==expected


def test_weekly_state_choices_and_first_signal_availability(panel):
    _, targets, decisions = run.make_schedules(panel)
    d = decisions[decisions.policy=="state_rule_vol20_exact"]
    assert d.iloc[0].signal_bar_start=="2018-01-01 00:00:00+00:00"
    assert d.iloc[0].feature_available=="2018-01-02 00:00:00+00:00"
    assert d.iloc[0].base_fill_time=="2018-01-03 00:00:00+00:00"
    assert (pd.to_datetime(d.base_fill_time.iloc[1:], utc=True).dt.weekday==0).all()
    t = targets[targets.policy=="state_rule_vol20_exact"]
    changes = t[t.mixture.ne(t.mixture.shift())]
    assert set(changes.signal_index)<=set(d.signal_index)
    assert (pd.to_datetime(t.base_fill_time, utc=True)-pd.to_datetime(t.feature_available, utc=True)==pd.Timedelta(days=1)).all()


def test_future_prices_and_volume_cannot_change_prior_fixed_targets(panel):
    boundary = 800
    changed = market()
    for frame in changed.values():
        frame.iloc[boundary:, :4] *= 3
        frame.iloc[boundary:, 4] *= 100
    _, original, original_decisions = run.make_schedules(panel)
    _, altered, altered_decisions = run.make_schedules(Panel(changed))
    pd.testing.assert_frame_equal(original[original.signal_index<boundary], altered[altered.signal_index<boundary])
    pd.testing.assert_frame_equal(original_decisions[original_decisions.signal_index<boundary],
                                  altered_decisions[altered_decisions.signal_index<boundary])
    assert not original[original.signal_index>=boundary].equals(altered[altered.signal_index>=boundary])


def test_default_lookup_and_explicit_missing_directory_zip_fallback(tmp_path):
    artifacts = tmp_path/"artifacts"
    artifacts.mkdir()
    original = artifacts/(run.SOURCE_RUNS[1]+".zip")
    original.touch()
    assert run.resolve_source(None, tmp_path)==original.resolve()
    latest = artifacts/run.SOURCE_RUNS[0]
    latest.mkdir()
    assert run.resolve_source(None, tmp_path)==latest.resolve()
    external = tmp_path/"with spaces"/"moved results"
    external.parent.mkdir()
    sibling = Path(str(external)+".zip")
    sibling.touch()
    assert run.resolve_source(external, tmp_path)==sibling.resolve()
    with pytest.raises(FileNotFoundError, match="Checked"):
        run.resolve_source(tmp_path/"explicitly_missing", tmp_path)


@pytest.fixture
def source(tmp_path, monkeypatch):
    # Synthetic data deliberately replaces the pinned hashes only inside this fixture.
    root = tmp_path/"prior results"
    root.mkdir()
    expected = {}
    for asset, frame in market("2024-12-31").items():
        path = root/f"{asset}-USD.csv"
        frame.to_csv(path, lineterminator="\n", float_format="%.17g")
        expected[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(run, "EXPECTED_INPUTS", expected)
    (root/"report.json").write_text(json.dumps(dict(synthetic_data_used=False, reserved_2025_used=False,
                                                  commit="synthetic_loader_fixture", files=expected)))
    return root


def test_result_directory_and_zip_load_identical_inputs(source, tmp_path):
    archive = tmp_path/"source.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for path in source.iterdir():
            z.write(path, path.name)
    folder_frames, _ = run.load_source(source)
    out = tmp_path/"out"
    out.mkdir()
    zip_frames, identity = run.load_source(archive, out)
    for asset in ("BTC", "ETH"):
        pd.testing.assert_frame_equal(folder_frames[asset], zip_frames[asset])
        assert len(zip_frames[asset])==2922
        assert (out/f"{asset}-USD.csv").read_bytes()==(source/f"{asset}-USD.csv").read_bytes()
    assert identity["downloads"]==0 and (out/"source_report.json").is_file()


def test_corrupt_price_bytes_are_rejected_before_evaluation(source):
    path = source/"BTC-USD.csv"
    path.write_bytes(path.read_bytes()+b"\n")
    with pytest.raises(ValueError, match="differs from"):
        run.load_source(source)


@pytest.mark.parametrize("flag", ["synthetic_data_used", "reserved_2025_used"])
def test_ineligible_source_flags_fail(source, flag):
    path = source/"report.json"
    report = json.loads(path.read_text())
    report[flag] = True
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="pre-2025"):
        run.load_source(source)


def test_no_future_calendar_or_unlabelled_synthetic_run(tmp_path):
    with pytest.raises(ValueError, match="pre-2025"):
        run.evaluate(market("2025-01-01"), tmp_path, dict(synthetic_data_used=True))
    with pytest.raises(ValueError, match="Explicit"):
        run.evaluate(market("2018-03-31"), tmp_path, {})
    with pytest.raises(ValueError, match="full reviewed"):
        run.evaluate(market("2018-03-31"), tmp_path, dict(synthetic_data_used=False))


def test_full_synthetic_workflow_reconciles_without_any_ml_fit(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("This fixed-rule experiment must never fit a model")
    monkeypatch.setattr(models, "fit_predict", forbidden)
    frames = market("2018-03-31")
    report = run.evaluate(frames, tmp_path, dict(synthetic_data_used=True))
    assert report["status"]=="SYNTHETIC_MECHANICS_ONLY"
    assert (report["policy_count"], report["ledger_count"], report["model_fits"])==(20,80,0)
    assert report["first_evaluation_date"]=="2018-01-03"
    assert report["exact_replay_passed"] and report["independent_buy_hold_checks"]==12
    assert report["reserved_2025_used"] is False and report["monte_carlo_run"] is False
    ledger = pd.read_csv(tmp_path/"daily_ledger.csv", float_precision="round_trip")
    one = ledger[(ledger.policy=="btc_buy_hold") & (ledger.scenario=="base")].copy()
    one.loc[one.index[0], "return"] += .001
    policy = next(p for p in run.policies() if p.name=="btc_buy_hold")
    with pytest.raises(ValueError, match="wealth reconstruction"):
        run.verify_ledger(one, Panel(frames), policy, 30., 0)
    archive = run.bundle(tmp_path)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and "specification.md" in z.namelist()
        for name, digest in report["files"].items():
            assert hashlib.sha256(z.read(name)).hexdigest()==digest
        assert not any("fit_records" in name or "predictions" in name for name in z.namelist())
    with pytest.raises(FileExistsError):
        run.bundle(tmp_path)
