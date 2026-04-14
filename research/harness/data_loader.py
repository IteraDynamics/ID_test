"""Research harness — OHLCV data loader and validator.

Responsibilities:
- Load hourly OHLCV CSV files with flexible timestamp parsing.
- Validate required columns, types, and ordering.
- Slice by date range.
- Return a clean, deterministically-sorted DataFrame.

Assumptions:
- Input format: CSV with columns [timestamp, open, high, low, close, volume].
- Timestamp column can be unix seconds/ms or ISO-format strings.
- No forward-filling or interpolation is applied — missing bars surface as gaps.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import numpy as np

REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}
TIMESTAMP_ALIASES = [
    "timestamp", "time", "date", "datetime", "Date", "Timestamp",
    "Unnamed: 0", "",  # pandas default when index was saved without label
]


class DataLoadError(ValueError):
    """Raised when OHLCV data fails validation."""


def load_ohlcv(
    path: str | Path,
    start: str | None = None,
    end: str | None = None,
    asset: str = "BTC",
) -> pd.DataFrame:
    """Load and validate an OHLCV CSV file.

    Parameters
    ----------
    path :
        Absolute or relative path to the CSV file.
    start :
        Optional ISO-format start date/datetime (inclusive), e.g. "2022-01-01".
    end :
        Optional ISO-format end date/datetime (inclusive), e.g. "2023-12-31".
    asset :
        Asset label — stored in df.attrs['asset'] for downstream use.

    Returns
    -------
    pd.DataFrame
        Columns: [open, high, low, close, volume] (lowercase).
        DatetimeIndex (UTC, tz-naive), sorted ascending.
        Missing values are NOT forward-filled.

    Raises
    ------
    DataLoadError
        On missing required columns, parse failure, or empty result.
    FileNotFoundError
        If the path does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"OHLCV file not found: {path}")

    try:
        raw = pd.read_csv(path)
    except Exception as exc:
        raise DataLoadError(f"Failed to parse CSV at {path}: {exc}") from exc

    # ── Normalise column names ────────────────────────────────────────
    raw.columns = [c.strip() for c in raw.columns]

    # Detect timestamp column
    ts_col = None
    for alias in TIMESTAMP_ALIASES:
        if alias in raw.columns:
            ts_col = alias
            break
    if ts_col is None:
        raise DataLoadError(
            f"No timestamp column found. Expected one of {TIMESTAMP_ALIASES}. "
            f"Got: {list(raw.columns)}"
        )

    # Lowercase all columns except the timestamp col we're about to parse
    rename_map = {c: c.lower() for c in raw.columns if c != ts_col}
    raw = raw.rename(columns=rename_map)

    # ── Parse timestamp ───────────────────────────────────────────────
    ts_series = raw[ts_col]
    if pd.api.types.is_numeric_dtype(ts_series):
        # Detect unix seconds vs milliseconds by magnitude
        median_val = ts_series.dropna().median()
        if median_val > 1e12:
            ts_parsed = pd.to_datetime(ts_series, unit="ms", utc=True).dt.tz_localize(None)
        else:
            ts_parsed = pd.to_datetime(ts_series, unit="s", utc=True).dt.tz_localize(None)
    else:
        ts_parsed = pd.to_datetime(ts_series, utc=False)
        if ts_parsed.dt.tz is not None:
            ts_parsed = ts_parsed.dt.tz_convert(None)

    raw.index = ts_parsed
    raw.index.name = "timestamp"
    raw = raw.drop(columns=[ts_col], errors="ignore")

    # ── Validate required columns ─────────────────────────────────────
    missing = REQUIRED_COLUMNS - set(raw.columns)
    if missing:
        raise DataLoadError(
            f"Missing required columns: {missing}. Available: {list(raw.columns)}"
        )

    # Keep only OHLCV columns
    df = raw[["open", "high", "low", "close", "volume"]].copy()

    # ── Cast to float ─────────────────────────────────────────────────
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    nan_count = df.isnull().sum().sum()
    if nan_count > 0:
        total = len(df) * len(df.columns)
        pct = 100 * nan_count / total
        if pct > 5.0:
            raise DataLoadError(
                f"Too many NaN values after parsing: {nan_count}/{total} ({pct:.1f}%). "
                "Check column types in CSV."
            )

    # ── Sort and deduplicate ──────────────────────────────────────────
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]

    # ── Date slicing ──────────────────────────────────────────────────
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index <= pd.Timestamp(end)]

    if len(df) == 0:
        raise DataLoadError(
            f"No data remaining after date slicing (start={start}, end={end})."
        )

    df.attrs["asset"] = asset
    df.attrs["source_path"] = str(path)
    return df


def validate_ohlcv(df: pd.DataFrame) -> list[str]:
    """Check a DataFrame for data quality issues.

    Returns a list of warning strings.  Empty list = clean.
    Does NOT raise — callers decide what to do with warnings.
    """
    warnings: list[str] = []

    if not isinstance(df.index, pd.DatetimeIndex):
        warnings.append("Index is not DatetimeIndex.")

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        warnings.append(f"Missing columns: {missing}")

    if df.isnull().any().any():
        counts = df.isnull().sum()
        warnings.append(f"NaN values present: {counts[counts > 0].to_dict()}")

    if (df["close"] <= 0).any():
        warnings.append("Non-positive close prices detected.")

    if (df["high"] < df["low"]).any():
        n = (df["high"] < df["low"]).sum()
        warnings.append(f"{n} bars where high < low.")

    if (df["volume"] < 0).any():
        warnings.append("Negative volume detected.")

    # Check for large gaps (> 4 hours between bars for hourly data)
    if isinstance(df.index, pd.DatetimeIndex) and len(df) > 1:
        deltas = df.index.to_series().diff().dropna()
        large_gaps = deltas[deltas > pd.Timedelta(hours=4)]
        if len(large_gaps) > 0:
            warnings.append(
                f"{len(large_gaps)} gaps > 4h detected. First at {large_gaps.index[0]}"
            )

    return warnings


def make_synthetic_ohlcv(
    n_bars: int = 1000,
    start: str = "2022-01-01",
    freq: str = "1h",
    seed: int = 42,
    initial_price: float = 20000.0,
) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing.

    Uses geometric Brownian motion with a mild drift.
    """
    rng = np.random.default_rng(seed)
    n = n_bars
    dt = 1 / (365 * 24)  # hourly fraction of year
    mu = 0.30             # 30% annual drift
    sigma = 0.75          # 75% annual volatility (BTC-like)

    log_returns = (mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(n)
    prices = initial_price * np.exp(np.cumsum(log_returns))

    noise = rng.uniform(0.998, 1.002, size=n)
    high = prices * (1 + rng.uniform(0.001, 0.015, size=n))
    low = prices * (1 - rng.uniform(0.001, 0.015, size=n))
    open_ = prices * noise
    volume = rng.uniform(100, 2000, size=n) * (1 + np.abs(log_returns) * 100)

    idx = pd.date_range(start=start, periods=n, freq=freq)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": prices, "volume": volume},
        index=idx,
    )
