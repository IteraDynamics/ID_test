"""OHLCV resampling utilities.

All resampling is strictly backward-looking — no lookahead bias.

Convention: a bar labeled T covers the half-open interval [T, T+freq).
The bar's close is the last observed price before T+freq.  This matches
the backtest engine's closed-bar assumption: the strategy at step i only
sees bars [0..i].

The pandas default for time-based resample uses label="left" and
closed="left", which produces exactly this convention for crypto data
that trades continuously (no market-open gaps to worry about).
"""

from __future__ import annotations

import pandas as pd

_OHLCV_AGG: dict[str, str] = {
    "open":   "first",
    "high":   "max",
    "low":    "min",
    "close":  "last",
    "volume": "sum",
}


def resample_ohlcv(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Resample OHLCV data to a coarser frequency.

    Parameters
    ----------
    df :
        OHLCV DataFrame with a tz-naive DatetimeIndex sorted ascending.
        Must contain columns: open, high, low, close.  volume is optional.
    freq :
        pandas offset alias, e.g. ``"4h"``, ``"1D"``, ``"W"``.

    Returns
    -------
    pd.DataFrame
        Resampled OHLCV, same column set as input.  Incomplete periods
        (trailing partial bar) are dropped via ``dropna(subset=["close"])``.
    """
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"resample_ohlcv: missing required columns {missing}")

    agg = {col: _OHLCV_AGG[col] for col in _OHLCV_AGG if col in df.columns}
    resampled = (
        df.resample(freq, label="left", closed="left")
        .agg(agg)
        .dropna(subset=["close"])
    )
    return resampled


def align_equity_curves(
    curves: dict[str, pd.Series],
    base_freq: str = "1h",
) -> pd.DataFrame:
    """Align multiple equity curves to a common DatetimeIndex.

    Curves from different timeframe sleeves have different index frequencies
    (e.g. 1H vs 4H).  This function reindexes all curves to ``base_freq``
    using forward-fill so that between-bar equity is held constant (the
    position did not change, only the bar clock advanced).

    Parameters
    ----------
    curves :
        Mapping of sleeve label → equity Series (DatetimeIndex, USD values).
    base_freq :
        Target resolution for the aligned DataFrame.  Should match the
        finest-grained sleeve (typically ``"1h"``).

    Returns
    -------
    pd.DataFrame
        Columns = sleeve labels.  Index = common DatetimeIndex at base_freq.
        Leading NaN rows (before all curves have a first value) are dropped.
    """
    if not curves:
        raise ValueError("align_equity_curves: no curves provided")

    # Common period: latest start → earliest end across all sleeves
    start = max(c.index[0] for c in curves.values())
    end   = min(c.index[-1] for c in curves.values())

    if start >= end:
        raise ValueError(
            f"align_equity_curves: no overlapping period between sleeves "
            f"(latest start={start}, earliest end={end})"
        )

    idx = pd.date_range(start, end, freq=base_freq)
    aligned: dict[str, pd.Series] = {}
    for label, curve in curves.items():
        aligned[label] = (
            curve
            .loc[start:end]
            .reindex(idx)
            .ffill()
        )

    df = pd.DataFrame(aligned)
    # Drop leading rows where any sleeve is still NaN (e.g. 4H warmup longer)
    return df.dropna()
