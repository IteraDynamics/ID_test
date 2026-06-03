"""Recovery Trust Gate — outcome labeler.

For each candidate re-risk event, evaluate forward price performance over
horizon_days calendar days to assign a label:
  1  (positive)  — recovery was genuine
  0  (negative)  — fake rebound / continued decline
 -1  (ambiguous) — neither threshold met; excluded from training
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Label thresholds (LOCKED — do not modify)
POSITIVE_MIN_RETURN   =  0.05   # +5% forward return
POSITIVE_MAX_DRAWDOWN = -0.10   # drawdown no worse than -10%
NEGATIVE_MAX_RETURN   = -0.05   # forward return <= -5%  OR
NEGATIVE_MIN_DRAWDOWN = -0.15   # drawdown <= -15%


def _daily_close(price_series: pd.Series) -> pd.Series:
    """Resample an intraday price series to daily close (last)."""
    if isinstance(price_series.index, pd.DatetimeIndex):
        freq = pd.infer_freq(price_series.index[:20])
        if freq is not None and "D" not in freq.upper():
            return price_series.resample("D").last().dropna()
    return price_series


def label_candidates(
    candidates_df: pd.DataFrame,
    price_series: pd.Series,
    horizon_days: int = 60,
) -> pd.DataFrame:
    """Assign outcome labels to candidate re-risk events.

    Parameters
    ----------
    candidates_df:
        Output of detect_candidates() — must have a 'timestamp' column.
    price_series:
        Asset close price.  Will be resampled to daily if intraday.
    horizon_days:
        Number of calendar days to evaluate forward performance.

    Returns
    -------
    candidates_df augmented with columns:
        forward_return_60d, max_drawdown_60d, label, label_str, label_available
    """
    daily = _daily_close(price_series)

    out = candidates_df.copy()
    fwd_returns  = []
    max_dds      = []
    labels       = []
    label_strs   = []
    availables   = []

    for _, row in out.iterrows():
        ts = pd.Timestamp(row["timestamp"])

        # Find the nearest daily bar at or after ts
        future_mask = daily.index >= ts
        if not future_mask.any():
            fwd_returns.append(np.nan)
            max_dds.append(np.nan)
            labels.append(-1)
            label_strs.append("ambiguous")
            availables.append(False)
            continue

        start_idx = daily.index.get_indexer([ts], method="bfill")[0]
        if start_idx < 0 or start_idx >= len(daily):
            fwd_returns.append(np.nan)
            max_dds.append(np.nan)
            labels.append(-1)
            label_strs.append("ambiguous")
            availables.append(False)
            continue

        entry_price = float(daily.iloc[start_idx])
        horizon_end = ts + pd.Timedelta(days=horizon_days)

        window = daily.iloc[start_idx:]
        window = window[window.index <= horizon_end]

        # Need full horizon — at least 80% of expected days
        min_bars = int(horizon_days * 0.80 * 5 / 7)  # approx trading days
        label_available = len(window) >= min_bars

        if len(window) < 2:
            fwd_returns.append(np.nan)
            max_dds.append(np.nan)
            labels.append(-1)
            label_strs.append("ambiguous")
            availables.append(False)
            continue

        exit_price = float(window.iloc[-1])
        fwd_ret = exit_price / entry_price - 1.0

        # Max peak-to-trough drawdown over window
        rolling_peak = window.expanding().max()
        dd_series = window / rolling_peak - 1.0
        max_dd = float(dd_series.min())

        # Labelling rules (LOCKED)
        if fwd_ret >= POSITIVE_MIN_RETURN and max_dd >= POSITIVE_MAX_DRAWDOWN:
            lbl = 1
            lbl_str = "positive"
        elif fwd_ret <= NEGATIVE_MAX_RETURN or max_dd <= NEGATIVE_MIN_DRAWDOWN:
            lbl = 0
            lbl_str = "negative"
        else:
            lbl = -1
            lbl_str = "ambiguous"

        fwd_returns.append(fwd_ret)
        max_dds.append(max_dd)
        labels.append(lbl)
        label_strs.append(lbl_str)
        availables.append(label_available)

    out["forward_return_60d"] = fwd_returns
    out["max_drawdown_60d"]   = max_dds
    out["label"]              = labels
    out["label_str"]          = label_strs
    out["label_available"]    = availables

    n_pos  = (out["label"] == 1).sum()
    n_neg  = (out["label"] == 0).sum()
    n_amb  = (out["label"] == -1).sum()
    log.info(
        "Labelled %d candidates: %d positive, %d negative, %d ambiguous",
        len(out), n_pos, n_neg, n_amb,
    )
    return out
