from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import research.jump_risk_engine.lab as lab
from research.jump_risk_engine.artifacts import make_run_dir
from research.jump_risk_engine.energy import add_market_energy_features
from research.jump_risk_engine.lab import JumpRiskConfig, read_ohlcv


BASELINE_FEATURES = [
    "ret_1",
    "abs_ret_1",
    "ret_3",
    "ret_12",
    "ret_fast",
    "ret_slow",
    "ret_accel_fast_vs_slow",
    "realized_vol",
    "fast_vol",
    "slow_vol",
    "vol_ratio_fast_slow",
    "vol_rank",
    "atr_proxy",
    "range_rank",
    "vol_of_vol",
    "skew",
    "kurt",
    "volume_z",
    "distance_sma_fast",
    "distance_sma_slow",
    "trend_fast_gt_slow",
    "hour_utc",
    "day_of_week",
]

STRUCTURE_FEATURES = [
    "vol_compression_score",
    "vol_slope_12",
    "vol_slope_24",
    "vol_accel_12_24",
    "bb_width_fast",
    "bb_width_slow",
    "bb_width_ratio",
    "bb_width_rank",
    "bb_compression_score",
    "range_ratio_fast_slow",
    "squeeze_flag",
    "squeeze_duration",
    "range_squeeze_flag",
    "range_squeeze_duration",
    "distance_high_fast",
    "distance_high_slow",
    "distance_low_fast",
    "distance_low_slow",
    "drawdown_fast",
    "drawdown_slow",
    "breakout_proximity_fast",
    "breakout_proximity_slow",
    "breakdown_proximity_fast",
    "breakdown_proximity_slow",
    "trend_strength_fast_slow",
    "range_position_fast",
    "range_position_slow",
]

ENERGY_FEATURES = [
    "deep_squeeze_flag",
    "deep_squeeze_duration",
    "compression_depth",
    "compression_area_fast",
    "compression_area_slow",
    "deep_compression_area_fast",
    "range_compression_area_fast",
    "expansion_pressure",
    "compression_release_pressure",
    "range_release_pressure",
    "directional_pressure",
    "upside_pressure",
    "downside_pressure",
    "vol_slope_6",
    "vol_accel_6_12",
    "vol_ignition",
    "breakout_tension_fast",
    "breakdown_tension_fast",
    "breakout_tension_slow",
    "breakdown_tension_slow",
    "quiet_absorption",
    "quiet_absorption_area",
]

EXPERIMENTS = {
    "baseline_only": BASELINE_FEATURES,
    "baseline_structure": BASELINE_FEATURES + STRUCTURE_FEATURES,
    "baseline_energy": BASELINE_FEATURES + ENERGY_FEATURES,
    "structure_energy": STRUCTURE_FEATURES + ENERGY_FEATURES,
    "all_features": BASELINE_FEATURES + STRUCTURE_FEATURES + ENERGY_FEATURES,
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Research-only Jump Risk feature-family ablation lab. Does not touch Core v1 runtime.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--asset", required=True, help="Asset label, e.g. BTC, ETH, SPY, QQQ, GLD")
    p.add_argument("--data", required=True, help="CSV containing timestamp/date + OHLCV columns")
    p.add_argument("--out-dir", default="artifacts/jump_risk_engine_v0")
    p.add_argument("--run-name", default="feature-ablation-v0")
    p.add_argument("--horizon-bars", type=int, default=24)
    p.add_argument("--vol-window", type=int, default=96)
    p.add_argument("--fast-window", type=int, default=24)
    p.add_argument("--slow-window", type=int, default=240)
    p.add_argument("--jump-z", type=float, default=3.0)
    p.add_argument("--absolute-jump", type=float, default=0.05)
    p.add_argument("--test-start-year", type=int, default=2020)
    p.add_argument("--models", default="logistic,gbm", help="Comma-separated: logistic,gbm,rf")
    p.add_argument("--targets", default="any,down,up", help="Comma-separated: any,down,up")
    p.add_argument("--write-predictions", action="store_true", help="Write full OOS prediction CSVs. Off by default because these files are large.")
    p.add_argument("--write-dataset", action="store_true", help="Write the full ablation dataset CSV. Off by default because it is large.")
    return p.parse_args()


def _fmt(x: object) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.4f}"
    return str(x)


def _top_lift(aggregate: dict[str, Any], quantile: float) -> tuple[float | None, float | None]:
    diag = aggregate.get("diagnostics") or {}
    for row in diag.get("lift_at_top_quantiles", []):
        if abs(float(row.get("top_quantile", -1.0)) - quantile) < 1e-9:
            return row.get("event_rate"), row.get("lift_vs_unconditional")
    return None, None


def _metric_row(experiment: str, run: dict[str, Any]) -> dict[str, Any]:
    agg = run["aggregate"]
    top1_rate, top1_lift = _top_lift(agg, 0.01)
    top5_rate, top5_lift = _top_lift(agg, 0.05)
    top10_rate, top10_lift = _top_lift(agg, 0.10)
    return {
        "experiment": experiment,
        "target": run["target"],
        "model": run["model"],
        "status": agg.get("status"),
        "rows": agg.get("rows"),
        "events": agg.get("events"),
        "event_rate": agg.get("event_rate"),
        "roc_auc": agg.get("roc_auc"),
        "average_precision": agg.get("average_precision"),
        "brier": agg.get("brier"),
        "top1_event_rate": top1_rate,
        "top1_lift": top1_lift,
        "top5_event_rate": top5_rate,
        "top5_lift": top5_lift,
        "top10_event_rate": top10_rate,
        "top10_lift": top10_lift,
    }


def _write_prediction_outputs(run_dir: Path, stem: str, experiment: str, run: dict[str, Any], write_predictions: bool) -> str | None:
    pred_frame = run.pop("_predictions", pd.DataFrame())
    if pred_frame.empty or not write_predictions:
        return None
    pred_dir = run_dir / experiment / "predictions"
    pred_dir.mkdir(parents=True, exist_ok=True)
    path = pred_dir / f"{stem}_{experiment}_{run['target']}_{run['model']}_oos_predictions.csv"
    pred_frame.reset_index().to_csv(path, index=False)
    run["aggregate"]["oos_predictions_csv"] = str(path)
    return str(path)


def _feature_importance_rows(experiment: str, run: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fold in run.get("folds", []):
        if fold.get("status") != "PASS":
            continue
        for rank, item in enumerate(fold.get("top_feature_importance", []), start=1):
            rows.append(
                {
                    "experiment": experiment,
                    "target": run["target"],
                    "model": run["model"],
                    "test_year": fold.get("test_year"),
                    "rank": rank,
                    "feature": item.get("feature"),
                    "importance": item.get("importance"),
                }
            )
    return rows


def _feature_stability_rows(feature_importance: pd.DataFrame) -> list[dict[str, Any]]:
    if feature_importance.empty:
        return []
    rows: list[dict[str, Any]] = []
    group_cols = ["experiment", "target", "model", "feature"]
    for keys, g in feature_importance.groupby(group_cols, dropna=False):
        exp, target, model, feature = keys
        rows.append(
            {
                "experiment": exp,
                "target": target,
                "model": model,
                "feature": feature,
                "appearances_top20": int(len(g)),
                "years_appeared": int(g["test_year"].nunique()),
                "avg_rank": float(g["rank"].mean()),
                "median_rank": float(g["rank"].median()),
                "avg_importance": float(g["importance"].mean()),
            }
        )
    rows.sort(key=lambda r: (r["experiment"], r["target"], r["model"], -r["years_appeared"], r["avg_rank"]))
    return rows


def _delta_rows(summary: pd.DataFrame, baseline_experiment: str = "baseline_only") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if summary.empty:
        return rows
    base = summary[summary["experiment"] == baseline_experiment]
    for _, row in summary.iterrows():
        match = base[(base["target"] == row["target"]) & (base["model"] == row["model"])]
        if match.empty:
            continue
        b = match.iloc[0]
        rows.append(
            {
                "experiment": row["experiment"],
                "target": row["target"],
                "model": row["model"],
                "delta_vs": baseline_experiment,
                "delta_auc": _diff(row.get("roc_auc"), b.get("roc_auc")),
                "delta_ap": _diff(row.get("average_precision"), b.get("average_precision")),
                "delta_top5_lift": _diff(row.get("top5_lift"), b.get("top5_lift")),
                "delta_top10_lift": _diff(row.get("top10_lift"), b.get("top10_lift")),
                "delta_top5_event_rate": _diff(row.get("top5_event_rate"), b.get("top5_event_rate")),
            }
        )
    return rows


def _diff(a: Any, b: Any) -> float | None:
    if pd.isna(a) or pd.isna(b):
        return None
    return float(a) - float(b)


def _run_with_features(
    frame: pd.DataFrame,
    cfg: JumpRiskConfig,
    features: list[str],
    targets: tuple[str, ...],
    models: tuple[str, ...],
    experiment: str,
    progress_state: dict[str, int],
) -> list[dict[str, Any]]:
    missing = [c for c in features if c not in frame.columns]
    if missing:
        raise ValueError(f"Missing ablation features: {missing}")
    original_features = list(lab.FEATURE_COLS)
    lab.FEATURE_COLS[:] = list(dict.fromkeys(features))
    try:
        runs: list[dict[str, Any]] = []
        for target in targets:
            for model in models:
                progress_state["current"] += 1
                print(
                    f"[{progress_state['current']}/{progress_state['total']}] "
                    f"experiment={experiment:<18} target={target:<4} model={model:<8} features={len(lab.FEATURE_COLS)}",
                    flush=True,
                )
                runs.append(lab.run_walk_forward(frame, cfg, target, model))
        return runs
    finally:
        lab.FEATURE_COLS[:] = original_features


def main() -> None:
    args = parse_args()
    cfg = JumpRiskConfig(
        asset=args.asset.upper(),
        horizon_bars=args.horizon_bars,
        vol_window=args.vol_window,
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        jump_z=args.jump_z,
        absolute_jump=args.absolute_jump,
        test_start_year=args.test_start_year,
    )
    models = tuple(x.strip() for x in args.models.split(",") if x.strip())
    targets = tuple(x.strip() for x in args.targets.split(",") if x.strip())
    run_dir = make_run_dir(args.out_dir, "ablation", cfg, args.run_name)
    stem = f"{cfg.asset.lower()}_h{cfg.horizon_bars}_z{cfg.jump_z:g}_abs{cfg.absolute_jump:g}".replace(".", "p")

    print("Preparing ablation dataset...", flush=True)
    ohlcv = read_ohlcv(args.data)
    base_frame = lab.build_feature_label_frame(ohlcv, cfg)
    log_ret = np.log(ohlcv["close"].astype(float)).diff()
    frame = add_market_energy_features(
        base_frame,
        close=ohlcv["close"].astype(float),
        high=ohlcv["high"].astype(float),
        low=ohlcv["low"].astype(float),
        ret=log_ret,
        realized_vol=base_frame["realized_vol"],
        fast_vol=base_frame["fast_vol"],
        slow_vol=base_frame["slow_vol"],
        vol_rank=base_frame["vol_rank"],
        range_rank=base_frame["range_rank"],
        fast_window=cfg.fast_window,
        slow_window=cfg.slow_window,
    ).replace([np.inf, -np.inf], np.nan).dropna()

    print(f"Rows: {len(frame)}", flush=True)
    print(f"Out dir: {run_dir}", flush=True)
    print(f"Full prediction CSVs: {'ON' if args.write_predictions else 'OFF'}", flush=True)
    print(f"Full dataset CSV: {'ON' if args.write_dataset else 'OFF'}", flush=True)
    print(flush=True)

    summary_rows: list[dict[str, Any]] = []
    feature_importance_rows: list[dict[str, Any]] = []
    reports: dict[str, Any] = {}
    progress_state = {"current": 0, "total": len(EXPERIMENTS) * len(targets) * len(models)}

    for experiment, features in EXPERIMENTS.items():
        exp_dir = run_dir / experiment
        exp_dir.mkdir(parents=True, exist_ok=True)
        runs = _run_with_features(frame, cfg, features, targets, models, experiment, progress_state)
        prediction_paths: list[str] = []
        for run in runs:
            prediction_path = _write_prediction_outputs(run_dir, stem, experiment, run, args.write_predictions)
            if prediction_path:
                prediction_paths.append(prediction_path)
            summary_rows.append(_metric_row(experiment, run))
            feature_importance_rows.extend(_feature_importance_rows(experiment, run))

        report = {
            "config": asdict(cfg),
            "experiment": experiment,
            "features": features,
            "feature_count": len(features),
            "prediction_csvs": prediction_paths,
            "runs": runs,
        }
        reports[experiment] = report
        (exp_dir / f"{stem}_{experiment}_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    summary = pd.DataFrame(summary_rows)
    feature_importance = pd.DataFrame(feature_importance_rows)
    stability = pd.DataFrame(_feature_stability_rows(feature_importance))
    deltas = pd.DataFrame(_delta_rows(summary))

    summary.to_csv(run_dir / f"{stem}_ablation_summary.csv", index=False)
    deltas.to_csv(run_dir / f"{stem}_ablation_deltas.csv", index=False)
    feature_importance.to_csv(run_dir / f"{stem}_feature_importance_by_fold.csv", index=False)
    stability.to_csv(run_dir / f"{stem}_feature_importance_stability.csv", index=False)
    dataset_path = None
    if args.write_dataset:
        dataset_path = run_dir / f"{stem}_ablation_dataset.csv"
        frame.reset_index().to_csv(dataset_path, index=False)

    manifest_outputs = {
        "summary": str(run_dir / f"{stem}_ablation_summary.csv"),
        "deltas": str(run_dir / f"{stem}_ablation_deltas.csv"),
        "feature_importance_by_fold": str(run_dir / f"{stem}_feature_importance_by_fold.csv"),
        "feature_importance_stability": str(run_dir / f"{stem}_feature_importance_stability.csv"),
    }
    if dataset_path:
        manifest_outputs["dataset"] = str(dataset_path)

    manifest = {
        "experiment": "feature_ablation_v0",
        "artifact_dir": str(run_dir),
        "config": asdict(cfg),
        "models": models,
        "targets": targets,
        "rows": int(len(frame)),
        "start": frame.index.min().isoformat(),
        "end": frame.index.max().isoformat(),
        "write_predictions": bool(args.write_predictions),
        "write_dataset": bool(args.write_dataset),
        "feature_families": {
            "baseline": BASELINE_FEATURES,
            "structure": STRUCTURE_FEATURES,
            "energy": ENERGY_FEATURES,
        },
        "experiments": {name: {"feature_count": len(features)} for name, features in EXPERIMENTS.items()},
        "outputs": manifest_outputs,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    print("Jump Risk feature ablation research complete")
    print(f"Asset: {cfg.asset}")
    print(f"Rows: {len(frame)}")
    print(f"Window: {frame.index.min().isoformat()} -> {frame.index.max().isoformat()}")
    print(f"Out dir: {run_dir}")
    print()
    print("Best top-5 lift by target/model:")
    if not summary.empty:
        ordered = summary.sort_values(["target", "model", "top5_lift"], ascending=[True, True, False])
        for (target, model), group in ordered.groupby(["target", "model"]):
            best = group.iloc[0]
            print(
                f"- target={target:<4} model={model:<8} best={best['experiment']:<18} "
                f"auc={_fmt(best['roc_auc'])} ap={_fmt(best['average_precision'])} "
                f"top5_rate={best['top5_event_rate']:.2%} lift={best['top5_lift']:.2f}x"
            )
    print()
    print("Ablation files written:")
    print(f"- {run_dir / f'{stem}_ablation_summary.csv'}")
    print(f"- {run_dir / f'{stem}_ablation_deltas.csv'}")
    print(f"- {run_dir / f'{stem}_feature_importance_stability.csv'}")
    if args.write_predictions:
        print("- prediction CSVs written under each experiment/predictions folder")
    else:
        print("- prediction CSVs skipped; rerun with --write-predictions if needed")


if __name__ == "__main__":
    main()
