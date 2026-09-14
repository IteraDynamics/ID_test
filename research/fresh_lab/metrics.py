"""Descriptive discovery metrics, including dependence-sensitive Sharpe."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def finite_or_none(value: float) -> float | None:
    return float(value) if np.isfinite(value) else None


def metrics(ledger: pd.DataFrame) -> dict:
    r = ledger["net_return"].to_numpy(dtype=float)
    n = len(r)
    if n < 2 or not np.isfinite(r).all() or (r <= -1).any():
        raise ValueError("Invalid metric sample")
    wealth = np.cumprod(1 + r)
    mean = r.mean()
    variance = r.var(ddof=1)
    vol = np.sqrt(variance * 252)
    sharpe = mean * 252 / vol if vol > 1e-12 else math.nan
    centered = r - mean
    lags = min(20, n - 1)
    lrv = float(centered @ centered) / n
    for k in range(1, lags + 1):
        covariance = float(centered[k:] @ centered[:-k]) / n
        lrv += 2 * (1 - k / (lags + 1)) * covariance
    hac_sharpe = mean * np.sqrt(252 / lrv) if lrv > 1e-16 else math.nan
    # These two nodes preserve open losses that a close-only curve can hide.
    base = float(ledger["nav"].iloc[0]) / (1 + r[0])
    nodes = np.column_stack((ledger["nav_open"], ledger["nav"])).reshape(-1) / base
    running_peak = np.maximum.accumulate(np.r_[1.0, nodes])[1:]
    max_dd = float(np.max(1 - nodes / running_peak))
    close_peak = np.maximum.accumulate(np.r_[1.0, wealth])[1:]
    close_dd = float(np.max(1 - wealth / close_peak))
    annual_log_growth = float(np.log1p(r).sum()) * 252 / n
    cagr = math.expm1(annual_log_growth)
    underwater = wealth < close_peak - 1e-12
    longest, current = 0, 0
    for flag in underwater:
        current = current + 1 if flag else 0
        longest = max(longest, current)
    downside = np.sqrt(np.mean(np.minimum(r, 0) ** 2) * 252)
    gross = (ledger["gross_open"] + ledger["gross_close"]) / 2
    active = gross > 1e-10
    best = np.argsort(r)[-min(5, n):]
    without_best = r.copy()
    without_best[best] = 0
    return {
        "sessions": n, "total_return": float(wealth[-1] - 1),
        "cagr": cagr, "annual_mean": float(mean * 252),
        "annual_ce_gamma3": float(mean * 252 - 1.5 * variance * 252),
        "annual_vol": float(vol), "sharpe": finite_or_none(sharpe),
        "sharpe_hac20": finite_or_none(hac_sharpe),
        "calmar": finite_or_none(cagr / max_dd if max_dd > 1e-12 else math.nan),
        "sortino": finite_or_none(mean * 252 / downside if downside > 1e-12 else math.nan),
        "max_drawdown": max_dd, "max_close_drawdown": close_dd,
        "worst_day": float(r.min()),
        "expected_shortfall_5pct": float(np.sort(r)[:max(1, math.ceil(n * .05))].mean()),
        "longest_underwater_sessions": longest,
        "turnover_annual": float(ledger["turnover"].sum() * 252 / n),
        "trade_cost_drag_annual": float(ledger["trade_cost_return"].mean() * 252),
        "carry_cost_drag_annual": float(ledger["carry_cost_return"].mean() * 252),
        "average_gross_at_marks": float(gross.mean()),
        "maximum_gross_at_marks": float(ledger[["gross_open", "gross_close"]].max().max()),
        "active_session_fraction": float(active.mean()),
        "positive_day_fraction": float((r > 0).mean()),
        "order_legs": int(ledger["orders"].sum()),
        "cagr_without_best5_days": float(np.expm1(np.log1p(without_best).sum() * 252 / n)),
    }


def pareto(table: pd.DataFrame) -> pd.Series:
    """Non-dominated on net CAGR, HAC Sharpe and shallower drawdown."""
    flags = pd.Series(False, index=table.index)
    good = table[["cagr", "sharpe_hac20", "max_drawdown"]].notna().all(axis=1)
    values = table.loc[good, ["cagr", "sharpe_hac20", "max_drawdown"]].to_numpy()
    values[:, 2] *= -1
    for i, row in enumerate(values):
        dominated = np.any(np.all(values >= row, axis=1) & np.any(values > row, axis=1))
        flags.loc[table.index[good][i]] = not dominated
    return flags
