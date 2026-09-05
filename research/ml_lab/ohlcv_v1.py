"""Frozen OHLCV normalization inherited from Jump Risk at 83e4e11.

Preserves timestamp inference, duplicate handling and missing-volume behavior.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

def _normalise_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    cols = {c.lower().strip(): c for c in df.columns}
    ts_col = cols.get("timestamp") or cols.get("date") or cols.get("datetime") or cols.get("time")
    if ts_col is None:
        # Many research CSVs use the timestamp as the unnamed first column.
        first = df.columns[0]
        parsed = pd.to_datetime(df[first], utc=True, errors="coerce")
        if parsed.notna().mean() > 0.8:
            ts_col = first
        else:
            raise ValueError("CSV must include a timestamp/date/datetime/time column or timestamp-like first column")

    out = df.copy()
    out["timestamp"] = pd.to_datetime(out[ts_col], utc=True, errors="coerce")
    out = out.dropna(subset=["timestamp"]).sort_values("timestamp")
    out = out.drop_duplicates("timestamp").set_index("timestamp")

    rename = {}
    for name in ("open", "high", "low", "close", "volume"):
        if name in cols:
            rename[cols[name]] = name
    out = out.rename(columns=rename)
    missing = [c for c in ("open", "high", "low", "close") if c not in out.columns]
    if missing:
        raise ValueError(f"Missing OHLC columns: {missing}")
    if "volume" not in out.columns:
        out["volume"] = np.nan
    out = out[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
    return out.dropna(subset=["open", "high", "low", "close"])


def read_ohlcv(path: str | Path) -> pd.DataFrame:
    return _normalise_ohlcv(pd.read_csv(path))
