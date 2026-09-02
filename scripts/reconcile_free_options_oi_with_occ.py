"""Reconcile sandbox SPY option open interest against OCC's official daily report.

Research-only source-governance probe for the dealer-gamma exploration screen.
It does not compute gamma exposure, generate alpha, or touch runtime/portfolio state.

OCC states that a report displayed on date T reflects open interest following the
previous trading day's settlement. Therefore this probe compares an OCC report date
to a separately supplied mirror observation date (normally the prior trading day).

Example:
    python scripts/reconcile_free_options_oi_with_occ.py \
        --occ-report-date 2024-01-03 --mirror-date 2024-01-02 --year 2024

The probe is deliberately fail-closed. OCC has changed CSV layouts over time; if the
schema cannot be normalized unambiguously, it prints the observed columns and returns
SCHEMA_UNRESOLVED rather than guessing.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd


OCC_ENDPOINT = "https://marketdata.theocc.com/daily-open-interest"
DEFAULT_MIRROR_DIR = Path("artifacts/free_options_history_probe")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--occ-report-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--mirror-date", required=True, help="YYYY-MM-DD; normally prior trading day")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--mirror-file", default=None)
    parser.add_argument("--output-dir", default="artifacts/free_options_occ_reconciliation")
    return parser.parse_args()


def normalize_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def first_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    present = set(columns)
    for candidate in candidates:
        if candidate in present:
            return candidate
    return None


def read_occ_csv(payload: bytes) -> pd.DataFrame:
    text = payload.decode("utf-8-sig", errors="replace")
    if "<html" in text[:500].lower() or "<!doctype" in text[:500].lower():
        raise ValueError("OCC response is HTML, not CSV")
    # Let pandas detect comma/tab/pipe if OCC changes delimiter.
    return pd.read_csv(io.StringIO(text), sep=None, engine="python")


def normalize_occ(frame: pd.DataFrame, symbol: str) -> tuple[pd.DataFrame | None, dict[str, object]]:
    original_columns = [str(c) for c in frame.columns]
    data = frame.copy()
    data.columns = [normalize_name(c) for c in data.columns]
    columns = list(data.columns)

    symbol_col = first_column(
        columns,
        (
            "underlying_symbol",
            "underlying",
            "product_symbol",
            "product",
            "class_symbol",
            "root_symbol",
            "symbol",
        ),
    )
    expiry_col = first_column(
        columns,
        (
            "expiration_date",
            "expiration",
            "expiry_date",
            "expiry",
            "contract_date",
            "series_contract_date",
            "series_date",
        ),
    )
    strike_col = first_column(columns, ("strike_price", "strike"))
    type_col = first_column(columns, ("option_type", "put_call", "call_put", "type", "cp"))
    oi_col = first_column(columns, ("open_interest", "openinterest", "oi"))

    call_oi_col = first_column(columns, ("call_open_interest", "call_oi", "call"))
    put_oi_col = first_column(columns, ("put_open_interest", "put_oi", "put"))

    metadata: dict[str, object] = {
        "original_columns": original_columns,
        "normalized_columns": columns,
        "resolved": {
            "symbol": symbol_col,
            "expiration": expiry_col,
            "strike": strike_col,
            "type": type_col,
            "open_interest": oi_col,
            "call_open_interest": call_oi_col,
            "put_open_interest": put_oi_col,
        },
    }

    if not symbol_col or not expiry_col or not strike_col:
        return None, metadata

    data = data[data[symbol_col].astype(str).str.upper().str.strip() == symbol.upper()].copy()
    if data.empty:
        metadata["symbol_rows"] = 0
        return None, metadata

    data["expiration"] = pd.to_datetime(data[expiry_col], errors="coerce").dt.normalize()
    data["strike"] = pd.to_numeric(data[strike_col], errors="coerce")

    if type_col and oi_col:
        option_type = data[type_col].astype(str).str.lower().str.strip()
        option_type = option_type.replace({"c": "call", "p": "put"})
        out = pd.DataFrame(
            {
                "expiration": data["expiration"],
                "strike": data["strike"],
                "type": option_type,
                "occ_open_interest": pd.to_numeric(data[oi_col], errors="coerce"),
            }
        )
    elif call_oi_col and put_oi_col:
        common = data[["expiration", "strike", call_oi_col, put_oi_col]].copy()
        calls = common[["expiration", "strike", call_oi_col]].rename(columns={call_oi_col: "occ_open_interest"})
        calls["type"] = "call"
        puts = common[["expiration", "strike", put_oi_col]].rename(columns={put_oi_col: "occ_open_interest"})
        puts["type"] = "put"
        out = pd.concat([calls, puts], ignore_index=True)
        out["occ_open_interest"] = pd.to_numeric(out["occ_open_interest"], errors="coerce")
    else:
        return None, metadata

    out = out.dropna(subset=["expiration", "strike", "occ_open_interest"])
    out = out[out["type"].isin({"call", "put"})]
    # Aggregate defensively if OCC emits multiple exchange/series rows for the same economic contract.
    out = out.groupby(["expiration", "strike", "type"], as_index=False)["occ_open_interest"].sum()
    metadata["symbol_rows"] = int(len(data))
    metadata["normalized_contract_rows"] = int(len(out))
    return out, metadata


def load_mirror(path: Path, mirror_date: str, symbol: str) -> pd.DataFrame:
    columns = ["date", "expiration", "strike", "type", "open_interest"]
    frame = pd.read_parquet(path, columns=columns)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["expiration"] = pd.to_datetime(frame["expiration"], errors="coerce").dt.normalize()
    target = pd.Timestamp(mirror_date).normalize()
    data = frame[frame["date"] == target].copy()
    data["strike"] = pd.to_numeric(data["strike"], errors="coerce")
    data["type"] = data["type"].astype(str).str.lower().str.strip().replace({"c": "call", "p": "put"})
    data["mirror_open_interest"] = pd.to_numeric(data["open_interest"], errors="coerce")
    data = data.dropna(subset=["expiration", "strike", "mirror_open_interest"])
    data = data[data["type"].isin({"call", "put"})]
    # The mirror should normally be unique; aggregation makes any duplicate issue visible but deterministic.
    return data.groupby(["expiration", "strike", "type"], as_index=False)["mirror_open_interest"].sum()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    mirror_path = Path(args.mirror_file) if args.mirror_file else DEFAULT_MIRROR_DIR / f"spy_options_{args.year}.parquet"
    report_name = f"occ_{args.occ_report_date}_vs_mirror_{args.mirror_date}_{args.symbol.upper()}.json"
    report_path = output_dir / report_name

    if not mirror_path.exists():
        report = {
            "status": "NOT_USABLE",
            "reason": "MIRROR_FILE_MISSING",
            "mirror_path": str(mirror_path),
        }
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2

    occ_dt = pd.Timestamp(args.occ_report_date)
    query = urllib.parse.urlencode(
        {
            "reportDate": occ_dt.strftime("%m/%d/%Y"),
            "action": "download",
            "format": "csv",
        }
    )
    url = f"{OCC_ENDPOINT}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "IteraDynamics-research-source-probe/1.0"})

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
            content_type = response.headers.get("Content-Type")
    except Exception as exc:
        report = {
            "status": "NOT_USABLE",
            "reason": "OCC_DOWNLOAD_FAILED",
            "url": url,
            "error": f"{type(exc).__name__}: {exc}",
        }
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 3

    raw_path = output_dir / f"occ_daily_oi_{args.occ_report_date}.csv"
    raw_path.write_bytes(payload)

    try:
        occ_raw = read_occ_csv(payload)
    except Exception as exc:
        report = {
            "status": "NOT_USABLE",
            "reason": "OCC_CSV_READ_FAILED",
            "url": url,
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
            "content_type": content_type,
            "error": f"{type(exc).__name__}: {exc}",
        }
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 4

    occ, schema_meta = normalize_occ(occ_raw, args.symbol)
    if occ is None or occ.empty:
        report = {
            "status": "NOT_USABLE",
            "reason": "OCC_SCHEMA_UNRESOLVED_OR_NO_SYMBOL_ROWS",
            "url": url,
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
            "content_type": content_type,
            "schema": schema_meta,
        }
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 5

    mirror = load_mirror(mirror_path, args.mirror_date, args.symbol)
    if mirror.empty:
        report = {
            "status": "NOT_USABLE",
            "reason": "NO_MIRROR_ROWS_FOR_DATE",
            "mirror_date": args.mirror_date,
            "mirror_path": str(mirror_path),
        }
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 6

    joined = occ.merge(mirror, on=["expiration", "strike", "type"], how="inner")
    if joined.empty:
        report = {
            "status": "NOT_USABLE",
            "reason": "NO_COMMON_CONTRACT_KEYS",
            "occ_contract_rows": int(len(occ)),
            "mirror_contract_rows": int(len(mirror)),
            "schema": schema_meta,
        }
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 7

    joined["difference"] = joined["mirror_open_interest"] - joined["occ_open_interest"]
    joined["abs_difference"] = joined["difference"].abs()
    exact = joined["difference"] == 0
    exact_rate = float(exact.mean())
    common_keys = int(len(joined))
    occ_key_coverage = common_keys / len(occ) if len(occ) else 0.0
    mirror_key_coverage = common_keys / len(mirror) if len(mirror) else 0.0

    # For a sandbox provenance spot-check, require broad key overlap and near-exact OI identity.
    reconciles = common_keys >= 100 and exact_rate >= 0.95 and occ_key_coverage >= 0.80
    report = {
        "status": "RECONCILES" if reconciles else "MISMATCH",
        "reason": "OCC_PRIOR_SETTLEMENT_OI_SPOT_CHECK",
        "symbol": args.symbol.upper(),
        "occ_report_date": args.occ_report_date,
        "mirror_observation_date": args.mirror_date,
        "timing_rule": "OCC report date T reflects open interest following the previous trading day's settlement; mirror date is supplied explicitly and must be that prior trading day.",
        "occ_source": {
            "url": url,
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
            "content_type": content_type,
            "schema": schema_meta,
        },
        "mirror_source": {
            "path": str(mirror_path),
            "contract_rows_for_date": int(len(mirror)),
        },
        "comparison": {
            "occ_contract_rows": int(len(occ)),
            "common_contract_keys": common_keys,
            "occ_key_coverage": occ_key_coverage,
            "mirror_key_coverage": mirror_key_coverage,
            "exact_open_interest_matches": int(exact.sum()),
            "exact_open_interest_match_rate": exact_rate,
            "median_absolute_difference": float(joined["abs_difference"].median()),
            "mean_absolute_difference": float(joined["abs_difference"].mean()),
            "max_absolute_difference": float(joined["abs_difference"].max()),
        },
        "boundary": "Source-governance check only; a RECONCILES result authorizes construction of the sandbox gamma-pressure screen, not any strategy/runtime/portfolio action.",
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if reconciles else 8


if __name__ == "__main__":
    raise SystemExit(main())
