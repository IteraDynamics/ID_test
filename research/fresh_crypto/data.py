"""Reuse UTC spot bars; optional Coinbase downloads are explicitly requested."""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from research.fresh_discovery.data import sha, write_json

ASSETS = ("BTC", "ETH")
START = pd.Timestamp("2017-01-01", tz="UTC")
END = pd.Timestamp("2025-01-01", tz="UTC")
WARMUP = 365


def normalize(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Timestamps denote UTC bar START. Never fill a missing intraday/daily bar."""
    raw = raw.rename(columns=lambda c: c.strip().lower().replace(" ", "_"))
    if raw.columns.has_duplicates:
        raise ValueError("Duplicate column names")
    time_columns = [c for c in ("timestamp", "date", "datetime", "time") if c in raw]
    if len(time_columns) != 1 or not set(("open", "high", "low", "close", "volume")) <= set(raw):
        raise ValueError("Need one timestamp/date/datetime/time and open, high, low, close, volume")
    labels = raw[time_columns[0]]
    if pd.api.types.is_numeric_dtype(labels):
        # Seconds and milliseconds are supported explicitly; reject ambiguous units.
        magnitude = float(labels.abs().median())
        unit = "s" if 1e9 < magnitude < 1e10 else "ms" if 1e12 < magnitude < 1e13 else None
        if unit is None:
            raise ValueError("Unrecognized epoch timestamp units")
        dates = pd.DatetimeIndex(pd.to_datetime(labels, unit=unit, utc=True, errors="raise"))
    else:
        dates = pd.DatetimeIndex(pd.to_datetime(labels, utc=True, errors="raise", format="mixed"))
    if dates.hasnans:
        raise ValueError("Missing timestamps")
    mask = (dates >= START) & (dates < END)
    # Future prices are not validated, aggregated, or evaluated. Only date labels are inspected.
    frame = raw.loc[mask, ["open", "high", "low", "close", "volume"]].astype(float)
    frame.index = dates[mask]
    if len(frame) < 2 or frame.index.has_duplicates:
        raise ValueError("Insufficient pre-2025 history or duplicate timestamps")
    frame = frame.sort_index()
    gaps = frame.index.to_series().diff().dropna()
    step = gaps.min()
    if step not in [pd.Timedelta(hours=h) for h in (1, 4, 24)]:
        raise ValueError("Supported bar sizes: 1 hour, 4 hours, or 1 UTC day")
    if (gaps != step).any():
        raise ValueError("Missing/irregular bars; no filling or interior-day deletion allowed")
    if ((frame.index - frame.index.normalize()) % step != pd.Timedelta(0)).any():
        raise ValueError("Bars must align with UTC midnight and use bar-start labels")
    values = frame.to_numpy()
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ValueError("Invalid price or volume")
    if ((frame.low > frame[["open", "close"]].min(axis=1)).any()
            or (frame.high < frame[["open", "close"]].max(axis=1)).any()
            or (frame.low > frame.high).any()):
        raise ValueError("Invalid OHLC range")
    expected = int(pd.Timedelta(days=1) / step)
    counts = frame.close.resample("1D").count()
    complete = counts[counts == expected].index
    daily = frame.resample("1D").agg(dict(open="first", high="max", low="min", close="last", volume="sum"))
    daily = daily.loc[complete]
    calendar = pd.date_range(daily.index.min(), END - pd.Timedelta(days=1), freq="D") if len(daily) else []
    if not len(daily) or not daily.index.equals(calendar):
        raise ValueError("Daily history must be continuous through 2024-12-31 (complete UTC day)")
    if len(daily) < WARMUP + 2 + 3 * 365:
        raise ValueError("Need 365 warmup days plus at least three evaluation years before 2025")
    daily.index.name = "timestamp"
    return daily, dict(source_bar_seconds=int(step.total_seconds()),
                       excluded_outside_development_rows=int((~mask).sum()),
                       incomplete_boundary_days_removed=int((counts != expected).sum()),
                       first_date=str(daily.index[0].date()), last_date=str(daily.index[-1].date()),
                       daily_rows=len(daily), assumed_timestamp_semantics="UTC_bar_start")


def discover(root: Path) -> dict[str, list[Path]]:
    paths = sorted(root.rglob("*.csv")) if root.exists() else []
    return {a: [p for p in paths if re.search(rf"(?i)(?:^|[^a-z]){a}(?:[-_]?usd)?(?:[^a-z]|$)", p.stem)
                and not any(s in p.parts for s in (".venv", ".git", "artifacts"))] for a in ASSETS}


def download(asset: str, root: Path) -> Path:
    """Coinbase Exchange spot, <=290 UTC daily buckets per request; no credentials."""
    path = root / "fresh_crypto_20260914" / f"{asset}-USD.csv"
    if path.exists():
        raise FileExistsError(f"Refusing to replace cache: {path}")
    rows, cursor = {}, START
    while cursor < END:
        stop = min(cursor + pd.Timedelta(days=290), END)
        # Coinbase endpoints may include an end bucket: keep the request itself
        # inside development history instead of requesting 2025-01-01 midnight.
        params = urllib.parse.urlencode(dict(start=cursor.isoformat(),
                                             end=(stop-pd.Timedelta(seconds=1)).isoformat(), granularity=86400))
        url = f"https://api.exchange.coinbase.com/products/{asset}-USD/candles?{params}"
        for attempt in range(4):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "Itera-fresh-crypto-research"})
                with urllib.request.urlopen(request, timeout=30) as response:
                    batch = json.load(response)
                if not isinstance(batch, list) or not batch:
                    raise ValueError("Empty or invalid Coinbase candle response")
                break
            except (OSError, ValueError):
                if attempt == 3:
                    raise
                time.sleep(attempt + 1)
        for row in batch:
            if not isinstance(row, list) or len(row) != 6:
                raise ValueError("Unexpected Coinbase candle schema")
            stamp = pd.Timestamp(row[0], unit="s", tz="UTC")
            if START <= stamp < END:
                if stamp in rows and rows[stamp] != row:
                    raise ValueError("Conflicting overlapping Coinbase candles")
                rows[stamp] = row
        cursor = stop
        time.sleep(.2)
    raw = pd.DataFrame(list(rows.values()), columns=["timestamp", "low", "high", "open", "close", "volume"])
    frame, _ = normalize(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, lineterminator="\n", float_format="%.17g")
    write_json(path.with_suffix(".json"), dict(provider="Coinbase Exchange", product=f"{asset}-USD",
               granularity_seconds=86400, start=str(START), end_exclusive=str(END), sha256=sha(path)))
    return path


def load_inputs(root: Path, explicit: dict[str, Path | None], out: Path,
                allow_download: bool = False, source_label: str = "operator_local_unverified"):
    inventory, frames, records, errors = [], {}, {}, []
    candidates = discover(root)
    for asset in ASSETS:
        paths = [explicit[asset]] if explicit.get(asset) else candidates[asset]
        valid = []
        for path in paths:
            try:
                frame, info = normalize(pd.read_csv(path))
                record = dict(asset=asset, source_path=str(path.resolve()), source_sha256=sha(path),
                              source_label=source_label, **info)
                sidecar = path.with_suffix(".json")
                if sidecar.exists():
                    # Sidecars are evidence, never authority to override validation.
                    record["source_sidecar_sha256"] = sha(sidecar)
                valid.append((frame, record))
                inventory.append(dict(path=str(path), asset=asset, eligible=True, **info))
            except (ValueError, OSError, TypeError) as exc:
                inventory.append(dict(path=str(path), asset=asset, eligible=False, reason=str(exc)))
        # Byte-equivalent daily inputs from multiple resolutions are interchangeable;
        # different histories are not chosen by length, returns, or file mtime.
        unique = {}
        for frame, record in valid:
            key = frame.to_csv(lineterminator="\n", float_format="%.17g")
            unique.setdefault(key, (frame, record))
        if not unique and allow_download and not explicit.get(asset):
            path = download(asset, root)
            frame, info = normalize(pd.read_csv(path))
            unique[asset] = (frame, dict(asset=asset, source_path=str(path.resolve()), source_sha256=sha(path),
                           source_label="Coinbase Exchange downloaded by this runner", **info))
            inventory.append(dict(path=str(path), asset=asset, eligible=True, downloaded=True, **info))
        write_json(out / "data_inventory.json", dict(search_root=str(root.resolve()), files=inventory))
        if len(unique) != 1:
            reason = "No eligible" if not unique else "Multiple different eligible"
            errors.append(f"{reason} {asset} data files; supply --{asset.lower()}-csv explicitly")
            continue
        frames[asset], records[asset] = next(iter(unique.values()))
    if errors:
        raise ValueError(". ".join(errors) + ". See data_inventory.json.")
    first = max(f.index[0] for f in frames.values())
    for asset in ASSETS:
        records[asset]["leading_days_trimmed_for_common_window"] = int((frames[asset].index < first).sum())
        frames[asset] = frames[asset].loc[first:]
        path = out / f"{asset}-USD.csv"
        frames[asset].to_csv(path, lineterminator="\n", float_format="%.17g")
        records[asset]["normalized_sha256"] = sha(path)
    if not frames["BTC"].index.equals(frames["ETH"].index):
        raise ValueError("BTC and ETH calendars differ")
    write_json(out / "data_manifest.json", dict(assets=records, holdout_prices_used=False,
               common_first_date=str(first.date()), common_last_date="2024-12-31"))
    return frames, records
