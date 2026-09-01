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


def _flatten_yfinance_columns(frame: pd.DataFrame, asset: str) -> pd.DataFrame:
    if not isinstance(frame.columns, pd.MultiIndex):
        return frame

    # yfinance may return either (Price, Ticker) or (Ticker, Price), depending
    # on version and invocation. Select the requested ticker when possible,
    # then collapse the remaining level to the OHLCV field names.
    for level in range(frame.columns.nlevels):
        values = {str(value).upper() for value in frame.columns.get_level_values(level)}
        if asset.upper() in values:
            frame = frame.xs(asset, axis=1, level=level, drop_level=True)
            break

    if isinstance(frame.columns, pd.MultiIndex):
        # A single ticker can still leave a redundant one-value level.
        while isinstance(frame.columns, pd.MultiIndex) and frame.columns.nlevels > 1:
            unique_counts = [frame.columns.get_level_values(level).nunique() for level in range(frame.columns.nlevels)]
            removable = next((level for level, count in enumerate(unique_counts) if count == 1), None)
            if removable is None:
                break
            frame.columns = frame.columns.droplevel(removable)

    if isinstance(frame.columns, pd.MultiIndex):
        raise RuntimeError(
            f"Could not normalize yfinance MultiIndex columns for {asset}: {list(frame.columns)[:10]}"
        )
    return frame


def _normalize_download(raw: pd.DataFrame, asset: str) -> pd.DataFrame:
    if raw.empty:
        raise RuntimeError(f"yfinance returned no rows for {asset}")

    frame = _flatten_yfinance_columns(raw.copy(), asset)
    frame.columns = [str(column).strip().lower() for column in frame.columns]

    required = ["open", "high", "low", "close"]
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise RuntimeError(
            f"Downloaded data for {asset} is missing columns {missing}; received columns: {list(frame.columns)}"
        )

    # Normalize the source frame's index first. Assigning Series from the old
    # naive Date index into a new UTC index causes pandas label alignment to
    # produce all-NaN columns.
    normalized_index = pd.to_datetime(frame.index, utc=True, errors="coerce")
    valid_index = ~normalized_index.isna()
    frame = frame.loc[valid_index].copy()
    frame.index = normalized_index[valid_index]
    frame.index.name = "timestamp"

    output = pd.DataFrame(index=frame.index)
    for column in required:
        output[column] = pd.to_numeric(frame[column], errors="coerce").to_numpy()
    if "volume" in frame.columns:
        output["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0.0).to_numpy()
    else:
        output["volume"] = 0.0

    output = output.dropna(subset=required).sort_index()
    output = output[~output.index.duplicated(keep="last")]
    if output.empty:
        raise RuntimeError(
            f"No usable normalized rows for {asset}; raw rows={len(raw)}, columns={list(frame.columns)}"
        )
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

    failed: list[tuple[str, str]] = []

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
        try:
            raw = yf.download(
                asset,
                start=args.start,
                end=args.end,
                interval=interval,
                auto_adjust=args.auto_adjust,
                progress=False,
                actions=False,
                threads=False,
                group_by="column",
                multi_level_index=False,
            )
            frame = _normalize_download(raw, asset)
            _write_csv(path, frame, overwrite=args.overwrite)
            _write_manifest(path, request, frame)
        except Exception as exc:  # noqa: BLE001 -- bulk pulls must not die on one bad ticker
            print(f"  FAILED: {exc}", flush=True)
            failed.append((asset, str(exc)))
            print()
            continue
        print(
            f"  wrote {len(frame):,} rows | {frame.index.min().isoformat()} -> {frame.index.max().isoformat()}",
            flush=True,
        )
        print()

    succeeded = len(assets) - len(failed)
    print(f"Download complete: {succeeded}/{len(assets)} succeeded, {len(failed)} failed.")
    if failed:
        print("Failed assets (expected for delisted/renamed/acquired tickers, not necessarily a bug):")
        for asset, reason in failed:
            print(f"  - {asset}: {reason}")


if __name__ == "__main__":
    main()
