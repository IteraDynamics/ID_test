"""Convenience function: compute_regime_series.

Runs a BaselineRegimeEngine (or any custom engine with a compatible
``classify_dataframe`` method) over a full OHLCV DataFrame and returns
a pandas Series of RegimeLabel values aligned to the input index.
"""

from __future__ import annotations

import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.regimes.baseline_engine import BaselineRegimeEngine


def compute_regime_series(
    df: pd.DataFrame,
    engine: BaselineRegimeEngine | None = None,
) -> pd.Series:
    """Classify every bar in *df* and return a Series of RegimeLabel values.

    Parameters
    ----------
    df :
        OHLCV DataFrame with a datetime-like index and columns
        [open, high, low, close, volume].
    engine :
        An instantiated regime engine.  Defaults to ``BaselineRegimeEngine()``
        with stock parameters.

    Returns
    -------
    pd.Series
        dtype=object (RegimeLabel str values), indexed like *df*.
        Warmup bars are labelled ``RegimeLabel.UNKNOWN``.

    Example
    -------
    >>> from research.regimes import compute_regime_series
    >>> regime_s = compute_regime_series(df)
    >>> df["regime"] = regime_s
    """
    if engine is None:
        engine = BaselineRegimeEngine()

    signals = engine.classify_dataframe(df)
    labels = [sig.label for sig in signals]
    return pd.Series(labels, index=df.index, name="regime", dtype=object)
