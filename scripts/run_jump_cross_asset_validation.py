from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 2 locked-candidate Jump Risk validation across Core v1 assets. "
            "Runs the exact BTC-selected candidates at z=3.0 and abs=5% without retuning. "
            "Input data must be hourly."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--asset-data",
        action="append",
        required=True,
        metavar="ASSET=PATH",
        help=(
            "Asset and hourly OHLCV CSV mapping. Repeat for ETH, SPY, QQQ, and GLD. "
            "SOL is intentionally outside this Phase 2 Core-universe validation."
        ),
    )
    parser.add_argument("--out-dir", default="artifacts/jump_risk_engine_v0")
    parser.add_argument("--cache-dir", default="artifacts/research_engine_v1/cache")
    parser.add_argument("--run-name", default="cross-asset-validation-v0")
    parser.add_argument("--test-start-year", type=int, default=2020)
    parser.add_argument("--vol-window", type=int, default=96)
    parser.add_argument("--fast-window", type=int, default=24)
    parser.add_argument("--slow-window", type=int, default=240)
    parser.add_argument(
        "--allow-noncore-assets",
        action="store_true",
        help="Permit assets outside ETH, SPY, QQQ, and GLD for a separately scoped experiment.",
    )
    return parser.parse_args()


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in cleaned.split("-") if part) or "unnamed"


def _detect_timestamp_column(frame: pd.DataFrame) -> str:
    lower = {str(column).strip().lower(): str(column) for column in frame.columns}
    for candidate in ("timestamp", "datetime", "date", "time"):
        if candidate in lower:
            return lower[candidate]
    first = str(frame.columns[0])
    parsed = pd.to_datetime(frame[first], utc=True, errors="coerce")
    if parsed.notna().mean() > 0.8:
        return first
    raise ValueError("Unable to identify a timestamp column")


def _validate_hourly_file(asset: str, path: Path) -> dict[str, Any]:
    sample = pd.read_csv(path, nrows=5000)
    if sample.empty:
        raise ValueError(f"Data file is empty for {asset}: {path}")
    timestamp_column = _detect_timestamp_column(sample)
    timestamps = pd.to_datetime(sample[timestamp_column], utc=True, errors="coerce").dropna().sort_values()
    if len(timestamps) < 3:
        raise ValueError(f"Not enough valid timestamps to validate cadence for {asset}: {path}")

    deltas = timestamps.diff().dropna().dt.total_seconds()
    positive = deltas[deltas > 0]
    if positive.empty:
        raise ValueError(f"Unable to determine cadence for {asset}: {path}")

    median_seconds = float(positive.median())
    if not 3000 <= median_seconds <= 5400:
        raise ValueError(
            f"{asset} file is not hourly: median spacing is {median_seconds / 3600.0:.2f} hours ({path}). "
            "Daily SPY/QQQ/GLD files are not valid for the locked hourly transfer test."
        )

    return {
        "path": str(path),
        "timestamp_column": timestamp_column,
        "sample_rows": int(len(timestamps)),
        "median_spacing_seconds": median_seconds,
        "validated_as_hourly": True,
    }


def _parse_asset_data(values: list[str], allow_noncore: bool) -> tuple[dict[str, Path], dict[str, Any]]:
    allowed = {"ETH", "SPY", "QQQ", "GLD"}
    mappings: dict[str, Path] = {}
    validations: dict[str, Any] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"Expected ASSET=PATH, received: {raw!r}")
        asset_raw, path_raw = raw.split("=", 1)
        asset = asset_raw.strip().upper()
        path = Path(path_raw.strip())
        if not asset or not path_raw.strip():
            raise ValueError(f"Invalid ASSET=PATH mapping: {raw!r}")
        if not allow_noncore and asset not in allowed:
            raise ValueError(
                f"Asset {asset!r} is outside the locked Phase 2 scope {sorted(allowed)}. "
                "Use --allow-noncore-assets only for an explicitly separate experiment."
            )
        if asset in mappings:
            raise ValueError(f"Duplicate asset mapping: {asset}")
        if not path.exists():
            raise FileNotFoundError(f"Data file not found for {asset}: {path}")
        mappings[asset] = path
        validations[asset] = _validate_hourly_file(asset, path)
    return mappings, validations


def _atomic_json(path: Path, payload: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temp.replace(path)


def _latest_child_run(root: Path, asset: str) -> Path:
    candidates = sorted(
        [path for path in root.glob(f"*_{asset.lower()}_*") if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No candidate robustness child run found for {asset} under {root}")
    return candidates[0]


def _read_csv(run_dir: Path, filename: str) -> pd.DataFrame:
    path = run_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing expected child artifact: {path}")
    return pd.read_csv(path)


def _asset_summary(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    keep = [
        "asset",
        "candidate",
        "horizon_bars",
        "target",
        "model",
        "feature_set",
        "event_rate",
        "roc_auc",
        "average_precision",
        "brier",
        "top1_event_rate",
        "top1_lift",
        "top5_event_rate",
        "top5_lift",
        "top10_event_rate",
        "top10_lift",
        "avg_year_auc",
        "min_year_auc",
        "avg_year_ap",
        "min_year_ap",
        "elapsed_seconds",
        "source_run_dir",
    ]
    return summary[[column for column in keep if column in summary.columns]].copy()


def main() -> None:
    args = parse_args()
    mappings, cadence_validation = _parse_asset_data(args.asset_data, args.allow_noncore_assets)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.out_dir) / "cross_asset_validation" / f"{timestamp}_{_slug(args.run_name)}"
    children_root = run_dir / "runs"
    children_root.mkdir(parents=True, exist_ok=False)

    state_path = run_dir / "state.json"
    manifest_path = run_dir / "manifest.json"
    state: dict[str, Any] = {"completed": {}, "failed": {}}
    manifest: dict[str, Any] = {
        "experiment": "jump_risk_cross_asset_validation_v0",
        "artifact_dir": str(run_dir),
        "scope": {
            "included_assets": list(mappings),
            "excluded_asset": "SOL",
            "reason": "Phase 2 is restricted to the current Core v1 research universe.",
            "gld_included_when_hourly_data_is_available": True,
        },
        "locked_candidate_policy": {
            "source_asset": "BTC",
            "bar_interval": "1h",
            "jump_z": 3.0,
            "absolute_jump": 0.05,
            "retuning_allowed": False,
            "candidates": [
                "immediate_any_h2: GBM + baseline_energy",
                "immediate_down_h2: logistic + baseline_structure",
                "medium_up_h18: GBM + baseline_energy",
                "extended_up_h120: logistic + baseline_structure",
            ],
        },
        "asset_data": {asset: str(path) for asset, path in mappings.items()},
        "cadence_validation": cadence_validation,
        "config": {
            "test_start_year": args.test_start_year,
            "vol_window": args.vol_window,
            "fast_window": args.fast_window,
            "slow_window": args.slow_window,
        },
    }
    _atomic_json(manifest_path, manifest)
    _atomic_json(state_path, state)

    print("Jump Risk Phase 2 cross-asset validation")
    print(f"Assets: {list(mappings)}")
    print("Validated cadence: hourly")
    print("Locked thresholds: z=3.0, absolute jump=5%")
    print(f"Run dir: {run_dir}")
    print()

    child_dirs: dict[str, str] = {}
    for position, (asset, data_path) in enumerate(mappings.items(), start=1):
        print(f"[{position}/{len(mappings)}] {asset}: locked candidates", flush=True)
        child_out = children_root / asset.lower()
        child_out.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_jump_candidate_robustness.py"),
            "--asset",
            asset,
            "--data",
            str(data_path),
            "--out-dir",
            str(child_out),
            "--cache-dir",
            args.cache_dir,
            "--run-name",
            f"locked-transfer-{asset.lower()}-v0",
            "--jump-z-grid",
            "3.0",
            "--absolute-jump-grid",
            "0.05",
            "--test-start-year",
            str(args.test_start_year),
            "--vol-window",
            str(args.vol_window),
            "--fast-window",
            str(args.fast_window),
            "--slow-window",
            str(args.slow_window),
        ]
        try:
            subprocess.run(command, check=True)
            child_run = _latest_child_run(child_out / "candidate_robustness", asset)
            child_dirs[asset] = str(child_run)
            state["completed"][asset] = {
                "data": str(data_path),
                "run_dir": str(child_run),
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            state["failed"].pop(asset, None)
            _atomic_json(state_path, state)
            print(f"  captured: {child_run}", flush=True)
        except Exception as exc:
            state["failed"][asset] = {
                "data": str(data_path),
                "error": repr(exc),
                "failed_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            _atomic_json(state_path, state)
            raise
        print()

    summaries: list[pd.DataFrame] = []
    years: list[pd.DataFrame] = []
    calibration: list[pd.DataFrame] = []
    stability: list[pd.DataFrame] = []
    for asset, child_dir_raw in child_dirs.items():
        child_dir = Path(child_dir_raw)
        for filename, destination in (
            ("robustness_summary.csv", summaries),
            ("robustness_by_year.csv", years),
            ("robustness_calibration.csv", calibration),
            ("robustness_year_stability.csv", stability),
        ):
            frame = _read_csv(child_dir, filename)
            frame["asset"] = asset
            frame["source_run_dir"] = str(child_dir)
            destination.append(frame)

    summary_all = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    years_all = pd.concat(years, ignore_index=True) if years else pd.DataFrame()
    calibration_all = pd.concat(calibration, ignore_index=True) if calibration else pd.DataFrame()
    stability_all = pd.concat(stability, ignore_index=True) if stability else pd.DataFrame()

    summary_path = run_dir / "cross_asset_summary.csv"
    compact_path = run_dir / "cross_asset_candidate_scorecard.csv"
    years_path = run_dir / "cross_asset_by_year.csv"
    calibration_path = run_dir / "cross_asset_calibration.csv"
    stability_path = run_dir / "cross_asset_year_stability.csv"

    summary_all.to_csv(summary_path, index=False)
    _asset_summary(summary_all).to_csv(compact_path, index=False)
    years_all.to_csv(years_path, index=False)
    calibration_all.to_csv(calibration_path, index=False)
    stability_all.to_csv(stability_path, index=False)

    manifest["child_runs"] = child_dirs
    manifest["outputs"] = {
        "summary": str(summary_path),
        "scorecard": str(compact_path),
        "by_year": str(years_path),
        "calibration": str(calibration_path),
        "year_stability": str(stability_path),
    }
    _atomic_json(manifest_path, manifest)

    print("Jump Risk Phase 2 cross-asset validation complete")
    print(f"Out dir: {run_dir}")
    print()
    print("Candidate results by asset:")
    if not summary_all.empty:
        for _, row in summary_all.sort_values(["asset", "candidate"]).iterrows():
            print(
                f"- asset={row['asset']:<4} candidate={row['candidate']:<22} "
                f"auc={row['roc_auc']:.4f} ap={row['average_precision']:.4f} "
                f"top5_rate={row['top5_event_rate']:.2%} lift={row['top5_lift']:.2f}x"
            )
    print()
    print("Reference files:")
    print(f"- {compact_path}")
    print(f"- {years_path}")
    print(f"- {calibration_path}")
    print(f"- {stability_path}")
    print(f"- {manifest_path}")


if __name__ == "__main__":
    main()
