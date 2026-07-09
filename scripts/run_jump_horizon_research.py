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

from research.jump_risk_engine.artifacts import slugify


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run multiple Jump Risk ablation horizons into one timestamped research folder.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--asset", required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--out-dir", default="artifacts/jump_risk_engine_v0")
    p.add_argument("--run-name", default="horizon-sweep-v0")
    p.add_argument("--horizons", default="6,12,24,48,72", help="Comma-separated horizon bars")
    p.add_argument("--vol-window", type=int, default=96)
    p.add_argument("--fast-window", type=int, default=24)
    p.add_argument("--slow-window", type=int, default=240)
    p.add_argument("--jump-z", type=float, default=3.0)
    p.add_argument("--absolute-jump", type=float, default=0.05)
    p.add_argument("--test-start-year", type=int, default=2020)
    p.add_argument("--models", default="logistic,gbm")
    p.add_argument("--targets", default="any,down,up")
    p.add_argument("--write-predictions", action="store_true", help="Forward --write-predictions to each ablation run")
    p.add_argument("--write-dataset", action="store_true", help="Forward --write-dataset to each ablation run")
    return p.parse_args()


def _parse_horizons(value: str) -> list[int]:
    horizons: list[int] = []
    for piece in value.split(","):
        piece = piece.strip()
        if not piece:
            continue
        h = int(piece)
        if h <= 0:
            raise ValueError(f"Horizon must be positive: {h}")
        horizons.append(h)
    if not horizons:
        raise ValueError("At least one horizon is required")
    return horizons


def _run_cmd(cmd: list[str]) -> None:
    print("$ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def _find_latest_horizon_dir(root: Path, horizon: int) -> Path:
    candidates = sorted(
        [p for p in root.glob(f"*_h{horizon}_*") if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No artifact directory found for horizon {horizon} under {root}")
    return candidates[0]


def _load_summary(run_dir: Path) -> pd.DataFrame:
    matches = list(run_dir.glob("*_ablation_summary.csv"))
    if not matches:
        raise FileNotFoundError(f"Missing ablation summary under {run_dir}")
    df = pd.read_csv(matches[0])
    df["source_run_dir"] = str(run_dir)
    return df


def _load_deltas(run_dir: Path) -> pd.DataFrame:
    matches = list(run_dir.glob("*_ablation_deltas.csv"))
    if not matches:
        return pd.DataFrame()
    df = pd.read_csv(matches[0])
    df["source_run_dir"] = str(run_dir)
    return df


def _best_rows(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    ordered = summary.sort_values(["horizon_bars", "target", "model", "top5_lift"], ascending=[True, True, True, False])
    return ordered.groupby(["horizon_bars", "target", "model"], as_index=False).head(1).reset_index(drop=True)


def _global_best_rows(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    ordered = summary.sort_values(["target", "model", "top5_lift"], ascending=[True, True, False])
    return ordered.groupby(["target", "model"], as_index=False).head(1).reset_index(drop=True)


def main() -> None:
    args = parse_args()
    horizons = _parse_horizons(args.horizons)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    asset = slugify(args.asset)
    sweep_dir = Path(args.out_dir) / "horizon_sweep" / f"{timestamp}_{asset}_{slugify(args.run_name)}"
    sweep_dir.mkdir(parents=True, exist_ok=False)

    child_root = sweep_dir / "runs"
    child_root.mkdir(parents=True, exist_ok=True)

    print("Jump Risk horizon exploration")
    print(f"Horizons: {horizons}")
    print(f"Sweep dir: {sweep_dir}")
    print()

    horizon_dirs: dict[int, str] = {}
    for i, horizon in enumerate(horizons, start=1):
        print(f"=== Horizon {horizon} bars ({i}/{len(horizons)}) ===", flush=True)
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_jump_ablation_research.py"),
            "--asset",
            args.asset,
            "--data",
            args.data,
            "--out-dir",
            str(child_root),
            "--run-name",
            f"{args.run_name}-h{horizon}",
            "--horizon-bars",
            str(horizon),
            "--vol-window",
            str(args.vol_window),
            "--fast-window",
            str(args.fast_window),
            "--slow-window",
            str(args.slow_window),
            "--jump-z",
            str(args.jump_z),
            "--absolute-jump",
            str(args.absolute_jump),
            "--test-start-year",
            str(args.test_start_year),
            "--models",
            args.models,
            "--targets",
            args.targets,
        ]
        if args.write_predictions:
            cmd.append("--write-predictions")
        if args.write_dataset:
            cmd.append("--write-dataset")
        _run_cmd(cmd)
        ablation_root = child_root / "ablation"
        run_dir = _find_latest_horizon_dir(ablation_root, horizon)
        horizon_dirs[horizon] = str(run_dir)
        print(f"Captured horizon {horizon} artifacts: {run_dir}")
        print()

    summaries: list[pd.DataFrame] = []
    deltas: list[pd.DataFrame] = []
    for horizon, run_dir_str in horizon_dirs.items():
        run_dir = Path(run_dir_str)
        s = _load_summary(run_dir)
        s["horizon_bars"] = horizon
        summaries.append(s)
        d = _load_deltas(run_dir)
        if not d.empty:
            d["horizon_bars"] = horizon
            deltas.append(d)

    summary = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    delta_summary = pd.concat(deltas, ignore_index=True) if deltas else pd.DataFrame()
    best_by_horizon = _best_rows(summary)
    global_best = _global_best_rows(summary)

    summary_path = sweep_dir / "horizon_summary.csv"
    deltas_path = sweep_dir / "horizon_deltas.csv"
    best_path = sweep_dir / "horizon_best_by_target_model.csv"
    global_best_path = sweep_dir / "horizon_global_best_by_target_model.csv"

    summary.to_csv(summary_path, index=False)
    delta_summary.to_csv(deltas_path, index=False)
    best_by_horizon.to_csv(best_path, index=False)
    global_best.to_csv(global_best_path, index=False)

    manifest: dict[str, Any] = {
        "experiment": "horizon_sweep_v0",
        "artifact_dir": str(sweep_dir),
        "asset": args.asset.upper(),
        "data": args.data,
        "horizons": horizons,
        "models": args.models,
        "targets": args.targets,
        "jump_z": args.jump_z,
        "absolute_jump": args.absolute_jump,
        "child_runs": horizon_dirs,
        "outputs": {
            "horizon_summary": str(summary_path),
            "horizon_deltas": str(deltas_path),
            "best_by_target_model": str(best_path),
            "global_best_by_target_model": str(global_best_path),
        },
    }
    (sweep_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    print("Jump Risk horizon exploration complete")
    print(f"Out dir: {sweep_dir}")
    print()
    print("Global best top-5 lift by target/model:")
    if not global_best.empty:
        for _, row in global_best.sort_values(["target", "model"]).iterrows():
            print(
                f"- target={row['target']:<4} model={row['model']:<8} "
                f"h={int(row['horizon_bars']):<3} exp={row['experiment']:<18} "
                f"auc={row['roc_auc']:.4f} ap={row['average_precision']:.4f} "
                f"top5_rate={row['top5_event_rate']:.2%} lift={row['top5_lift']:.2f}x"
            )
    print()
    print("Sweep files written:")
    print(f"- {summary_path}")
    print(f"- {best_path}")
    print(f"- {global_best_path}")


if __name__ == "__main__":
    main()
