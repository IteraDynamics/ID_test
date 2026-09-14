"""Self-financing adjusted-unit ledger, with explicit collateral and debit costs."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import ASSETS


@dataclass(frozen=True)
class Scenario:
    name: str
    one_way_bps: float
    borrow_annual: float
    funding_spread_annual: float
    extra_delay: int = 0
    funding_base: bool = True


SCENARIOS = (
    Scenario("frictionless", 0, 0, 0, funding_base=False),
    Scenario("base", 5, 0.01, 0.015),
    Scenario("cost_stress", 15, 0.03, 0.03),
    Scenario("delay_one_session", 5, 0.01, 0.015, extra_delay=1),
)


def rebalance(values: np.ndarray, cash: float, weights: np.ndarray, rate: float):
    """Solve post-fee equity so target weights and cash reconcile exactly."""
    nav = float(cash + values.sum())
    if (not np.isfinite(np.r_[values, cash, weights, rate]).all() or nav <= 0
            or rate < 0 or rate * np.abs(weights).sum() >= 1):
        raise ValueError("Invalid rebalance state or insolvent portfolio")
    lo, hi = 0.0, nav
    if rate * np.abs(values).sum() >= nav:
        raise ValueError("Liquidation costs exhaust equity")
    # The residual is strictly increasing because rate*sum(abs(weights)) < 1.
    for _ in range(45):
        middle = (lo + hi) / 2
        residual = middle + rate * np.abs(weights * middle - values).sum() - nav
        if residual > 0:
            hi = middle
        else:
            lo = middle
    after = (lo + hi) / 2
    target = weights * after
    trades = target - values
    fees = rate * np.abs(trades)
    new_cash = float(cash - trades.sum() - fees.sum())
    if abs(new_cash + target.sum() - after) > 1e-10 * nav:
        raise ValueError("Post-fee cash/inventory reconciliation failed")
    return target, new_cash, fees, trades


def simulate(frames: dict[str, pd.DataFrame], schedule: dict[int, np.ndarray],
             scenario: Scenario, first_signal: int) -> pd.DataFrame:
    dates = frames["SPY"].index
    opens = np.column_stack([frames[a].open for a in ASSETS])
    closes = np.column_stack([frames[a].close for a in ASSETS])
    start, end = first_signal + 1, len(dates) - 1
    if scenario.extra_delay < 0 or not schedule or min(schedule) < first_signal:
        raise ValueError("Invalid execution schedule")
    if any(s < 0 or s >= end or len(w) != len(ASSETS) for s, w in schedule.items()):
        raise ValueError("Invalid signal index/weight shape")
    orders = {t + 1 + scenario.extra_delay: (t, w) for t, w in schedule.items()
              if t + 1 + scenario.extra_delay < end}
    orders[end] = (-1, np.zeros(len(ASSETS)))
    units = np.zeros(len(ASSETS))
    cash = last_nav = 1.0
    previous_close = closes[start-1]
    rows = []
    for t in range(start, end + 1):
        old_values = units * previous_close
        short_value = float(-old_values.clip(max=0).sum())
        long_value = float(old_values.clip(min=0).sum())
        # Short sale proceeds are restricted, earn no rebate, and cannot finance longs.
        debit = max(0.0, long_value - last_nav)
        days = (dates[t] - dates[t-1]).days
        base_rate = 0.0
        if scenario.funding_base:
            window_days = (dates[t-1] - dates[t-22]).days
            base_rate = max(0.0, (closes[t-1, -1] / closes[t-22, -1] - 1)
                            * 365 / window_days)
        funding = debit * (base_rate + scenario.funding_spread_annual) * days / 365
        borrow = short_value * scenario.borrow_annual * days / 365
        cash -= funding + borrow
        contribution = units * (opens[t] - previous_close)
        values = units * opens[t]
        pre_nav = float(cash + values.sum())
        if pre_nav <= 0:
            raise ValueError(f"Insolvent at {dates[t]}; do not discard or rank this run")
        fees = np.zeros(len(ASSETS))
        trades = np.zeros(len(ASSETS))
        signal_index = -2
        if t in orders:
            signal_index, weights = orders[t]
            values, cash, fees, trades = rebalance(values, cash, weights,
                                                  scenario.one_way_bps / 10_000)
            units = values / opens[t]
        contribution += units * (closes[t] - opens[t])
        values = units * closes[t]
        nav = float(cash + values.sum())
        if nav <= 0:
            raise ValueError(f"Insolvent at {dates[t]} close")
        ret = nav / last_nav - 1
        pnl = float(contribution.sum() - fees.sum() - funding - borrow)
        residual = (nav - last_nav) - pnl
        if abs(residual) > 1e-10 * last_nav:
            raise ValueError("Daily P&L does not reconcile")
        risky = values[:-1]
        row = dict(date=str(dates[t].date()), nav=nav, **{"return": ret},
                   gross_market_pnl=float(contribution.sum()) / last_nav,
                   execution_cost=float(fees.sum()) / last_nav,
                   funding_cost=funding / last_nav, borrow_cost=borrow / last_nav,
                   turnover=float(np.abs(trades).sum()) / pre_nav,
                   gross_risky_exposure=float(np.abs(risky).sum()) / nav,
                   net_risky_exposure=float(risky.sum()) / nav,
                   cash_weight=cash / nav, bil_weight=float(values[-1]) / nav,
                   restricted_short_proceeds=float(-values.clip(max=0).sum()) / nav,
                   long_financing_debit=debit / last_nav,
                   signal_date=(str(dates[signal_index].date()) if signal_index >= 0 else ""),
                   rebalance=t in orders, terminal_liquidation=t == end,
                   accounting_residual=residual / last_nav)
        for j, asset in enumerate(ASSETS):
            row[f"{asset}_weight"] = float(values[j]) / nav
            row[f"{asset}_pnl"] = float(contribution[j] - fees[j]) / last_nav
        rows.append(row)
        last_nav, previous_close = nav, closes[t]
    if np.abs(units).sum() > 1e-12:
        raise ValueError("Final portfolio did not liquidate")
    return pd.DataFrame(rows)
