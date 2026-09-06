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
from research.jump_risk_engine.energy import add_market_energy_features
from research.jump_risk_engine.lab import JumpRiskConfig, read_ohlcv
from research.research_engine.cache import CacheKey, ResearchCache, fingerprint_file
from scripts.run_jump_ablation_research import BASELINE_FEATURES, ENERGY_FEATURES, STRUCTURE_FEATURES


CANDIDATES = [
    {
        "name": "immediate_any_h2",
        "horizon_bars": 2,
        "target": "any",
        "model": "gbm",
        "feature_set": "baseline_energy",
    },
    {
        "name": "immediate_down_h2",
        "horizon_bars": 2,
        "target": "down",
        "model": "logistic",
        "feature_set": "baseline_structure",
    },
    {
        "name": "medium_up_h18",
        "horizon_bars": 18,
        "target": "up",
        "model": "gbm",
        "feature_set": "baseline_energy",
    },
    {
        "name": "extended_up_h120",
        "horizon_bars": 120,
        "target": "up",
        "model": "logistic",
        "feature_set": "baseline_structure",
    },
]

FEATURE_SETS = {
    "baseline_energy": list(dict.fromkeys(BASELINE_FEATURES + ENERGY_FEATURES)),
    "baseline_structure": list(dict.fromkeys(BASELINE_FEATURES + STRUCTURE_FEATURES)),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Robustness validation for locked Jump Risk candidate signals.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--asset", required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--out-dir", default="artifacts/jump_risk_engine_v0")
    p.add_argument("--cache-dir", default="artifacts/research_engine_v1/cache")
    p.add_argument("--run-name", default="candidate-robustness-v0")
    p.add_argument("--resume-dir")
    p.add_argument("--jump-z-grid", default="2.5,3.0,3.5")
    p.add_argument("--absolute-jump-grid", default="0.05")
    p.add_argument("--vol-window", type=int, default=96)
    p.add_argument("--fast-window", type=int, default=24)
    p.add_argument("--slow-window", type=int, default=240)
    p.add_argument("--test-start-year", type=int, default=2020)
    return p.parse_args()


def _float_grid(value: str) -> list[float]:
    result = [float(piece.strip()) for piece in value.split(",") if piece.strip()]
    if not result:
        raise ValueError("Grid cannot be empty")
    return result


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in cleaned.split("-") if part)


def _atomic_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


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


def _top_lift(aggregate: dict[str, Any], quantile: float) -> tuple[float | None, float | None, int | None]:
    diagnostics = aggregate.get("diagnostics") or {}
    for row in diagnostics.get("lift_at_top_quantiles", []):
        if abs(float(row.get("top_quantile", -1.0)) - quantile) < 1e-9:
            return row.get("event_rate"), row.get("lift_vs_unconditional"), row.get("n")
    return None, None, None


def _spec_id(candidate: dict[str, Any], jump_z: float, absolute_jump: float) -> str:
    return f"{candidate['name']}__z{jump_z:g}__abs{absolute_jump:g}".replace(".", "p")


def _run_candidate(frame: pd.DataFrame, cfg: JumpRiskConfig, candidate: dict[str, Any]) -> dict[str, Any]:
    features = FEATURE_SETS[candidate["feature_set"]]
    original = list(lab.FEATURE_COLS)
    lab.FEATURE_COLS[:] = features
    try:
        run = lab.run_walk_forward(frame, cfg, candidate["target"], candidate["model"])
    finally:
        lab.FEATURE_COLS[:] = original
    return run


def _summary_row(candidate: dict[str, Any], cfg: JumpRiskConfig, run: dict[str, Any], elapsed: float, cache_hit: bool) -> dict[str, Any]:
    aggregate = run["aggregate"]
    top1_rate, top1_lift, top1_n = _top_lift(aggregate, 0.01)
    top5_rate, top5_lift, top5_n = _top_lift(aggregate, 0.05)
    top10_rate, top10_lift, top10_n = _top_lift(aggregate, 0.10)
    return {
        "candidate": candidate["name"],
        "asset": cfg.asset,
        "horizon_bars": cfg.horizon_bars,
        "target": candidate["target"],
        "model": candidate["model"],
        "feature_set": candidate["feature_set"],
        "jump_z": cfg.jump_z,
        "absolute_jump": cfg.absolute_jump,
        "status": aggregate.get("status"),
        "rows": aggregate.get("rows"),
        "events": aggregate.get("events"),
        "event_rate": aggregate.get("event_rate"),
        "roc_auc": aggregate.get("roc_auc"),
        "average_precision": aggregate.get("average_precision"),
        "brier": aggregate.get("brier"),
        "top1_n": top1_n,
        "top1_event_rate": top1_rate,
        "top1_lift": top1_lift,
        "top5_n": top5_n,
        "top5_event_rate": top5_rate,
        "top5_lift": top5_lift,
        "top10_n": top10_n,
        "top10_event_rate": top10_rate,
        "top10_lift": top10_lift,
        "cache_hit": cache_hit,
        "elapsed_seconds": elapsed,
    }


def _year_rows(candidate: dict[str, Any], cfg: JumpRiskConfig, run: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fold in run.get("folds", []):
        rows.append(
            {
                "candidate": candidate["name"],
                "asset": cfg.asset,
                "horizon_bars": cfg.horizon_bars,
                "target": candidate["target"],
                "model": candidate["model"],
                "feature_set": candidate["feature_set"],
                "jump_z": cfg.jump_z,
                "absolute_jump": cfg.absolute_jump,
                **{k: v for k, v in fold.items() if k != "top_feature_importance"},
            }
        )
    return rows


def _calibration_rows(candidate: dict[str, Any], cfg: JumpRiskConfig, run: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket in (run.get("aggregate", {}).get("calibration") or []):
        rows.append(
            {
                "candidate": candidate["name"],
                "asset": cfg.asset,
                "horizon_bars": cfg.horizon_bars,
                "target": candidate["target"],
                "model": candidate["model"],
                "feature_set": candidate["feature_set"],
                "jump_z": cfg.jump_z,
                "absolute_jump": cfg.absolute_jump,
                **bucket,
            }
        )
    return rows


def _refresh(run_dir: Path, state: dict[str, Any]) -> None:
    completed = list(state.get("completed", {}).values())
    summary = pd.DataFrame([item["summary"] for item in completed]) if completed else pd.DataFrame()
    yearly = pd.DataFrame([row for item in completed for row in item["yearly"]]) if completed else pd.DataFrame()
    calibration = pd.DataFrame([row for item in completed for row in item["calibration"]]) if completed else pd.DataFrame()

    summary.to_csv(run_dir / "robustness_summary.csv", index=False)
    yearly.to_csv(run_dir / "robustness_by_year.csv", index=False)
    calibration.to_csv(run_dir / "robustness_calibration.csv", index=False)

    if not summary.empty:
        baseline = summary[(summary["jump_z"] == 3.0) & (summary["absolute_jump"] == 0.05)][
            ["candidate", "roc_auc", "average_precision", "top5_lift", "top5_event_rate"]
        ].rename(
            columns={
                "roc_auc": "baseline_auc",
                "average_precision": "baseline_ap",
                "top5_lift": "baseline_top5_lift",
                "top5_event_rate": "baseline_top5_event_rate",
            }
        )
        comparison = summary.merge(baseline, on="candidate", how="left")
        comparison["delta_auc_vs_locked"] = comparison["roc_auc"] - comparison["baseline_auc"]
        comparison["delta_ap_vs_locked"] = comparison["average_precision"] - comparison["baseline_ap"]
        comparison["delta_top5_lift_vs_locked"] = comparison["top5_lift"] - comparison["baseline_top5_lift"]
        comparison["delta_top5_event_rate_vs_locked"] = comparison["top5_event_rate"] - comparison["baseline_top5_event_rate"]
        comparison.to_csv(run_dir / "robustness_vs_locked_threshold.csv", index=False)

        passing_years = yearly[yearly.get("status") == "PASS"] if not yearly.empty else yearly
        if not passing_years.empty:
            stability = passing_years.groupby(
                ["candidate", "jump_z", "absolute_jump"], as_index=False
            ).agg(
                years_tested=("test_year", "nunique"),
                auc_mean=("roc_auc", "mean"),
                auc_min=("roc_auc", "min"),
                auc_max=("roc_auc", "max"),
                ap_mean=("average_precision", "mean"),
                ap_min=("average_precision", "min"),
                positive_auc_years=("roc_auc", lambda values: int((values > 0.5).sum())),
            )
            stability.to_csv(run_dir / "robustness_year_stability.csv", index=False)


def main() -> None:
    args = parse_args()
    z_grid = _float_grid(args.jump_z_grid)
    abs_grid = _float_grid(args.absolute_jump_grid)
    data_fingerprint = fingerprint_file(args.data)

    if args.resume_dir:
        run_dir = Path(args.resume_dir)
        if not run_dir.exists():
            raise FileNotFoundError(run_dir)
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = Path(args.out_dir) / "candidate_robustness" / f"{timestamp}_{_slug(args.asset)}_{_slug(args.run_name)}"
        run_dir.mkdir(parents=True, exist_ok=False)

    state_path = run_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"completed": {}, "failed": {}}
    cache = ResearchCache(args.cache_dir)
    ohlcv = read_ohlcv(args.data)

    specs = [
        (candidate, jump_z, absolute_jump)
        for candidate in CANDIDATES
        for jump_z in z_grid
        for absolute_jump in abs_grid
    ]
    pending = [item for item in specs if _spec_id(*item) not in state["completed"]]

    manifest = {
        "experiment": "jump_candidate_robustness_v0",
        "artifact_dir": str(run_dir),
        "asset": args.asset.upper(),
        "data": args.data,
        "data_fingerprint": data_fingerprint,
        "jump_z_grid": z_grid,
        "absolute_jump_grid": abs_grid,
        "candidates": CANDIDATES,
        "feature_sets": FEATURE_SETS,
        "resume_dir": str(run_dir),
    }
    _atomic_json(run_dir / "manifest.json", manifest)

    print("Jump Risk locked-candidate robustness validation", flush=True)
    print(f"Run dir: {run_dir}", flush=True)
    print(f"Configurations: {len(specs)} | completed: {len(specs) - len(pending)} | pending: {len(pending)}", flush=True)
    print(flush=True)

    for position, (candidate, jump_z, absolute_jump) in enumerate(pending, start=1):
        spec_id = _spec_id(candidate, jump_z, absolute_jump)
        cfg = JumpRiskConfig(
            asset=args.asset.upper(),
            horizon_bars=int(candidate["horizon_bars"]),
            vol_window=args.vol_window,
            fast_window=args.fast_window,
            slow_window=args.slow_window,
            jump_z=jump_z,
            absolute_jump=absolute_jump,
            test_start_year=args.test_start_year,
        )
        cache_key = CacheKey(
            namespace="jump-risk-enriched-frame",
            asset=args.asset.upper(),
            timeframe="1h",
            dataset_fingerprint=data_fingerprint,
            parameters=asdict(cfg),
            version="jump-risk-frame-v1",
        )

        print(
            f"[{position}/{len(pending)}] {candidate['name']} z={jump_z:g} abs={absolute_jump:g}",
            flush=True,
        )
        started = time.perf_counter()
        try:
            frame, cache_hit = cache.get_or_build_frame(
                cache_key,
                lambda cfg=cfg: _build_frame(ohlcv, cfg),
                metadata={"candidate": candidate["name"], "source": args.data},
            )
            run = _run_candidate(frame, cfg, candidate)
            run.pop("_predictions", None)
            elapsed = time.perf_counter() - started
            state["completed"][spec_id] = {
                "summary": _summary_row(candidate, cfg, run, elapsed, cache_hit),
                "yearly": _year_rows(candidate, cfg, run),
                "calibration": _calibration_rows(candidate, cfg, run),
            }
            state["failed"].pop(spec_id, None)
            _atomic_json(state_path, state)
            _refresh(run_dir, state)
            summary = state["completed"][spec_id]["summary"]
            print(
                f"  done in {elapsed / 60:.1f} min | cache={'hit' if cache_hit else 'miss'} | "
                f"auc={summary['roc_auc']:.4f} ap={summary['average_precision']:.4f} "
                f"top5_lift={summary['top5_lift']:.2f}x",
                flush=True,
            )
        except Exception as exc:
            state["failed"][spec_id] = {
                "candidate": candidate,
                "jump_z": jump_z,
                "absolute_jump": absolute_jump,
                "error": repr(exc),
                "failed_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            _atomic_json(state_path, state)
            _refresh(run_dir, state)
            raise

    _refresh(run_dir, state)
    print()
    print("Jump Risk candidate robustness validation complete")
    print(f"Out dir: {run_dir}")
    print("Reference files:")
    print(f"- {run_dir / 'robustness_summary.csv'}")
    print(f"- {run_dir / 'robustness_by_year.csv'}")
    print(f"- {run_dir / 'robustness_year_stability.csv'}")
    print(f"- {run_dir / 'robustness_calibration.csv'}")
    print(f"- {run_dir / 'robustness_vs_locked_threshold.csv'}")
    print(f"- {run_dir / 'manifest.json'}")
    print(f"- {state_path}")


if __name__ == "__main__":
    main()
