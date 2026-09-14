"""Independent economic identities, time-boundary canaries and local-data checks."""
from __future__ import annotations

import json
import io
import urllib.parse

import numpy as np
import pandas as pd
import pytest

from research.fresh_crypto import data, engine, run


def frames(n=500):
    dates = pd.date_range(end="2024-12-31", periods=n, tz="UTC")
    t = np.arange(n)
    result = {}
    for asset, phase in (("BTC", 0.), ("ETH", .8)):
        close = 100 * np.exp(.0004*t + .2*np.sin(t/41 + phase))
        opening = np.r_[close[0], close[:-1]] * (1 + .0005*np.cos(t/7))
        result[asset] = pd.DataFrame(dict(open=opening, high=np.maximum(opening, close)*1.001,
                                         low=np.minimum(opening, close)*.999, close=close, volume=10.), index=dates)
        result[asset].index.name = "timestamp"
    return result


def raw_daily(n=2922):
    return frames(n)["BTC"].reset_index()


def test_utc_normalization_boundaries_and_future_canary():
    raw = raw_daily()
    reference, info = data.normalize(raw)
    future = raw.iloc[[-1]].copy()
    future["timestamp"] = pd.Timestamp("2025-01-01", tz="UTC")
    future[["open", "high", "low", "close", "volume"]] = np.nan
    augmented, after = data.normalize(pd.concat([raw, future], ignore_index=True))
    pd.testing.assert_frame_equal(reference, augmented)
    assert info["source_bar_seconds"] == 86400
    assert after["excluded_outside_development_rows"] == 1
    assert reference.index[-1] == pd.Timestamp("2024-12-31", tz="UTC")


@pytest.mark.parametrize("fault", ["gap", "duplicate", "ohlc", "nonfinite", "last_day", "shift"])
def test_bad_data_rejected(fault):
    raw = raw_daily()
    if fault == "gap":
        raw = raw.drop(index=500)
    elif fault == "duplicate":
        raw = pd.concat([raw, raw.iloc[[500]]], ignore_index=True)
    elif fault == "ohlc":
        raw.loc[500, "high"] = 0.
    elif fault == "nonfinite":
        raw.loc[500, "close"] = np.inf
    elif fault == "last_day":
        raw = raw.iloc[:-1]
    else:
        raw["timestamp"] += pd.Timedelta(hours=1)
    with pytest.raises(ValueError):
        data.normalize(raw)


@pytest.mark.parametrize("hours", [1, 4])
def test_complete_intraday_aggregation_and_missing_bar_rejection(hours):
    dates = pd.date_range("2017-01-01", "2024-12-31 23:00", freq=f"{hours}h", tz="UTC")
    raw = pd.DataFrame(dict(timestamp=dates, open=100., high=102., low=99., close=101., volume=2.))
    daily, info = data.normalize(raw)
    assert len(daily) == 2922
    assert (daily.volume == 2 * 24/hours).all()
    assert info["source_bar_seconds"] == hours * 3600
    with pytest.raises(ValueError, match="Missing/irregular"):
        data.normalize(raw.drop(index=1000))


def test_local_reuse_inventory_and_ambiguity(tmp_path, monkeypatch):
    source, out = tmp_path / "data", tmp_path / "out"
    source.mkdir()
    out.mkdir()
    for asset in data.ASSETS:
        raw_daily().to_csv(source / f"{asset}-USD.csv", index=False)
    def forbidden(*args):
        raise AssertionError("Offline reuse attempted a download")
    monkeypatch.setattr(data, "download", forbidden)
    loaded, records = data.load_inputs(source, {}, out)
    assert loaded["BTC"].index.equals(loaded["ETH"].index)
    assert records["BTC"]["source_sha256"] == data.sha(source / "BTC-USD.csv")
    # Different eligible histories must not be silently selected.
    changed = raw_daily()
    changed[["open", "high", "low", "close"]] *= 2
    changed.to_csv(source / "BTC_1D.csv", index=False)
    with pytest.raises(ValueError, match="Multiple different eligible BTC"):
        data.load_inputs(source, {}, out)
    data.load_inputs(source, {"BTC": source / "BTC-USD.csv"}, out)


def test_inventory_reports_both_assets_and_ignores_usdt(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    raw_daily(500).to_csv(tmp_path / "BTC_4H.csv", index=False)
    raw_daily().to_csv(tmp_path / "ETHUSDT.csv", index=False)
    assert not data.discover(tmp_path)["ETH"]
    with pytest.raises(ValueError, match="No eligible BTC.*No eligible ETH"):
        data.load_inputs(tmp_path, {}, out)
    record = json.loads((out / "data_inventory.json").read_text())
    assert len(record["files"]) == 1 and not record["files"][0]["eligible"]


def test_opt_in_download_batches_and_never_keeps_2025(tmp_path, monkeypatch):
    requests = []
    def fake_response(request, timeout):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
        start, stop = pd.Timestamp(query["start"][0]), pd.Timestamp(query["end"][0])
        assert start >= data.START and stop < data.END
        assert (stop-start).days <= 290 and query["granularity"] == ["86400"]
        requests.append((start, stop))
        # Endpoint overlaps and inclusive end buckets are intentional canaries.
        stamps = pd.date_range(start, stop.ceil("D"), freq="D")
        rows = [[int(t.timestamp()), 99., 102., 100., 101., 2.] for t in stamps]
        return io.BytesIO(json.dumps(rows[::-1]).encode())
    monkeypatch.setattr(data.urllib.request, "urlopen", fake_response)
    monkeypatch.setattr(data.time, "sleep", lambda _: None)
    path = data.download("BTC", tmp_path)
    frame, _ = data.normalize(pd.read_csv(path))
    assert len(requests) == 11 and len(frame) == 2922
    assert frame.index[-1] < data.END
    metadata = json.loads(path.with_suffix(".json").read_text())
    assert metadata["sha256"] == data.sha(path)
    with pytest.raises(FileExistsError):
        data.download("BTC", tmp_path)


@pytest.mark.parametrize("weights", [np.array([1., 0.]), np.array([0., 1.]), np.array([.5, .5])])
@pytest.mark.parametrize("delay", [0, 1])
def test_buy_hold_closed_form_includes_both_fees(weights, delay):
    market = frames()
    rate = .003
    ledger = engine.simulate(market, {365: weights}, rate * 10_000, delay)
    ratios = np.array([market[a].open.iloc[-1] / market[a].open.iloc[367+delay] for a in data.ASSETS])
    # Invest 1/(1+c), hold fixed units, then sell at (1-c).
    expected = float(weights @ ratios) * (1-rate)/(1+rate)
    assert ledger.nav.iloc[-1] == pytest.approx(expected, abs=2e-12)
    assert np.prod(1+ledger["return"]) == pytest.approx(expected, abs=2e-12)
    assert ledger.iloc[-1].risky_exposure == pytest.approx(0)
    assert ledger.accounting_residual.abs().max() < 1e-12


def test_weekends_latency_and_no_same_midnight_fill():
    market = frames()
    ledger = engine.simulate(market, {365: np.array([1., 0.])}, 0.)
    dates = pd.to_datetime(ledger.date)
    assert (dates.diff().dropna() == pd.Timedelta(days=1)).all()
    assert (dates.dt.dayofweek >= 5).any()
    fill = ledger[ledger.signal_bar_start != ""].iloc[0]
    assert pd.Timestamp(fill.fill_time) - pd.Timestamp(fill.signal_available) == pd.Timedelta(days=1)
    assert pd.Timestamp(fill.signal_available) - pd.Timestamp(fill.signal_bar_start) == pd.Timedelta(days=1)


def test_future_perturbation_cannot_change_earlier_targets_or_pnl():
    market = frames(620)
    altered = {a: f.copy() for a, f in market.items()}
    for frame in altered.values():
        frame.iloc[500:, :4] *= 4
    orders, _ = engine.schedules(market)
    changed, _ = engine.schedules(altered)
    for name in orders:
        for t in orders[name]:
            if t < 500:
                np.testing.assert_array_equal(orders[name][t], changed[name][t])
        original_ledger = engine.simulate(market, orders[name], 30.)
        changed_ledger = engine.simulate(altered, changed[name], 30.)
        stop = str(market["BTC"].index[500].date())
        pd.testing.assert_frame_equal(original_ledger[original_ledger.date < stop], changed_ledger[changed_ledger.date < stop])


def test_spot_risk_sizing_does_not_fill_abstention():
    covariance = np.eye(2) * .01
    np.testing.assert_array_equal(engine.size(np.array([.1, 0.]), covariance, .4), [.1, 0.])
    sized = engine.size(np.array([.5, .5]), np.eye(2), .2)
    assert np.sqrt(sized @ sized) == pytest.approx(.2)
    with pytest.raises(ValueError):
        engine.size(np.array([1., 1.]), covariance, None)
    with pytest.raises(ValueError):
        engine.simulate(frames(), {365: np.array([1.5, -.5])}, 30.)


def test_planted_trend_and_breakout_use_prior_extremes():
    market = frames()
    for frame in market.values():
        for field in ("open", "high", "low", "close"):
            frame[field] = np.arange(len(frame), dtype=float) + 100.
    orders, _ = engine.schedules(market)
    np.testing.assert_array_equal(orders["trend_ensemble_uncapped"][365], [.5, .5])
    np.testing.assert_array_equal(orders["breakout_uncapped"][365], [.5, .5])
    np.testing.assert_array_equal(orders["rotation_uncapped"][365], [1., 0.])
    for frame in market.values():
        for field in ("open", "high", "low", "close"):
            frame[field] = 700. - np.arange(len(frame), dtype=float)
    orders, _ = engine.schedules(market)
    for family in ("trend_ensemble", "breakout", "rotation"):
        np.testing.assert_array_equal(orders[f"{family}_uncapped"][365], [0., 0.])


def test_365_metrics_and_drawdown_initial_capital():
    ledger = engine.simulate(frames(), {365: np.array([1., 0.])}, 30.)
    m = engine.metrics(ledger)
    returns = ledger["return"].to_numpy()
    assert m["annual_volatility"] == pytest.approx(returns.std(ddof=1)*np.sqrt(365))
    assert m["cash_excess_sharpe"] == pytest.approx(returns.mean()/returns.std(ddof=1)*np.sqrt(365))
    wealth = np.r_[1., np.cumprod(1+returns)]
    assert m["max_drawdown"] == pytest.approx(np.min(wealth/np.maximum.accumulate(wealth)-1))
    years = (pd.Timestamp(ledger.date.iloc[-1])-pd.Timestamp(ledger.date.iloc[0])).days / 365.25
    assert m["cagr"] == pytest.approx(wealth[-1]**(1/years)-1)


def test_full_synthetic_pipeline_replays_all_policies(tmp_path):
    market = frames(560)
    report = run.evaluate(market, tmp_path, dict(synthetic_data_used=True))
    assert report["status"] == "SYNTHETIC_MECHANICS_ONLY"
    assert report["candidate_count"] == 9 and report["ledger_count"] == 64
    assert report["exact_replay_passed"]
    summary = pd.read_csv(tmp_path / "metrics.csv")
    assert len(summary[(summary.period == "full") & (summary.scenario == "base")]) == 16
    archive = run.bundle(tmp_path)
    assert archive.exists()
