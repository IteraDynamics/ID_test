"""Share/cash ledger with precommitted quantities and explicit dividends/costs."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


class InsolventError(RuntimeError):
    """A candidate exhausted its equity; do not present partial-path performance."""


@dataclass(frozen=True)
class Scenario:
    name: str
    cost_bps: float
    delay: int = 0
    financing_rate: float = 0.06
    borrow_rate: float = 0.03
    cash_rate: float = 0.0


SCENARIOS = (
    Scenario("zero_trade_cost", 0),
    Scenario("base_2bps", 2),
    Scenario("stress_10bps", 10, financing_rate=0.08, borrow_rate=0.06),
    Scenario("stress_25bps", 25, financing_rate=0.10, borrow_rate=0.10),
    Scenario("delay_1session", 2, delay=1),
)


def carry(cash: float, q: np.ndarray, price: np.ndarray,
          fraction: float, scenario: Scenario) -> tuple[float, float]:
    """Short proceeds are segregated; financing is charged on free-cash deficit."""
    short = float(np.maximum(-q * price, 0).sum())
    free_cash = cash - short
    interest = max(free_cash, 0) * scenario.cash_rate * fraction
    expense = (max(-free_cash, 0) * scenario.financing_rate
               + short * scenario.borrow_rate) * fraction
    return interest, expense


def execute(cash: float, q: np.ndarray, desired: np.ndarray,
            price: np.ndarray, cost_bps: float) -> tuple[float, np.ndarray, float, float, int]:
    change = desired - q
    notional = float(np.abs(change * price).sum())
    fee = notional * cost_bps / 10000
    cash = cash - float(change @ price) - fee
    return cash, desired.copy(), fee, notional, int((np.abs(change * price) > 1e-10).sum())


def simulate(panel: dict[str, pd.DataFrame], target: pd.DataFrame,
             mode: str, gross: float, scenario: Scenario,
             start: str) -> pd.DataFrame:
    if mode not in ("full", "day", "night", "hold"):
        raise ValueError(f"Unknown execution mode: {mode}")
    if not np.isfinite(gross) or gross <= 0 or scenario.delay < 0:
        raise ValueError("Invalid exposure or delay")
    for value in (scenario.cost_bps, scenario.financing_rate, scenario.borrow_rate,
                  scenario.cash_rate):
        if not np.isfinite(value) or value < 0:
            raise ValueError("Invalid cost assumption")
    dates = panel["Close"].index
    symbols = list(panel["Close"].columns)
    if not target.index.equals(dates) or list(target.columns) != symbols:
        raise ValueError("Target/price alignment mismatch")
    if not np.isfinite(target.to_numpy()).all():
        raise ValueError("Nonfinite target")
    eligible = np.flatnonzero(dates >= pd.Timestamp(start))
    if len(eligible) < 2 or eligible[0] < scenario.delay + 1:
        raise ValueError("Insufficient scored history/warmup")
    o, c, div = (panel[k].to_numpy(dtype=float) for k in ("Open", "Close", "Dividends"))
    if any(not np.isfinite(a).all() for a in (o, c, div)) or (o <= 0).any() or (c <= 0).any():
        raise ValueError("Invalid execution prices")
    weights = target.to_numpy(dtype=float)
    cash = 1.0
    q = np.zeros(len(symbols))
    rows = []
    for step, i in enumerate(eligible):
        previous_nav = cash + float(q @ c[i - 1])
        if previous_nav <= 0:
            raise InsolventError(f"Nonpositive prior equity on {dates[i].date()}")
        # All quantities are fixed using information at PRIOR close; never today's fill.
        signal_i = i - 1 - scenario.delay
        planned = weights[signal_i] * gross * previous_nav / c[i - 1]
        prior_q = q.copy()
        calendar_days = (dates[i] - dates[i - 1]).days
        if not 1 <= calendar_days <= 7:
            raise ValueError("Unexpected calendar gap")
        night_years = (calendar_days - 6.5 / 24) / 365.25
        day_years = (6.5 / 24) / 365.25
        night_interest, night_expense = carry(cash, q, c[i - 1], night_years, scenario)
        distribution = float(q @ div[i])
        cash += night_interest - night_expense + distribution
        if mode == "hold":
            open_target = planned if step == 0 else q
        elif mode in ("full", "day"):
            open_target = planned
        else:
            open_target = np.zeros_like(q)
        cash, q, fee_open, turnover_open, orders_open = execute(
            cash, q, open_target, o[i], scenario.cost_bps)
        nav_open = cash + float(q @ o[i])
        if nav_open <= 0:
            raise InsolventError(f"Equity exhausted at open on {dates[i].date()}")
        gross_open = float(np.abs(q * o[i]).sum()) / nav_open
        net_open = float(q @ o[i]) / nav_open
        intraday_q = q.copy()
        day_interest, day_expense = carry(cash, q, o[i], day_years, scenario)
        cash += day_interest - day_expense
        close_target = planned if mode == "night" else q
        if mode == "day" or step == len(eligible) - 1:
            close_target = np.zeros_like(q)
        cash, q, fee_close, turnover_close, orders_close = execute(
            cash, q, close_target, c[i], scenario.cost_bps)
        nav_close = cash + float(q @ c[i])
        if nav_close <= 0:
            raise InsolventError(f"Equity exhausted at close on {dates[i].date()}")
        asset_pnl = prior_q * (o[i] - c[i - 1] + div[i]) + intraday_q * (c[i] - o[i])
        trade_cost = fee_open + fee_close
        carry_cost = night_expense + day_expense
        interest = night_interest + day_interest
        expected = float(asset_pnl.sum()) + interest - trade_cost - carry_cost
        error = nav_close - previous_nav - expected
        if abs(error) > 1e-9 * max(1, abs(nav_close)):
            raise ArithmeticError(f"Cash/inventory/P&L reconciliation failed: {error}")
        gross_close = float(np.abs(q * c[i]).sum()) / nav_close
        row = {
            "date": dates[i], "nav": nav_close, "nav_open": nav_open,
            "net_return": nav_close / previous_nav - 1,
            "asset_return": float(asset_pnl.sum()) / previous_nav,
            "trade_cost_return": trade_cost / previous_nav,
            "carry_cost_return": carry_cost / previous_nav,
            "interest_return": interest / previous_nav,
            "turnover": (turnover_open + turnover_close) / previous_nav,
            "gross_open": gross_open, "gross_close": gross_close,
            "net_open": net_open, "net_close": float(q @ c[i]) / nav_close,
            "orders": orders_open + orders_close, "cash": cash,
            "holdings_value": float(q @ c[i]), "dividend_cash": distribution,
            "accounting_error": error,
            "signal_date": dates[signal_i],
        }
        for j, symbol in enumerate(symbols):
            row[f"pnl_{symbol}"] = float(asset_pnl[j])
        rows.append(row)
    result = pd.DataFrame(rows).set_index("date")
    if np.abs(q).sum() != 0:
        raise ArithmeticError("Terminal inventory is not flat")
    return result
