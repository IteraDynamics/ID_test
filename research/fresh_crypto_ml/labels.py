"""Independent 14-day counterfactuals; these resets never enter portfolio returns."""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.fresh_crypto.data import WARMUP
from .design import HORIZON, LABEL_COST, PROFILES


def rebalance_many(values, cash, weights, rate):
    """Vectorized post-fee accounting for independent long-only label portfolios."""
    nav = cash+values.sum(axis=1)
    if (not np.isfinite(np.r_[values.ravel(), cash, weights.ravel(), rate]).all()
            or (nav <= 0).any() or (weights < 0).any() or (weights.sum(axis=1)>1+1e-12).any()
            or rate < 0 or rate >= 1):
        raise ValueError("Invalid counterfactual accounting state")
    lo, hi = np.zeros_like(nav), nav.copy()
    for _ in range(45):
        mid = (lo+hi)/2
        residual = mid+rate*np.abs(weights*mid[:, None]-values).sum(axis=1)-nav
        hi = np.where(residual > 0, mid, hi)
        lo = np.where(residual > 0, lo, mid)
    target = weights*((lo+hi)/2)[:, None]
    trades = target-values
    after_cash = cash-trades.sum(axis=1)-rate*np.abs(trades).sum(axis=1)
    if (after_cash < -1e-10*nav).any():
        raise ValueError("Counterfactual borrowed cash")
    return target, after_cash


def terminal_wealth(panel, target_path, starts, rate=LABEL_COST):
    """At signal s: enter at s+2, follow s..s+13 targets, liquidate s+16 open."""
    starts = np.asarray(starts, dtype=int)
    if len(starts)==0 or starts.min()<WARMUP or starts.max()+2+HORIZON>=len(panel.dates):
        raise ValueError("Incomplete counterfactual interval")
    units, cash = np.zeros((len(starts), 2)), np.ones(len(starts))
    for offset in range(HORIZON+1):
        opening = panel.opens[starts+2+offset]
        weights = target_path[starts+offset] if offset<HORIZON else np.zeros_like(units)
        values, cash = rebalance_many(units*opening, cash, weights, rate)
        units = values/opening
    if np.max(np.abs(units))>1e-12 or (cash<=0).any():
        raise ValueError("Invalid terminal counterfactual")
    return cash


def make_labels(panel):
    starts = np.arange(WARMUP, len(panel.dates)-2-HORIZON)
    parts = []
    for profile in PROFILES:
        trend = terminal_wealth(panel, panel.trend[profile], starts)
        allocation = terminal_wealth(panel, panel.allocation[profile], starts)
        parts.append(pd.DataFrame(dict(profile=profile, signal_index=starts,
                     signal_bar_start=panel.dates[starts].astype(str),
                     feature_available=(panel.dates[starts]+pd.Timedelta(days=1)).astype(str),
                     entry_time=panel.dates[starts+2].astype(str),
                     label_available=panel.dates[starts+2+HORIZON].astype(str),
                     trend_terminal_nav=trend, allocation_terminal_nav=allocation,
                     target=np.log(trend)-np.log(allocation))))
    return pd.concat(parts, ignore_index=True)
