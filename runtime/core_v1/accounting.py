"""Core v1 accounting extracted verbatim from the frozen paper runner.

No clock, network, persistence, strategy choice or allocation lives here. These
functions retain the original mutation order, arithmetic and rounding behavior.
"""
from __future__ import annotations
from typing import Any
import pandas as pd

def default_sleeve_state(capital: float, weight: float) -> dict[str, Any]:
    return {
        "cash": capital * weight,
        "qty": 0.0,
        "cost_basis": 0.0,
        "avg_entry": None,
        "realized_pnl": 0.0,
        "last_action": None,
        "last_price": None,
        "last_target_exposure": 0.0,
        "last_timestamp": None,
    }


def migrate_sleeve_state(s: dict[str, Any], capital: float, weight: float) -> None:
    s.setdefault("cash", capital * weight)
    s.setdefault("qty", 0.0)
    s.setdefault("realized_pnl", 0.0)
    s.setdefault("last_action", None)
    s.setdefault("last_price", None)
    s.setdefault("last_target_exposure", 0.0)
    s.setdefault("last_timestamp", None)

    qty = float(s.get("qty", 0.0) or 0.0)
    if "cost_basis" not in s or s.get("cost_basis") is None:
        # Backward-compatible migration for positions opened before cost-basis telemetry existed.
        # Use the sleeve's initial allocation as the best available starting basis.
        s["cost_basis"] = capital * weight if abs(qty) > 1e-12 else 0.0
        s["basis_source"] = "backfilled_initial_allocation" if abs(qty) > 1e-12 else "none"
    cost_basis = float(s.get("cost_basis", 0.0) or 0.0)
    s["avg_entry"] = cost_basis / qty if abs(qty) > 1e-12 and cost_basis > 0 else None


def sleeve_nav(sleeve_state: dict[str, Any], price: float) -> float:
    return float(sleeve_state.get("cash", 0.0)) + float(sleeve_state.get("qty", 0.0)) * price


def apply_cash_yield(state: dict[str, Any], sleeve_label: str, sleeve_family: str, bil: pd.DataFrame) -> float:
    if sleeve_family not in ("equity", "gold"):
        return 0.0
    s = state["sleeves"][sleeve_label]
    last_ts = s.get("last_bil_yield_date")
    returns = bil["close"].pct_change().dropna()
    if returns.empty:
        return 0.0
    if last_ts:
        returns = returns.loc[returns.index > pd.Timestamp(last_ts)]
    if returns.empty:
        return 0.0
    growth = float((1.0 + returns).prod())
    cash_before = float(s.get("cash", 0.0))
    cash_yield = cash_before * (growth - 1.0)
    s["cash"] = cash_before * growth
    s["last_bil_yield_date"] = str(returns.index[-1].date())
    return cash_yield


def execute_paper_fill(
    state: dict[str, Any],
    sleeve_label: str,
    price: float,
    target_exposure: float,
    fee_rate: float,
    slippage_bps: float,
    min_delta: float,
) -> dict[str, Any] | None:
    s = state["sleeves"][sleeve_label]
    nav = sleeve_nav(s, price)
    if nav <= 0:
        return None

    current_qty = float(s.get("qty", 0.0) or 0.0)
    current_cost_basis = float(s.get("cost_basis", 0.0) or 0.0)
    current_value = current_qty * price
    current_exposure = current_value / nav
    delta_exposure = target_exposure - current_exposure
    if abs(delta_exposure) < min_delta:
        return None

    target_value = nav * target_exposure
    delta_value = target_value - current_value
    side = "BUY" if delta_value > 0 else "SELL"
    slip = slippage_bps / 10000.0
    fill_price = price * (1.0 + slip if side == "BUY" else 1.0 - slip)
    qty = abs(delta_value) / fill_price
    notional = qty * fill_price
    fee = notional * fee_rate
    realized_trade_pnl = 0.0
    sold_cost_basis = 0.0

    if side == "BUY":
        max_affordable = max(0.0, float(s.get("cash", 0.0))) / (fill_price * (1.0 + fee_rate))
        qty = min(qty, max_affordable)
        notional = qty * fill_price
        fee = notional * fee_rate
        s["qty"] = current_qty + qty
        s["cash"] = float(s.get("cash", 0.0)) - notional - fee
        s["cost_basis"] = current_cost_basis + notional + fee
    else:
        qty = min(qty, max(0.0, current_qty))
        notional = qty * fill_price
        fee = notional * fee_rate
        if current_qty > 0:
            sold_cost_basis = current_cost_basis * (qty / current_qty)
        realized_trade_pnl = notional - fee - sold_cost_basis
        remaining_qty = current_qty - qty
        remaining_cost_basis = max(0.0, current_cost_basis - sold_cost_basis)
        if remaining_qty < 1e-12:
            remaining_qty = 0.0
            remaining_cost_basis = 0.0
        s["qty"] = remaining_qty
        s["cash"] = float(s.get("cash", 0.0)) + notional - fee
        s["cost_basis"] = remaining_cost_basis
        s["realized_pnl"] = float(s.get("realized_pnl", 0.0)) + realized_trade_pnl
        state["realized_pnl"] = float(state.get("realized_pnl", 0.0)) + realized_trade_pnl

    new_qty = float(s.get("qty", 0.0) or 0.0)
    new_cost_basis = float(s.get("cost_basis", 0.0) or 0.0)
    s["avg_entry"] = new_cost_basis / new_qty if new_qty > 1e-12 and new_cost_basis > 0 else None

    slippage_cost = abs(qty * (fill_price - price))
    state["realized_fees"] = float(state.get("realized_fees", 0.0)) + fee
    state["realized_slippage"] = float(state.get("realized_slippage", 0.0)) + slippage_cost
    return {
        "side": side,
        "qty": qty,
        "price": fill_price,
        "mid": price,
        "notional": notional,
        "fee": fee,
        "slippage_cost": slippage_cost,
        "realized_pnl": realized_trade_pnl,
        "sold_cost_basis": sold_cost_basis,
        "cost_basis_after": s.get("cost_basis", 0.0),
        "avg_entry_after": s.get("avg_entry"),
    }


def mark_to_market(s: dict[str, Any], price: float) -> dict[str, float]:
    qty = float(s.get("qty", 0.0) or 0.0)
    cost_basis = float(s.get("cost_basis", 0.0) or 0.0)
    position_value = qty * price
    unrealized_pnl = position_value - cost_basis if qty > 1e-12 else 0.0
    return {
        "qty": qty,
        "cost_basis": cost_basis,
        "position_value": position_value,
        "avg_entry": cost_basis / qty if qty > 1e-12 and cost_basis > 0 else 0.0,
        "unrealized_pnl": unrealized_pnl,
        "unrealized_return": unrealized_pnl / cost_basis if cost_basis > 0 else 0.0,
    }
