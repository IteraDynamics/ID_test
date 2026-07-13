from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


SUPPORTED_INTERVALS = {"1d"}


@dataclass(frozen=True)
class DownloadRequest:
    asset: str
    start: str
    end: str
    interval: str
    auto_adjust: bool
    provider: str = "yfinance"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Canonical research-only equity/ETF downloader for Itera Dynamics. "
            "Uses yfinance and writes normalized timestamp,open,high,low,close,volume CSV files."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--asset",
        action="append",
        required=True,
        help="Ticker to download. Repeat for multiple assets, e.g. --asset SPY --asset QQQ.",
    )
    parser.add_argument(
        "--interval",
        default="1d",
        help=(
            "Download interval. This canonical equity downloader currently supports only 1d. "
            "Deep multi-year hourly ETF history requires a separately approved provider and workflow."
        ),
    )
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--auto-adjust", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def _require_yfinance() -> Any:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError(
            "yfinance is required for equity/ETF downloads. Install it with: "
            "python -m pip install yfinance"
        ) from exc
    return yf


def _validate_interval(interval: str) -> str:
    normalized = interval.strip().lower()
    if normalized not in SUPPORTED_INTERVALS:
        raise ValueError(
            f"Unsupported interval {interval!r}. This script intentionally supports only daily equity/ETF data. "
            "Do not use it for locked hourly Jump Risk transfer tests."
        )
    return normalized


def _validate_dates(start: str, end: str) -> None:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    if end_ts < start_ts:
        raise ValueError(f"End date {end!r} is before start date {start!r}")


def _normalize_download(raw: pd.DataFrame, asset: str) -> pd.DataFrame:
    if raw.empty:
        raise RuntimeError(f"yfinance returned no rows for {asset}")

    frame = raw.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        if asset in frame.columns.get_level_values(-1):
            frame = frame.xs(asset, axis=1, level=-1)
        else:
            frame.columns = frame.columns.get_level_values(0)

    rename = {str(column).strip().lower(): column for column in frame.columns}
    required = ["open", "high", "low", "close"]
    missing = [name for name in required if name not in rename]
    if missing:
        raise RuntimeError(f"Downloaded data for {asset} is missing columns: {missing}")

    output = pd.DataFrame(index=pd.to_datetime(frame.index, utc=True))
    output["open"] = pd.to_numeric(frame[rename["open"]], errors="coerce")
    output["high"] = pd.to_numeric(frame[rename["high"]], errors="coerce")
    output["low"] = pd.to_numeric(frame[rename["low"]], errors="coerce")
    output["close"] = pd.to_numeric(frame[rename["close"]], errors="coerce")
    if "volume" in rename:
        output["volume"] = pd.to_numeric(frame[rename["volume"]], errors="coerce")
    else:
        output["volume"] = 0.0

    output = output.dropna(subset=required).sort_index()
    output = output[~output.index.duplicated(keep="last")]
    output.index.name = "timestamp"
    if output.empty:
        raise RuntimeError(f"No usable normalized rows for {asset}")
    return output


def _output_path(output_dir: Path, request: DownloadRequest) -> Path:
    if request.interval == "1d":
        return output_dir / f"{request.asset.upper()}_1D.csv"
    raise ValueError(request.interval)


def _write_csv(path: Path, frame: pd.DataFrame, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file without --overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    frame.reset_index().to_csv(temp, index=False)
    temp.replace(path)


def _write_manifest(path: Path, request: DownloadRequest, frame: pd.DataFrame) -> None:
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    payload = {
        "request": asdict(request),
        "output": str(path),
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": int(len(frame)),
        "actual_start": frame.index.min().isoformat(),
        "actual_end": frame.index.max().isoformat(),
        "schema": ["timestamp", "open", "high", "low", "close", "volume"],
        "notes": [
            "Equity/ETF data source: yfinance.",
            "This file is daily data and is not interchangeable with hourly crypto data.",
            "Locked cross-asset Jump Risk transfer tests require matching hourly bars.",
        ],
    }
    temp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temp.replace(manifest_path)


def main() -> None:
    args = parse_args()
    interval = _validate_interval(args.interval)
    _validate_dates(args.start, args.end)
    yf = _require_yfinance()

    assets = list(dict.fromkeys(asset.strip().upper() for asset in args.asset if asset.strip()))
    if not assets:
        raise ValueError("At least one non-empty --asset is required")

    output_dir = Path(args.output_dir)
    print("Itera equity/ETF OHLCV downloader")
    print("Provider: yfinance")
    print(f"Assets: {assets}")
    print(f"Interval: {interval}")
    print(f"Window: {args.start} -> {args.end}")
    print()

    for position, asset in enumerate(assets, start=1):
        request = DownloadRequest(
            asset=asset,
            start=args.start,
            end=args.end,
            interval=interval,
            auto_adjust=bool(args.auto_adjust),
        )
        path = _output_path(output_dir, request)
        print(f"[{position}/{len(assets)}] {asset} -> {path}", flush=True)
        raw = yf.download(
            asset,
            start=args.start,
            end=args.end,
            interval=interval,
            auto_adjust=args.auto_adjust,
            progress=False,
            actions=False,
            threads=False,
        )
        frame = _normalize_download(raw, asset)
        _write_csv(path, frame, overwrite=args.overwrite)
        _write_manifest(path, request, frame)
        print(
            f"  wrote {len(frame):,} rows | {frame.index.min().isoformat()} -> {frame.index.max().isoformat()}",
            flush=True,
        )
        print()

    print("Download complete")


if __name__ == "__main__":
    main()
