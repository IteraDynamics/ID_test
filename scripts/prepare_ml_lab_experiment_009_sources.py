from __future__ import annotations

import argparse
import hashlib
import urllib.request
from pathlib import Path

import pandas as pd

# Keep standalone script execution working until the separate packaging migration.
import sys as _artifact_sys
from pathlib import Path as _ArtifactPath
if str(_ArtifactPath(__file__).resolve().parents[1]) not in _artifact_sys.path:
    _artifact_sys.path.insert(0, str(_ArtifactPath(__file__).resolve().parents[1]))


VIX_SERIES = "VIXCLS"
VIX_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prepare deterministic zero-dollar sources for ML Lab Experiment 009")
    p.add_argument("--output-dir", default="artifacts/ml_lab_experiment_009")
    p.add_argument("--vix-output", default="data/VIX_1D.csv")
    return p.parse_args()


def _sha256(path: Path) -> str:
    from research.artifact_io.v1 import sha256_file_v1
    return sha256_file_v1(path, chunk_size=1048576, factory=hashlib.sha256)


def _download_once(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        with urllib.request.urlopen(VIX_URL, timeout=30) as response:
            data = response.read()
    except Exception as exc:
        raise RuntimeError(f"VIX_FRED_ACQUISITION_FAILURE:{exc}") from exc
    if not data:
        raise RuntimeError("VIX_FRED_EMPTY_RESPONSE")
    tmp.write_bytes(data)
    tmp.replace(path)


def _load_vixcls(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    if raw.shape[1] < 2:
        raise ValueError("VIX_FRED_SCHEMA_FAILURE")
    date_col = raw.columns[0]
    value_col = VIX_SERIES if VIX_SERIES in raw.columns else raw.columns[1]
    timestamp = pd.to_datetime(raw[date_col], errors="coerce", utc=True)
    value = pd.to_numeric(raw[value_col].replace(".", pd.NA), errors="coerce")
    frame = pd.DataFrame({"timestamp": timestamp, "close": value}).dropna()
    frame = frame.drop_duplicates(subset=["timestamp"], keep="last").sort_values("timestamp")
    if len(frame) < 500:
        raise ValueError(f"VIX_FRED_COVERAGE_FAILURE:{len(frame)}")
    return frame


def _materialize_ohlcv(frame: pd.DataFrame, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(
        {
            "timestamp": frame["timestamp"],
            "open": frame["close"].astype(float),
            "high": frame["close"].astype(float),
            "low": frame["close"].astype(float),
            "close": frame["close"].astype(float),
            "volume": 0.0,
        }
    )
    tmp = output.with_suffix(".tmp")
    out.to_csv(tmp, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    tmp.replace(output)


def main() -> None:
    args = parse_args()
    cache = Path(args.output_dir) / "source_cache" / f"{VIX_SERIES}.csv"
    output = Path(args.vix_output)

    _download_once(cache)
    frame = _load_vixcls(cache)

    if output.exists():
        print(
            f"VIX_OUTPUT_ALREADY_EXISTS path={output} sha256={_sha256(output)}; "
            "leaving existing file unchanged"
        )
        return

    _materialize_ohlcv(frame, output)
    print(f"VIX_SOURCE_CACHE={cache}")
    print(f"VIX_SOURCE_SHA256={_sha256(cache)}")
    print(f"VIX_OUTPUT={output}")
    print(f"VIX_OUTPUT_SHA256={_sha256(output)}")
    print(f"VIX_ROWS={len(frame)}")
    print(f"VIX_FIRST={frame['timestamp'].min().date()}")
    print(f"VIX_LAST={frame['timestamp'].max().date()}")


if __name__ == "__main__":
    main()
