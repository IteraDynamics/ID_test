#!/usr/bin/env python
"""Forensic genesis-to-now state replay for the Core v1 paper runtime.

audit_core_v1_accounting.py proves the live ledger is internally
consistent (every fill's own bookkeeping ties out, Cash + Market Value =
NAV, and NAV = Capital + Realized + Unrealized + Cash Yield). It cannot
tell you whether that Cash Yield figure is itself legitimate — a ledger
can be perfectly self-consistent while still containing artifacts from
long-fixed bugs (e.g. stale daily-bar reuse) that were never reset.

This script answers that different question: replay the runtime from
capital, sleeve-by-sleeve, cycle-by-cycle, using today's corrected
scripts.run_core_v1_paper_live functions (execute_paper_fill,
apply_cash_yield, mark_to_market — imported directly, not reimplemented,
so this is genuinely "what would today's code have produced"), driven
only by the historical (price, target_exposure) pairs already recorded in
core_v1_signals.jsonl. Comparing the replay to what state.json actually
holds — cycle by cycle, using each signal event's own recorded totals as
a historical snapshot of state.json at that moment — pinpoints exactly
when and how far the live state has drifted from a clean genesis.

Two independent cash-yield estimates are cross-checked against a third:
  (a) replayed  — apply_cash_yield() run against BIL bars reconstructed
      from core_v1_market_data.jsonl (or, if that log is unavailable, the
      as-logged cash_yield_applied totals from core_v1_signals.jsonl).
  (b) signals-log sum — sum of cash_yield_applied across every cycle.
  (c) cash-ledger residual — live cash minus a fills-only replay that
      never applies any cash yield at all (the same technique
      audit_core_v1_accounting.py uses to explain its "Cash Yield" line).
(a) and (b) should agree closely; if (c) is materially larger than both,
the live state's cash yield figure includes more than genuine BIL
interest — i.e. it is phantom, most likely inherited from historical
stale-price or daily-bar-completion bugs that inflated cash directly.

Read-only. Never touches state.json, the logs, or the runtime.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from runtime.core_v1.allocation import SELECTED_CORE_V1_SLEEVES

CASH_YIELD_FAMILIES = {"equity", "gold"}
CASH_SENSITIVE_FIELDS = {"nav", "cash", "position_value", "cost_basis", "unrealized_pnl", "fees", "high_water_nav"}
SLEEVE_BY_LABEL = {s.label: s for s in SELECTED_CORE_V1_SLEEVES}
STALE_BAR_GAP_DAYS = 5  # a daily bar advancing by more than this many calendar days (or going backwards) is not an ordinary weekend/holiday gap
IMPLAUSIBLE_SINGLE_YIELD_FRAC = 0.005  # >0.5% in one credit is far beyond any plausible single/multi-day BIL return


def _load_runtime_module():
    """Imports scripts/run_core_v1_paper_live.py as a module so this script
    replays through the actual current execute_paper_fill / apply_cash_yield
    / mark_to_market / sleeve_nav / default_sleeve_state functions, rather
    than a second, possibly-drifted reimplementation of the same logic."""
    path = Path(__file__).resolve().parent / "run_core_v1_paper_live.py"
    spec = importlib.util.spec_from_file_location("core_v1_runtime_under_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def money(x: float | None) -> str:
    return "—" if x is None else f"${x:,.2f}"


def signed_money(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{'+' if x >= 0 else '-'}${abs(x):,.2f}"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"required input not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    if not path.exists():
        return [], 0
    rows: list[dict[str, Any]] = []
    malformed = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            malformed += 1
    return rows, malformed


def infer_rates_from_fill(fill: dict[str, Any] | None, fallback_fee_rate: float, fallback_slippage_bps: float) -> tuple[float, float]:
    """Recovers the exact fee_rate/slippage_bps a historical fill was executed
    under from its own recorded fields, so replaying it through today's
    execute_paper_fill isolates logic differences from rate-assumption noise.
    Falls back to the provided defaults only when no fill occurred (nothing
    to infer from) or the fill's numbers are degenerate.
    """
    if not fill:
        return fallback_fee_rate, fallback_slippage_bps
    notional = float(fill.get("notional") or 0.0)
    fee = float(fill.get("fee") or 0.0)
    fee_rate = fee / notional if notional > 1e-9 else fallback_fee_rate
    fill_price = float(fill.get("price") or 0.0)
    mid = float(fill.get("mid") or 0.0)
    if mid > 1e-9 and fill_price > 0:
        side = str(fill.get("side", "")).upper()
        slip_frac = (fill_price / mid - 1.0) if side == "BUY" else (1.0 - fill_price / mid)
        slippage_bps = slip_frac * 10000.0
    else:
        slippage_bps = fallback_slippage_bps
    return fee_rate, slippage_bps


def build_bil_frame(rt, market_data_rows: list[dict[str, Any]]):
    """A single, ever-available BIL close-price series built from every
    per-cycle 'BIL_yield' row in core_v1_market_data.jsonl, deduplicated by
    timestamp. Passing progressively larger prefixes of this frame into
    apply_cash_yield (as replay proceeds cycle by cycle) reproduces exactly
    what the live runtime saw at each point in time, with no look-ahead.
    """
    pd = rt.pd
    bil_rows = [r for r in market_data_rows if r.get("sleeve") == "BIL_yield" or r.get("asset") == "BIL"]
    if not bil_rows:
        return None
    bil_rows.sort(key=lambda r: (r.get("cycle", 0), str(r.get("timestamp", ""))))
    frame = pd.DataFrame({
        "timestamp": pd.to_datetime([r["timestamp"] for r in bil_rows], utc=True, errors="coerce").tz_convert(None),
        "close": [float(r["close"]) for r in bil_rows],
        "cycle": [int(r.get("cycle", 0)) for r in bil_rows],
    }).dropna(subset=["timestamp"])
    frame = frame.drop_duplicates(subset="timestamp", keep="last").set_index("timestamp").sort_index()
    return frame


def bil_prefix_for_cycle(bil_frame, cycle: int):
    if bil_frame is None:
        return None
    sub = bil_frame[bil_frame["cycle"] <= cycle]
    return sub[["close"]] if not sub.empty else None


def check_genesis_completeness(sorted_events: list[dict[str, Any]], fills: list[dict[str, Any]]) -> dict[str, Any]:
    reasons: list[str] = []
    if not sorted_events:
        return {"complete": False, "reasons": ["core_v1_signals.jsonl has no events — nothing to replay"]}

    first_event = sorted_events[0]
    first_cycle = first_event.get("cycle")
    if first_cycle not in (1, None) and first_cycle != 1:
        reasons.append(f"earliest logged cycle is #{first_cycle}, not #1 — earlier cycles were never logged (or the log has rotated)")

    for row in first_event.get("signals", []):
        exposure_before = float(row.get("current_exposure_before") or 0.0)
        if abs(exposure_before) > 1e-9:
            reasons.append(f"{row.get('sleeve')} already had {exposure_before:.2%} exposure at the first logged cycle — a position existed before logging began")

    first_ts = first_event.get("timestamp")
    if first_ts and fills:
        earliest_fill_ts = min((f.get("timestamp") or "9999" for f in fills), default=None)
        if earliest_fill_ts and str(earliest_fill_ts) < str(first_ts):
            reasons.append(f"earliest fill ({earliest_fill_ts}) predates the earliest logged signal cycle ({first_ts})")

    return {"complete": not reasons, "reasons": reasons}


def find_suspicious_bar_transitions(sorted_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flags, per daily-bar sleeve, any transition between distinct bar dates
    that is not an ordinary weekend/holiday gap (>STALE_BAR_GAP_DAYS calendar
    days forward, or any move backwards) — the signature of the runtime
    getting stuck on (or double-consuming) a daily bar.
    """
    import pandas as pd

    last_date: dict[str, Any] = {}
    suspicious: list[dict[str, Any]] = []
    for event in sorted_events:
        cycle = event.get("cycle")
        for row in event.get("signals", []):
            label = row.get("sleeve")
            sleeve = SLEEVE_BY_LABEL.get(label)
            if sleeve is None or sleeve.timeframe != "1D":
                continue
            bar_ts = pd.to_datetime(row.get("bar_timestamp"), errors="coerce")
            if pd.isna(bar_ts):
                continue
            bar_date = bar_ts.normalize()
            prev = last_date.get(label)
            if prev is not None and bar_date != prev:
                gap_days = (bar_date - prev).days
                if gap_days < 0 or gap_days > STALE_BAR_GAP_DAYS:
                    suspicious.append({
                        "sleeve": label, "cycle": cycle, "timestamp": event.get("timestamp"),
                        "previous_bar_date": str(prev.date()), "new_bar_date": str(bar_date.date()), "gap_days": gap_days,
                    })
            if prev is None or bar_date != prev:
                last_date[label] = bar_date
    return suspicious


def classify_divergence(field: str, label: str, cycle: int, suspicious_bars: list[dict[str, Any]], genesis: dict[str, Any], missing_log: bool) -> str:
    if missing_log:
        return "missing log data"
    if not genesis["complete"]:
        return "expected due to unavailable historical state"
    for sb in suspicious_bars:
        if sb["sleeve"] == label and abs(sb["cycle"] - cycle) <= 2:
            return "stale price artifact"
    if "cash" in field or "yield" in field:
        return "cash yield artifact"
    return "unknown"


def replay(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    rt = _load_runtime_module()

    state_path = Path(args.state_path)
    fills_path = Path(args.fills_log)
    signals_path = Path(args.signals_log)
    market_data_path = Path(args.market_data_log) if args.market_data_log else None

    live_state = read_json(state_path)
    fills, malformed_fill_lines = read_jsonl(fills_path)
    signals, malformed_signal_lines = read_jsonl(signals_path)
    market_data, malformed_market_lines = read_jsonl(market_data_path) if market_data_path else ([], 0)

    tol = args.dollar_tolerance
    capital = float(live_state.get("capital", args.capital))
    sorted_events = sorted(signals, key=lambda e: (e.get("cycle", 0), str(e.get("timestamp", ""))))

    genesis = check_genesis_completeness(sorted_events, fills)
    suspicious_bars = find_suspicious_bar_transitions(sorted_events)
    bil_frame = build_bil_frame(rt, market_data)
    cash_yield_reconstruction_mode = "market_data_log" if bil_frame is not None else ("signals_log_fallback" if sorted_events else "unavailable")
    # In fallback mode, cash yield is only distributed approximately across
    # sleeves (proportional to cash, not each sleeve's own BIL-return math),
    # so small resulting drift in these fields reflects that approximation,
    # not contamination — widen their tolerance rather than let it flip a
    # PARTIAL (can't fully reconstruct) into a false FAIL (contaminated).
    effective_tol = {
        field: tol if (cash_yield_reconstruction_mode == "market_data_log" or field not in CASH_SENSITIVE_FIELDS) else max(tol, args.cash_yield_fallback_tolerance)
        for field in ("nav", "cash", "position_value", "cost_basis", "unrealized_pnl", "realized_pnl", "fees", "slippage", "high_water_nav", "drawdown_frac")
    }
    fill_tol = tol if cash_yield_reconstruction_mode == "market_data_log" else max(tol, args.cash_yield_fallback_tolerance)

    full_state = {
        "sleeves": {s.label: rt.default_sleeve_state(capital, s.weight) for s in SELECTED_CORE_V1_SLEEVES},
        "realized_pnl": 0.0, "realized_fees": 0.0, "realized_slippage": 0.0,
    }
    fills_only_state = {
        "sleeves": {s.label: rt.default_sleeve_state(capital, s.weight) for s in SELECTED_CORE_V1_SLEEVES},
        "realized_pnl": 0.0, "realized_fees": 0.0, "realized_slippage": 0.0,
    }

    full_hwm = capital
    fill_divergences: list[dict[str, Any]] = []
    cycle_history: list[dict[str, Any]] = []
    cash_yield_events: list[dict[str, Any]] = []
    cash_yield_cumulative = 0.0
    cash_yield_per_sleeve = {s.label: 0.0 for s in SELECTED_CORE_V1_SLEEVES}
    residual_series: list[dict[str, Any]] = []
    first_divergence_cycle: int | None = None
    missing_signal_rows = 0

    for event in sorted_events:
        cycle = event.get("cycle")
        rows_by_label = {r.get("sleeve"): r for r in event.get("signals", [])}
        prices_this_cycle: dict[str, float] = {}
        cash_yield_this_cycle = 0.0
        bil_prefix = bil_prefix_for_cycle(bil_frame, cycle)

        for sleeve in SELECTED_CORE_V1_SLEEVES:
            label = sleeve.label
            row = rows_by_label.get(label)
            if row is None:
                missing_signal_rows += 1
                continue
            price = float(row["price"])
            target_exposure = float(row["target_exposure"])
            actual_fill = row.get("fill")
            prices_this_cycle[label] = price

            if sleeve.family in CASH_YIELD_FAMILIES:
                if bil_prefix is not None and not bil_prefix.empty:
                    y = rt.apply_cash_yield(full_state, label, sleeve.family, bil_prefix)
                elif cash_yield_reconstruction_mode == "signals_log_fallback":
                    # No market-data log available: distribute this cycle's logged
                    # aggregate cash_yield_applied across yield-eligible sleeves in
                    # proportion to their current cash, as an approximation.
                    aggregate = float(event.get("cash_yield_applied", 0.0) or 0.0)
                    eligible_cash = {
                        s2.label: float(full_state["sleeves"][s2.label].get("cash", 0.0))
                        for s2 in SELECTED_CORE_V1_SLEEVES if s2.family in CASH_YIELD_FAMILIES
                    }
                    total_eligible_cash = sum(eligible_cash.values())
                    share = (eligible_cash.get(label, 0.0) / total_eligible_cash) if total_eligible_cash > 1e-9 else 0.0
                    y = aggregate * share
                    full_state["sleeves"][label]["cash"] = float(full_state["sleeves"][label].get("cash", 0.0)) + y
                else:
                    y = 0.0
                if abs(y) > 1e-12:
                    cash_before = float(full_state["sleeves"][label].get("cash", 0.0)) - y
                    growth_frac = y / cash_before if cash_before > 1e-9 else 0.0
                    cash_yield_cumulative += y
                    cash_yield_per_sleeve[label] += y
                    cash_yield_this_cycle += y
                    cash_yield_events.append({
                        "cycle": cycle, "sleeve": label, "timestamp": event.get("timestamp"),
                        "amount": y, "growth_frac": growth_frac,
                        "implausible": abs(growth_frac) > IMPLAUSIBLE_SINGLE_YIELD_FRAC,
                    })

            fee_rate, slippage_bps = infer_rates_from_fill(actual_fill, args.fee if sleeve.family == "trend" else args.equity_fee,
                                                             args.crypto_slippage_bps if sleeve.family == "trend" else args.equity_slippage_bps)
            replayed_fill = rt.execute_paper_fill(full_state, label, price, target_exposure, fee_rate, slippage_bps, args.rebalance_threshold)
            rt.execute_paper_fill(fills_only_state, label, price, target_exposure, fee_rate, slippage_bps, args.rebalance_threshold)

            # A fill for a yield-eligible sleeve depends on that sleeve's cash,
            # which in fallback reconstruction mode carries approximation
            # noise from the proportional cash-yield split above — widen its
            # tolerance the same way, so that noise doesn't masquerade as a
            # fill-level divergence. Trend/crypto sleeves never receive cash
            # yield, so their fills stay held to the strict tolerance.
            this_fill_tol = fill_tol if sleeve.family in CASH_YIELD_FAMILIES else tol
            for f_field in ("qty", "notional", "fee", "realized_pnl"):
                exp_val = (replayed_fill or {}).get(f_field)
                act_val = (actual_fill or {}).get(f_field)
                if exp_val is None and act_val is None:
                    continue
                exp_num = float(exp_val) if exp_val is not None else 0.0
                act_num = float(act_val) if act_val is not None else 0.0
                if abs(exp_num - act_num) > this_fill_tol:
                    cause = classify_divergence(f"fill.{f_field}", label, cycle, suspicious_bars, genesis, False)
                    if first_divergence_cycle is None:
                        first_divergence_cycle = cycle
                    fill_divergences.append({
                        "cycle": cycle, "sleeve": label, "field": f"fill.{f_field}", "timestamp": event.get("timestamp"),
                        "expected_replayed": exp_num, "live_stored": act_num, "difference": act_num - exp_num, "likely_cause": cause,
                    })

            full_state["sleeves"][label]["last_price"] = price
            full_state["sleeves"][label]["last_timestamp"] = row.get("bar_timestamp")
            fills_only_state["sleeves"][label]["last_price"] = price
            fills_only_state["sleeves"][label]["last_timestamp"] = row.get("bar_timestamp")

        def totals_for(state_dict):
            nav = sum(rt.sleeve_nav(state_dict["sleeves"][s.label], prices_this_cycle.get(s.label, state_dict["sleeves"][s.label].get("last_price") or 0.0)) for s in SELECTED_CORE_V1_SLEEVES)
            cash = sum(float(state_dict["sleeves"][s.label].get("cash", 0.0)) for s in SELECTED_CORE_V1_SLEEVES)
            mtms = {s.label: rt.mark_to_market(state_dict["sleeves"][s.label], prices_this_cycle.get(s.label, state_dict["sleeves"][s.label].get("last_price") or 0.0)) for s in SELECTED_CORE_V1_SLEEVES}
            position_value = sum(v["position_value"] for v in mtms.values())
            cost_basis = sum(v["cost_basis"] for v in mtms.values())
            unrealized = sum(v["unrealized_pnl"] for v in mtms.values())
            return {"nav": nav, "cash": cash, "position_value": position_value, "cost_basis": cost_basis, "unrealized_pnl": unrealized,
                    "realized_pnl": state_dict["realized_pnl"], "fees": state_dict["realized_fees"], "slippage": state_dict["realized_slippage"]}

        full_totals = totals_for(full_state)
        fills_only_totals = totals_for(fills_only_state)
        full_hwm = max(full_hwm, full_totals["nav"])

        live_totals = {
            "nav": event.get("total_nav"), "cash": event.get("cash_total"), "position_value": event.get("position_value_total"),
            "cost_basis": event.get("cost_basis_total"), "unrealized_pnl": event.get("unrealized_pnl"),
            "realized_pnl": event.get("realized_pnl"), "fees": event.get("fees_total"), "slippage": event.get("slippage_total"),
        }
        cycle_diffs = {}
        for field in ("nav", "cash", "position_value", "cost_basis", "unrealized_pnl", "realized_pnl", "fees", "slippage"):
            live_val = live_totals.get(field)
            replayed_val = full_totals.get(field)
            if live_val is None:
                continue
            diff = float(live_val) - replayed_val
            cycle_diffs[field] = diff
            if abs(diff) > effective_tol.get(field, tol):
                cause = classify_divergence(field, "portfolio", cycle, suspicious_bars, genesis, False)
                if first_divergence_cycle is None:
                    first_divergence_cycle = cycle
                fill_divergences.append({
                    "cycle": cycle, "sleeve": "portfolio", "field": field, "timestamp": event.get("timestamp"),
                    "expected_replayed": replayed_val, "live_stored": float(live_val), "difference": diff, "likely_cause": cause,
                })

        residual_cash = float(event.get("cash_total") or 0.0) - fills_only_totals["cash"]
        residual_series.append({"cycle": cycle, "timestamp": event.get("timestamp"), "residual_cash_vs_no_yield_replay": residual_cash})

        cycle_history.append({
            "cycle": cycle, "timestamp": event.get("timestamp"),
            "replayed": full_totals, "live": live_totals, "diffs": cycle_diffs,
            "cash_yield_this_cycle": cash_yield_this_cycle,
            "cash_yield_cumulative": cash_yield_cumulative,
            "residual_cash_vs_no_yield_replay": residual_cash,
        })

    # First cycle where the phantom (no-yield) residual jumps abnormally.
    residual_jump_cycle = None
    prev_residual = 0.0
    typical_jump = None
    deltas = [abs(r["residual_cash_vs_no_yield_replay"] - (residual_series[i - 1]["residual_cash_vs_no_yield_replay"] if i else 0.0)) for i, r in enumerate(residual_series)]
    if len(deltas) > 3:
        sorted_deltas = sorted(deltas)
        typical_jump = sorted_deltas[len(sorted_deltas) // 2] or 0.01
        for i, r in enumerate(residual_series):
            if deltas[i] > max(10 * typical_jump, 5.0):
                residual_jump_cycle = r["cycle"]
                break

    last_prices = {s.label: full_state["sleeves"][s.label].get("last_price") or 0.0 for s in SELECTED_CORE_V1_SLEEVES}
    mtms_final = {s.label: rt.mark_to_market(full_state["sleeves"][s.label], last_prices[s.label]) for s in SELECTED_CORE_V1_SLEEVES}
    final_nav = sum(rt.sleeve_nav(full_state["sleeves"][s.label], last_prices[s.label]) for s in SELECTED_CORE_V1_SLEEVES)
    replayed_final = {
        "nav": final_nav,
        "cash": sum(float(full_state["sleeves"][s.label].get("cash", 0.0)) for s in SELECTED_CORE_V1_SLEEVES),
        "position_value": sum(v["position_value"] for v in mtms_final.values()),
        "cost_basis": sum(v["cost_basis"] for v in mtms_final.values()),
        "unrealized_pnl": sum(v["unrealized_pnl"] for v in mtms_final.values()),
        "realized_pnl": full_state["realized_pnl"],
        "fees": full_state["realized_fees"],
        "slippage": full_state["realized_slippage"],
        "high_water_nav": full_hwm,
        "drawdown_frac": (final_nav / full_hwm - 1.0) if full_hwm else 0.0,
        "cash_yield": cash_yield_cumulative,
    }
    live_final = {
        "nav": float(live_state.get("last_total_nav", 0.0) or 0.0),
        "cash": float(live_state.get("total_cash", 0.0) or 0.0),
        "position_value": float(live_state.get("total_position_value", 0.0) or 0.0),
        "cost_basis": float(live_state.get("total_cost_basis", 0.0) or 0.0),
        "unrealized_pnl": float(live_state.get("unrealized_pnl", 0.0) or 0.0),
        "realized_pnl": float(live_state.get("realized_pnl", 0.0) or 0.0),
        "fees": float(live_state.get("realized_fees", 0.0) or 0.0),
        "slippage": float(live_state.get("realized_slippage", 0.0) or 0.0),
        "high_water_nav": float(live_state.get("high_water_nav", 0.0) or 0.0),
        "drawdown_frac": float(live_state.get("drawdown_frac", 0.0) or 0.0),
    }

    final_comparison: dict[str, Any] = {}
    for field in ("nav", "cash", "position_value", "cost_basis", "unrealized_pnl", "realized_pnl", "fees", "slippage", "high_water_nav", "drawdown_frac"):
        replayed_val = replayed_final.get(field)
        live_val = live_final.get(field)
        final_comparison[field] = {"replayed": replayed_val, "live": live_val, "difference": (live_val - replayed_val) if (replayed_val is not None and live_val is not None) else None}

    per_sleeve_comparison = []
    for sleeve in SELECTED_CORE_V1_SLEEVES:
        label = sleeve.label
        rs = full_state["sleeves"][label]
        ls = live_state.get("sleeves", {}).get(label, {})
        row = {
            "sleeve": label, "family": sleeve.family,
            "cash": {"replayed": float(rs.get("cash", 0.0)), "live": float(ls.get("cash", 0.0) or 0.0)},
            "qty": {"replayed": float(rs.get("qty", 0.0)), "live": float(ls.get("qty", 0.0) or 0.0)},
            "cost_basis": {"replayed": float(rs.get("cost_basis", 0.0)), "live": float(ls.get("cost_basis", 0.0) or 0.0)},
            "avg_entry": {"replayed": rs.get("avg_entry"), "live": ls.get("avg_entry")},
            "realized_pnl": {"replayed": float(rs.get("realized_pnl", 0.0)), "live": float(ls.get("realized_pnl", 0.0) or 0.0)},
            "unrealized_pnl": {"replayed": mtms_final[label]["unrealized_pnl"], "live": None},
            "market_value": {"replayed": mtms_final[label]["position_value"], "live": None},
            "last_price": {"replayed": rs.get("last_price"), "live": ls.get("last_price")},
            "last_timestamp": {"replayed": rs.get("last_timestamp"), "live": ls.get("last_timestamp")},
            "cash_yield_credited": {"replayed": cash_yield_per_sleeve[label], "live": None},
        }
        t = live_state.get("sleeve_telemetry", {}).get(label, {})
        row["unrealized_pnl"]["live"] = float(t.get("unrealized_pnl")) if t.get("unrealized_pnl") is not None else None
        row["market_value"]["live"] = float(t.get("position_value")) if t.get("position_value") is not None else None
        for f in ("cash", "qty", "cost_basis", "realized_pnl"):
            row[f]["difference"] = row[f]["live"] - row[f]["replayed"]
        per_sleeve_comparison.append(row)

    # --- Cash yield forensics: three independent estimates ---
    cash_yield_signals_sum = sum(float(ev.get("cash_yield_applied", 0.0) or 0.0) for ev in sorted_events) if sorted_events else None
    live_cash_from_state = float(live_state.get("total_cash", 0.0) or 0.0)
    fills_only_final_cash = sum(float(fills_only_state["sleeves"][s.label].get("cash", 0.0)) for s in SELECTED_CORE_V1_SLEEVES)
    cash_yield_ledger_residual = live_cash_from_state - fills_only_final_cash

    cash_yield_forensics = {
        "replayed_via_apply_cash_yield": cash_yield_cumulative,
        "reconstruction_mode": cash_yield_reconstruction_mode,
        "signals_log_sum": cash_yield_signals_sum,
        "cash_ledger_residual_vs_live": cash_yield_ledger_residual,
        "suspected_phantom_amount": (cash_yield_ledger_residual - cash_yield_cumulative) if cash_yield_cumulative is not None else None,
        "residual_note": (
            "The (c) cash-ledger residual is informational, not a pass/fail trigger: it understates true cumulative "
            "cash yield whenever yield-derived cash gets reinvested into new positions rather than sitting idle (a "
            "fills-only replay without any yield then buys fewer shares too, not just less cash, so the two replays' "
            "final cash balances converge even though yield was genuinely credited along the way). Treat (a) vs (b) "
            "as the reliable cross-check; use (c) only when cash utilization stays well below 100% throughout."
        ),
        "first_abnormal_residual_jump_cycle": residual_jump_cycle,
        "per_sleeve_replayed_cash_yield": cash_yield_per_sleeve,
        "implausible_single_credits": [e for e in cash_yield_events if e["implausible"]],
    }

    final_comparison_mismatches = [
        {"field": field, **cell} for field, cell in final_comparison.items()
        if cell.get("difference") is not None and abs(cell["difference"]) > effective_tol.get(field, tol)
    ]

    material_findings = (
        [d for d in fill_divergences if abs(d["difference"]) > tol]
        + cash_yield_forensics["implausible_single_credits"]
        + final_comparison_mismatches
    )

    if not genesis["complete"] or cash_yield_reconstruction_mode != "market_data_log" or malformed_fill_lines or malformed_signal_lines or missing_signal_rows:
        verdict = "FAIL" if material_findings else "PARTIAL"
    else:
        verdict = "FAIL" if material_findings else "PASS"

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "verdict": verdict,
        "inputs": {
            "state_path": str(state_path), "fills_log": str(fills_path), "signals_log": str(signals_path),
            "market_data_log": str(market_data_path) if market_data_path else None,
            "fill_count": len(fills), "signal_event_count": len(signals),
            "malformed_fill_lines": malformed_fill_lines, "malformed_signal_lines": malformed_signal_lines,
            "malformed_market_data_lines": malformed_market_lines, "missing_signal_rows": missing_signal_rows,
        },
        "genesis_completeness": genesis,
        "suspicious_bar_transitions": suspicious_bars,
        "first_divergence_cycle": first_divergence_cycle,
        "divergences": fill_divergences,
        "cash_yield_forensics": cash_yield_forensics,
        "final_comparison": final_comparison,
        "final_comparison_mismatches": final_comparison_mismatches,
        "material_findings_count": len(material_findings),
        "per_sleeve_comparison": per_sleeve_comparison,
        "cycle_history": cycle_history,
    }
    return (0 if verdict == "PASS" else (2 if verdict == "FAIL" else 1)), report


def write_json_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    tmp.replace(path)


def write_csv_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["sleeve", "family", "field", "replayed", "live", "difference"]
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in report["per_sleeve_comparison"]:
            for field in ("cash", "qty", "cost_basis", "realized_pnl", "unrealized_pnl", "market_value"):
                cell = row[field]
                writer.writerow({"sleeve": row["sleeve"], "family": row["family"], "field": field,
                                  "replayed": cell.get("replayed"), "live": cell.get("live"), "difference": cell.get("difference")})
        writer.writerow({})
        for field, cell in report["final_comparison"].items():
            writer.writerow({"sleeve": "PORTFOLIO", "family": "", "field": field,
                              "replayed": cell.get("replayed"), "live": cell.get("live"), "difference": cell.get("difference")})
    tmp.replace(path)


def print_report(report: dict[str, Any]) -> None:
    bar = "=" * 50
    print(bar)
    print("Genesis Completeness")
    print(bar)
    g = report["genesis_completeness"]
    if g["complete"]:
        print("Signals log covers genesis: no evidence of pre-existing, unlogged state.")
    else:
        print("Signals log does NOT fully cover genesis:")
        for reason in g["reasons"]:
            print(f"  - {reason}")
    print()

    print(bar)
    print("Final Comparison: Replayed (clean, from capital) vs Live state.json")
    print(bar)
    for field, cell in report["final_comparison"].items():
        diff = cell["difference"]
        flag = "" if diff is None or abs(diff) <= 0.01 else "  <-- DIVERGES"
        print(f"{field:16s}: replayed={money(cell['replayed']) if 'pnl' in field or field in ('nav','cash','position_value','cost_basis','fees','slippage','high_water_nav') else cell['replayed']} "
              f"live={cell['live']} diff={cell['difference']}{flag}")
    print()

    print(bar)
    print("Cash Yield Forensics")
    print(bar)
    cy = report["cash_yield_forensics"]
    print(f"Reconstruction mode                          : {cy['reconstruction_mode']}")
    print(f"(a) Replayed via apply_cash_yield             : {signed_money(cy['replayed_via_apply_cash_yield'])}")
    print(f"(b) Sum of cash_yield_applied (signals log)   : {signed_money(cy['signals_log_sum'])}")
    print(f"(c) Cash-ledger residual vs live (no-yield replay): {signed_money(cy['cash_ledger_residual_vs_live'])}")
    print(f"Suspected phantom amount ((c) - (a))           : {signed_money(cy['suspected_phantom_amount'])}")
    if cy["first_abnormal_residual_jump_cycle"] is not None:
        print(f"First cycle with an abnormal residual jump    : cycle #{cy['first_abnormal_residual_jump_cycle']}")
    if cy["implausible_single_credits"]:
        print("Implausible single cash-yield credits:")
        for e in cy["implausible_single_credits"]:
            print(f"  cycle #{e['cycle']} {e['sleeve']} @ {e['timestamp']}: {signed_money(e['amount'])} ({e['growth_frac']:+.4%} in one credit)")
    print()

    if report["suspicious_bar_transitions"]:
        print(bar)
        print("Suspicious Daily-Bar Transitions")
        print(bar)
        for sb in report["suspicious_bar_transitions"]:
            print(f"  {sb['sleeve']} cycle #{sb['cycle']} @ {sb['timestamp']}: bar jumped {sb['previous_bar_date']} -> {sb['new_bar_date']} ({sb['gap_days']} days)")
        print()

    print(bar)
    print("Per-Sleeve Comparison (final state)")
    print(bar)
    for row in report["per_sleeve_comparison"]:
        print(f"{row['sleeve']} ({row['family']})")
        for field in ("cash", "qty", "cost_basis", "realized_pnl", "unrealized_pnl", "market_value"):
            cell = row[field]
            print(f"  {field:14s}: replayed={cell.get('replayed')} live={cell.get('live')} diff={cell.get('difference')}")
    print()

    print(bar)
    print("Divergences")
    print(bar)
    if report["divergences"]:
        print(f"First divergence at cycle #{report['first_divergence_cycle']}")
        for d in report["divergences"]:
            print(
                f"  cycle #{d['cycle']} sleeve={d['sleeve']} field={d['field']} ts={d['timestamp']} "
                f"expected={d['expected_replayed']} stored={d['live_stored']} diff={d['difference']} cause={d['likely_cause']}"
            )
    else:
        print("No cycle-level divergences detected between replay and the historical signals-log snapshots.")
    print()

    print(bar)
    print("Result")
    print(bar)
    verdict = report["verdict"]
    print(verdict)
    if verdict == "PASS":
        print("Clean replay from genesis reproduces live state within rounding — the current state is economically valid, not just internally consistent.")
    elif verdict == "PARTIAL":
        print("Some reconstruction is impossible from available logs (see Genesis Completeness / reconstruction mode above), but no material contamination was found in what could be checked.")
    else:
        nav_gap = report["final_comparison"]["nav"]["difference"]
        print("Replayed clean state MATERIALLY DIVERGES from live state.json.")
        if nav_gap is not None:
            print(f"Suspected phantom NAV: live state.json holds {signed_money(nav_gap)} more than a clean replay from genesis can account for.")
        if report["first_divergence_cycle"] is not None:
            print(f"This first became visible at cycle #{report['first_divergence_cycle']} — see Divergences above for the exact field(s) and likely cause.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Forensic genesis-to-now state replay audit for the Core v1 paper runtime")
    p.add_argument("--state-path", default=os.getenv("CORE_V1_STATE_PATH", "/opt/itera/runtime/core_v1/state.json"))
    p.add_argument("--fills-log", default=os.getenv("CORE_V1_FILLS_LOG", "/opt/itera/logs/core_v1_fills.jsonl"))
    p.add_argument("--signals-log", default=os.getenv("CORE_V1_SIGNALS_LOG", "/opt/itera/logs/core_v1_signals.jsonl"))
    p.add_argument("--market-data-log", default=os.getenv("CORE_V1_MARKET_DATA_LOG", "/opt/itera/logs/core_v1_market_data.jsonl"))
    p.add_argument("--capital", type=float, default=float(os.getenv("CORE_V1_CAPITAL", "100000")))
    p.add_argument("--fee", type=float, default=float(os.getenv("FEE_RATE", "0.0006")))
    p.add_argument("--equity-fee", type=float, default=float(os.getenv("EQUITY_FEE_RATE", "0.0001")))
    p.add_argument("--crypto-slippage-bps", type=float, default=float(os.getenv("CORE_V1_CRYPTO_SLIPPAGE_BPS", "3.0")))
    p.add_argument("--equity-slippage-bps", type=float, default=float(os.getenv("CORE_V1_EQUITY_SLIPPAGE_BPS", "0.5")))
    p.add_argument("--rebalance-threshold", type=float, default=float(os.getenv("REBALANCE_THRESHOLD", "0.02")))
    p.add_argument("--dollar-tolerance", type=float, default=0.01)
    p.add_argument("--cash-yield-fallback-tolerance", type=float, default=5.0, help="Wider tolerance applied to cash/NAV-sensitive fields only when core_v1_market_data.jsonl is unavailable and cash yield must be approximated from the signals log.")
    p.add_argument("--json-output", default=os.getenv("CORE_V1_STATE_REPLAY_JSON_PATH", str(REPO_ROOT / "artifacts" / "core_v1_state_replay_audit.json")))
    p.add_argument("--csv-output", default=os.getenv("CORE_V1_STATE_REPLAY_CSV_PATH", str(REPO_ROOT / "artifacts" / "core_v1_state_replay_audit.csv")))
    p.add_argument("--json", action="store_true", help="Print the full JSON report to stdout instead of the human-readable console report.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    code, report = replay(args)
    write_json_report(Path(args.json_output), report)
    write_csv_report(Path(args.csv_output), report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
    else:
        print_report(report)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
