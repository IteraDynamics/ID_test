from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

import download_equity_data as dl

# Keep standalone script execution working until the separate packaging migration.
import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
if str(_ArtifactPath(__file__).resolve().parents[1]) not in _artifact_sys.path:
    _artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parents[1]))


DESTINATION_UNIVERSE = (
    "EWA", "EWC", "EWG", "EWH", "EWI", "EWJ", "EWL",
    "EWM", "EWW", "EWP", "EWS", "EWT", "EWU", "EWZ",
)
START = "2004-01-01"
END = "2025-01-01"  # yfinance end is exclusive; intended last usable date 2024-12-31.
INTERVAL = "1d"
AUTO_ADJUST = False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prepare frozen destination sources for ML Lab Experiment 011")
    p.add_argument("--output-dir", default="data/ml_lab_transfer_011")
    p.add_argument("--overwrite", action="store_true")
    return p.parse_args()


def _sha256(path: Path) -> str:
    from research.artifact_io.v1 import sha256_file_v1
    return sha256_file_v1(path, chunk_size=1048576, factory=hashlib.sha256)


def _validate_existing(path: Path, asset: str) -> dict[str, Any]:
    frame = pd.read_csv(path)
    expected = ["timestamp", "open", "high", "low", "close", "volume"]
    if list(frame.columns) != expected:
        raise ValueError(f"SOURCE_SCHEMA_FAILURE:{asset}:{list(frame.columns)}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
    if frame["timestamp"].isna().any():
        raise ValueError(f"SOURCE_TIMESTAMP_FAILURE:{asset}")
    if frame["timestamp"].duplicated().any():
        raise ValueError(f"SOURCE_DUPLICATE_TIMESTAMP:{asset}")
    if not frame["timestamp"].is_monotonic_increasing:
        raise ValueError(f"SOURCE_ORDER_FAILURE:{asset}")
    if len(frame) < 2000:
        raise ValueError(f"SOURCE_COVERAGE_FAILURE:{asset}:{len(frame)}")
    return {
        "asset": asset,
        "path": str(path),
        "rows": int(len(frame)),
        "first": str(frame["timestamp"].min().date()),
        "last": str(frame["timestamp"].max().date()),
        "sha256": _sha256(path),
    }


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    yf = dl._require_yfinance()

    records: list[dict[str, Any]] = []
    for position, asset in enumerate(DESTINATION_UNIVERSE, start=1):
        request = dl.DownloadRequest(
            asset=asset,
            start=START,
            end=END,
            interval=INTERVAL,
            auto_adjust=AUTO_ADJUST,
        )
        path = dl._output_path(out_dir, request)
        print(f"[{position}/{len(DESTINATION_UNIVERSE)}] {asset} -> {path}", flush=True)

        if path.exists() and not args.overwrite:
            record = _validate_existing(path, asset)
            record["acquisition"] = "existing_validated"
            records.append(record)
            print(f"  existing validated | {record['rows']:,} rows", flush=True)
            continue

        raw = yf.download(
            asset,
            start=START,
            end=END,
            interval=INTERVAL,
            auto_adjust=AUTO_ADJUST,
            progress=False,
            actions=False,
            threads=False,
            group_by="column",
            multi_level_index=False,
        )
        frame = dl._normalize_download(raw, asset)
        dl._write_csv(path, frame, overwrite=bool(args.overwrite))
        dl._write_manifest(path, request, frame)
        record = _validate_existing(path, asset)
        record["acquisition"] = "downloaded"
        records.append(record)
        print(
            f"  wrote {record['rows']:,} rows | {record['first']} -> {record['last']}",
            flush=True,
        )

    if len(records) != len(DESTINATION_UNIVERSE):
        raise RuntimeError("DESTINATION_SOURCE_COUNT_FAILURE")

    payload = {
        "experiment": "ML_LAB_EXPERIMENT_011_CROSS_UNIVERSE_TRANSFER",
        "status": "SOURCE_PREPARATION_ONLY",
        "universe": list(DESTINATION_UNIVERSE),
        "request": {
            "start": START,
            "end_exclusive": END,
            "interval": INTERVAL,
            "auto_adjust": AUTO_ADJUST,
            "provider": "yfinance",
        },
        "sources": records,
    }
    manifest = out_dir / "experiment_011_source_manifest.json"
    manifest.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
