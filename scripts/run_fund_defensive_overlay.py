#!/usr/bin/env python
"""IteraDynamics — Fund v1 defensive exposure overlay research runner.

This experiment tests whether a defensive overlay can improve the calibrated
Fund v1 portfolio by reducing exposure during high-risk market conditions.

This is not an alpha sleeve. It cannot add risk or increase exposure. It can
only multiply the existing Fund v1 sleeve returns by a defensive exposure
scale between MIN_SCALE and 1.0.

Design goal:
    Reduce max drawdown / improve Calmar / improve 2022 behavior without
    materially damaging CAGR or Sharpe.

This version prints both no-cost research overlays and cost-adjusted estimates
for the viable A/B schedules. It also adds yearly attribution and worst drawdown
window analysis so we can verify whether the overlay improves risk repeatedly
or only benefits from one lucky avoided event.

PowerShell:
python scripts\run_fund_defensive_overlay.py `
  --btc-data "data\btcusd_3600s_2019-01-01_to_2025-12-30.csv" `
  --eth-data "data\ethusd_3600s_2019-01-01_to_2025-12-30.csv" `
  --strategy trend_following_v8_ecap60_add80 `
  --calibrate `
  --fee 0.0006 `
  --base-slippage 3 `
  --slippage-vol-factor 50 `
  --rebalance-threshold 0.05
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s — %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("fund_defensive_overlay")

import numpy as np
import pandas as pd

from research.harness.backtest_engine import BacktestResult, run_backtest
from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.execution_model import ExecutionConfig
from research.harness.resampler import align_equity_curves, resample_ohlcv
from research.strategies import REGISTRY as STRATEGY_REGISTRY

DEFAULT_STRATEGY = "trend_following_v8_ecap60_add80"


@dataclass(frozen=True)
class SleeveConfig:
    label: str
    asset: str
    timeframe: str
    data_path: str
    calibrated: bool = False


@dataclass(frozen=True)
class DefensiveSchedule:
    name: str
    lookback_h: int
    dd_trigger: float
    dd_release: float
    trend_ema_h: int
    min_scale: float
    confirm_h: int
    release_confirm_h: int


SCHEDULES: list[DefensiveSchedule] = [
    DefensiveSchedule("A_light_dd20_trend", 90 * 24, 0.20, 0.12, 200 * 24, 0.75, 24, 48),
    DefensiveSchedule("B_medium_dd15_trend", 90 * 24, 0.15, 0.08, 200 * 24, 0.60, 24, 72),
    DefensiveSchedule("C_strong_dd12_trend", 90 * 24, 0.12, 0.06, 200 * 24, 0.40, 12, 96),
]
COST_ADJUST_SCHEDULES = {"A_light_dd20_trend", "B_medium_dd15_trend"}
ATTRIBUTION_NAMES = ["A_light_dd20_trend_costed", "B_medium_dd15_trend_costed"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Test defensive exposure reducer overlay on calibrated Fund v1", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--btc-data", required=True, help="Path to BTC/USD 1H OHLCV CSV")
    p.add_argument("--eth-data", required=True, help="Path to ETH/USD 1H OHLCV CSV")
    p.add_argument("--strategy", default=DEFAULT_STRATEGY)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--calibrate", action="store_true")
    p.add_argument("--calibrators-dir", default=None)
    p.add_argument("--fee", type=float, default=None)
    p.add_argument("--base-slippage", type=float, default=None)
    p.add_argument("--slippage-vol-factor", type=float, default=None)
    p.add_argument("--cooldown", type=int, default=None)
    p.add_argument("--rebalance-threshold", type=float, default=None)
    p.add_argument("--overlay-fee", type=float, default=None, help="Fee rate charged on defensive scale transitions. Defaults to --fee or env execution fee.")
    p.add_argument("--overlay-slippage-bps", type=float, default=3.0, help="Simple slippage bps charged on defensive scale transitions")
    p.add_argument("--out-dir", default=None)
    return p.parse_args()


def _perf(eq: pd.Series, label: str) -> dict[str, Any]:
    eq = eq.dropna()
    if len(eq) < 2:
        return {"label": label, "total_ret": 0.0, "cagr": 0.0, "max_dd": 0.0, "sharpe": 0.0, "calmar": 0.0, "ann_vol": 0.0}
    delta_s = (eq.index[-1] - eq.index[0]).total_seconds()
    n_gaps = len(eq) - 1
    bar_sec = delta_s / n_gaps if n_gaps > 0 and delta_s > 0 else 3600.0
    bars_per_year = 365.25 * 24 * 3600 / bar_sec
    initial = float(eq.iloc[0])
    final = float(eq.iloc[-1])
    years = len(eq) / bars_per_year
    total_ret = (final / initial - 1.0) * 100.0
    cagr = ((final / initial) ** (1.0 / max(years, 1 / 365)) - 1.0) * 100.0
    running_max = eq.cummax()
    max_dd = float(((eq - running_max) / running_max).min()) * 100.0
    bar_rets = eq.pct_change().dropna()
    std = float(bar_rets.std())
    ann_vol = std * np.sqrt(bars_per_year) * 100.0
    sharpe = float(bar_rets.mean() / std * np.sqrt(bars_per_year)) if std > 1e-12 else 0.0
    calmar = cagr / abs(max_dd) if abs(max_dd) > 1e-6 else 0.0
    return {"label": label, "total_ret": total_ret, "cagr": cagr, "max_dd": max_dd, "sharpe": sharpe, "calmar": calmar, "ann_vol": ann_vol}


def _year_return(eq: pd.Series, year: int) -> float | None:
    sl = eq[eq.index.year == year]
    if len(sl) < 2:
        return None
    return (float(sl.iloc[-1]) / float(sl.iloc[0]) - 1.0) * 100.0


def _year_maxdd(eq: pd.Series, year: int) -> float | None:
    sl = eq[eq.index.year == year]
    if len(sl) < 2:
        return None
    running_max = sl.cummax()
    return float(((sl - running_max) / running_max).min()) * 100.0


def _delta(perf: dict[str, Any], baseline: dict[str, Any]) -> dict[str, float]:
    return {"cagr": perf["cagr"] - baseline["cagr"], "max_dd": perf["max_dd"] - baseline["max_dd"], "sharpe": perf["sharpe"] - baseline["sharpe"], "calmar": perf["calmar"] - baseline["calmar"]}


def _drawdown_window(eq: pd.Series) -> dict[str, Any]:
    eq = eq.dropna()
    running_max = eq.cummax()
    dd = (eq - running_max) / running_max
    trough = dd.idxmin()
    peak = eq.loc[:trough].idxmax()
    post = eq.loc[trough:]
    recovered = post[post >= float(eq.loc[peak])]
    recovery = recovered.index[0] if len(recovered) else None
    duration_days = (trough - peak).total_seconds() / 86400.0
    recovery_days = None if recovery is None else (recovery - trough).total_seconds() / 86400.0
    return {
        "peak": str(peak),
        "trough": str(trough),
        "recovery": None if recovery is None else str(recovery),
        "max_dd_pct": float(dd.loc[trough] * 100.0),
        "peak_to_trough_days": float(duration_days),
        "trough_to_recovery_days": None if recovery_days is None else float(recovery_days),
    }


def _print_perf_row(d: dict[str, Any], delta: dict[str, float] | None = None, extra: str = "") -> None:
    delta_text = "" if delta is None else f" | ΔCAGR {delta['cagr']:+6.2f} ΔDD {delta['max_dd']:+6.2f} ΔSharpe {delta['sharpe']:+6.3f} ΔCalmar {delta['calmar']:+6.3f}"
    print(f"  {d['label']:<28} {d['total_ret']:>+9.2f}% {d['cagr']:>+8.2f}% {d['max_dd']:>9.2f}% {d['sharpe']:>8.3f} {d['calmar']:>8.3f} {d['ann_vol']:>8.2f}%{delta_text}{extra}")


def _load_calibrators(strategy_name: str, calibrate: bool, calibrators_dir: str | None) -> dict | None:
    if not calibrate:
        return None
    try:
        from research.ml.calibration.model_store import load_calibrator
        cal = load_calibrator(strategy_name, models_dir=calibrators_dir)
        if cal is not None and cal.is_fitted:
            log.info("Calibrator loaded for %s", strategy_name)
            return {strategy_name: cal}
        log.warning("No fitted calibrator found for %s — running uncalibrated", strategy_name)
    except ImportError:
        log.warning("ML calibration not available — running uncalibrated")
    return None


def _build_sleeves(args: argparse.Namespace) -> list[SleeveConfig]:
    return [SleeveConfig("BTC_1H", "BTC", "1H", args.btc_data, args.calibrate), SleeveConfig("BTC_4H", "BTC", "4H", args.btc_data, args.calibrate), SleeveConfig("ETH_1H", "ETH", "1H", args.eth_data, args.calibrate), SleeveConfig("ETH_4H", "ETH", "4H", args.eth_data, args.calibrate)]


def _load_data(args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for asset, path in (("BTC", args.btc_data), ("ETH", args.eth_data)):
        log.info("Loading %s data: %s", asset, path)
        df = load_ohlcv(path, start=args.start, end=args.end, asset=asset)
        for w in validate_ohlcv(df):
            log.warning("Data warning [%s]: %s", asset, w)
        log.info("Loaded %d bars  %s → %s  [%s]", len(df), df.index[0], df.index[-1], asset)
        out[asset] = df
    return out


def _run_sleeves(sleeves: list[SleeveConfig], raw_data: dict[str, pd.DataFrame], strategy_module: Any, capital: float, exec_config: ExecutionConfig, rebalance_threshold: float, calibrators: dict | None) -> dict[str, BacktestResult]:
    results: dict[str, BacktestResult] = {}
    for s in sleeves:
        df = raw_data[s.asset]
        if s.timeframe == "4H":
            df = resample_ohlcv(df, "4h")
            log.info("Resampled %s to 4H: %d bars  %s → %s", s.asset, len(df), df.index[0], df.index[-1])
        log.info("Running sleeve %s at full notional capital%s", s.label, " (calibrated)" if calibrators else "")
        results[s.label] = run_backtest(df=df, strategy_module=strategy_module, initial_capital=capital, exec_config=exec_config, rebalance_threshold=rebalance_threshold, asset=s.asset, calibrators=calibrators if s.calibrated else None)
    return results


def _normalised_sleeve_returns(results: dict[str, BacktestResult]) -> pd.DataFrame:
    curves = {label: result.equity_curve for label, result in results.items()}
    aligned = align_equity_curves(curves, base_freq="1h")
    return aligned.pct_change().fillna(0.0)


def _risk_index(raw_data: dict[str, pd.DataFrame]) -> pd.Series:
    common = raw_data["BTC"].index.intersection(raw_data["ETH"].index)
    btc = raw_data["BTC"].loc[common, "close"]
    eth = raw_data["ETH"].loc[common, "close"]
    idx = 0.5 * (btc / float(btc.iloc[0])) + 0.5 * (eth / float(eth.iloc[0]))
    idx.name = "crypto_index"
    return idx


def _defensive_scale(index: pd.Series, schedule: DefensiveSchedule) -> pd.Series:
    px = index.dropna()
    roll_high = px.rolling(schedule.lookback_h, min_periods=max(24, schedule.lookback_h // 10)).max()
    dd = 1.0 - (px / roll_high)
    ema = px.ewm(span=schedule.trend_ema_h, adjust=False).mean()
    below_trend = px < ema
    raw_risk = (dd >= schedule.dd_trigger) & below_trend
    raw_release = (dd <= schedule.dd_release) | (~below_trend)
    scale = np.ones(len(px), dtype=float)
    active = False
    risk_count = 0
    release_count = 0
    for i, (risk, release) in enumerate(zip(raw_risk.values, raw_release.values)):
        risk_count = risk_count + 1 if risk else 0
        release_count = release_count + 1 if release else 0
        if not active and risk_count >= schedule.confirm_h:
            active = True
            release_count = 0
        elif active and release_count >= schedule.release_confirm_h:
            active = False
            risk_count = 0
        scale[i] = schedule.min_scale if active else 1.0
    return pd.Series(scale, index=px.index, name=schedule.name)


def _apply_equal_weights(returns: pd.DataFrame, capital: float, label: str) -> pd.Series:
    equity = capital * (1.0 + returns.mean(axis=1)).cumprod()
    equity.name = label
    return equity


def _apply_defensive_overlay(returns: pd.DataFrame, scale: pd.Series, capital: float, label: str) -> pd.Series:
    common = returns.index.intersection(scale.index)
    s = scale.loc[common].shift(1)
    s.iloc[0] = scale.loc[common].iloc[0]
    equity = capital * (1.0 + returns.loc[common].mean(axis=1) * s).cumprod()
    equity.name = label
    return equity


def _apply_defensive_overlay_costed(returns: pd.DataFrame, scale: pd.Series, capital: float, label: str, overlay_fee: float, overlay_slippage_bps: float) -> tuple[pd.Series, dict[str, float]]:
    common = returns.index.intersection(scale.index)
    raw_scale = scale.loc[common]
    s = raw_scale.shift(1)
    s.iloc[0] = raw_scale.iloc[0]
    equal_ret = returns.loc[common].mean(axis=1)
    equity_vals: list[float] = []
    nav = float(capital)
    prev_scale = float(s.iloc[0])
    total_notional = total_fees = total_slip = 0.0
    transitions = 0
    for ts, ret in equal_ret.items():
        current_scale = float(s.loc[ts])
        if abs(current_scale - prev_scale) > 1e-9:
            notional = abs(current_scale - prev_scale) * nav
            fee = notional * overlay_fee
            slip = notional * overlay_slippage_bps / 10000.0
            nav -= fee + slip
            total_notional += notional
            total_fees += fee
            total_slip += slip
            transitions += 1
            prev_scale = current_scale
        nav *= (1.0 + float(ret) * current_scale)
        equity_vals.append(nav)
    eq = pd.Series(equity_vals, index=equal_ret.index, name=label)
    cost = {"transitions": float(transitions), "total_overlay_notional": total_notional, "total_overlay_fees": total_fees, "total_overlay_slippage": total_slip, "total_overlay_cost": total_fees + total_slip, "cost_pct_final_nav": ((total_fees + total_slip) / max(float(eq.iloc[-1]), 1e-9)) * 100.0}
    return eq, cost


def _save_outputs(out_dir: Path, baseline_eq: pd.Series, schedule_equities: dict[str, pd.Series], schedule_summaries: dict[str, Any], scales: dict[str, pd.Series], attribution_rows: list[dict[str, Any]], drawdown_rows: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"baseline_equal": baseline_eq, **schedule_equities}).to_csv(out_dir / "equity_curves.csv")
    pd.DataFrame(scales).to_csv(out_dir / "defensive_scales.csv")
    pd.DataFrame(attribution_rows).to_csv(out_dir / "yearly_attribution.csv", index=False)
    pd.DataFrame(drawdown_rows).to_csv(out_dir / "drawdown_windows.csv", index=False)
    schedule_summaries["yearly_attribution"] = attribution_rows
    schedule_summaries["drawdown_windows"] = drawdown_rows
    (out_dir / "summary.json").write_text(json.dumps(schedule_summaries, indent=2, default=str))


def main() -> None:
    args = parse_args()
    exec_config = ExecutionConfig.from_env()
    if args.fee is not None:
        exec_config.taker_fee_rate = args.fee
    if args.base_slippage is not None:
        exec_config.base_slippage_bps = args.base_slippage
    if args.slippage_vol_factor is not None:
        exec_config.slippage_vol_factor = args.slippage_vol_factor
    if args.cooldown is not None:
        exec_config.cooldown_bars = args.cooldown
    rebalance_threshold = args.rebalance_threshold if args.rebalance_threshold is not None else float(os.getenv("REBALANCE_THRESHOLD", "0.02"))
    overlay_fee = args.overlay_fee if args.overlay_fee is not None else exec_config.taker_fee_rate

    raw_data = _load_data(args)
    strategy_module = STRATEGY_REGISTRY[args.strategy]
    calibrators = _load_calibrators(args.strategy, args.calibrate, args.calibrators_dir)
    sleeves = _build_sleeves(args)
    sleeve_results = _run_sleeves(sleeves, raw_data, strategy_module, args.capital, exec_config, rebalance_threshold, calibrators)

    returns = _normalised_sleeve_returns(sleeve_results)
    idx = _risk_index(raw_data)
    common = returns.index.intersection(idx.index)
    returns = returns.loc[common]
    idx = idx.loc[common]

    baseline_eq = _apply_equal_weights(returns, args.capital, "baseline_equal")
    baseline_perf = _perf(baseline_eq, "Baseline Equal")

    print("\n" + "=" * 126)
    print("  FUND V1 DEFENSIVE OVERLAY — Exposure Reducer")
    print(f"  Period: {str(common[0])[:10]} → {str(common[-1])[:10]}  ({len(common):,} bars)")
    print(f"  Strategy: {args.strategy}  |  Calibrated: {bool(args.calibrate and calibrators)}")
    print(f"  Overlay cost estimate: fee={overlay_fee * 10000:.1f}bps  slippage={args.overlay_slippage_bps:.1f}bps")
    print("=" * 126)
    print(f"  {'Portfolio':<28} {'TotRet':>10} {'CAGR':>9} {'MaxDD':>10} {'Sharpe':>8} {'Calmar':>8} {'AnnVol':>9}  Deltas vs Equal")
    print("  " + "-" * 122)
    _print_perf_row(baseline_perf)

    schedule_equities: dict[str, pd.Series] = {}
    summaries: dict[str, Any] = {"baseline_equal": baseline_perf}
    scales: dict[str, pd.Series] = {}

    for schedule in SCHEDULES:
        scale = _defensive_scale(idx, schedule).loc[common]
        scales[schedule.name] = scale
        no_cost_eq = _apply_defensive_overlay(returns, scale, args.capital, schedule.name)
        schedule_equities[schedule.name] = no_cost_eq
        perf = _perf(no_cost_eq, schedule.name)
        risk_off_pct = float((scale < 0.999).mean() * 100.0)
        switches = int(np.sum(np.diff((scale < 0.999).astype(int)) != 0))
        _print_perf_row(perf, _delta(perf, baseline_perf), extra=f" | riskOff {risk_off_pct:4.1f}% switches {switches:3d}")
        entry: dict[str, Any] = {"no_cost_performance": perf, "no_cost_delta_vs_equal": _delta(perf, baseline_perf), "risk_off_pct": risk_off_pct, "switches": switches, "params": schedule.__dict__}
        if schedule.name in COST_ADJUST_SCHEDULES:
            cost_eq, cost_info = _apply_defensive_overlay_costed(returns, scale, args.capital, f"{schedule.name}_costed", overlay_fee, args.overlay_slippage_bps)
            schedule_equities[f"{schedule.name}_costed"] = cost_eq
            cost_perf = _perf(cost_eq, f"{schedule.name}_costed")
            _print_perf_row(cost_perf, _delta(cost_perf, baseline_perf), extra=f" | overlayCost ${cost_info['total_overlay_cost']:,.0f} transitions {int(cost_info['transitions'])}")
            entry["cost_adjusted_performance"] = cost_perf
            entry["cost_adjusted_delta_vs_equal"] = _delta(cost_perf, baseline_perf)
            entry["overlay_costs"] = cost_info
        summaries[schedule.name] = entry

    print("=" * 126)
    print("\n  2022 STRESS CHECK")
    print("  " + "-" * 86)
    print(f"  Baseline Equal             return={_year_return(baseline_eq, 2022):+7.2f}%  maxDD={_year_maxdd(baseline_eq, 2022):7.2f}%")
    for name, eq in schedule_equities.items():
        print(f"  {name:<26} return={_year_return(eq, 2022):+7.2f}%  maxDD={_year_maxdd(eq, 2022):7.2f}%")

    attribution_rows: list[dict[str, Any]] = []
    years = sorted(set(baseline_eq.index.year))
    print("\n  YEARLY ATTRIBUTION — COSTED CANDIDATES")
    print("  " + "-" * 98)
    print(f"  {'Year':<6} {'Candidate':<26} {'BaseRet':>9} {'CandRet':>9} {'ΔRet':>9} {'BaseDD':>9} {'CandDD':>9} {'ΔDD':>9}")
    for yr in years:
        base_r = _year_return(baseline_eq, yr)
        base_dd = _year_maxdd(baseline_eq, yr)
        for name in ATTRIBUTION_NAMES:
            if name not in schedule_equities:
                continue
            eq = schedule_equities[name]
            cand_r = _year_return(eq, yr)
            cand_dd = _year_maxdd(eq, yr)
            if base_r is None or base_dd is None or cand_r is None or cand_dd is None:
                continue
            row = {"year": yr, "candidate": name, "baseline_return_pct": base_r, "candidate_return_pct": cand_r, "delta_return_pct": cand_r - base_r, "baseline_maxdd_pct": base_dd, "candidate_maxdd_pct": cand_dd, "delta_maxdd_pct": cand_dd - base_dd}
            attribution_rows.append(row)
            print(f"  {yr:<6} {name:<26} {base_r:>+8.2f}% {cand_r:>+8.2f}% {cand_r-base_r:>+8.2f}% {base_dd:>8.2f}% {cand_dd:>8.2f}% {cand_dd-base_dd:>+8.2f}%")

    drawdown_rows = [{"portfolio": "baseline_equal", **_drawdown_window(baseline_eq)}]
    for name in ATTRIBUTION_NAMES:
        if name in schedule_equities:
            drawdown_rows.append({"portfolio": name, **_drawdown_window(schedule_equities[name])})
    print("\n  WORST DRAWDOWN WINDOWS")
    print("  " + "-" * 108)
    print(f"  {'Portfolio':<28} {'MaxDD':>9} {'Peak':<20} {'Trough':<20} {'Recovery':<20} {'P→T days':>9} {'T→R days':>9}")
    for row in drawdown_rows:
        rec = row['recovery'] if row['recovery'] is not None else 'unrecovered'
        trd = row['trough_to_recovery_days'] if row['trough_to_recovery_days'] is not None else float('nan')
        print(f"  {row['portfolio']:<28} {row['max_dd_pct']:>8.2f}% {row['peak'][:19]:<20} {row['trough'][:19]:<20} {rec[:19]:<20} {row['peak_to_trough_days']:>9.1f} {trd:>9.1f}")

    print("\n  LIMITATION")
    print("  " + "-" * 86)
    print("  This is still a research approximation. Cost-adjusted rows estimate scale")
    print("  transition costs but do not fully simulate live sleeve-level order routing.")

    run_id = f"fund_defensive_overlay_{str(common[0])[:10]}_{str(common[-1])[:10]}"
    out_dir = Path(args.out_dir) if args.out_dir else Path("artifacts") / run_id
    summaries["limitation"] = "Costed rows estimate defensive scale transition costs; not full live order routing."
    summaries["overlay_cost_assumptions"] = {"overlay_fee": overlay_fee, "overlay_slippage_bps": args.overlay_slippage_bps}
    _save_outputs(out_dir, baseline_eq, schedule_equities, summaries, scales, attribution_rows, drawdown_rows)
    log.info("Artifacts saved to: %s", out_dir)
    print(f"\n  Artifacts: {out_dir}")
    print("    equity_curves.csv  defensive_scales.csv  yearly_attribution.csv  drawdown_windows.csv  summary.json\n")


if __name__ == "__main__":
    main()
