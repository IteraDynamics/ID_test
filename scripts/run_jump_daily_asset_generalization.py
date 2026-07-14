from __future__ import annotations

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
sys.path.insert(0, str(REPO_ROOT))

import research.jump_risk_engine.lab as lab
from research.jump_risk_engine.energy import add_market_energy_features
from research.jump_risk_engine.lab import JumpRiskConfig, read_ohlcv
from research.research_engine.cache import CacheKey, ResearchCache, fingerprint_file
from scripts.run_jump_ablation_research import BASELINE_FEATURES, ENERGY_FEATURES, STRUCTURE_FEATURES


# Daily-native study. These are not the BTC hourly candidates relabeled as days.
# The architecture roles are preserved, while horizons are chosen for daily bars.
STUDY_SPECS = [
    {
        "lane": "immediate_any",
        "target": "any",
        "model": "gbm",
        "feature_set": "baseline_energy",
        "horizons": [2, 5],
    },
    {
        "lane": "immediate_down",
        "target": "down",
        "model": "logistic",
        "feature_set": "baseline_structure",
        "horizons": [2, 5],
    },
    {
        "lane": "medium_up",
        "target": "up",
        "model": "gbm",
        "feature_set": "baseline_energy",
        "horizons": [5, 10, 20],
    },
    {
        "lane": "extended_up",
        "target": "up",
        "model": "logistic",
        "feature_set": "baseline_structure",
        "horizons": [20, 40, 60],
    },
]

FEATURE_SETS = {
    "baseline_energy": list(dict.fromkeys(BASELINE_FEATURES + ENERGY_FEATURES)),
    "baseline_structure": list(dict.fromkeys(BASELINE_FEATURES + STRUCTURE_FEATURES)),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Daily-native Jump Risk asset generalization study for SPY, QQQ, and GLD. "
            "This is explicitly separate from the locked hourly BTC-to-ETH transfer test."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--asset-data",
        action="append",
        required=True,
        metavar="ASSET=PATH",
        help="Repeat for SPY, QQQ, and GLD, e.g. --asset-data SPY=.\\data\\SPY_1D.csv",
    )
    p.add_argument("--out-dir", default="artifacts/jump_risk_engine_v0")
    p.add_argument("--cache-dir", default="artifacts/research_engine_v1/cache")
    p.add_argument("--run-name", default="daily-asset-generalization-v0")
    p.add_argument("--resume-dir")
    p.add_argument("--jump-z-grid", default="2.5,3.0,3.5")
    p.add_argument(
        "--absolute-jump-grid",
        default="0.03,0.05",
        help="Daily absolute floors. Both are tested to avoid making conclusions depend on one arbitrary floor.",
    )
    p.add_argument("--vol-window", type=int, default=20)
    p.add_argument("--fast-window", type=int, default=10)
    p.add_argument("--slow-window", type=int, default=60)
    p.add_argument("--test-start-year", type=int, default=2020)
    return p.parse_args()


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in cleaned.split("-") if part) or "unnamed"


def _parse_float_grid(value: str) -> list[float]:
    values = [float(piece.strip()) for piece in value.split(",") if piece.strip()]
    if not values:
        raise ValueError("Grid cannot be empty")
    return values


def _parse_asset_data(values: list[str]) -> dict[str, Path]:
    allowed = {"SPY", "QQQ", "GLD"}
    result: dict[str, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"Expected ASSET=PATH, received {raw!r}")
        asset_raw, path_raw = raw.split("=", 1)
        asset = asset_raw.strip().upper()
        path = Path(path_raw.strip())
        if asset not in allowed:
            raise ValueError(f"Daily study scope is {sorted(allowed)}; received {asset!r}")
        if asset in result:
            raise ValueError(f"Duplicate asset mapping: {asset}")
        if not path.exists():
            raise FileNotFoundError(f"Data file not found for {asset}: {path}")
        result[asset] = path
    return result


def _validate_daily_cadence(path: Path) -> dict[str, Any]:
    frame = read_ohlcv(path)
    if len(frame) < 3:
        raise ValueError(f"Not enough rows to validate cadence: {path}")
    gaps = frame.index.to_series().sort_values().diff().dropna().dt.total_seconds() / 86400.0
    median_days = float(gaps.median())
    if median_days < 0.75 or median_days > 4.0:
        raise ValueError(
            f"Expected daily bars for {path}, but median timestamp gap is {median_days:.3f} days"
        )
    return {
        "rows": int(len(frame)),
        "start": frame.index.min().isoformat(),
        "end": frame.index.max().isoformat(),
        "median_gap_days": median_days,
    }


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


def _run_one(frame: pd.DataFrame, cfg: JumpRiskConfig, target: str, model: str, feature_set: str) -> dict[str, Any]:
    original = list(lab.FEATURE_COLS)
    lab.FEATURE_COLS[:] = FEATURE_SETS[feature_set]
    try:
        run = lab.run_walk_forward(frame, cfg, target, model)
    finally:
        lab.FEATURE_COLS[:] = original
    run.pop("_predictions", None)
    return run


def _spec_id(spec: dict[str, Any]) -> str:
    return (
        f"{spec['asset']}__{spec['lane']}__h{spec['horizon_bars']}__{spec['target']}__"
        f"{spec['model']}__{spec['feature_set']}__z{spec['jump_z']:g}__abs{spec['absolute_jump']:g}"
    ).replace(".", "p")


def _summary_row(spec: dict[str, Any], run: dict[str, Any], elapsed_seconds: float, rows: int, cache_hit: bool) -> dict[str, Any]:
    aggregate = run["aggregate"]
    top1_rate, top1_lift, top1_n = _top_lift(aggregate, 0.01)
    top5_rate, top5_lift, top5_n = _top_lift(aggregate, 0.05)
    top10_rate, top10_lift, top10_n = _top_lift(aggregate, 0.10)
    passed_folds = [fold for fold in run.get("folds", []) if fold.get("status") == "PASS"]
    yearly_auc = [float(fold["roc_auc"]) for fold in passed_folds if fold.get("roc_auc") is not None]
    yearly_ap = [float(fold["average_precision"]) for fold in passed_folds if fold.get("average_precision") is not None]
    return {
        **spec,
        "status": aggregate.get("status"),
        "rows": rows,
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
        "passed_years": len(passed_folds),
        "avg_year_auc": float(np.mean(yearly_auc)) if yearly_auc else None,
        "min_year_auc": float(np.min(yearly_auc)) if yearly_auc else None,
        "avg_year_ap": float(np.mean(yearly_ap)) if yearly_ap else None,
        "min_year_ap": float(np.min(yearly_ap)) if yearly_ap else None,
        "cache_hit": cache_hit,
        "elapsed_seconds": elapsed_seconds,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def _refresh_outputs(run_dir: Path, state: dict[str, Any]) -> None:
    rows = list(state.get("completed", {}).values())
    summary = pd.DataFrame(rows)
    summary_path = run_dir / "daily_generalization_summary.csv"
    best_lane_path = run_dir / "daily_generalization_best_by_asset_lane.csv"
    best_asset_path = run_dir / "daily_generalization_best_by_asset_target_model.csv"
    timing_path = run_dir / "daily_generalization_timing.csv"

    summary.to_csv(summary_path, index=False)
    if summary.empty:
        pd.DataFrame().to_csv(best_lane_path, index=False)
        pd.DataFrame().to_csv(best_asset_path, index=False)
        pd.DataFrame().to_csv(timing_path, index=False)
        return

    ranked = summary.sort_values(
        ["status", "top5_lift", "roc_auc"],
        ascending=[True, False, False],
        na_position="last",
    )
    ranked.groupby(["asset", "lane"], as_index=False).head(1).to_csv(best_lane_path, index=False)
    ranked.groupby(["asset", "target", "model"], as_index=False).head(1).to_csv(best_asset_path, index=False)
    summary[
        [
            "asset",
            "lane",
            "horizon_bars",
            "target",
            "model",
            "feature_set",
            "jump_z",
            "absolute_jump",
            "cache_hit",
            "elapsed_seconds",
            "completed_at_utc",
        ]
    ].sort_values("completed_at_utc").to_csv(timing_path, index=False)


def main() -> None:
    args = parse_args()
    asset_data = _parse_asset_data(args.asset_data)
    jump_z_grid = _parse_float_grid(args.jump_z_grid)
    absolute_grid = _parse_float_grid(args.absolute_jump_grid)

    cadence = {asset: _validate_daily_cadence(path) for asset, path in asset_data.items()}

    if args.resume_dir:
        run_dir = Path(args.resume_dir)
        if not run_dir.exists():
            raise FileNotFoundError(f"Resume directory does not exist: {run_dir}")
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = Path(args.out_dir) / "daily_asset_generalization" / f"{timestamp}_{_slug(args.run_name)}"
        run_dir.mkdir(parents=True, exist_ok=False)

    state_path = run_dir / "state.json"
    manifest_path = run_dir / "manifest.json"
    results_dir = run_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"completed": {}, "failed": {}}
    completed = state.setdefault("completed", {})
    failed = state.setdefault("failed", {})

    specs: list[dict[str, Any]] = []
    for asset in asset_data:
        for template in STUDY_SPECS:
            for horizon in template["horizons"]:
                for jump_z in jump_z_grid:
                    for absolute_jump in absolute_grid:
                        specs.append(
                            {
                                "asset": asset,
                                "lane": template["lane"],
                                "horizon_bars": int(horizon),
                                "target": template["target"],
                                "model": template["model"],
                                "feature_set": template["feature_set"],
                                "jump_z": float(jump_z),
                                "absolute_jump": float(absolute_jump),
                            }
                        )

    manifest = {
        "experiment": "jump_risk_daily_asset_generalization_v0",
        "artifact_dir": str(run_dir),
        "assets": {asset: str(path) for asset, path in asset_data.items()},
        "cadence_validation": cadence,
        "study_scope": {
            "bar_cadence": "daily",
            "assets": list(asset_data),
            "hourly_transfer_comparison": False,
            "description": "Daily-native discovery study, separate from locked BTC-to-ETH hourly transfer.",
        },
        "study_specs": STUDY_SPECS,
        "jump_z_grid": jump_z_grid,
        "absolute_jump_grid": absolute_grid,
        "config": {
            "vol_window": args.vol_window,
            "fast_window": args.fast_window,
            "slow_window": args.slow_window,
            "test_start_year": args.test_start_year,
        },
        "resume_command": (
            f"python .\\scripts\\run_jump_daily_asset_generalization.py "
            + " ".join(f'--asset-data \"{asset}={path}\"' for asset, path in asset_data.items())
            + f" --resume-dir {run_dir}"
        ),
    }
    _atomic_json(manifest_path, manifest)
    _atomic_json(state_path, state)

    pending = [spec for spec in specs if _spec_id(spec) not in completed]
    print("Jump Risk daily asset generalization study")
    print(f"Assets: {list(asset_data)}")
    print(f"Configurations: {len(specs)} | completed: {len(specs) - len(pending)} | pending: {len(pending)}")
    print(f"Run dir: {run_dir}")
    print()

    cache = ResearchCache(args.cache_dir)
    source_fingerprints = {asset: fingerprint_file(path) for asset, path in asset_data.items()}
    ohlcv_by_asset = {asset: read_ohlcv(path) for asset, path in asset_data.items()}

    for position, spec in enumerate(pending, start=1):
        spec_id = _spec_id(spec)
        asset = spec["asset"]
        cfg = JumpRiskConfig(
            asset=asset,
            horizon_bars=spec["horizon_bars"],
            vol_window=args.vol_window,
            fast_window=args.fast_window,
            slow_window=args.slow_window,
            jump_z=spec["jump_z"],
            absolute_jump=spec["absolute_jump"],
            test_start_year=args.test_start_year,
        )
        cache_key = CacheKey(
            namespace="jump-risk-daily-generalization-frame",
            asset=asset,
            timeframe="1d",
            dataset_fingerprint=source_fingerprints[asset],
            parameters={
                "horizon_bars": cfg.horizon_bars,
                "vol_window": cfg.vol_window,
                "fast_window": cfg.fast_window,
                "slow_window": cfg.slow_window,
                "jump_z": cfg.jump_z,
                "absolute_jump": cfg.absolute_jump,
            },
            version="v1",
        )

        print(
            f"[{position}/{len(pending)}] asset={asset:<3} lane={spec['lane']:<14} h={spec['horizon_bars']:<3} "
            f"z={spec['jump_z']:g} abs={spec['absolute_jump']:g}",
            flush=True,
        )
        started = time.perf_counter()
        try:
            frame, cache_hit = cache.get_or_build_frame(
                cache_key,
                lambda cfg=cfg, asset=asset: _build_frame(ohlcv_by_asset[asset], cfg),
                metadata={"asset": asset, "source": str(asset_data[asset]), "study": "daily_asset_generalization_v0"},
            )
            run = _run_one(frame, cfg, spec["target"], spec["model"], spec["feature_set"])
            elapsed = time.perf_counter() - started
            payload = {
                "spec": spec,
                "config": asdict(cfg),
                "cache_hit": cache_hit,
                "elapsed_seconds": elapsed,
                "run": run,
            }
            _atomic_json(results_dir / f"{spec_id}.json", payload)
            completed[spec_id] = _summary_row(spec, run, elapsed, len(frame), cache_hit)
            failed.pop(spec_id, None)
            _atomic_json(state_path, state)
            _refresh_outputs(run_dir, state)
            aggregate = run["aggregate"]
            _, top5_lift, _ = _top_lift(aggregate, 0.05)
            print(
                f"  done in {elapsed / 60.0:.1f} min | cache={'hit' if cache_hit else 'miss'} | "
                f"auc={aggregate.get('roc_auc')} ap={aggregate.get('average_precision')} top5_lift={top5_lift}",
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
            _atomic_json(state_path, state)
            _refresh_outputs(run_dir, state)
            print(f"  FAILED after {elapsed / 60.0:.1f} min: {exc!r}", flush=True)
            raise

    _refresh_outputs(run_dir, state)
    summary = pd.DataFrame(list(completed.values()))

    print()
    print("Jump Risk daily asset generalization study complete")
    print(f"Out dir: {run_dir}")
    print()
    print("Best top-5 lift by asset/lane:")
    if not summary.empty:
        best = summary.sort_values(["top5_lift", "roc_auc"], ascending=[False, False], na_position="last").groupby(
            ["asset", "lane"], as_index=False
        ).head(1)
        for _, row in best.sort_values(["asset", "lane"]).iterrows():
            print(
                f"- asset={row['asset']:<3} lane={row['lane']:<14} h={int(row['horizon_bars']):<3} "
                f"z={row['jump_z']:<3g} abs={row['absolute_jump']:<4g} model={row['model']:<8} "
                f"auc={row['roc_auc']:.4f} ap={row['average_precision']:.4f} "
                f"top5_rate={row['top5_event_rate']:.2%} lift={row['top5_lift']:.2f}x"
            )
    print()
    print("Reference files:")
    print(f"- {run_dir / 'daily_generalization_summary.csv'}")
    print(f"- {run_dir / 'daily_generalization_best_by_asset_lane.csv'}")
    print(f"- {run_dir / 'daily_generalization_best_by_asset_target_model.csv'}")
    print(f"- {run_dir / 'daily_generalization_timing.csv'}")
    print(f"- {manifest_path}")
    print(f"- {state_path}")


if __name__ == "__main__":
    main()
