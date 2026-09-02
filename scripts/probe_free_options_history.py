"""Sandbox source probe for free historical SPY options-chain data.

Research-only. Downloads one yearly Parquet file from the public preservation
mirror of the Philipp Dubach historical options dataset and validates whether
it is structurally usable for the dealer-gamma exploration screen.

This script does NOT compute gamma exposure, does NOT generate a strategy
result, and does NOT modify runtime/portfolio state.

Expected source schema:
  date, expiration, strike, type, open_interest, implied_volatility, gamma
plus quote fields and contract identifiers.

Usage:
    python scripts/probe_free_options_history.py --year 2024

The script writes a SHA-256 source manifest and JSON validation report under
artifacts/free_options_history_probe/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

import pandas as pd


BASE_URL = (
    "https://raw.githubusercontent.com/SaidBahaDev/options-dataset-hist/"
    "main/data/parquet_spy/options_{year}.parquet"
)
REQUIRED_COLUMNS = {
    "date",
    "expiration",
    "strike",
    "type",
    "open_interest",
    "implied_volatility",
    "gamma",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument(
        "--output-dir",
        default="artifacts/free_options_history_probe",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_frame(frame: pd.DataFrame, year: int) -> dict[str, object]:
    missing_columns = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing_columns:
        return {
            "status": "NOT_USABLE",
            "reason": "MISSING_REQUIRED_COLUMNS",
            "missing_columns": missing_columns,
        }

    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["expiration"] = pd.to_datetime(data["expiration"], errors="coerce")

    invalid_type_rows = int((~data["type"].astype(str).str.lower().isin({"call", "put"})).sum())
    negative_oi_rows = int((pd.to_numeric(data["open_interest"], errors="coerce") < 0).sum())
    expiration_before_observation = int((data["expiration"] < data["date"]).sum())

    report = {
        "status": "USABLE" if not (invalid_type_rows or negative_oi_rows or expiration_before_observation) else "PARTIAL",
        "year_requested": year,
        "rows": int(len(data)),
        "date_min": None if data["date"].dropna().empty else data["date"].min().date().isoformat(),
        "date_max": None if data["date"].dropna().empty else data["date"].max().date().isoformat(),
        "distinct_dates": int(data["date"].nunique(dropna=True)),
        "distinct_expirations": int(data["expiration"].nunique(dropna=True)),
        "distinct_strikes": int(pd.to_numeric(data["strike"], errors="coerce").nunique(dropna=True)),
        "call_rows": int((data["type"].astype(str).str.lower() == "call").sum()),
        "put_rows": int((data["type"].astype(str).str.lower() == "put").sum()),
        "missing_open_interest_rows": int(data["open_interest"].isna().sum()),
        "zero_open_interest_rows": int((pd.to_numeric(data["open_interest"], errors="coerce") == 0).sum()),
        "missing_gamma_rows": int(data["gamma"].isna().sum()),
        "missing_iv_rows": int(data["implied_volatility"].isna().sum()),
        "invalid_type_rows": invalid_type_rows,
        "negative_open_interest_rows": negative_oi_rows,
        "expiration_before_observation_rows": expiration_before_observation,
    }
    return report


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_url = BASE_URL.format(year=args.year)
    local_path = output_dir / f"spy_options_{args.year}.parquet"
    manifest_path = output_dir / f"spy_options_{args.year}_source_manifest.json"
    report_path = output_dir / f"spy_options_{args.year}_validation.json"

    try:
        urllib.request.urlretrieve(source_url, local_path)
    except Exception as exc:  # fail closed; no fallback source is silently substituted
        report = {
            "status": "NOT_USABLE",
            "reason": "DOWNLOAD_FAILED",
            "source_url": source_url,
            "error": f"{type(exc).__name__}: {exc}",
        }
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2

    manifest = {
        "source_url": source_url,
        "local_path": str(local_path),
        "bytes": local_path.stat().st_size,
        "sha256": sha256_file(local_path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    try:
        frame = pd.read_parquet(local_path)
    except Exception as exc:
        report = {
            "status": "NOT_USABLE",
            "reason": "PARQUET_READ_FAILED",
            "source_manifest": manifest,
            "error": f"{type(exc).__name__}: {exc}",
            "note": "No dependency was added for this sandbox probe; install a local pandas-compatible Parquet engine only if needed.",
        }
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 3

    report = validate_frame(frame, args.year)
    report["source_manifest"] = manifest
    report["provenance_caveat"] = (
        "Public preservation mirror; upstream market-data sourcing is not independently documented. "
        "Acceptable only for sandbox screening pending internal consistency and spot checks against OCC."
    )
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "USABLE" else 4


if __name__ == "__main__":
    raise SystemExit(main())
