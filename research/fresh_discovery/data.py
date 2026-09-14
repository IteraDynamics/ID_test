"""Immutable daily ETF snapshots. Discovery never requests 2025 or later."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

MACRO = ("SPY", "QQQ", "IWM", "EFA", "EEM", "IEF", "TLT", "GLD", "DBC", "VNQ")
SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
PULLBACK = ("SPY", "QQQ", "IWM", "EFA", "EEM")
ASSETS = MACRO + SECTORS + ("BIL",)
START = "2007-06-01"
END_EXCLUSIVE = "2025-01-01"
EVALUATION_START = "2008-07-01"
REQUEST = dict(start=START, end=END_EXCLUSIVE, interval="1d", auto_adjust=False,
               back_adjust=False, actions=True, repair=False, keepna=True)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
                    encoding="utf-8", newline="\n")


def normalize(raw: pd.DataFrame, asset: str) -> pd.DataFrame:
    required = ["date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]
    if not set(required).issubset(raw.columns):
        raise ValueError(f"{asset}: missing raw OHLC/adjusted-close columns")
    dates = pd.DatetimeIndex(pd.to_datetime(raw.date, errors="raise"))
    if dates.tz is not None or not dates.equals(dates.normalize()):
        raise ValueError(f"{asset}: dates must be timezone-free daily session labels")
    if dates.has_duplicates or not dates.is_monotonic_increasing or len(dates) < 253:
        raise ValueError(f"{asset}: duplicate/unsorted/insufficient rows")
    if dates.min() < pd.Timestamp(START) or dates.max() >= pd.Timestamp(END_EXCLUSIVE):
        raise ValueError(f"{asset}: input crosses the discovery boundary")
    if (dates.dayofweek >= 5).any() or dates.to_series().diff().max().days > 7:
        raise ValueError(f"{asset}: invalid or incomplete session calendar")
    values = raw[required[1:]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values[:, :5] <= 0).any() or (values[:, 5] <= 0).any():
        raise ValueError(f"{asset}: nonfinite/nonpositive price or volume; no filling allowed")
    tolerance = 1e-6 * values[:, 3]
    if ((values[:, 2] > values[:, [0, 3]].min(axis=1) + tolerance).any()
            or (values[:, 1] + tolerance < values[:, [0, 3]].max(axis=1)).any()
            or (values[:, 2] > values[:, 1] + tolerance).any()):
        raise ValueError(f"{asset}: invalid OHLC range")
    factor = values[:, 4] / values[:, 3]
    frame = pd.DataFrame(values[:, :4] * factor[:, None], index=dates,
                         columns=["open", "high", "low", "close"])
    frame.index.name = "date"
    return frame


def download_snapshot(root: Path) -> None:
    """Resume verified per-symbol files; refuse to overwrite an existing snapshot."""
    import yfinance as yf

    root.mkdir(parents=True, exist_ok=True)
    entries = {}
    for asset in ASSETS:
        path, manifest = root / f"{asset}.csv", root / f"{asset}.json"
        if path.exists() or manifest.exists():
            if not (path.exists() and manifest.exists()):
                raise ValueError(f"Incomplete {asset} cache pair; move it aside before retrying")
            record = json.loads(manifest.read_text(encoding="utf-8"))
            if (record["request"] != REQUEST or record["asset"] != asset
                    or record["csv_sha256"] != sha(path)):
                raise ValueError(f"{asset}: cache identity mismatch")
            normalize(pd.read_csv(path), asset)
            print(f"{asset}: verified cached snapshot", flush=True)
        else:
            raw = yf.Ticker(asset).history(**REQUEST, timeout=30, raise_errors=True)
            if raw.empty:
                raise ValueError(f"{asset}: provider returned no data")
            raw = raw.copy()
            # Keep the exchange's session date, not its UTC-converted midnight.
            raw.index = pd.DatetimeIndex(raw.index).tz_localize(None).normalize()
            raw.index.name = "date"
            raw = raw.reset_index()
            normalize(raw, asset)
            record = dict(asset=asset, provider="Yahoo Finance via yfinance", request=REQUEST,
                          acquired_utc=datetime.now(timezone.utc).isoformat(), rows=len(raw),
                          yfinance=importlib.metadata.version("yfinance"))
            temporary = path.with_suffix(".csv.tmp")
            raw.to_csv(temporary, index=False, lineterminator="\n", float_format="%.17g")
            temporary.replace(path)
            record["csv_sha256"] = sha(path)
            write_json(manifest, record)
            print(f"{asset}: saved {len(raw):,} daily rows", flush=True)
        entries[asset] = dict(csv_sha256=sha(path), manifest_sha256=sha(manifest))
    snapshot = dict(schema_version=1, request=REQUEST, assets=list(ASSETS), files=entries)
    target = root / "snapshot.json"
    if target.exists() and json.loads(target.read_text(encoding="utf-8")) != snapshot:
        raise ValueError("Snapshot identity changed; use a new data directory")
    write_json(target, snapshot)
    load_snapshot(root)


def load_snapshot(root: Path) -> tuple[dict[str, pd.DataFrame], dict]:
    manifest_path = root / "snapshot.json"
    snapshot = json.loads(manifest_path.read_text(encoding="utf-8"))
    if snapshot["assets"] != list(ASSETS) or snapshot["request"] != REQUEST:
        raise ValueError("Unexpected snapshot universe or date request")
    frames = {}
    for asset in ASSETS:
        path, manifest = root / f"{asset}.csv", root / f"{asset}.json"
        recorded = snapshot["files"][asset]
        if recorded != dict(csv_sha256=sha(path), manifest_sha256=sha(manifest)):
            raise ValueError(f"{asset}: snapshot hash mismatch")
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        raw = pd.read_csv(path)
        if (metadata["request"] != REQUEST or metadata["asset"] != asset
                or metadata["csv_sha256"] != sha(path) or metadata["rows"] != len(raw)):
            raise ValueError(f"{asset}: source manifest mismatch")
        frames[asset] = normalize(raw, asset)
    reference = frames["SPY"].index
    if reference[0] != pd.Timestamp(START) or reference[-1] != pd.Timestamp("2024-12-31"):
        raise ValueError("SPY snapshot lacks the required first/last session")
    for asset, frame in frames.items():
        if not reference.equals(frame.index):
            missing = reference.difference(frame.index).strftime("%Y-%m-%d").tolist()[:5]
            raise ValueError(f"{asset}: calendar differs from SPY; missing examples={missing}")
    return frames, dict(snapshot_sha256=sha(manifest_path), **snapshot)
