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
    p = argparse.ArgumentParser(
        description=(
            "Phase 2 locked-candidate Jump Risk validation across Core v1 assets. "
            "Runs the exact BTC-selected candidates at z=3.0 and abs=5% without retuning."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--asset-data",
        action="append",
        required=True,
        metavar="ASSET=PATH",
        help=(
            "Asset and OHLCV CSV mapping. Repeat for ETH, SPY, QQQ, and GLD. "
            "SOL is intentionally outside this Phase 2 Core-universe validation."
        ),
    )
    p.add_argument("--out-dir", default="artifacts/jump_risk_engine_v0")
    p.add_argument("--cache-dir", default="artifacts/research_engine_v1/cache")
    p.add_argument("--run-name", default="cross-asset-validation-v0")
    p.add_argument("--test-start-year", type=int, default=2020)
    p.add_argument("--vol-window", type=int, default=96)
    p.add_argument("--fast-window", type=int, default=24)
    p.add_argument("--slow-window", type=int, default=240)
    p.add_argument(
        "--allow-noncore-assets",
        action="store_true",
        help="Permit assets outside ETH, SPY, QQQ, and GLD. Off by default to preserve the locked Phase 2 scope.",
    )
    return p.parse_args()


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in cleaned.split("-") if part) or "unnamed"


def _parse_asset_data(values: list[str], allow_noncore: bool) -> dict[str, Path]:
    allowed = {"ETH", "SPY", "QQQ", "GLD"}
    mappings: dict[str, Path] = {}
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
    return mappings


def _atomic_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _latest_child_run(root: Path, asset: str) -> Path:
    candidates = sorted(
        [p for p in root.glob(f"*_{asset.lower()}_*") if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
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
    return summary[[col for col in keep if col in summary.columns]].copy()


def main() -> None:
    args = parse_args()
    mappings = _parse_asset_data(args.asset_data, args.allow_noncore_assets)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.out_dir) / "cross_asset_validation" / f"{timestamp}_{_slug(args.run_name)}"
    children_root = run_dir / "runs"
    children_root.mkdir(parents=True, exist_ok=False)

    state_path = run_dir / "state.json"
    manifest_path = run_dir / "manifest.json"
    state: dict[str, Any] = {"completed": {}, "failed": {}}

    manifest = {
        "experiment": "jump_risk_cross_asset_validation_v0",
        "artifact_dir": str(run_dir),
        "scope": {
            "included_assets": list(mappings),
            "excluded_asset": "SOL",
            "reason": "Phase 2 is restricted to the current Core v1 research universe.",
            "gld_included": True,
        },
        "locked_candidate_policy": {
            "source_asset": "BTC",
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
        summary = _read_csv(child_dir, "robustness_summary.csv")
        summary["asset"] = asset
        summary["source_run_dir"] = str(child_dir)
        summaries.append(summary)

        by_year = _read_csv(child_dir, "robustness_by_year.csv")
        by_year["asset"] = asset
        by_year["source_run_dir"] = str(child_dir)
        years.append(by_year)

        cal = _read_csv(child_dir, "robustness_calibration.csv")
        cal["asset"] = asset
        cal["source_run_dir"] = str(child_dir)
        calibration.append(cal)

        stable = _read_csv(child_dir, "robustness_year_stability.csv")
        stable["asset"] = asset
        stable["source_run_dir"] = str(child_dir)
        stability.append(stable)

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
        ordered = summary_all.sort_values(["asset", "candidate"])
        for _, row in ordered.iterrows():
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
