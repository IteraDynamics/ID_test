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
EvalResult = Literal[
    "NO_ACTION_ALREADY_NORMAL",
    "NO_ACTION_ALREADY_RISK_OFF",
    "NO_ACTION_DATA_UNAVAILABLE",
    "ENTER_RISK_OFF_DESTINATION",
    "EXIT_RISK_OFF_DESTINATION",
]


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
    fill_timing: str
    allow_weekend_etf_fills: bool


@dataclass(frozen=True)
class StateEvaluation:
    timestamp: str
    mode: str
    allocator_id: str
    governed_budget_id: str
    prior_state: State
    new_state: State
    result: EvalResult
    reason: str
    source_data_cutoff: str | None
    fund_nav: float | None
    fund_peak_nav: float | None
    fund_drawdown: float | None
    btc_close: float | None
    btc_sma: float | None
    trigger_dd: float
    release_dd: float
    release_mode: str
    crypto_scale: float
    gld_weight: float
    bil_weight: float


@dataclass(frozen=True)
class AllocationIntent:
    intent_id: str
    timestamp: str
    execution_timestamp: str
    mode: str
    allocator_id: str
    governed_budget_id: str
    prior_state: State
    new_state: State
    reason: str
    source_data_cutoff: str | None
    target_weights: dict[str, float]
    execution_policy: dict[str, Any]
    inputs: dict[str, float | None]
    parameters: dict[str, Any]


@dataclass(frozen=True)
class PaperFill:
    timestamp: str
    intent_id: str
    fill_id: str
    symbol: str
    side: str
    prior_weight: float
    target_weight: float
    weight_delta: float
    notional: float
    fill_price: float | None
    friction_bps: float
    estimated_friction: float
    mode: str


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(blob).hexdigest()[:16]}"


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return "n/a" if math.isnan(v) else f"{v:.2f}%"


def _fmt_money(value: Any) -> str:
    if value is None:
        return "n/a"
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


def _day(ts: Any) -> pd.Timestamp:
    """Return a timezone-naive midnight Timestamp used as the replay key."""
    return pd.Timestamp(ts).tz_localize(None).normalize()


def _iso_date(ts: Any) -> str:
    return _day(ts).date().isoformat()


def _iso_ts(ts: Any) -> str:
    return _day(ts).strftime("%Y-%m-%dT00:00:00Z")


def _parse_replay_ts(ts: str) -> pd.Timestamp:
    return _day(ts)


def _compute_drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def _target_weights_for_state(state: State, cfg: AllocatorConfig) -> dict[str, float]:
    if state == "NORMAL":
        return {"fund_v1_exposure": 1.0, "GLD": 0.0, "BIL": 0.0}
    return {
        "fund_v1_exposure": cfg.crypto_scale,
        "GLD": (1.0 - cfg.crypto_scale) * cfg.gld_weight,
        "BIL": (1.0 - cfg.crypto_scale) * cfg.bil_weight,
    }


def _validate_config(cfg: AllocatorConfig) -> None:
    if cfg.mode != "paper":
        raise ValueError("Paper replay only supports mode='paper'")
    if cfg.enabled:
        raise ValueError("Paper replay config must remain enabled=false")
    if cfg.release_mode != "either":
        raise ValueError("Prototype currently supports release_mode='either' only")
    if not 0.0 <= cfg.crypto_scale <= 1.0:
        raise ValueError("crypto_scale must be in [0, 1]")
    if cfg.gld_weight < 0.0 or cfg.bil_weight < 0.0:
        raise ValueError("destination weights must be non-negative")
    if abs(cfg.gld_weight + cfg.bil_weight - 1.0) > 1e-9:
        raise ValueError("gld_weight + bil_weight must equal 1.0")
    for state in ("NORMAL", "RISK_OFF_DESTINATION"):
        weights = _target_weights_for_state(state, cfg)  # type: ignore[arg-type]
        if abs(sum(weights.values()) - 1.0) > 1e-9:
            raise ValueError(f"target weights for {state} do not sum to 1.0")


def _next_execution_date(eval_ts: pd.Timestamp, etf_calendar: pd.Index) -> pd.Timestamp | None:
    eval_day = _day(eval_ts)
    calendar = pd.DatetimeIndex([_day(x) for x in etf_calendar]).sort_values().unique()
    candidates = calendar[calendar >= eval_day]
    return None if len(candidates) == 0 else pd.Timestamp(candidates[0])


def _evaluate_state_machine(
    dates: pd.Index,
    baseline: pd.Series,
    drawdown: pd.Series,
    btc_close: pd.Series,
    btc_sma: pd.Series,
    cfg: AllocatorConfig,
    etf_calendar: pd.Index,
) -> tuple[list[StateEvaluation], list[AllocationIntent], pd.Series]:
    dates = pd.DatetimeIndex([_day(x) for x in dates]).sort_values().unique()
    evaluations: list[StateEvaluation] = []
    intents: list[AllocationIntent] = []
    state: State = "NORMAL"
    effective_state: list[State] = []
    prior_peak = baseline.cummax()

    for idx, ts in enumerate(dates):
        prior_state = state
        new_state = state
        source_cutoff = None
        fund_nav = fund_peak = fund_dd = btc_c = btc_s = None

        if idx == 0:
            result: EvalResult = "NO_ACTION_DATA_UNAVAILABLE"
            reason = "no_prior_confirmed_bar"
        else:
            prior_ts = pd.Timestamp(dates[idx - 1])
            source_cutoff = _iso_date(prior_ts)
            fund_nav = _as_float(baseline.loc[prior_ts]) if prior_ts in baseline.index else None
            fund_peak = _as_float(prior_peak.loc[prior_ts]) if prior_ts in prior_peak.index else None
            fund_dd = _as_float(drawdown.loc[prior_ts]) if prior_ts in drawdown.index else None
            btc_c = _as_float(btc_close.loc[prior_ts]) if prior_ts in btc_close.index else None
            btc_s = _as_float(btc_sma.loc[prior_ts]) if prior_ts in btc_sma.index else None

            if fund_nav is None or fund_peak is None or fund_dd is None or btc_c is None or btc_s is None:
                result = "NO_ACTION_DATA_UNAVAILABLE"
                reason = "required_prior_inputs_missing"
            else:
                enter = fund_dd <= cfg.trigger_dd and btc_c < btc_s
                exit_ = fund_dd >= cfg.release_dd or btc_c >= btc_s
                if state == "NORMAL" and enter:
                    new_state = "RISK_OFF_DESTINATION"
                    state = new_state
                    result = "ENTER_RISK_OFF_DESTINATION"
                    reason = "drawdown_trigger_and_btc_trend_break"
                elif state == "RISK_OFF_DESTINATION" and exit_:
                    new_state = "NORMAL"
                    state = new_state
                    result = "EXIT_RISK_OFF_DESTINATION"
                    reason = "drawdown_recovery_or_btc_trend_recovery"
                elif state == "NORMAL":
                    result = "NO_ACTION_ALREADY_NORMAL"
                    reason = "normal_state_conditions_not_met"
                else:
                    result = "NO_ACTION_ALREADY_RISK_OFF"
                    reason = "risk_off_release_conditions_not_met"

        evaluation = StateEvaluation(
            timestamp=_iso_ts(ts),
            mode=cfg.mode,
            allocator_id=cfg.allocator_id,
            governed_budget_id=cfg.governed_budget_id,
            prior_state=prior_state,
            new_state=new_state,
            result=result,
            reason=reason,
            source_data_cutoff=source_cutoff,
            fund_nav=fund_nav,
            fund_peak_nav=fund_peak,
            fund_drawdown=fund_dd,
            btc_close=btc_c,
            btc_sma=btc_s,
            trigger_dd=cfg.trigger_dd,
            release_dd=cfg.release_dd,
            release_mode=cfg.release_mode,
            crypto_scale=cfg.crypto_scale,
            gld_weight=cfg.gld_weight,
            bil_weight=cfg.bil_weight,
        )
        evaluations.append(evaluation)
        effective_state.append(state)

        if result in {"ENTER_RISK_OFF_DESTINATION", "EXIT_RISK_OFF_DESTINATION"}:
            execution_ts = _next_execution_date(ts, etf_calendar)
            if execution_ts is None:
                continue
            target_weights = _target_weights_for_state(new_state, cfg)
            payload = {
                "timestamp": _iso_ts(ts),
                "execution_timestamp": _iso_ts(execution_ts),
                "new_state": new_state,
                "source_data_cutoff": source_cutoff,
                "target_weights": target_weights,
            }
            intents.append(
                AllocationIntent(
                    intent_id=_stable_id("intent", payload),
                    timestamp=_iso_ts(ts),
                    execution_timestamp=_iso_ts(execution_ts),
                    mode=cfg.mode,
                    allocator_id=cfg.allocator_id,
                    governed_budget_id=cfg.governed_budget_id,
                    prior_state=prior_state,
                    new_state=new_state,
                    reason=reason,
                    source_data_cutoff=source_cutoff,
                    target_weights=target_weights,
                    execution_policy={
                        "venue_mode": cfg.mode,
                        "fill_timing": cfg.fill_timing,
                        "allow_weekend_etf_fills": cfg.allow_weekend_etf_fills,
                    },
                    inputs={
                        "fund_nav": fund_nav,
                        "fund_peak_nav": fund_peak,
                        "fund_drawdown": fund_dd,
                        "btc_close": btc_c,
                        "btc_sma": btc_s,
                    },
                    parameters={
                        "trigger_dd": cfg.trigger_dd,
                        "release_dd": cfg.release_dd,
                        "release_mode": cfg.release_mode,
                        "crypto_scale": cfg.crypto_scale,
                        "btc_sma_window": cfg.btc_sma_window,
                        "gld_weight": cfg.gld_weight,
                        "bil_weight": cfg.bil_weight,
                    },
                )
            )

    return evaluations, intents, pd.Series(effective_state, index=dates, name="state")


def _simulate_paper_replay(
    dates: pd.Index,
    baseline: pd.Series,
    gld_curve: pd.Series,
    bil_curve: pd.Series,
    gld_close: pd.Series,
    bil_close: pd.Series,
    intents: list[AllocationIntent],
    cfg: AllocatorConfig,
    capital: float,
) -> tuple[pd.DataFrame, list[PaperFill]]:
    dates = pd.DatetimeIndex([_day(x) for x in dates]).sort_values().unique()
    returns = pd.DataFrame(
        {
            "fund_v1_exposure": _normalized_returns(baseline),
            "GLD": _normalized_returns(gld_curve),
            "BIL": _normalized_returns(bil_curve),
        }
    ).reindex(dates).fillna(0.0)

    intent_by_exec: dict[pd.Timestamp, list[AllocationIntent]] = {}
    for intent in intents:
        exec_ts = _parse_replay_ts(intent.execution_timestamp)
        intent_by_exec.setdefault(exec_ts, []).append(intent)

    current_weights = _target_weights_for_state("NORMAL", cfg)
    nav = capital
    rows: list[dict[str, Any]] = []
    fills: list[PaperFill] = []

    for i, ts in enumerate(dates):
        ts = pd.Timestamp(ts)
        day_ret = 0.0 if i == 0 else sum(float(current_weights[sym]) * float(returns.loc[ts, sym]) for sym in current_weights)
        nav_before_cost = nav * (1.0 + day_ret)
        nav_after_cost = nav_before_cost

        if ts in intent_by_exec:
            for intent in intent_by_exec[ts]:
                target = intent.target_weights
                for symbol in ("fund_v1_exposure", "GLD", "BIL"):
                    prior_weight = float(current_weights.get(symbol, 0.0))
                    target_weight = float(target.get(symbol, 0.0))
                    weight_delta = target_weight - prior_weight
                    if abs(weight_delta) <= 1e-12:
                        continue
                    notional = nav_after_cost * abs(weight_delta)
                    friction = notional * (cfg.friction_bps / 10_000.0)
                    nav_after_cost -= friction
                    price = None
                    if symbol == "GLD" and ts in gld_close.index:
                        price = _as_float(gld_close.loc[ts])
                    elif symbol == "BIL" and ts in bil_close.index:
                        price = _as_float(bil_close.loc[ts])
                    elif symbol == "fund_v1_exposure" and ts in baseline.index:
                        price = _as_float(baseline.loc[ts])
                    fill_payload = {
                        "intent_id": intent.intent_id,
                        "timestamp": _iso_ts(ts),
                        "symbol": symbol,
                        "target_weight": target_weight,
                        "notional": round(notional, 6),
                    }
                    fills.append(
                        PaperFill(
                            timestamp=_iso_ts(ts),
                            intent_id=intent.intent_id,
                            fill_id=_stable_id("fill", fill_payload),
                            symbol=symbol,
                            side="BUY" if weight_delta > 0 else "SELL",
                            prior_weight=prior_weight,
                            target_weight=target_weight,
                            weight_delta=weight_delta,
                            notional=notional,
                            fill_price=price,
                            friction_bps=cfg.friction_bps,
                            estimated_friction=friction,
                            mode=cfg.mode,
                        )
                    )
                current_weights = {k: float(v) for k, v in target.items()}

        rows.append(
            {
                "timestamp": ts,
                "nav_before_cost": nav_before_cost,
                "nav": nav_after_cost,
                "daily_return_before_cost": day_ret,
                "weight_fund_v1_exposure": current_weights["fund_v1_exposure"],
                "weight_GLD": current_weights["GLD"],
                "weight_BIL": current_weights["BIL"],
            }
        )
        nav = nav_after_cost

    if intents and not fills:
        raise RuntimeError("Replay generated allocation intents but no paper fills. Check execution timestamp alignment.")

    return pd.DataFrame(rows).set_index("timestamp"), fills


def _write_jsonl(path: Path, rows: list[Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            payload = asdict(row) if hasattr(row, "__dataclass_fields__") else row
            f.write(json.dumps(payload, default=str, sort_keys=True) + "\n")


def _load_inputs(args: argparse.Namespace) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    baseline = _load_baseline_cache(args.baseline_cache)
    btc_close = _load_close(args.btc_daily, "BTC", args.start, args.end)
    gld_close = _load_close(args.gld_data, "GLD", args.start, args.end)
    bil_close = _load_close(args.bil_data, "BIL", args.start, args.end)
    gld_curve = _buy_hold_curve(args.gld_data, "GLD", args.capital, args.start, args.end)
    bil_curve = _buy_hold_curve(args.bil_data, "BIL", args.capital, args.start, args.end)
    return baseline, btc_close, gld_close, bil_close, gld_curve, bil_curve


def _render_summary(
    args: argparse.Namespace,
    cfg: AllocatorConfig,
    baseline: pd.Series,
    paper: pd.DataFrame,
    evaluations: list[StateEvaluation],
    intents: list[AllocationIntent],
    fills: list[PaperFill],
) -> tuple[str, dict[str, Any]]:
    paper_nav = paper["nav"]
    baseline_aligned = baseline.reindex(paper_nav.index).dropna()
    paper_nav = paper_nav.reindex(baseline_aligned.index).dropna()
    baseline_aligned = baseline_aligned.reindex(paper_nav.index)
    baseline_metrics = compute_metrics(baseline_aligned, trades=[], params={"strategy_id": "baseline", "asset": "PORTFOLIO", "initial_capital": args.capital})
    paper_metrics = compute_metrics(paper_nav, trades=[], params={"strategy_id": cfg.allocator_id, "asset": "PORTFOLIO", "initial_capital": args.capital})
    total_friction = sum(fill.estimated_friction for fill in fills)
    transitions = sum(1 for e in evaluations if e.result in {"ENTER_RISK_OFF_DESTINATION", "EXIT_RISK_OFF_DESTINATION"})
    risk_off_days = int((paper["weight_GLD"] + paper["weight_BIL"] > 0).sum())
    risk_off_pct = risk_off_days / max(len(paper), 1) * 100.0

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": asdict(cfg),
        "start": args.start,
        "end": args.end,
        "baseline": {
            "cagr_pct": baseline_metrics.cagr_pct,
            "max_drawdown_pct": baseline_metrics.max_drawdown_pct,
            "sharpe": baseline_metrics.sharpe,
            "calmar": baseline_metrics.calmar,
            "final_nav": float(baseline_aligned.iloc[-1]) if len(baseline_aligned) else None,
        },
        "paper": {
            "cagr_pct": paper_metrics.cagr_pct,
            "max_drawdown_pct": paper_metrics.max_drawdown_pct,
            "sharpe": paper_metrics.sharpe,
            "calmar": paper_metrics.calmar,
            "final_nav": float(paper_nav.iloc[-1]) if len(paper_nav) else None,
        },
        "delta": {
            "cagr_pct": paper_metrics.cagr_pct - baseline_metrics.cagr_pct,
            "max_drawdown_pct": paper_metrics.max_drawdown_pct - baseline_metrics.max_drawdown_pct,
            "sharpe": paper_metrics.sharpe - baseline_metrics.sharpe,
            "calmar": paper_metrics.calmar - baseline_metrics.calmar,
        },
        "counts": {
            "evaluations": len(evaluations),
            "state_transitions": transitions,
            "allocation_intents": len(intents),
            "paper_fills": len(fills),
            "risk_off_days": risk_off_days,
            "risk_off_pct_days": risk_off_pct,
        },
        "costs": {"total_estimated_friction": total_friction},
    }

    md = [
        "# DefensiveDestinationAllocator Paper Replay Summary\n",
        "This is a paper-only replay artifact. It is not a trading instruction and does not approve live runtime integration.\n",
        "## Configuration\n",
        f"- Allocator: `{cfg.allocator_id}`",
        f"- Mode: `{cfg.mode}`",
        f"- Enabled: `{cfg.enabled}`",
        f"- Governed budget: `{cfg.governed_budget_id}`",
        f"- Trigger / release: `{cfg.trigger_dd:.0%}` / `{cfg.release_dd:.0%}`",
        f"- BTC SMA window: `{cfg.btc_sma_window}`",
        f"- Crypto scale: `{cfg.crypto_scale:.0%}`",
        f"- Destination: `{cfg.gld_weight:.0%} GLD / {cfg.bil_weight:.0%} BIL`",
        f"- Friction: `{cfg.friction_bps:.2f}` bps per changed notional\n",
        "## Metrics\n",
        "| Label | Final NAV | CAGR | MaxDD | Sharpe | Calmar |",
        "|---|---:|---:|---:|---:|---:|",
        f"| Baseline | {_fmt_money(summary['baseline']['final_nav'])} | {_fmt_pct(summary['baseline']['cagr_pct'])} | {_fmt_pct(summary['baseline']['max_drawdown_pct'])} | {summary['baseline']['sharpe']:.3f} | {summary['baseline']['calmar']:.3f} |",
        f"| Paper allocator | {_fmt_money(summary['paper']['final_nav'])} | {_fmt_pct(summary['paper']['cagr_pct'])} | {_fmt_pct(summary['paper']['max_drawdown_pct'])} | {summary['paper']['sharpe']:.3f} | {summary['paper']['calmar']:.3f} |\n",
        "## Counts\n",
        f"- State evaluations: `{len(evaluations)}`",
        f"- State transitions: `{transitions}`",
        f"- Allocation intents: `{len(intents)}`",
        f"- Paper fills: `{len(fills)}`",
        f"- Risk-off days: `{risk_off_days}` / `{len(paper)}` (`{risk_off_pct:.2f}%`)",
        f"- Total estimated friction: `{_fmt_money(total_friction)}`\n",
        "## Boundary\n",
        "```text",
        "PAPER ONLY",
        "NO LIVE BROKER",
        "NO RUNTIME STATE MUTATION",
        "NO AGENTIC OVERRIDES",
        "```\n",
    ]
    return "\n".join(md), summary


def _write_outputs(
    args: argparse.Namespace,
    cfg: AllocatorConfig,
    baseline: pd.Series,
    paper: pd.DataFrame,
    evaluations: list[StateEvaluation],
    intents: list[AllocationIntent],
    fills: list[PaperFill],
) -> Path:
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
    md, summary = _render_summary(args, cfg, baseline, paper, evaluations, intents, fills)
    (out_dir / "replay_summary.md").write_text(md, encoding="utf-8")
    (out_dir / "replay_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (out_dir / "allocator_config.json").write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
    return out_dir / "replay_summary.md"


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
        fill_timing="next_etf_daily_close_proxy",
        allow_weekend_etf_fills=False,
    )
    _validate_config(cfg)

    baseline, btc_close_raw, gld_close_raw, bil_close_raw, gld_curve_raw, bil_curve_raw = _load_inputs(args)
    common_dates = baseline.index.intersection(gld_curve_raw.index).intersection(bil_curve_raw.index).sort_values()
    common_dates = pd.DatetimeIndex([_day(x) for x in common_dates]).sort_values().unique()
    baseline = baseline.reindex(common_dates).dropna()
    common_dates = baseline.index
    gld_curve = gld_curve_raw.reindex(common_dates).dropna()
    bil_curve = bil_curve_raw.reindex(common_dates).dropna()
    common_dates = baseline.index.intersection(gld_curve.index).intersection(bil_curve.index).sort_values()

    baseline = baseline.reindex(common_dates)
    gld_curve = gld_curve.reindex(common_dates)
    bil_curve = bil_curve.reindex(common_dates)
    gld_close = gld_close_raw.reindex(common_dates).ffill()
    bil_close = bil_close_raw.reindex(common_dates).ffill()
    btc_close = btc_close_raw.reindex(common_dates).ffill()
    btc_sma = btc_close_raw.rolling(cfg.btc_sma_window, min_periods=cfg.btc_sma_window).mean().reindex(common_dates).ffill()
    drawdown = _compute_drawdown(baseline)

    evaluations, intents, state_series = _evaluate_state_machine(common_dates, baseline, drawdown, btc_close, btc_sma, cfg, common_dates)
    paper, fills = _simulate_paper_replay(common_dates, baseline, gld_curve, bil_curve, gld_close, bil_close, intents, cfg, args.capital)
    paper["state"] = state_series.reindex(paper.index)
    summary_path = _write_outputs(args, cfg, baseline, paper, evaluations, intents, fills)

    paper_nav = paper["nav"]
    baseline_metrics = compute_metrics(baseline.reindex(paper_nav.index), trades=[], params={"strategy_id": "baseline", "asset": "PORTFOLIO", "initial_capital": args.capital})
    paper_metrics = compute_metrics(paper_nav, trades=[], params={"strategy_id": cfg.allocator_id, "asset": "PORTFOLIO", "initial_capital": args.capital})
    total_friction = sum(fill.estimated_friction for fill in fills)
    transitions = sum(1 for e in evaluations if e.result in {"ENTER_RISK_OFF_DESTINATION", "EXIT_RISK_OFF_DESTINATION"})

    print("=" * 132)
    print("  DEFENSIVE DESTINATION ALLOCATOR — PAPER REPLAY")
    print("=" * 132)
    print(f"  Destination      : {cfg.gld_weight:.0%} GLD / {cfg.bil_weight:.0%} BIL")
    print(f"  Trigger / Release: {cfg.trigger_dd:.0%} / {cfg.release_dd:.0%}")
    print(f"  BTC SMA          : {cfg.btc_sma_window}")
    print(f"  Crypto scale     : {cfg.crypto_scale:.0%}")
    print(f"  Friction         : {cfg.friction_bps:.2f} bps per changed notional")
    print("-" * 132)
    print(f"  {'Label':<18} {'Final NAV':>14} {'CAGR%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'Calmar':>8}")
    print("  " + "-" * 130)
    print(f"  {'baseline':<18} {_fmt_money(float(baseline.iloc[-1])):>14} {baseline_metrics.cagr_pct:>8.2f}% {baseline_metrics.max_drawdown_pct:>8.2f}% {baseline_metrics.sharpe:>8.3f} {baseline_metrics.calmar:>8.3f}")
    print(f"  {'paper_allocator':<18} {_fmt_money(float(paper_nav.iloc[-1])):>14} {paper_metrics.cagr_pct:>8.2f}% {paper_metrics.max_drawdown_pct:>8.2f}% {paper_metrics.sharpe:>8.3f} {paper_metrics.calmar:>8.3f}")
    print("-" * 132)
    print(f"  Evaluations       : {len(evaluations)}")
    print(f"  Transitions       : {transitions}")
    print(f"  Allocation intents: {len(intents)}")
    print(f"  Paper fills       : {len(fills)}")
    print(f"  Estimated friction: {_fmt_money(total_friction)}")
    print("=" * 132)
    print(f"  Summary: {summary_path}")
    print("  Verdict: PAPER ONLY; no runtime, broker, or live execution changes.\n")


if __name__ == "__main__":
    main()
