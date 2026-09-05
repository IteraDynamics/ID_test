"""Historical macro source acquisition/parsing, separate from computation.

Experiment 009 retains download-on-cache-miss behavior. Offline/frozen consumers
use saved macro state instead; importing this module does not acquire data.
"""
from __future__ import annotations
from pathlib import Path
import urllib.request
import numpy as np
import pandas as pd
from research.ml_lab import cross_sectional_v1 as exp5

FRED_SERIES = ("DGS2", "DGS10", "DGS3MO")
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"

def _download_once(series: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{series}.csv"
    if path.exists():
        return path
    url = FRED_URL.format(series=series)
    tmp = path.with_suffix(".tmp")
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read()
    except Exception as exc:  # fail closed
        raise RuntimeError(f"FRED_ACQUISITION_FAILURE:{series}:{exc}") from exc
    if not data:
        raise RuntimeError(f"FRED_EMPTY_RESPONSE:{series}")
    tmp.write_bytes(data)
    tmp.replace(path)
    return path


def _load_fred(path: Path, series: str) -> pd.Series:
    raw = pd.read_csv(path)
    if raw.shape[1] < 2:
        raise ValueError(f"FRED_SCHEMA_FAILURE:{series}")
    date_col = raw.columns[0]
    value_col = series if series in raw.columns else raw.columns[1]
    idx = pd.to_datetime(raw[date_col], errors="coerce", utc=True)
    values = pd.to_numeric(raw[value_col].replace(".", np.nan), errors="coerce")
    out = pd.Series(values.to_numpy(dtype=float), index=pd.DatetimeIndex(idx), name=series).dropna()
    out = out[~out.index.duplicated(keep="last")].sort_index()
    if len(out) < 500:
        raise ValueError(f"FRED_COVERAGE_FAILURE:{series}:{len(out)}")
    return out


def _load_vix(path: Path) -> pd.Series:
    if not path.exists():
        raise FileNotFoundError(f"MISSING_VIX_SOURCE:{path}")
    frame = exp5.read_ohlcv(path).sort_index()
    close = frame["close"].astype(float).rename("VIX")
    if len(close) < 500:
        raise ValueError(f"VIX_COVERAGE_FAILURE:{len(close)}")
    return close


download_once = _download_once
load_fred = _load_fred
load_vix = _load_vix
