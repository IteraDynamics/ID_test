"""Synthetic mechanics only: these tests make no market-profitability claim."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.fresh_discovery.accounting import Scenario, rebalance, simulate
from research.fresh_discovery.data import ASSETS, REQUEST, load_snapshot, normalize, sha, write_json
from research.fresh_discovery.metrics import metrics, pareto_flags
from research.fresh_discovery.run import first_signal, mechanics_canary, run_screen
from research.fresh_discovery.strategies import Features, make_schedules, policies, size_target


def synthetic_frames(n=340, seed=471):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2007-06-01", periods=n)
    common = rng.normal(.0003, .008, (n, 1))
    returns = common + rng.normal(0, .004, (n, len(ASSETS)))
    returns[:, -1] = rng.normal(.00008, .00003, n)
    closes = 100 * np.exp(np.cumsum(returns, axis=0))
    opens = closes * np.exp(rng.normal(0, .001, closes.shape))
    return {asset: pd.DataFrame(dict(open=opens[:, j], high=np.maximum(opens[:, j], closes[:, j]) * 1.001,
                                    low=np.minimum(opens[:, j], closes[:, j]) * .999, close=closes[:, j]),
                                index=dates)
            for j, asset in enumerate(ASSETS)}


def flat_frames(n=258):
    frames = synthetic_frames(n)
    for frame in frames.values():
        frame.loc[:, :] = 100.
    return frames


def raw_frame(frame):
    raw = frame.rename(columns=str.title).reset_index(names="date")
    raw["Adj Close"] = raw.Close
    raw["Volume"] = 1_000_000
    return raw


def test_rebalance_matches_independent_algebra_and_round_trip():
    cost = .002
    values, cash, fees, _ = rebalance(np.array([0.]), 1., np.array([1.]), cost)
    assert values[0] == pytest.approx(1 / (1 + cost), abs=1e-12)
    assert cash == pytest.approx(0, abs=1e-12)
    assert fees[0] == pytest.approx(cost / (1 + cost), abs=1e-12)
    _, cash, _, _ = rebalance(values, cash, np.array([0.]), cost)
    assert cash == pytest.approx((1 - cost) / (1 + cost), abs=1e-12)


def test_rebalance_target_identity_for_long_short_and_leverage():
    values, cash, fees, trades = rebalance(np.array([.2, -.1, .5]), .4,
                                           np.array([1.2, -.5, 0.]), .001)
    nav = values.sum() + cash
    np.testing.assert_allclose(values / nav, [1.2, -.5, 0.], atol=1e-12)
    assert nav == pytest.approx(1 - fees.sum())
    assert cash == pytest.approx(.4 - trades.sum() - fees.sum())


def test_accounting_canary_is_live():
    assert mechanics_canary() == {"insolvent_accounting_rejected": True}


@pytest.mark.parametrize("values,cash,weights,cost", [
    ([2.], -3., [1.], .001), ([1.], 0., [np.nan], .001),
    ([1.], 0., [1.], -1.), ([1.], 0., [1000.], .01),
])
def test_bad_accounting_states_fail(values, cash, weights, cost):
    with pytest.raises(ValueError):
        rebalance(np.array(values), cash, np.array(weights), cost)


def test_open_execution_timing_costs_and_terminal_gap():
    frames = flat_frames(256)
    spy = frames["SPY"]
    # At signal close: 100. Entry at 120: the 20% entry gap cannot be captured.
    spy.iloc[253] = [120., 132., 120., 132.]
    spy.iloc[254] = [150., 150., 150., 150.]
    spy.iloc[255] = [160., 999., 160., 999.]  # exit at open: no terminal intraday gain
    w = np.zeros(len(ASSETS)); w[0] = 1
    result = simulate(frames, {252: w}, Scenario("zero", 0, 0, 0, funding_base=False), 252)
    assert result.nav.iloc[-1] == pytest.approx(160 / 120)
    assert result["return"].iloc[0] == pytest.approx(.1)
    assert result.signal_date.iloc[0] == str(spy.index[252].date())
    assert result.terminal_liquidation.sum() == 1
    assert result.gross_risky_exposure.iloc[-1] == 0
    delayed = simulate(frames, {252: w}, Scenario("delay", 0, 0, 0, 1, False), 252)
    assert delayed.nav.iloc[0] == 1
    assert delayed.nav.iloc[-1] == pytest.approx(160 / 150)
    cost = .001
    costly = simulate(frames, {252: w}, Scenario("cost", cost * 10000, 0, 0, funding_base=False), 252)
    assert costly.nav.iloc[-1] == pytest.approx(160 / 120 * (1-cost) / (1+cost))


def test_calendar_day_short_borrow_and_financing_are_not_free():
    frames = flat_frames(256)
    dates = frames["SPY"].index
    w = np.zeros(len(ASSETS)); w[0] = -.5; w[-1] = .5
    result = simulate(frames, {252: w}, Scenario("borrow", 0, .10, .20, funding_base=False), 252)
    expected = .5 * .10 * (dates[255] - dates[253]).days / 365
    assert result.nav.iloc[-1] == pytest.approx(1 - expected)
    # Restricted short proceeds may not cancel the long financing debit.
    w[:] = 0; w[0] = 1.5; w[1] = -.5
    result = simulate(frames, {252: w}, Scenario("levered", 0, 0, .10, funding_base=False), 252)
    first_accrual = .5 * .10 * (dates[254] - dates[253]).days / 365
    second_accrual = (.5 + first_accrual) * .10 * (dates[255] - dates[254]).days / 365
    assert result.nav.iloc[-1] == pytest.approx(1 - first_accrual - second_accrual)
    assert result.funding_cost.sum() > 0


def test_adjusted_prices_include_distribution_once():
    frames = flat_frames(256)
    raw = raw_frame(frames["SPY"])
    # A 1% ex-dividend drop, fully offset by the distribution in total-return data.
    raw.loc[:253, "Adj Close"] = 99.
    raw.loc[254:, ["Open", "High", "Low", "Close", "Adj Close"]] = 99.
    frames["SPY"] = normalize(raw, "SPY")
    w = np.zeros(len(ASSETS)); w[0] = 1
    result = simulate(frames, {252: w}, Scenario("zero", 0, 0, 0, funding_base=False), 252)
    assert result.nav.iloc[-1] == pytest.approx(1)


@pytest.mark.parametrize("fault", ["duplicate", "unsorted", "missing", "nan", "zero", "range", "holdout"])
def test_invalid_source_rejected(fault):
    raw = raw_frame(synthetic_frames()["SPY"])
    if fault == "duplicate": raw.loc[1, "date"] = raw.loc[0, "date"]
    if fault == "unsorted": raw = raw.iloc[::-1]
    if fault == "missing": raw = raw.drop(columns="Adj Close")
    if fault == "nan": raw.loc[3, "Close"] = np.nan
    if fault == "zero": raw.loc[3, "Volume"] = 0
    if fault == "range": raw.loc[3, "High"] = .001
    if fault == "holdout": raw.loc[len(raw)-1, "date"] = pd.Timestamp("2025-01-02")
    with pytest.raises(ValueError): normalize(raw, "SPY")


def test_future_data_does_not_change_earlier_signals_or_accounting():
    frames = synthetic_frames()
    altered = {a: f.copy() for a, f in frames.items()}
    for j, frame in enumerate(altered.values()):
        frame.iloc[310:] *= 1.1 + j / 50
    first = first_signal(frames)
    _, original, _ = make_schedules(frames, first)
    _, changed, _ = make_schedules(altered, first)
    for name in original:
        for t in original[name]:
            if t < 310:
                np.testing.assert_array_equal(original[name][t], changed[name][t])
    scenario = Scenario("causal", 5, .01, .015)
    a = simulate(frames, original["trend_pullback_5_g150"], scenario, first)
    b = simulate(altered, changed["trend_pullback_5_g150"], scenario, first)
    pd.testing.assert_frame_equal(a[a.date < str(frames["SPY"].index[310].date())],
                                  b[b.date < str(frames["SPY"].index[310].date())])
    assert not np.array_equal(a.nav.to_numpy(), b.nav.to_numpy())


def test_features_detect_planted_relative_momentum_and_pullback():
    frames = flat_frames(340)
    for j, asset in enumerate(ASSETS[:-1]):
        curve = 100 * np.exp(np.arange(340) * .0001 * (j+1))
        frames[asset].loc[:, :] = curve[:, None] * np.ones((1, 4))
    features = Features(frames)
    momentum = features.raw("dual_momentum", 126, 300)
    assert set(np.flatnonzero(momentum)) == {7, 8, 9}  # strongest three macro ETFs
    frames["SPY"].iloc[300, :] *= .995
    pullback = Features(frames).raw("trend_pullback", 3, 300)
    assert pullback[0] > 0
    assert Features(frames).raw("trend_only", 0, 300)[0] >= pullback[0]


def test_sector_market_hedge_and_target_limits():
    frames = synthetic_frames()
    f = Features(frames)
    t = 300
    base = f.raw("sector_reversal", 5, t)
    trailing = f.returns[t-63:t]
    beta = np.cov(trailing[:, :-1], rowvar=False)[:, 0] / trailing[:, 0].var(ddof=1)
    assert base @ beta == pytest.approx(0, abs=1e-12)
    target, risk = size_target(base, f.covariance(t), 1.5)
    assert np.abs(target[:-1]).sum() <= 1.5 + 1e-12
    assert risk <= .15 + 1e-12
    assert target[-1] == pytest.approx(max(0, 1 - target[:-1].clip(min=0).sum()))
    _, schedules, _ = make_schedules(frames, first_signal(frames))
    for p in policies():
        for w in schedules[p.name].values():
            assert np.abs(w[:-1]).sum() <= p.gross_cap + 1e-12


def test_abstention_not_normalized_back_to_full_exposure():
    base = np.r_[.05, np.zeros(len(ASSETS)-2)]
    w, _ = size_target(base, np.eye(len(base)) * .01, 1.5)
    assert w[0] == pytest.approx(.075)
    assert w[-1] == pytest.approx(.925)


def test_metrics_include_initial_loss_and_benchmark_excess():
    n = 3
    frame = pd.DataFrame(dict(date=["2020-01-02", "2020-01-03", "2020-01-06"],
                              **{"return": [-.1, 0, .1]}, turnover=np.zeros(n),
                              gross_risky_exposure=np.ones(n), net_risky_exposure=np.ones(n),
                              rebalance=[True, False, True], execution_cost=np.zeros(n),
                              funding_cost=np.zeros(n), borrow_cost=np.zeros(n)))
    result = metrics(frame, np.array([.001, .001, .001]), np.array([-.05, 0, .05]))
    assert result["max_drawdown"] == pytest.approx(-.1)
    assert result["longest_underwater_sessions"] == 3
    assert result["excess_sharpe"] < 0
    assert result["spy_beta"] == pytest.approx(2.)


def test_pareto_uses_all_three_objectives():
    frame = pd.DataFrame(dict(scenario=["base"]*3, period=["full"]*3,
                              cagr=[.1, .2, .3], excess_sharpe=[1, 2, 1.5],
                              max_drawdown=[-.2, -.1, -.3]))
    assert pareto_flags(frame).pareto_cagr_sharpe_drawdown.tolist() == [False, True, True]


def test_snapshot_hash_and_calendar_contract(tmp_path):
    dates = pd.bdate_range("2007-06-01", "2024-12-31")
    raw = pd.DataFrame(dict(date=dates, Open=100., High=101., Low=99., Close=100.,
                            **{"Adj Close": 100.}, Volume=1_000_000))
    files = {}
    for asset in ASSETS:
        csv, meta = tmp_path / f"{asset}.csv", tmp_path / f"{asset}.json"
        raw.to_csv(csv, index=False)
        write_json(meta, dict(asset=asset, request=REQUEST, csv_sha256=sha(csv), rows=len(raw)))
        files[asset] = dict(csv_sha256=sha(csv), manifest_sha256=sha(meta))
    write_json(tmp_path / "snapshot.json", dict(assets=list(ASSETS), request=REQUEST, files=files))
    frames, _ = load_snapshot(tmp_path)
    assert len(frames) == len(ASSETS)
    # A missing session must still fail after the file/manifest hashes are updated.
    csv, meta = tmp_path / "QQQ.csv", tmp_path / "QQQ.json"
    raw.drop(index=10).to_csv(csv, index=False)
    write_json(meta, dict(asset="QQQ", request=REQUEST, csv_sha256=sha(csv), rows=len(raw)-1))
    files["QQQ"] = dict(csv_sha256=sha(csv), manifest_sha256=sha(meta))
    write_json(tmp_path / "snapshot.json", dict(assets=list(ASSETS), request=REQUEST, files=files))
    with pytest.raises(ValueError, match="calendar differs"):
        load_snapshot(tmp_path)
    (tmp_path / "SPY.csv").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_snapshot(tmp_path)


def test_complete_synthetic_screen_is_deterministic_and_no_overwrite(tmp_path):
    frames = synthetic_frames(432)
    identity = {"data": {"status": "SYNTHETIC_MECHANICS_ONLY_NOT_MARKET_EVIDENCE"}}
    a, b = tmp_path / "a", tmp_path / "b"
    report_a = run_screen(frames, a, identity)
    report_b = run_screen(frames, b, identity)
    assert report_a["policies"] == 28
    assert report_a["candidates"] == 20
    assert report_a["ledgers"] == 112
    assert report_a["reserved_2025_used"] is False
    assert report_a["max_accounting_residual"] < 1e-10
    for path in a.glob("*.csv"):
        assert path.read_bytes() == (b / path.name).read_bytes(), path.name
    assert json.loads((a / "report.json").read_text()) == json.loads((b / "report.json").read_text())
    with pytest.raises(FileExistsError): run_screen(frames, a, identity)
