from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

import research.jump_risk_engine.lab as lab
from research.jump_risk_engine.artifacts import make_run_dir
from research.jump_risk_engine.energy import add_market_energy_features
from research.jump_risk_engine.lab import JumpRiskConfig, read_ohlcv
from scripts.run_jump_ablation_research import BASELINE_FEATURES, ENERGY_FEATURES, STRUCTURE_FEATURES


LANES: dict[str, list[dict[str, Any]]] = {
    "short_any": [
        {
            "target": "any",
            "model": "gbm",
            "feature_set": "baseline_energy",
            "horizons": [2, 4, 6, 8, 12],
        }
    ],
    "short_down": [
        {
            "target": "down",
            "model": "logistic",
            "feature_set": "baseline_structure",
            "horizons": [2, 4, 6, 8, 12],
        },
        {
            "target": "down",
            "model": "gbm",
            "feature_set": "baseline_structure",
            "horizons": [2, 4, 6, 8, 12],
        },
    ],
    "medium_up": [
        {
            "target": "up",
            "model": "gbm",
            "feature_set": "baseline_energy",
            "horizons": [12, 18, 24, 36, 48],
        }
    ],
    "extended_up": [
        {
            "target": "up",
            "model": "logistic",
            "feature_set": "baseline_structure",
            "horizons": [48, 72, 96, 120],
        }
    ],
}

FEATURE_SETS = {
    "baseline_energy": list(dict.fromkeys(BASELINE_FEATURES + ENERGY_FEATURES)),
    "baseline_structure": list(dict.fromkeys(BASELINE_FEATURES + STRUCTURE_FEATURES)),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Resumable targeted Jump Risk horizon refinement. Runs only previously winning configurations.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--asset", required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--out-dir", default="artifacts/jump_risk_engine_v0")
    p.add_argument("--run-name", default="targeted-horizon-refinement-v0")
    p.add_argument("--resume-dir", help="Resume an existing targeted refinement artifact directory")
    p.add_argument(
        "--lanes",
        default="short_any,short_down,medium_up,extended_up",
        help="Comma-separated subset: short_any,short_down,medium_up,extended_up",
    )
    p.add_argument("--vol-window", type=int, default=96)
    p.add_argument("--fast-window", type=int, default=24)
    p.add_argument("--slow-window", type=int, default=240)
    p.add_argument("--jump-z", type=float, default=3.0)
    p.add_argument("--absolute-jump", type=float, default=0.05)
    p.add_argument("--test-start-year", type=int, default=2020)
    return p.parse_args()


def _selected_specs(lane_names: list[str]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for lane in lane_names:
        if lane not in LANES:
            raise ValueError(f"Unknown lane {lane!r}; expected one of {sorted(LANES)}")
        for template in LANES[lane]:
            for horizon in template["horizons"]:
                specs.append(
                    {
                        "lane": lane,
                        "target": template["target"],
                        "model": template["model"],
                        "feature_set": template["feature_set"],
                        "horizon_bars": int(horizon),
                    }
                )
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for spec in specs:
        key = _spec_id(spec)
        if key not in seen:
            seen.add(key)
            unique.append(spec)
    return unique


def _spec_id(spec: dict[str, Any]) -> str:
    return (
        f"{spec['lane']}__h{spec['horizon_bars']}__{spec['target']}__"
        f"{spec['model']}__{spec['feature_set']}"
    )


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"completed": {}, "failed": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _top_lift(aggregate: dict[str, Any], quantile: float) -> tuple[float | None, float | None]:
    diagnostics = aggregate.get("diagnostics") or {}
    for row in diagnostics.get("lift_at_top_quantiles", []):
        if abs(float(row.get("top_quantile", -1.0)) - quantile) < 1e-9:
            return row.get("event_rate"), row.get("lift_vs_unconditional")
    return None, None


def _summary_row(spec: dict[str, Any], run: dict[str, Any], elapsed_seconds: float, rows: int) -> dict[str, Any]:
    aggregate = run["aggregate"]
    top1_rate, top1_lift = _top_lift(aggregate, 0.01)
    top5_rate, top5_lift = _top_lift(aggregate, 0.05)
    top10_rate, top10_lift = _top_lift(aggregate, 0.10)
    return {
        **spec,
        "status": aggregate.get("status"),
        "rows": rows,
        "events": aggregate.get("events"),
        "event_rate": aggregate.get("event_rate"),
        "roc_auc": aggregate.get("roc_auc"),
        "average_precision": aggregate.get("average_precision"),
        "brier": aggregate.get("brier"),
        "top1_event_rate": top1_rate,
        "top1_lift": top1_lift,
        "top5_event_rate": top5_rate,
        "top5_lift": top5_lift,
        "top10_event_rate": top10_rate,
        "top10_lift": top10_lift,
        "elapsed_seconds": elapsed_seconds,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def _build_frame(ohlcv: pd.DataFrame, cfg: JumpRiskConfig) -> pd.DataFrame:
    base = lab.build_feature_label_frame(ohlcv, cfg)
    log_ret = np.log(ohlcv["close"].astype(float)).diff()
    return add_market_energy_features(
        base,
        close=ohlcv["close"].astype(float),
        high=ohlcv["high"].astype(float),
        low=ohlcv["low"].astype(float),
        ret=log_ret,
        realized_vol=base["realized_vol"],
        fast_vol=base["fast_vol"],
        slow_vol=base["slow_vol"],
        vol_rank=base["vol_rank"],
        range_rank=base["range_rank"],
        fast_window=cfg.fast_window,
        slow_window=cfg.slow_window,
    ).replace([np.inf, -np.inf], np.nan).dropna()


def _run_one(frame: pd.DataFrame, cfg: JumpRiskConfig, spec: dict[str, Any]) -> dict[str, Any]:
    features = FEATURE_SETS[spec["feature_set"]]
    missing = [name for name in features if name not in frame.columns]
    if missing:
        raise ValueError(f"Missing targeted refinement features: {missing}")

    original = list(lab.FEATURE_COLS)
    lab.FEATURE_COLS[:] = features
    try:
        run = lab.run_walk_forward(frame, cfg, spec["target"], spec["model"])
    finally:
        lab.FEATURE_COLS[:] = original

    # Full OOS predictions are intentionally discarded in this refinement pass.
    run.pop("_predictions", None)
    return run


def _refresh_outputs(run_dir: Path, state: dict[str, Any]) -> None:
    rows = list(state.get("completed", {}).values())
    summary = pd.DataFrame(rows)
    summary_path = run_dir / "targeted_horizon_summary.csv"
    best_lane_path = run_dir / "targeted_horizon_best_by_lane.csv"
    best_target_path = run_dir / "targeted_horizon_best_by_target_model.csv"
    timing_path = run_dir / "targeted_horizon_timing.csv"

    summary.to_csv(summary_path, index=False)
    if summary.empty:
        pd.DataFrame().to_csv(best_lane_path, index=False)
        pd.DataFrame().to_csv(best_target_path, index=False)
        pd.DataFrame().to_csv(timing_path, index=False)
        return

    ranked = summary.sort_values("top5_lift", ascending=False, na_position="last")
    ranked.groupby("lane", as_index=False).head(1).to_csv(best_lane_path, index=False)
    ranked.groupby(["target", "model"], as_index=False).head(1).to_csv(best_target_path, index=False)
    summary[
        [
            "lane",
            "horizon_bars",
            "target",
            "model",
            "feature_set",
            "elapsed_seconds",
            "completed_at_utc",
        ]
    ].sort_values("completed_at_utc").to_csv(timing_path, index=False)


def main() -> None:
    args = parse_args()
    lane_names = [value.strip() for value in args.lanes.split(",") if value.strip()]
    specs = _selected_specs(lane_names)

    if args.resume_dir:
        run_dir = Path(args.resume_dir)
        if not run_dir.exists():
            raise FileNotFoundError(f"Resume directory does not exist: {run_dir}")
    else:
        seed_cfg = JumpRiskConfig(asset=args.asset.upper())
        run_dir = make_run_dir(args.out_dir, "targeted_horizon", seed_cfg, args.run_name)

    state_path = run_dir / "state.json"
    manifest_path = run_dir / "manifest.json"
    results_dir = run_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    state = _load_state(state_path)
    completed = state.setdefault("completed", {})
    failed = state.setdefault("failed", {})

    manifest = {
        "experiment": "targeted_horizon_refinement_v0",
        "artifact_dir": str(run_dir),
        "asset": args.asset.upper(),
        "data": args.data,
        "lanes": lane_names,
        "specifications": specs,
        "feature_sets": FEATURE_SETS,
        "config": {
            "vol_window": args.vol_window,
            "fast_window": args.fast_window,
            "slow_window": args.slow_window,
            "jump_z": args.jump_z,
            "absolute_jump": args.absolute_jump,
            "test_start_year": args.test_start_year,
        },
        "resume_command": (
            f"python .\\scripts\\run_jump_targeted_horizon_research.py --asset {args.asset} "
            f"--data {args.data} --resume-dir {run_dir} --lanes {args.lanes}"
        ),
    }
    _write_json(manifest_path, manifest)

    pending = [spec for spec in specs if _spec_id(spec) not in completed]
    print("Targeted Jump Risk horizon refinement", flush=True)
    print(f"Run dir: {run_dir}", flush=True)
    print(f"Selected configurations: {len(specs)}", flush=True)
    print(f"Already completed: {len(specs) - len(pending)}", flush=True)
    print(f"Pending: {len(pending)}", flush=True)
    print(flush=True)

    if not pending:
        _refresh_outputs(run_dir, state)
        print("Nothing to run; the selected refinement set is already complete.")
        return

    ohlcv = read_ohlcv(args.data)
    frames: dict[int, tuple[JumpRiskConfig, pd.DataFrame]] = {}
    run_started = time.perf_counter()

    for position, spec in enumerate(pending, start=1):
        spec_id = _spec_id(spec)
        horizon = int(spec["horizon_bars"])
        print(
            f"[{position}/{len(pending)}] lane={spec['lane']:<11} h={horizon:<3} "
            f"target={spec['target']:<4} model={spec['model']:<8} features={spec['feature_set']}",
            flush=True,
        )

        if horizon not in frames:
            print(f"  Building shared feature/label frame for h={horizon}...", flush=True)
            cfg = JumpRiskConfig(
                asset=args.asset.upper(),
                horizon_bars=horizon,
                vol_window=args.vol_window,
                fast_window=args.fast_window,
                slow_window=args.slow_window,
                jump_z=args.jump_z,
                absolute_jump=args.absolute_jump,
                test_start_year=args.test_start_year,
            )
            frames[horizon] = (cfg, _build_frame(ohlcv, cfg))

        cfg, frame = frames[horizon]
        started = time.perf_counter()
        try:
            run = _run_one(frame, cfg, spec)
            elapsed = time.perf_counter() - started
            result_payload = {
                "spec": spec,
                "config": asdict(cfg),
                "elapsed_seconds": elapsed,
                "run": run,
            }
            _write_json(results_dir / f"{spec_id}.json", result_payload)
            completed[spec_id] = _summary_row(spec, run, elapsed, len(frame))
            failed.pop(spec_id, None)
            _write_json(state_path, state)
            _refresh_outputs(run_dir, state)
            agg = run["aggregate"]
            _, top5_lift = _top_lift(agg, 0.05)
            print(
                f"  Complete in {elapsed / 60.0:.1f} min | auc={agg.get('roc_auc')} "
                f"ap={agg.get('average_precision')} top5_lift={top5_lift}",
                flush=True,
            )
        except Exception as exc:
            elapsed = time.perf_counter() - started
            failed[spec_id] = {
                "spec": spec,
                "error": repr(exc),
                "elapsed_seconds": elapsed,
                "failed_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            _write_json(state_path, state)
            _refresh_outputs(run_dir, state)
            print(f"  FAILED after {elapsed / 60.0:.1f} min: {exc!r}", flush=True)
            raise

    total_elapsed = time.perf_counter() - run_started
    _refresh_outputs(run_dir, state)
    summary = pd.DataFrame(list(completed.values()))

    print()
    print("Targeted Jump Risk horizon refinement complete")
    print(f"Completed configurations: {len(completed)}")
    print(f"Elapsed this invocation: {total_elapsed / 60.0:.1f} minutes")
    print(f"Out dir: {run_dir}")
    print()
    print("Best top-5 lift by lane:")
    if not summary.empty:
        best = summary.sort_values("top5_lift", ascending=False, na_position="last").groupby("lane", as_index=False).head(1)
        for _, row in best.sort_values("lane").iterrows():
            print(
                f"- lane={row['lane']:<11} h={int(row['horizon_bars']):<3} "
                f"target={row['target']:<4} model={row['model']:<8} "
                f"features={row['feature_set']:<18} auc={row['roc_auc']:.4f} "
                f"ap={row['average_precision']:.4f} top5_rate={row['top5_event_rate']:.2%} "
                f"lift={row['top5_lift']:.2f}x"
            )
    print()
    print("Reference files:")
    print(f"- {run_dir / 'targeted_horizon_summary.csv'}")
    print(f"- {run_dir / 'targeted_horizon_best_by_lane.csv'}")
    print(f"- {run_dir / 'targeted_horizon_timing.csv'}")
    print(f"- {manifest_path}")
    print(f"- {state_path}")


if __name__ == "__main__":
    main()
