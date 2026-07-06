#!/usr/bin/env python
"""Forensic accounting reconciliation for the Core v1 paper runtime.

This is not a price or strategy audit (see audit_core_v1_prices.py for that).
It proves every dollar of P&L Mission Control displays by independently
recomputing the ledger from scratch — purely from state.json and
core_v1_fills.jsonl, with no network calls and no dependency on the runtime
or dashboard code paths it is checking.

Accounting model this script verifies (reverse-engineered from
scripts/run_core_v1_paper_live.py's execute_paper_fill/mark_to_market/
apply_cash_yield, and confirmed by direct simulation):

- Each fill's fee is folded into cost_basis on entry (BUY) and subtracted
  directly from that trade's realized P&L on exit (SELL). It is never a
  separate deduction from NAV — "Lifetime Fees" is an informational total,
  not a ledger line that reduces P&L again on top of Realized/Unrealized.
- "Slippage" is likewise informational: the executed fill_price already
  contains the slippage premium, so slippage_cost is a reporting metric of
  execution quality, not a second cash outflow.
- Equity/gold sleeves accrue BIL-rate interest on idle cash every cycle
  (apply_cash_yield), credited straight into that sleeve's cash balance.
  This is real income, but it is never recorded in realized_pnl,
  unrealized_pnl, realized_fees, or realized_slippage — it only shows up as
  cash that fill-by-fill replay can't otherwise explain. It is exactly this
  yield that makes NAV grow faster than Realized + Unrealized alone, which
  is the "unrealized P&L looks small relative to total P&L" effect this
  script was written to explain rather than assume as a bug.

The correct identity is therefore:

    Initial Capital + Realized P&L + Unrealized P&L + Cash Yield = NAV

not the naive "... - Fees - Slippage = NAV" (that double-counts costs
already embedded in Realized/Unrealized). Both are reported below so the
naive formula's expected mismatch is never mistaken for a defect.
"""

from __future__ import annotations

import argparse
import csv
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
SLEEVE_ORDER = [s.label for s in SELECTED_CORE_V1_SLEEVES]


def money(x: float | None) -> str:
    return "—" if x is None else f"${x:,.2f}"


def signed_money(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{'+' if x >= 0 else '-'}${abs(x):,.2f}"


def pct(x: float | None) -> str:
    return "—" if x is None else f"{x:+.2%}" if x else "0.00%"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"required input not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Reads every line (no truncation — this is a full historical audit).

    Returns (rows, malformed_line_count) rather than silently dropping bad
    lines, since a forensic tool should surface a corrupt log rather than
    quietly under-count fills.
    """
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


def recompute_fill_ledger(
    sleeve_fills: list[dict[str, Any]],
    initial_cash: float,
    dollar_tol: float,
    price_tol: float,
) -> dict[str, Any]:
    """Replays a sleeve's fills through the exact arithmetic of
    execute_paper_fill (scripts/run_core_v1_paper_live.py) and cross-checks
    each fill's own recorded after-state against what that arithmetic
    predicts. Uses only fields already stored on each fill — no price
    lookups required.
    """
    qty = 0.0
    cost_basis = 0.0
    cash = initial_cash
    realized = 0.0
    fees = 0.0
    slippage = 0.0
    findings: list[dict[str, Any]] = []

    for i, f in enumerate(sleeve_fills, start=1):
        side = str(f.get("side", "")).upper()
        qf = float(f.get("qty", 0.0) or 0.0)
        fee = float(f.get("fee", 0.0) or 0.0)
        notional = float(f.get("notional", 0.0) or 0.0)
        slip = float(f.get("slippage_cost", 0.0) or 0.0)
        stored_realized = float(f.get("realized_pnl", 0.0) or 0.0)
        stored_cost_basis_after = f.get("cost_basis_after")
        stored_avg_entry_after = f.get("avg_entry_after")
        ts = f.get("timestamp")

        if side == "BUY":
            exp_qty = qty + qf
            exp_cost_basis = cost_basis + notional + fee
            exp_cash = cash - notional - fee
            exp_realized_trade = 0.0
        elif side == "SELL":
            sold_cost_basis = cost_basis * (qf / qty) if qty > 1e-12 else 0.0
            exp_realized_trade = notional - fee - sold_cost_basis
            exp_qty = qty - qf
            exp_cost_basis = max(0.0, cost_basis - sold_cost_basis)
            if exp_qty < 1e-12:
                exp_qty = 0.0
                exp_cost_basis = 0.0
            exp_cash = cash + notional - fee
        else:
            findings.append({"fill_number": i, "timestamp": ts, "field": "side", "expected": "BUY or SELL", "stored": side, "difference": None})
            continue

        exp_avg_entry = exp_cost_basis / exp_qty if exp_qty > 1e-12 and exp_cost_basis > 0 else None

        if stored_cost_basis_after is not None and abs(float(stored_cost_basis_after) - exp_cost_basis) > dollar_tol:
            findings.append({
                "fill_number": i, "timestamp": ts, "field": "cost_basis_after",
                "expected": exp_cost_basis, "stored": float(stored_cost_basis_after),
                "difference": float(stored_cost_basis_after) - exp_cost_basis,
            })
        if abs(exp_realized_trade - stored_realized) > dollar_tol:
            findings.append({
                "fill_number": i, "timestamp": ts, "field": "realized_pnl",
                "expected": exp_realized_trade, "stored": stored_realized,
                "difference": stored_realized - exp_realized_trade,
            })
        if stored_avg_entry_after is not None and exp_avg_entry is not None and abs(float(stored_avg_entry_after) - exp_avg_entry) > price_tol:
            findings.append({
                "fill_number": i, "timestamp": ts, "field": "avg_entry_after",
                "expected": exp_avg_entry, "stored": float(stored_avg_entry_after),
                "difference": float(stored_avg_entry_after) - exp_avg_entry,
            })

        qty, cost_basis, cash = exp_qty, exp_cost_basis, exp_cash
        realized += exp_realized_trade
        fees += fee
        slippage += slip

    return {
        "qty": qty, "cost_basis": cost_basis, "cash": cash, "realized_pnl": realized,
        "fees": fees, "slippage": slippage, "fill_count": len(sleeve_fills), "findings": findings,
    }


def audit(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    state_path = Path(args.state_path)
    fills_path = Path(args.fills_log)
    signals_path = Path(args.signals_log) if args.signals_log else None

    state = read_json(state_path)
    fills, malformed_fill_lines = read_jsonl(fills_path)
    signals, malformed_signal_lines = read_jsonl(signals_path) if signals_path else ([], 0)

    dollar_tol = args.dollar_tolerance
    price_tol = args.price_tolerance
    qty_tol = args.qty_tolerance

    capital = float(state.get("capital", args.capital))
    sleeves_state = state.get("sleeves", {})
    telemetry = state.get("sleeve_telemetry", {})

    total_cash = float(state.get("total_cash", sum(float(sleeves_state.get(l, {}).get("cash", 0.0) or 0.0) for l in SLEEVE_ORDER)))
    total_position_value = float(state.get("total_position_value", 0.0) or 0.0)
    total_cost_basis = float(state.get("total_cost_basis", sum(float(sleeves_state.get(l, {}).get("cost_basis", 0.0) or 0.0) for l in SLEEVE_ORDER)))
    realized_pnl_total = float(state.get("realized_pnl", 0.0) or 0.0)
    unrealized_pnl_total = float(state.get("unrealized_pnl", 0.0) or 0.0)
    fees_total_state = float(state.get("realized_fees", 0.0) or 0.0)
    slippage_total_state = float(state.get("realized_slippage", 0.0) or 0.0)
    total_nav = float(state.get("last_total_nav", total_cash + total_position_value) or 0.0)

    since_inception_pnl = total_nav - capital

    ledger_findings: list[dict[str, Any]] = []
    per_sleeve_rows: list[dict[str, Any]] = []
    all_fill_findings: list[dict[str, Any]] = []
    cash_yield_from_fills_total = 0.0
    fees_from_fills_total = 0.0
    slippage_from_fills_total = 0.0
    cash_ledger_rows: list[dict[str, Any]] = []

    for sleeve in SELECTED_CORE_V1_SLEEVES:
        label = sleeve.label
        s = sleeves_state.get(label, {})
        sleeve_fills = [f for f in fills if f.get("sleeve") == label]
        initial_cash = capital * sleeve.weight

        recon = recompute_fill_ledger(sleeve_fills, initial_cash, dollar_tol, price_tol)
        for ff in recon["findings"]:
            all_fill_findings.append({"sleeve": label, **ff})

        stored_qty = float(s.get("qty", 0.0) or 0.0)
        stored_cost_basis = float(s.get("cost_basis", 0.0) or 0.0)
        stored_cash = float(s.get("cash", 0.0) or 0.0)
        stored_realized = float(s.get("realized_pnl", 0.0) or 0.0)
        stored_avg_entry = s.get("avg_entry")
        last_price = float(s.get("last_price") or 0.0)

        qty_diff = stored_qty - recon["qty"]
        cost_basis_diff = stored_cost_basis - recon["cost_basis"]
        realized_diff = stored_realized - recon["realized_pnl"]
        cash_diff = stored_cash - recon["cash"]
        is_yield_eligible = sleeve.family in CASH_YIELD_FAMILIES

        if abs(qty_diff) > qty_tol:
            ledger_findings.append(f"{label}: final position qty does not match fill replay (stored={stored_qty:.8f}, replayed={recon['qty']:.8f}, diff={qty_diff:.8f})")
        if abs(cost_basis_diff) > dollar_tol:
            ledger_findings.append(f"{label}: final cost basis does not match fill replay (stored={money(stored_cost_basis)}, replayed={money(recon['cost_basis'])}, diff={money(cost_basis_diff)})")
        if abs(realized_diff) > dollar_tol:
            ledger_findings.append(f"{label}: final realized P&L does not match fill replay (stored={money(stored_realized)}, replayed={money(recon['realized_pnl'])}, diff={money(realized_diff)})")
        if not is_yield_eligible and abs(cash_diff) > dollar_tol:
            ledger_findings.append(f"{label}: cash does not reconcile to fills and this sleeve never accrues cash yield (stored={money(stored_cash)}, replayed={money(recon['cash'])}, diff={money(cash_diff)})")

        if is_yield_eligible:
            cash_yield_from_fills_total += cash_diff
        fees_from_fills_total += recon["fees"]
        slippage_from_fills_total += recon["slippage"]

        cash_ledger_rows.append({
            "sleeve": label, "family": sleeve.family, "yield_eligible": is_yield_eligible,
            "stored_cash": stored_cash, "replayed_cash": recon["cash"], "difference": cash_diff,
        })

        position_value = stored_qty * last_price
        unrealized = position_value - stored_cost_basis if abs(stored_qty) > 1e-12 else 0.0
        weight_now = (stored_cash + position_value) / total_nav if total_nav else 0.0

        per_sleeve_rows.append({
            "sleeve": label,
            "family": sleeve.family,
            "position_qty": stored_qty,
            "avg_entry": float(stored_avg_entry) if stored_avg_entry is not None else None,
            "cost_basis": stored_cost_basis,
            "market_value": position_value,
            "realized_pnl": stored_realized,
            "unrealized_pnl": unrealized,
            "lifetime_fees": recon["fees"],
            "lifetime_slippage": recon["slippage"],
            "current_weight": weight_now,
            "fill_count": recon["fill_count"],
        })

    cash_yield_from_signals_total = None
    cash_yield_cross_check_diff = None
    if signals:
        cash_yield_from_signals_total = sum(float(ev.get("cash_yield_applied", 0.0) or 0.0) for ev in signals)
        cash_yield_cross_check_diff = cash_yield_from_fills_total - cash_yield_from_signals_total
        if abs(cash_yield_cross_check_diff) > dollar_tol:
            ledger_findings.append(
                f"cumulative cash yield implied by fill-ledger replay ({money(cash_yield_from_fills_total)}) does not "
                f"match cumulative cash_yield_applied summed from {signals_path.name} ({money(cash_yield_from_signals_total)}), "
                f"diff={money(cash_yield_cross_check_diff)} — one of the two logs may be incomplete"
            )

    fees_ledger_diff = fees_total_state - fees_from_fills_total
    if abs(fees_ledger_diff) > dollar_tol:
        ledger_findings.append(f"state.realized_fees ({money(fees_total_state)}) does not equal the sum of every fill's fee ({money(fees_from_fills_total)}), diff={money(fees_ledger_diff)}")

    slippage_ledger_diff = slippage_total_state - slippage_from_fills_total
    if abs(slippage_ledger_diff) > dollar_tol:
        ledger_findings.append(f"state.realized_slippage ({money(slippage_total_state)}) does not equal the sum of every fill's slippage_cost ({money(slippage_from_fills_total)}), diff={money(slippage_ledger_diff)}")

    # --- P&L identity check ---
    realized_plus_unrealized = realized_pnl_total + unrealized_pnl_total
    naive_diff = since_inception_pnl - realized_plus_unrealized
    adjusted_identity = realized_plus_unrealized + cash_yield_from_fills_total
    adjusted_diff = since_inception_pnl - adjusted_identity
    pnl_identity_pass = abs(adjusted_diff) < dollar_tol

    # --- Accounting identities ---
    identity1_value = total_cash + total_position_value
    identity1_diff = identity1_value - total_nav
    identity1_pass = abs(identity1_diff) < dollar_tol

    identity2_naive_value = capital + realized_pnl_total + unrealized_pnl_total - fees_total_state - slippage_total_state
    identity2_naive_diff = total_nav - identity2_naive_value

    identity2_corrected_value = capital + realized_pnl_total + unrealized_pnl_total + cash_yield_from_fills_total
    identity2_corrected_diff = total_nav - identity2_corrected_value
    identity2_corrected_pass = abs(identity2_corrected_diff) < dollar_tol

    ok = (
        not ledger_findings
        and not all_fill_findings
        and identity1_pass
        and identity2_corrected_pass
        and pnl_identity_pass
        and malformed_fill_lines == 0
        and malformed_signal_lines == 0
    )

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "ok": ok,
        "inputs": {
            "state_path": str(state_path),
            "fills_log": str(fills_path),
            "signals_log": str(signals_path) if signals_path else None,
            "fill_count": len(fills),
            "malformed_fill_lines": malformed_fill_lines,
            "signal_count": len(signals),
            "malformed_signal_lines": malformed_signal_lines,
        },
        "portfolio_summary": {
            "initial_capital": capital,
            "current_nav": total_nav,
            "cash": total_cash,
            "market_value": total_position_value,
            "position_basis": total_cost_basis,
            "since_inception_pnl": since_inception_pnl,
        },
        "pnl_identity_check": {
            "realized_pnl": realized_pnl_total,
            "unrealized_pnl": unrealized_pnl_total,
            "realized_plus_unrealized": realized_plus_unrealized,
            "cash_yield_from_fill_replay": cash_yield_from_fills_total,
            "cash_yield_from_signals_log": cash_yield_from_signals_total,
            "cash_yield_cross_check_diff": cash_yield_cross_check_diff,
            "displayed_since_inception": since_inception_pnl,
            "naive_difference": naive_diff,
            "adjusted_difference": adjusted_diff,
            "pass": pnl_identity_pass,
        },
        "per_sleeve": per_sleeve_rows,
        "fill_reconciliation": {
            "fill_count": len(fills),
            "findings": all_fill_findings,
            "cash_ledger": cash_ledger_rows,
            "fees_check": {"state": fees_total_state, "from_fills": fees_from_fills_total, "difference": fees_ledger_diff, "pass": abs(fees_ledger_diff) <= dollar_tol},
            "slippage_check": {"state": slippage_total_state, "from_fills": slippage_from_fills_total, "difference": slippage_ledger_diff, "pass": abs(slippage_ledger_diff) <= dollar_tol},
        },
        "accounting_identity": {
            "cash_plus_market_value": {"value": identity1_value, "nav": total_nav, "difference": identity1_diff, "pass": identity1_pass},
            "capital_plus_pnl_minus_costs_naive": {
                "value": identity2_naive_value, "nav": total_nav, "difference": identity2_naive_diff,
                "note": "Expected to differ from NAV by (fees + slippage) minus cash yield: fees/slippage are already embedded in cost basis and realized P&L by execute_paper_fill, so subtracting them again here double-counts them. This is not a ledger defect.",
            },
            "capital_plus_pnl_plus_cash_yield_corrected": {"value": identity2_corrected_value, "nav": total_nav, "difference": identity2_corrected_diff, "pass": identity2_corrected_pass},
        },
        "ledger_findings": ledger_findings,
    }
    return (0 if ok else 2), report


def write_json_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    tmp.replace(path)


def write_csv_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sleeve", "family", "position_qty", "avg_entry", "cost_basis", "market_value",
        "realized_pnl", "unrealized_pnl", "lifetime_fees", "lifetime_slippage", "current_weight", "fill_count",
    ]
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in report["per_sleeve"]:
            writer.writerow({k: row.get(k) for k in fieldnames})
        writer.writerow({})
        writer.writerow({"sleeve": "TOTAL", "cost_basis": report["portfolio_summary"]["position_basis"],
                          "market_value": report["portfolio_summary"]["market_value"],
                          "realized_pnl": report["pnl_identity_check"]["realized_pnl"],
                          "unrealized_pnl": report["pnl_identity_check"]["unrealized_pnl"]})
    tmp.replace(path)


def print_report(report: dict[str, Any]) -> None:
    bar = "=" * 50
    ps = report["portfolio_summary"]
    pnl = report["pnl_identity_check"]
    fr = report["fill_reconciliation"]
    ai = report["accounting_identity"]

    print(bar)
    print("Portfolio Summary")
    print(bar)
    print(f"Initial Capital       : {money(ps['initial_capital'])}")
    print(f"Current NAV           : {money(ps['current_nav'])}")
    print(f"Cash                  : {money(ps['cash'])}")
    print(f"Market Value          : {money(ps['market_value'])}")
    print(f"Position Basis        : {money(ps['position_basis'])}")
    print(f"Since Inception P&L   : {signed_money(ps['since_inception_pnl'])}")
    print()

    print(bar)
    print("P&L Identity Check")
    print(bar)
    print(f"Realized P&L                        : {signed_money(pnl['realized_pnl'])}")
    print(f"Unrealized P&L                       : {signed_money(pnl['unrealized_pnl'])}")
    print(f"Realized + Unrealized                : {signed_money(pnl['realized_plus_unrealized'])}")
    print(f"Cash Yield (fill-ledger replay)       : {signed_money(pnl['cash_yield_from_fill_replay'])}")
    if pnl["cash_yield_from_signals_log"] is not None:
        print(f"Cash Yield (signals.jsonl sum)         : {signed_money(pnl['cash_yield_from_signals_log'])}")
        print(f"  cross-check diff                    : {money(pnl['cash_yield_cross_check_diff'])}")
    else:
        print("Cash Yield (signals.jsonl sum)         : not available (no signals log)")
    print(f"Realized + Unrealized + Cash Yield    : {signed_money(pnl['realized_plus_unrealized'] + pnl['cash_yield_from_fill_replay'])}")
    print(f"Displayed Since Inception              : {signed_money(pnl['displayed_since_inception'])}")
    print(f"Difference (naive, no cash yield)      : {money(pnl['naive_difference'])}  (expected ≈ cumulative cash yield above, not a bug)")
    print(f"Difference (adjusted for cash yield)   : {money(pnl['adjusted_difference'])}  -> {'PASS' if pnl['pass'] else 'FAIL'}")
    print()

    print(bar)
    print("Per Sleeve")
    print(bar)
    for row in report["per_sleeve"]:
        print(f"{row['sleeve']} ({row['family']})")
        print(f"  Current Position    : {row['position_qty']:.8f}")
        print(f"  Average Entry       : {money(row['avg_entry'])}")
        print(f"  Cost Basis          : {money(row['cost_basis'])}")
        print(f"  Current Market Value: {money(row['market_value'])}")
        print(f"  Realized P&L        : {signed_money(row['realized_pnl'])}")
        print(f"  Unrealized P&L      : {signed_money(row['unrealized_pnl'])}")
        print(f"  Lifetime Fees       : {money(row['lifetime_fees'])}")
        print(f"  Lifetime Slippage   : {money(row['lifetime_slippage'])}")
        print(f"  Current Weight      : {row['current_weight']:.2%}")
        print(f"  Fills               : {row['fill_count']}")
    print()

    print(bar)
    print("Fill Reconciliation")
    print(bar)
    print(f"Walked {fr['fill_count']} fills across {len(report['per_sleeve'])} sleeves.")
    if fr["findings"]:
        print(f"FOUND {len(fr['findings'])} DISCREPANC{'Y' if len(fr['findings']) == 1 else 'IES'}:")
        for finding in fr["findings"]:
            print(
                f"  sleeve={finding['sleeve']} fill#={finding['fill_number']} ts={finding['timestamp']} "
                f"field={finding['field']} expected={finding['expected']} stored={finding['stored']} diff={finding['difference']}"
            )
    else:
        print("All fills reconcile exactly with runtime bookkeeping (cost basis, realized P&L, average entry).")
    print("Cash ledger (stored cash vs. cash replayed from fills alone):")
    for row in fr["cash_ledger"]:
        label = "yield-eligible, difference expected" if row["yield_eligible"] else "no yield expected"
        print(f"  {row['sleeve']} ({label}): stored={money(row['stored_cash'])} replayed={money(row['replayed_cash'])} diff={money(row['difference'])}")
    fc, sc = fr["fees_check"], fr["slippage_check"]
    print(f"Fees ledger check     : state={money(fc['state'])} vs sum-of-fills={money(fc['from_fills'])} diff={money(fc['difference'])} -> {'PASS' if fc['pass'] else 'FAIL'}")
    print(f"Slippage ledger check : state={money(sc['state'])} vs sum-of-fills={money(sc['from_fills'])} diff={money(sc['difference'])} -> {'PASS' if sc['pass'] else 'FAIL'}")
    if report["ledger_findings"]:
        print("Ledger-level findings:")
        for msg in report["ledger_findings"]:
            print(f"  - {msg}")
    print()

    print(bar)
    print("Accounting Identity")
    print(bar)
    c1 = ai["cash_plus_market_value"]
    print(f"Cash + Market Value = NAV")
    print(f"  {money(c1['value'])} vs NAV {money(c1['nav'])}, diff={money(c1['difference'])} -> {'PASS' if c1['pass'] else 'FAIL'}")
    c2n = ai["capital_plus_pnl_minus_costs_naive"]
    print("Initial Capital + Realized + Unrealized - Fees - Slippage = NAV  (as specified)")
    print(f"  {money(c2n['value'])} vs NAV {money(c2n['nav'])}, diff={money(c2n['difference'])}")
    print(f"  NOTE: {c2n['note']}")
    c2c = ai["capital_plus_pnl_plus_cash_yield_corrected"]
    print("Initial Capital + Realized + Unrealized + Cash Yield = NAV  (corrected for this runtime's bookkeeping)")
    print(f"  {money(c2c['value'])} vs NAV {money(c2c['nav'])}, diff={money(c2c['difference'])} -> {'PASS' if c2c['pass'] else 'FAIL'}")
    print()

    print(bar)
    print("Result")
    print(bar)
    if report["ok"]:
        print("ACCOUNTING VERIFIED")
        print()
        print(
            "Unrealized P&L can legitimately be much smaller than total (since-inception) P&L because most of\n"
            "each equity/gold sleeve's allocation typically sits un-invested as idle cash between rebalances —\n"
            "with only a small number of fills so far, position sizes (and therefore mark-to-market exposure) are\n"
            "still small relative to total capital. On top of that, idle cash in equity/gold sleeves earns BIL-rate\n"
            "interest every cycle (apply_cash_yield), which is real income credited straight into cash — it grows\n"
            "NAV and Since-Inception P&L, but it is neither a realized trade gain nor a mark-to-market gain on an\n"
            "open position, so it never appears in the Unrealized (or Realized) P&L figures. That is why NAV growth\n"
            "can outpace Realized + Unrealized until it is added back explicitly, as this report does above."
        )
    else:
        print("ACCOUNTING RECONCILIATION FAILED — see findings above.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Forensic accounting reconciliation for the Core v1 paper runtime")
    p.add_argument("--state-path", default=os.getenv("CORE_V1_STATE_PATH", "/opt/itera/runtime/core_v1/state.json"))
    p.add_argument("--fills-log", default=os.getenv("CORE_V1_FILLS_LOG", "/opt/itera/logs/core_v1_fills.jsonl"))
    p.add_argument("--signals-log", default=os.getenv("CORE_V1_SIGNALS_LOG", "/opt/itera/logs/core_v1_signals.jsonl"))
    p.add_argument("--capital", type=float, default=float(os.getenv("CORE_V1_CAPITAL", "100000")))
    p.add_argument("--dollar-tolerance", type=float, default=0.01)
    p.add_argument("--price-tolerance", type=float, default=0.0001)
    p.add_argument("--qty-tolerance", type=float, default=1e-6)
    p.add_argument("--json-output", default=os.getenv("CORE_V1_ACCOUNTING_JSON_PATH", str(REPO_ROOT / "artifacts" / "core_v1_accounting_report.json")))
    p.add_argument("--csv-output", default=os.getenv("CORE_V1_ACCOUNTING_CSV_PATH", str(REPO_ROOT / "artifacts" / "core_v1_accounting_report.csv")))
    p.add_argument("--json", action="store_true", help="Print the full JSON report to stdout instead of the human-readable console report.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    code, report = audit(args)
    write_json_report(Path(args.json_output), report)
    write_csv_report(Path(args.csv_output), report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
    else:
        print_report(report)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
