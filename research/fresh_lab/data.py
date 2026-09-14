"""Immutable Yahoo snapshots and strict, common-calendar daily panel loading."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

INDEX = ("SPY", "QQQ", "IWM")
SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
SYMBOLS = INDEX + SECTORS
DATA_START = "2004-01-01"
DATA_END = "2024-01-01"  # exclusive; downloader cannot request later observations
SCORE_START = "2006-01-01"
FIELDS = ("Open", "High", "Low", "Close", "Adj Close", "Volume",
          "Dividends", "Stock Splits")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
                    encoding="utf-8", newline="\n")


def acquire(root: Path) -> None:
    """Download once. Refuse overwrite; incomplete snapshots have no manifest."""
    import yfinance as yf

    if root.exists():
        raise FileExistsError(f"Snapshot already exists: {root}. Use --reuse-data.")
    root.mkdir(parents=True)
    files = {}
    for symbol in SYMBOLS:
        print(f"Downloading {symbol}: {DATA_START} through 2023", flush=True)
        frame = yf.Ticker(symbol).history(
            start=DATA_START, end=DATA_END, interval="1d", auto_adjust=False,
            back_adjust=False, actions=True, repair=False, keepna=True,
            raise_errors=True,
        )
        if frame.empty:
            raise ValueError(f"{symbol}: empty vendor response")
        missing = set(FIELDS) - set(frame.columns)
        if missing:
            raise ValueError(f"{symbol}: missing vendor fields {sorted(missing)}")
        # Preserve the exchange-local session date, not a UTC-shifted date.
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index.date))
        frame.index.name = "date"
        if (frame.index >= pd.Timestamp(DATA_END)).any():
            raise ValueError(f"{symbol}: vendor returned excluded later history")
        frame = frame.loc[:, list(FIELDS)]
        path = root / f"{symbol}.csv"
        frame.to_csv(path, lineterminator="\n", float_format="%.12g")
        files[symbol] = {"filename": path.name, "sha256": digest(path),
                         "rows": len(frame), "start": str(frame.index[0].date()),
                         "end": str(frame.index[-1].date())}
    write_json(root / "manifest.json", {
        "source": "Yahoo Finance via yfinance", "start": DATA_START,
        "end_exclusive": DATA_END, "symbols": list(SYMBOLS), "files": files,
        "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        "yfinance_version": importlib.metadata.version("yfinance"),
        "price_convention": "Yahoo split-adjusted OHLC; dividends credited separately",
        "pit_certified": False,
    })


def load_panel(root: Path) -> tuple[dict[str, pd.DataFrame], dict]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if (manifest["start"] != DATA_START or manifest["end_exclusive"] != DATA_END
            or manifest["symbols"] != list(SYMBOLS)):
        raise ValueError("Snapshot identity differs from this batch's fixed universe/window")
    raw = {}
    calendar = None
    audit = {}
    for symbol in SYMBOLS:
        path = root / f"{symbol}.csv"
        if manifest["files"][symbol]["filename"] != path.name:
            raise ValueError(f"{symbol}: unexpected source filename")
        if digest(path) != manifest["files"][symbol]["sha256"]:
            raise ValueError(f"{symbol}: source hash mismatch")
        frame = pd.read_csv(path, index_col="date", parse_dates=["date"])
        if frame.empty or not set(FIELDS).issubset(frame.columns):
            raise ValueError(f"{symbol}: empty or incomplete snapshot")
        if not frame.index.is_unique or not frame.index.is_monotonic_increasing:
            raise ValueError(f"{symbol}: duplicate or unsorted sessions")
        values = frame.loc[:, list(FIELDS)].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"{symbol}: nonfinite source observations")
        if (frame[["Open", "High", "Low", "Close", "Adj Close"]] <= 0).any().any():
            raise ValueError(f"{symbol}: nonpositive price")
        if (frame["Volume"] <= 0).any() or (frame["Dividends"] < 0).any():
            raise ValueError(f"{symbol}: zero volume or negative distribution")
        if (frame["Stock Splits"] < 0).any():
            raise ValueError(f"{symbol}: invalid split ratio")
        tolerance = 1e-5 * frame["Close"]
        if ((frame["High"] + tolerance < frame[["Open", "Close", "Low"]].max(axis=1)).any()
                or (frame["Low"] - tolerance > frame[["Open", "Close", "High"]].min(axis=1)).any()):
            raise ValueError(f"{symbol}: inconsistent OHLC")
        if ((frame.index < pd.Timestamp(DATA_START)).any()
                or (frame.index >= pd.Timestamp(DATA_END)).any()):
            raise ValueError(f"{symbol}: source outside development window")
        if frame.index[0] > pd.Timestamp("2004-01-06") or frame.index[-1] < pd.Timestamp("2023-12-28"):
            raise ValueError(f"{symbol}: truncated development history")
        if calendar is None:
            calendar = frame.index
            if (calendar.to_series().diff().dropna().dt.days > 7).any():
                raise ValueError("SPY: unexplained calendar gap longer than seven days")
        elif not frame.index.equals(calendar):
            raise ValueError(f"{symbol}: calendar differs from SPY; no silent intersection/fill")
        # Yahoo OHLC are already split-adjusted. Do not multiply shares by split events.
        total = (frame["Close"] + frame["Dividends"]) / frame["Close"].shift(1) - 1
        adjusted = frame["Adj Close"].pct_change(fill_method=None)
        discrepancy = (total - adjusted).abs()
        # A source-convention canary, not certification of vendor data.
        if discrepancy.max() > 0.002:
            raise ValueError(f"{symbol}: dividend/adjusted-close reconciliation exceeds 20 bps")
        if total.abs().max() > 0.50:
            raise ValueError(f"{symbol}: >50% daily return requires source review")
        audit[symbol] = {"rows": len(frame),
                         "max_total_return_vs_adj_close_difference": float(discrepancy.max()),
                         "split_events": int((frame["Stock Splits"] != 0).sum())}
        raw[symbol] = frame
    panel = {field: pd.DataFrame({s: raw[s][field] for s in SYMBOLS})
             for field in ("Open", "Close", "Dividends")}
    panel["total_return"] = (panel["Close"] + panel["Dividends"]) / panel["Close"].shift(1) - 1
    panel["total_index"] = (1 + panel["total_return"].fillna(0)).cumprod()
    # The distribution belongs to the holder across the ex-date overnight interval.
    panel["night_return"] = ((panel["Open"] + panel["Dividends"])
                             / panel["Close"].shift(1) - 1)
    panel["day_return"] = panel["Close"] / panel["Open"] - 1
    return panel, {"manifest": manifest, "audit": audit,
                   "calendar_check": "all 12 identical to SPY; no independent exchange calendar",
                   "distribution_timing": "cash credited ex-date; payment-date lag omitted"}
