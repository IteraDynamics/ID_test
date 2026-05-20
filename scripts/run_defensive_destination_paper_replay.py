#!/usr/bin/env python
"""Paper-only replay prototype for DefensiveDestinationAllocator.

This script performs an isolated historical replay of the validated
state-confirmed GLD/BIL defensive destination allocator. It emits paper artifacts
only and does not import or invoke runtime brokers, live governors, or execution
code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from research.harness.metrics import compute_metrics
from scripts.run_risk_off_trigger_sweep import _buy_hold_curve, _load_baseline_cache, _normalized_returns
from scripts.run_state_confirmed_risk_off_sweep import _load_close

State = Literal["NORMAL", "RISK_OFF_DESTINATION"]
CostModel = Literal["full_reallocation", "destination_only"]
IntentApplication = Literal["before_return", "after_return"]


@dataclass(frozen=True)
class AllocatorConfig:
    allocator_id: str
    enabled: bool
    mode: str
    governed_budget_id: str
    trigger_dd: float
    release_dd: float
    release_mode: str
    btc_sma_window: int
    crypto_scale: float
    gld_weight: float
    bil_weight: float
    friction_bps: float
    cost_model: CostModel
    intent_application: IntentApplication
    fill_timing: str
    allow_weekend_etf_fills: bool


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(blob).hexdigest()[:16]}"


def _day(ts: Any) -> pd.Timestamp:
    return pd.Timestamp(ts).tz_localize(None).normalize()


def _iso_ts(ts: Any) -> str:
    return _day(ts).strftime("%Y-%m-%dT00:00:00Z")


def _iso_date(ts: Any) -> str:
    return _day(ts).date().isoformat()


def _fmt_money(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if math.isnan(v) else f"${v:,.2f}"


def _as_float(value: Any) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def _target_weights(state: State, cfg: AllocatorConfig) -> dict[str, float]:
    if state == "NORMAL":
        return {"fund_v1_exposure": 1.0, "GLD": 0.0, "BIL": 0.0}
    return {
        "fund_v1_exposure": cfg.crypto_scale,
        "GLD": (1.0 - cfg.crypto_scale) * cfg.gld_weight,
        "BIL": (1.0 - cfg.crypto_scale) * cfg.bil_weight,
    }


def _validate_config(cfg: AllocatorConfig) -> None:
    if cfg.enabled or cfg.mode != "paper":
        raise ValueError("Replay must remain enabled=false and mode='paper'")
    if cfg.release_mode != "either":
        raise ValueError("Prototype currently supports release_mode='either' only")
    if cfg.cost_model not in {"full_reallocation", "destination_only"}:
        raise ValueError("Unsupported cost model")
    if cfg.intent_application not in {"before_return", "after_return"}:
        raise ValueError("Unsupported intent application mode")
    if not 0.0 <= cfg.crypto_scale <= 1.0:
        raise ValueError("crypto_scale must be in [0, 1]")
    if cfg.gld_weight < 0 or cfg.bil_weight < 0 or abs(cfg.gld_weight + cfg.bil_weight - 1.0) > 1e-9:
        raise ValueError("GLD/BIL destination weights must be non-negative and sum to 1.0")
    for state in ("NORMAL", "RISK_OFF_DESTINATION"):
        if abs(sum(_target_weights(state, cfg).values()) - 1.0) > 1e-9:
            raise ValueError(f"Target weights for {state} do not sum to 1.0")


def _compute_drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def _charged_notional(symbol: str, notional: float, cfg: AllocatorConfig) -> float:
    if cfg.cost_model == "full_reallocation":
        return notional
    return notional if symbol in {"GLD", "BIL"} else 0.0


def _emit_fills(
    ts: pd.Timestamp,
    intent: dict[str, Any],
    current_weights: dict[str, float],
    nav: float,
    cfg: AllocatorConfig,
    baseline: pd.Series,
    gld_close: pd.Series,
    bil_close: pd.Series,
) -> tuple[dict[str, float], float, list[dict[str, Any]]]:
    fills: list[dict[str, Any]] = []
    target = intent["target_weights"]
    nav_after_cost = nav
    for symbol in ("fund_v1_exposure", "GLD", "BIL"):
        prior_weight = float(current_weights.get(symbol, 0.0))
        target_weight = float(target.get(symbol, 0.0))
        weight_delta = target_weight - prior_weight
        if abs(weight_delta) <= 1e-12:
            continue
        notional = nav_after_cost * abs(weight_delta)
        charged_notional = _charged_notional(symbol, notional, cfg)
        friction = charged_notional * (cfg.friction_bps / 10_000.0)
        nav_after_cost -= friction
        price = None
        if symbol == "GLD" and ts in gld_close.index:
            price = _as_float(gld_close.loc[ts])
        elif symbol == "BIL" and ts in bil_close.index:
            price = _as_float(bil_close.loc[ts])
        elif symbol == "fund_v1_exposure" and ts in baseline.index:
            price = _as_float(baseline.loc[ts])
        fill_payload = {
            "intent_id": intent["intent_id"],
            "timestamp": _iso_ts(ts),
            "symbol": symbol,
            "target_weight": target_weight,
            "notional": round(notional, 6),
            "cost_model": cfg.cost_model,
            "intent_application": cfg.intent_application,
        }
        fills.append(
            {
                "timestamp": _iso_ts(ts),
                "intent_id": intent["intent_id"],
                "fill_id": _stable_id("fill", fill_payload),
                "symbol": symbol,
                "side": "BUY" if weight_delta > 0 else "SELL",
                "prior_weight": prior_weight,
                "target_weight": target_weight,
                "weight_delta": weight_delta,
                "notional": notional,
                "charged_notional": charged_notional,
                "fill_price": price,
                "friction_bps": cfg.friction_bps,
                "estimated_friction": friction,
                "cost_model": cfg.cost_model,
                "intent_application": cfg.intent_application,
                "mode": cfg.mode,
            }
        )
    return {k: float(v) for k, v in target.items()}, nav_after_cost, fills


def _build_state_and_intents(
    dates: pd.Index,
    baseline: pd.Series,
    btc_close: pd.Series,
    btc_sma: pd.Series,
    cfg: AllocatorConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], pd.Series]:
    dates = pd.DatetimeIndex([_day(x) for x in dates]).sort_values().unique()
    drawdown = _compute_drawdown(baseline)
    peak = baseline.cummax()
    state: State = "NORMAL"
    states: list[State] = []
    evaluations: list[dict[str, Any]] = []
    intents: list[dict[str, Any]] = []

    for i, ts in enumerate(dates):
        prior_state = state
        new_state = state
        result = "NO_ACTION_DATA_UNAVAILABLE"
        reason = "no_prior_confirmed_bar"
        source_cutoff = None
        fund_nav = fund_peak = fund_dd = btc_c = btc_s = None
        if i > 0:
            p = pd.Timestamp(dates[i - 1])
            source_cutoff = _iso_date(p)
            fund_nav = _as_float(baseline.loc[p]) if p in baseline.index else None
            fund_peak = _as_float(peak.loc[p]) if p in peak.index else None
            fund_dd = _as_float(drawdown.loc[p]) if p in drawdown.index else None
            btc_c = _as_float(btc_close.loc[p]) if p in btc_close.index else None
            btc_s = _as_float(btc_sma.loc[p]) if p in btc_sma.index else None
            if None in {fund_nav, fund_peak, fund_dd, btc_c, btc_s}:
                reason = "required_prior_inputs_missing"
            else:
                enter = fund_dd <= cfg.trigger_dd and btc_c < btc_s
                exit_ = fund_dd >= cfg.release_dd or btc_c >= btc_s
                if state == "NORMAL" and enter:
                    state = new_state = "RISK_OFF_DESTINATION"
                    result = "ENTER_RISK_OFF_DESTINATION"
                    reason = "drawdown_trigger_and_btc_trend_break"
                elif state == "RISK_OFF_DESTINATION" and exit_:
                    state = new_state = "NORMAL"
                    result = "EXIT_RISK_OFF_DESTINATION"
                    reason = "drawdown_recovery_or_btc_trend_recovery"
                elif state == "NORMAL":
                    result = "NO_ACTION_ALREADY_NORMAL"
                    reason = "normal_state_conditions_not_met"
                else:
                    result = "NO_ACTION_ALREADY_RISK_OFF"
                    reason = "risk_off_release_conditions_not_met"

        evaluation = {
            "timestamp": _iso_ts(ts),
            "mode": cfg.mode,
            "allocator_id": cfg.allocator_id,
            "governed_budget_id": cfg.governed_budget_id,
            "prior_state": prior_state,
            "new_state": new_state,
            "result": result,
            "reason": reason,
            "source_data_cutoff": source_cutoff,
            "fund_nav": fund_nav,
            "fund_peak_nav": fund_peak,
            "fund_drawdown": fund_dd,
            "btc_close": btc_c,
            "btc_sma": btc_s,
            "trigger_dd": cfg.trigger_dd,
            "release_dd": cfg.release_dd,
            "release_mode": cfg.release_mode,
            "crypto_scale": cfg.crypto_scale,
            "gld_weight": cfg.gld_weight,
            "bil_weight": cfg.bil_weight,
        }
        evaluations.append(evaluation)
        states.append(state)

        if result in {"ENTER_RISK_OFF_DESTINATION", "EXIT_RISK_OFF_DESTINATION"}:
            target_weights = _target_weights(new_state, cfg)
            payload = {"timestamp": _iso_ts(ts), "new_state": new_state, "target_weights": target_weights}
            intents.append(
                {
                    "intent_id": _stable_id("intent", payload),
                    "timestamp": _iso_ts(ts),
                    "execution_timestamp": _iso_ts(ts),
                    "mode": cfg.mode,
                    "allocator_id": cfg.allocator_id,
                    "governed_budget_id": cfg.governed_budget_id,
                    "prior_state": prior_state,
                    "new_state": new_state,
                    "reason": reason,
                    "source_data_cutoff": source_cutoff,
                    "target_weights": target_weights,
                    "execution_policy": {
                        "venue_mode": cfg.mode,
                        "fill_timing": cfg.fill_timing,
                        "intent_application": cfg.intent_application,
                        "allow_weekend_etf_fills": cfg.allow_weekend_etf_fills,
                    },
                    "inputs": {
                        "fund_nav": fund_nav,
                        "fund_peak_nav": fund_peak,
                        "fund_drawdown": fund_dd,
                        "btc_close": btc_c,
                        "btc_sma": btc_s,
                    },
                    "parameters": {
                        "trigger_dd": cfg.trigger_dd,
                        "release_dd": cfg.release_dd,
                        "release_mode": cfg.release_mode,
                        "crypto_scale": cfg.crypto_scale,
                        "btc_sma_window": cfg.btc_sma_window,
                        "gld_weight": cfg.gld_weight,
                        "bil_weight": cfg.bil_weight,
                        "cost_model": cfg.cost_model,
                        "intent_application": cfg.intent_application,
                    },
                }
            )
    return evaluations, intents, pd.Series(states, index=dates, name="state")


def _simulate_replay(
    dates: pd.Index,
    baseline: pd.Series,
    gld_curve: pd.Series,
    bil_curve: pd.Series,
    gld_close: pd.Series,
    bil_close: pd.Series,
    intents: list[dict[str, Any]],
    cfg: AllocatorConfig,
    capital: float,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    dates = pd.DatetimeIndex([_day(x) for x in dates]).sort_values().unique()
    returns = pd.DataFrame(
        {
            "fund_v1_exposure": _normalized_returns(baseline),
            "GLD": _normalized_returns(gld_curve),
            "BIL": _normalized_returns(bil_curve),
        }
    ).reindex(dates).fillna(0.0)
    by_exec: dict[pd.Timestamp, list[dict[str, Any]]] = {}
    for intent in intents:
        by_exec.setdefault(_day(intent["execution_timestamp"]), []).append(intent)

    weights = _target_weights("NORMAL", cfg)
    nav = capital
    rows: list[dict[str, Any]] = []
    fills: list[dict[str, Any]] = []

    for i, ts in enumerate(dates):
        ts = pd.Timestamp(ts)
        nav_start = nav
        if cfg.intent_application == "before_return" and ts in by_exec:
            for intent in by_exec[ts]:
                weights, nav, new_fills = _emit_fills(ts, intent, weights, nav, cfg, baseline, gld_close, bil_close)
                fills.extend(new_fills)
        day_ret = 0.0 if i == 0 else sum(float(weights[s]) * float(returns.loc[ts, s]) for s in weights)
        nav_before_cost = nav * (1.0 + day_ret)
        nav = nav_before_cost
        if cfg.intent_application == "after_return" and ts in by_exec:
            for intent in by_exec[ts]:
                weights, nav, new_fills = _emit_fills(ts, intent, weights, nav, cfg, baseline, gld_close, bil_close)
                fills.extend(new_fills)
        rows.append(
            {
                "timestamp": ts,
                "nav_start": nav_start,
                "nav_before_cost": nav_before_cost,
                "nav": nav,
                "daily_return_before_cost": day_ret,
                "weight_fund_v1_exposure": weights["fund_v1_exposure"],
                "weight_GLD": weights["GLD"],
                "weight_BIL": weights["BIL"],
            }
        )
    if intents and not fills:
        raise RuntimeError("Replay generated allocation intents but no paper fills.")
    return pd.DataFrame(rows).set_index("timestamp"), fills


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, default=str, sort_keys=True) + "\n")


def _load_inputs(args: argparse.Namespace) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    return (
        _load_baseline_cache(args.baseline_cache),
        _load_close(args.btc_daily, "BTC", args.start, args.end),
        _load_close(args.gld_data, "GLD", args.start, args.end),
        _load_close(args.bil_data, "BIL", args.start, args.end),
        _buy_hold_curve(args.gld_data, "GLD", args.capital, args.start, args.end),
        _buy_hold_curve(args.bil_data, "BIL", args.capital, args.start, args.end),
    )


def _write_outputs(
    args: argparse.Namespace,
    cfg: AllocatorConfig,
    baseline: pd.Series,
    paper: pd.DataFrame,
    evaluations: list[dict[str, Any]],
    intents: list[dict[str, Any]],
    fills: list[dict[str, Any]],
) -> tuple[Path, dict[str, Any]]:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "state_evaluations.jsonl", evaluations)
    _write_jsonl(out_dir / "allocation_intents.jsonl", intents)
    _write_jsonl(out_dir / "paper_fills.jsonl", fills)
    pd.DataFrame(
        {
            "baseline": baseline.reindex(paper.index),
            "paper_allocator_nav": paper["nav"],
            "paper_nav_before_cost": paper["nav_before_cost"],
            "weight_fund_v1_exposure": paper["weight_fund_v1_exposure"],
            "weight_GLD": paper["weight_GLD"],
            "weight_BIL": paper["weight_BIL"],
        }
    ).to_csv(out_dir / "equity_curves.csv")
    b = baseline.reindex(paper.index).dropna()
    p = paper["nav"].reindex(b.index).dropna()
    b = b.reindex(p.index)
    bm = compute_metrics(b, trades=[], params={"strategy_id": "baseline", "asset": "PORTFOLIO", "initial_capital": args.capital})
    pm = compute_metrics(p, trades=[], params={"strategy_id": cfg.allocator_id, "asset": "PORTFOLIO", "initial_capital": args.capital})
    transitions = sum(1 for e in evaluations if e["result"] in {"ENTER_RISK_OFF_DESTINATION", "EXIT_RISK_OFF_DESTINATION"})
    total_friction = sum(float(f["estimated_friction"]) for f in fills)
    charged_notional = sum(float(f["charged_notional"]) for f in fills)
    gross_notional = sum(float(f["notional"]) for f in fills)
    risk_off_days = int((paper["weight_GLD"] + paper["weight_BIL"] > 0).sum())
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": asdict(cfg),
        "baseline": {"final_nav": float(b.iloc[-1]), "cagr_pct": bm.cagr_pct, "max_drawdown_pct": bm.max_drawdown_pct, "sharpe": bm.sharpe, "calmar": bm.calmar},
        "paper": {"final_nav": float(p.iloc[-1]), "cagr_pct": pm.cagr_pct, "max_drawdown_pct": pm.max_drawdown_pct, "sharpe": pm.sharpe, "calmar": pm.calmar},
        "counts": {"evaluations": len(evaluations), "state_transitions": transitions, "allocation_intents": len(intents), "paper_fills": len(fills), "risk_off_days": risk_off_days, "risk_off_pct_days": risk_off_days / max(len(paper), 1) * 100.0},
        "costs": {"gross_fill_notional": gross_notional, "charged_notional": charged_notional, "total_estimated_friction": total_friction},
    }
    (out_dir / "replay_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (out_dir / "allocator_config.json").write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
    md = out_dir / "replay_summary.md"
    md.write_text(
        "# DefensiveDestinationAllocator Paper Replay Summary\n\n"
        "This is a paper-only replay artifact. It is not a trading instruction and does not approve live runtime integration.\n\n"
        f"- Cost model: `{cfg.cost_model}`\n"
        f"- Intent application: `{cfg.intent_application}`\n"
        f"- Destination: `{cfg.gld_weight:.0%} GLD / {cfg.bil_weight:.0%} BIL`\n\n"
        "| Label | Final NAV | CAGR | MaxDD | Sharpe | Calmar |\n"
        "|---|---:|---:|---:|---:|---:|\n"
        f"| Baseline | {_fmt_money(summary['baseline']['final_nav'])} | {summary['baseline']['cagr_pct']:.2f}% | {summary['baseline']['max_drawdown_pct']:.2f}% | {summary['baseline']['sharpe']:.3f} | {summary['baseline']['calmar']:.3f} |\n"
        f"| Paper allocator | {_fmt_money(summary['paper']['final_nav'])} | {summary['paper']['cagr_pct']:.2f}% | {summary['paper']['max_drawdown_pct']:.2f}% | {summary['paper']['sharpe']:.3f} | {summary['paper']['calmar']:.3f} |\n\n"
        f"- State transitions: `{transitions}`\n"
        f"- Allocation intents: `{len(intents)}`\n"
        f"- Paper fills: `{len(fills)}`\n"
        f"- Gross fill notional: `{_fmt_money(gross_notional)}`\n"
        f"- Charged notional: `{_fmt_money(charged_notional)}`\n"
        f"- Total estimated friction: `{_fmt_money(total_friction)}`\n\n"
        "```text\nPAPER ONLY\nNO LIVE BROKER\nNO RUNTIME STATE MUTATION\nNO AGENTIC OVERRIDES\n```\n",
        encoding="utf-8",
    )
    return md, summary


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Paper-only DefensiveDestinationAllocator replay")
    p.add_argument("--baseline-cache", required=True)
    p.add_argument("--btc-daily", required=True)
    p.add_argument("--gld-data", required=True)
    p.add_argument("--bil-data", required=True)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--governed-budget-id", default="fund_v1_defensive_overlay_budget")
    p.add_argument("--trigger-dd", type=float, default=-0.18)
    p.add_argument("--release-dd", type=float, default=-0.12)
    p.add_argument("--btc-sma-window", type=int, default=200)
    p.add_argument("--crypto-scale", type=float, default=0.0)
    p.add_argument("--gld-weight", type=float, default=0.50)
    p.add_argument("--friction-bps", type=float, default=10.0)
    p.add_argument("--cost-model", choices=["full_reallocation", "destination_only"], default="full_reallocation")
    p.add_argument("--intent-application", choices=["before_return", "after_return"], default="after_return")
    p.add_argument("--out-dir", default="artifacts/defensive_destination_allocator")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = AllocatorConfig(
        allocator_id="defensive_destination_allocator_v1",
        enabled=False,
        mode="paper",
        governed_budget_id=args.governed_budget_id,
        trigger_dd=args.trigger_dd,
        release_dd=args.release_dd,
        release_mode="either",
        btc_sma_window=args.btc_sma_window,
        crypto_scale=args.crypto_scale,
        gld_weight=args.gld_weight,
        bil_weight=1.0 - args.gld_weight,
        friction_bps=args.friction_bps,
        cost_model=args.cost_model,
        intent_application=args.intent_application,
        fill_timing="daily_close_proxy",
        allow_weekend_etf_fills=False,
    )
    _validate_config(cfg)
    baseline, btc_close_raw, gld_close_raw, bil_close_raw, gld_curve_raw, bil_curve_raw = _load_inputs(args)
    common = baseline.index.intersection(gld_curve_raw.index).intersection(bil_curve_raw.index).sort_values()
    common = pd.DatetimeIndex([_day(x) for x in common]).sort_values().unique()
    baseline = baseline.reindex(common).dropna()
    common = baseline.index
    gld_curve = gld_curve_raw.reindex(common).dropna()
    bil_curve = bil_curve_raw.reindex(common).dropna()
    common = baseline.index.intersection(gld_curve.index).intersection(bil_curve.index).sort_values()
    baseline, gld_curve, bil_curve = baseline.reindex(common), gld_curve.reindex(common), bil_curve.reindex(common)
    gld_close, bil_close = gld_close_raw.reindex(common).ffill(), bil_close_raw.reindex(common).ffill()
    btc_close = btc_close_raw.reindex(common).ffill()
    btc_sma = btc_close_raw.rolling(cfg.btc_sma_window, min_periods=cfg.btc_sma_window).mean().reindex(common).ffill()
    evaluations, intents, state_series = _build_state_and_intents(common, baseline, btc_close, btc_sma, cfg)
    paper, fills = _simulate_replay(common, baseline, gld_curve, bil_curve, gld_close, bil_close, intents, cfg, args.capital)
    paper["state"] = state_series.reindex(paper.index)
    summary_path, summary = _write_outputs(args, cfg, baseline, paper, evaluations, intents, fills)

    print("=" * 132)
    print("  DEFENSIVE DESTINATION ALLOCATOR — PAPER REPLAY")
    print("=" * 132)
    print(f"  Destination       : {cfg.gld_weight:.0%} GLD / {cfg.bil_weight:.0%} BIL")
    print(f"  Trigger / Release : {cfg.trigger_dd:.0%} / {cfg.release_dd:.0%}")
    print(f"  BTC SMA           : {cfg.btc_sma_window}")
    print(f"  Crypto scale      : {cfg.crypto_scale:.0%}")
    print(f"  Cost model        : {cfg.cost_model}")
    print(f"  Intent application: {cfg.intent_application}")
    print(f"  Friction          : {cfg.friction_bps:.2f} bps per charged notional")
    print("-" * 132)
    print(f"  {'Label':<18} {'Final NAV':>14} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'Calmar':>8}")
    print("  " + "-" * 130)
    print(f"  {'baseline':<18} {_fmt_money(summary['baseline']['final_nav']):>14} {summary['baseline']['cagr_pct']:>8.2f}% {summary['baseline']['max_drawdown_pct']:>8.2f}% {summary['baseline']['sharpe']:>8.3f} {summary['baseline']['calmar']:>8.3f}")
    print(f"  {'paper_allocator':<18} {_fmt_money(summary['paper']['final_nav']):>14} {summary['paper']['cagr_pct']:>8.2f}% {summary['paper']['max_drawdown_pct']:>8.2f}% {summary['paper']['sharpe']:>8.3f} {summary['paper']['calmar']:>8.3f}")
    print("-" * 132)
    print(f"  Evaluations       : {summary['counts']['evaluations']}")
    print(f"  Transitions       : {summary['counts']['state_transitions']}")
    print(f"  Allocation intents: {summary['counts']['allocation_intents']}")
    print(f"  Paper fills       : {summary['counts']['paper_fills']}")
    print(f"  Gross fill notional: {_fmt_money(summary['costs']['gross_fill_notional'])}")
    print(f"  Charged notional  : {_fmt_money(summary['costs']['charged_notional'])}")
    print(f"  Estimated friction: {_fmt_money(summary['costs']['total_estimated_friction'])}")
    print("=" * 132)
    print(f"  Summary: {summary_path}")
    print("  Verdict: PAPER ONLY; no runtime, broker, or live execution changes.\n")


if __name__ == "__main__":
    main()
