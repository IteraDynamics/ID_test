"""Spot-only hypotheses and a full-equity ledger on the 365-day UTC calendar."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from research.fresh_discovery.accounting import rebalance
from .data import ASSETS, WARMUP


@dataclass(frozen=True)
class Policy:
    name: str
    family: str
    vol_target: float | None
    role: str


def policies():
    result = [Policy(f"{family}_{suffix}", family, target,
                     "control" if family == "equal_weight" else "candidate")
              for family in ("trend_ensemble", "breakout", "rotation", "equal_weight")
              for suffix, target in (("vol20", .20), ("vol40", .40), ("uncapped", None))]
    return result + [Policy(name, name, None, "benchmark")
                     for name in ("btc_buy_hold", "eth_buy_hold", "mix_buy_hold", "usd_cash")]


# These are cost ASSUMPTIONS, not quotes of an operator's exchange fee tier.
SCENARIOS = (("frictionless", 0., 0), ("base", 30., 0),
             ("cost_stress", 75., 0), ("delay_one_day", 30., 1))


def size(base, covariance, target):
    if (base < 0).any() or base.sum() > 1 + 1e-12:
        raise ValueError("Only unlevered long spot targets are supported")
    forecast = np.sqrt(max(0., float(base @ covariance @ base)))
    scale = min(1., target / forecast) if target is not None and forecast > 0 else 1.
    return base * scale


def schedules(frames, first=WARMUP):
    dates = frames["BTC"].index
    closes = np.column_stack([frames[a].close for a in ASSETS])
    highs = np.column_stack([frames[a].high for a in ASSETS])
    lows = np.column_stack([frames[a].low for a in ASSETS])
    returns = closes[1:] / closes[:-1] - 1
    specifications = policies()
    result = {p.name: {} for p in specifications}
    targets, state = [], np.zeros(2)
    # A close of bar t is known at t+1 midnight. Earliest fill t+2 midnight
    # provides a full day of latency. Final UTC open is reserved for liquidation.
    for t in range(180, len(dates) - 3):
        enter = closes[t] > highs[t-180:t].max(axis=0)
        leave = closes[t] < lows[t-60:t].min(axis=0)
        state = np.where(leave, 0., np.where(enter, 1., state))
        if t < first:
            continue
        cov = np.cov(returns[t-60:t], rowvar=False, ddof=1) * 365
        cov = .9 * cov + .1 * np.diag(np.diag(cov))
        trend = np.mean([closes[t] > closes[t-w] for w in (90, 180, 365)], axis=0) * .5
        momentum = closes[t] / closes[t-180] - 1
        rotation = np.zeros(2)
        winner = int(np.argmax(momentum))  # Fixed BTC-first tie breaking.
        if momentum[winner] > 0:
            rotation[winner] = 1.
        raw = dict(trend_ensemble=trend, breakout=state * .5,
                   rotation=rotation, equal_weight=np.array([.5, .5]))
        for policy in specifications:
            if policy.role == "benchmark":
                if t != first:
                    continue
                base = dict(btc_buy_hold=[1., 0.], eth_buy_hold=[0., 1.],
                            mix_buy_hold=[.5, .5], usd_cash=[0., 0.])[policy.name]
                target = np.array(base)
            else:
                target = size(raw[policy.family], cov, policy.vol_target)
            result[policy.name][t] = target
            targets.append(dict(policy=policy.name, signal_bar_start=str(dates[t]),
                                signal_available=str(dates[t] + pd.Timedelta(days=1)),
                                base_fill_time=str(dates[t] + pd.Timedelta(days=2)),
                                BTC=target[0], ETH=target[1], USD=1-target.sum()))
    return result, pd.DataFrame(targets)


def simulate(frames, schedule, one_way_bps, extra_delay=0, first=WARMUP):
    dates = frames["BTC"].index
    opens = np.column_stack([frames[a].open for a in ASSETS])
    closes = np.column_stack([frames[a].close for a in ASSETS])
    start, end = first + 2, len(dates) - 1
    if not schedule or min(schedule) < first or extra_delay < 0 or one_way_bps < 0:
        raise ValueError("Invalid execution schedule")
    for t, weights in schedule.items():
        if (t >= end or np.shape(weights) != (2,) or not np.isfinite(weights).all()
                or (weights < 0).any() or weights.sum() > 1 + 1e-12):
            raise ValueError("Invalid signal index or spot weights")
    orders = {t + 2 + extra_delay: (t, w) for t, w in schedule.items() if t + 2 + extra_delay < end}
    orders[end] = (-1, np.zeros(2))
    units, cash, previous_nav = np.zeros(2), 1., 1.
    previous_close = closes[start-1]
    rows = []
    for t in range(start, end + 1):
        contribution = units * (opens[t] - previous_close)
        values = units * opens[t]
        pre_nav = float(cash + values.sum())
        if pre_nav <= 0:
            raise ValueError("Portfolio insolvent")
        fees, trades, signal = np.zeros(2), np.zeros(2), -2
        if t in orders:
            signal, weights = orders[t]
            values, cash, fees, trades = rebalance(values, cash, weights, one_way_bps / 10_000)
            units = values / opens[t]
        contribution += units * (closes[t] - opens[t])
        values = units * closes[t]
        nav = float(cash + values.sum())
        residual = nav - previous_nav - contribution.sum() + fees.sum()
        if nav <= 0 or cash < -1e-10 * nav or abs(residual) > 1e-10 * previous_nav:
            raise ValueError("Spot cash/NAV/P&L reconciliation failed")
        rows.append(dict(date=str(dates[t].date()), nav=nav, **{"return": nav / previous_nav - 1},
                         turnover=float(np.abs(trades).sum()) / pre_nav,
                         execution_cost=float(fees.sum()) / previous_nav,
                         gross_market_pnl=float(contribution.sum()) / previous_nav,
                         BTC_weight=float(values[0]) / nav, ETH_weight=float(values[1]) / nav,
                         BTC_pnl=float(contribution[0] - fees[0]) / previous_nav,
                         ETH_pnl=float(contribution[1] - fees[1]) / previous_nav,
                         risky_exposure=float(values.sum()) / nav, USD_weight=cash / nav,
                         signal_bar_start=str(dates[signal]) if signal >= 0 else "",
                         signal_available=str(dates[signal] + pd.Timedelta(days=1)) if signal >= 0 else "",
                         fill_time=str(dates[t]) if t in orders else "",
                         terminal_liquidation=t == end, accounting_residual=residual / previous_nav))
        previous_nav, previous_close = nav, closes[t]
    if np.abs(units).sum() > 1e-12:
        raise ValueError("Terminal inventory is not zero")
    return pd.DataFrame(rows)


def metrics(frame):
    returns = frame["return"].to_numpy()
    dates = pd.to_datetime(frame.date)
    # First capital at initial day's open; final valuation is liquidation day's open.
    years = (dates.iloc[-1] - dates.iloc[0]).days / 365.25
    if years <= 0:
        raise ValueError("Insufficient evaluation duration")
    wealth = np.cumprod(1 + returns)
    cagr = wealth[-1] ** (1 / years) - 1
    peak = np.maximum.accumulate(np.r_[1., wealth])[1:]
    drawdown = wealth / peak - 1
    deviation = returns.std(ddof=1)
    underwater = longest = 0
    for value in drawdown:
        underwater = underwater + 1 if value < -1e-12 else 0
        longest = max(longest, underwater)
    return dict(cagr=float(cagr), cash_excess_sharpe=float(returns.mean() / deviation * np.sqrt(365))
                if deviation > 1e-12 else np.nan,
                max_drawdown=float(drawdown.min()), annual_volatility=float(deviation * np.sqrt(365)),
                calmar=float(cagr / -drawdown.min()) if drawdown.min() < -1e-12 else np.nan,
                certainty_equivalent_gamma3=float(returns.mean() * 365 - 1.5 * deviation**2 * 365),
                terminal_nav=float(wealth[-1]), mean_risky_exposure=float(frame.risky_exposure.mean()),
                annual_one_way_turnover=float(frame.turnover.sum() / years),
                annual_arithmetic_execution_drag=float(frame.execution_cost.sum() / years),
                worst_day=float(returns.min()), longest_underwater_days=longest)


def registry():
    return [asdict(p) for p in policies()]
