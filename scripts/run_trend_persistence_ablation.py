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

import scripts.run_trend_persistence_research as discovery
from research.jump_risk_engine.lab import read_ohlcv
from research.research_engine.cache import CacheKey, ResearchCache, fingerprint_file


# Locked from the completed hourly discovery sweep. These represent the distinct
# short- and multi-day continuation regimes; this runner does not search horizons.
LOCKED_CANDIDATES = [
    {"candidate": "short_h6", "horizon_bars": 6, "jump_z": 1.0, "absolute_floor": 0.03},
    {"candidate": "long_h72", "horizon_bars": 72, "jump_z": 2.0, "absolute_floor": 0.02},
    {"candidate": "long_h120", "horizon_bars": 120, "jump_z": 2.0, "absolute_floor": 0.02},
]

BASELINE = ["ret_1", "ret_fast", "ret_slow", "day_of_week"]
MOMENTUM = [
    "trend_strength",
    "trend_acceleration",
    "distance_fast_sma",
    "distance_slow_sma",
]
VOLATILITY = ["realized_vol", "fast_vol", "slow_vol", "vol_ratio", "vol_rank"]
STRUCTURE = [
    "distance_high_fast",
    "distance_low_fast",
    "range_position_fast",
    "range_position_slow",
]
VOLUME = ["volume_z"]

FEATURE_SETS = {
    "baseline": BASELINE,
    "baseline_momentum": BASELINE + MOMENTUM,
    "baseline_volatility": BASELINE + VOLATILITY,
    "baseline_structure": BASELINE + STRUCTURE,
    "baseline_volume": BASELINE + VOLUME,
    "momentum_volatility": BASELINE + MOMENTUM + VOLATILITY,
    "momentum_structure": BASELINE + MOMENTUM + STRUCTURE,
    "all_features": list(discovery.FEATURES),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Targeted feature-family ablation for Trend Persistence v0 hourly candidates.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--asset-data", action="append", required=True, metavar="ASSET=PATH")
    p.add_argument("--models", default="logistic,gbm")
    p.add_argument("--feature-sets", default=",".join(FEATURE_SETS))
    p.add_argument("--test-start-year", type=int, default=2020)
    p.add_argument("--out-dir", default="artifacts/trend_persistence_v0")
    p.add_argument("--cache-dir", default="artifacts/research_engine_v1/cache")
    p.add_argument("--run-name", default="trend-persistence-ablation-v0")
    p.add_argument("--resume-dir")
    return p.parse_args()


def _parse_asset_data(values: list[str]) -> dict[str, Path]:
    mappings: dict[str, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"Expected ASSET=PATH, received {raw!r}")
        asset_raw, path_raw = raw.split("=", 1)
        asset = asset_raw.strip().upper()
        path = Path(path_raw.strip())
        if not asset or not path.exists():
            raise FileNotFoundError(f"Invalid or missing dataset mapping: {raw!r}")
        if asset in mappings:
            raise ValueError(f"Duplicate asset mapping: {asset}")
        mappings[asset] = path
    return mappings


def _atomic_json(path: Path, payload: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temp.replace(path)


def _spec_id(spec: dict[str, Any]) -> str:
    return (
        f"{spec['asset']}__{spec['candidate']}__{spec['model']}__{spec['feature_set']}"
    ).lower().replace(".", "p")


def _run_with_features(
    frame: pd.DataFrame,
    cfg: discovery.ExperimentConfig,
    model_name: str,
    features: list[str],
) -> dict[str, Any]:
    original = list(discovery.FEATURES)
    discovery.FEATURES[:] = features
    try:
        return discovery._walk_forward(frame, cfg, model_name)
    finally:
        discovery.FEATURES[:] = original


def _year_metrics(result: dict[str, Any]) -> dict[str, Any]:
    passed = [fold for fold in result.get("folds", []) if fold.get("status") == "PASS"]
    aucs = [float(fold["roc_auc"]) for fold in passed if fold.get("roc_auc") is not None]
    aps = [float(fold["average_precision"]) for fold in passed if fold.get("average_precision") is not None]
    event_years = [int(fold.get("test_events", 0)) for fold in passed]
    return {
        "passed_years": len(passed),
        "avg_year_auc": float(np.mean(aucs)) if aucs else None,
        "min_year_auc": float(np.min(aucs)) if aucs else None,
        "avg_year_ap": float(np.mean(aps)) if aps else None,
        "min_year_ap": float(np.min(aps)) if aps else None,
        "min_year_events": min(event_years) if event_years else None,
    }


def _refresh_outputs(run_dir: Path, state: dict[str, Any]) -> None:
    rows = list(state.get("completed", {}).values())
    summary = pd.DataFrame(rows)
    summary_path = run_dir / "trend_persistence_ablation_summary.csv"
    best_path = run_dir / "trend_persistence_ablation_best.csv"
    comparison_path = run_dir / "trend_persistence_ablation_vs_all_features.csv"
    summary.to_csv(summary_path, index=False)
    if summary.empty:
        pd.DataFrame().to_csv(best_path, index=False)
        pd.DataFrame().to_csv(comparison_path, index=False)
        return

    valid = summary[summary["status"] == "PASS"].copy()
    ranked = valid.sort_values(
        ["top5_lift", "roc_auc", "events"], ascending=[False, False, False], na_position="last"
    )
    ranked.groupby(["asset", "candidate", "model"], as_index=False).head(1).to_csv(best_path, index=False)

    all_rows = valid[valid["feature_set"] == "all_features"][
        ["asset", "candidate", "model", "roc_auc", "average_precision", "top5_lift"]
    ].rename(
        columns={
            "roc_auc": "all_features_auc",
            "average_precision": "all_features_ap",
            "top5_lift": "all_features_top5_lift",
        }
    )
    comparison = valid.merge(all_rows, on=["asset", "candidate", "model"], how="left")
    comparison["delta_auc_vs_all"] = comparison["roc_auc"] - comparison["all_features_auc"]
    comparison["delta_ap_vs_all"] = comparison["average_precision"] - comparison["all_features_ap"]
    comparison["delta_top5_lift_vs_all"] = comparison["top5_lift"] - comparison["all_features_top5_lift"]
    comparison.to_csv(comparison_path, index=False)


def main() -> None:
    args = parse_args()
    mappings = _parse_asset_data(args.asset_data)
    defaults = discovery._defaults("1h")
    models = [item.strip().lower() for item in args.models.split(",") if item.strip()]
    unknown_models = sorted(set(models) - {"logistic", "gbm"})
    if unknown_models:
        raise ValueError(f"Unsupported models: {unknown_models}")
    feature_names = [item.strip() for item in args.feature_sets.split(",") if item.strip()]
    unknown_features = sorted(set(feature_names) - set(FEATURE_SETS))
    if unknown_features:
        raise ValueError(f"Unknown feature sets: {unknown_features}; available={sorted(FEATURE_SETS)}")

    if args.resume_dir:
        run_dir = Path(args.resume_dir)
        if not run_dir.exists():
            raise FileNotFoundError(f"Resume directory does not exist: {run_dir}")
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = Path(args.out_dir) / "ablation" / f"{timestamp}_{args.run_name}"
        run_dir.mkdir(parents=True, exist_ok=False)
    results_dir = run_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "state.json"
    manifest_path = run_dir / "manifest.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"completed": {}, "failed": {}}
    completed = state.setdefault("completed", {})
    failed = state.setdefault("failed", {})

    specs: list[dict[str, Any]] = []
    for asset in mappings:
        for candidate in LOCKED_CANDIDATES:
            for model in models:
                for feature_set in feature_names:
                    specs.append({"asset": asset, "model": model, "feature_set": feature_set, **candidate})

    manifest = {
        "experiment": "trend_persistence_feature_ablation_v0",
        "research_only": True,
        "timeframe": "1h",
        "assets": {asset: str(path) for asset, path in mappings.items()},
        "locked_candidates": LOCKED_CANDIDATES,
        "feature_sets": {name: FEATURE_SETS[name] for name in feature_names},
        "models": models,
        "test_start_year": args.test_start_year,
        "configuration_count": len(specs),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "resume_command": (
            "python .\\scripts\\run_trend_persistence_ablation.py "
            + " ".join(f'--asset-data "{asset}={path}"' for asset, path in mappings.items())
            + f' --resume-dir "{run_dir}"'
        ),
    }
    _atomic_json(manifest_path, manifest)
    _atomic_json(state_path, state)

    pending = [spec for spec in specs if _spec_id(spec) not in completed]
    print("Trend Persistence targeted feature ablation")
    print(f"Assets: {list(mappings)}")
    print(f"Locked candidates: {[item['candidate'] for item in LOCKED_CANDIDATES]}")
    print(f"Feature sets: {feature_names}")
    print(f"Configurations: {len(specs)} | completed: {len(specs) - len(pending)} | pending: {len(pending)}")
    print(f"Run dir: {run_dir}")
    print()

    cache = ResearchCache(args.cache_dir)
    ohlcv_by_asset = {asset: read_ohlcv(path) for asset, path in mappings.items()}
    fingerprints = {asset: fingerprint_file(path) for asset, path in mappings.items()}

    for position, spec in enumerate(pending, start=1):
        spec_id = _spec_id(spec)
        asset = spec["asset"]
        cfg = discovery.ExperimentConfig(
            asset=asset,
            timeframe="1h",
            horizon_bars=int(spec["horizon_bars"]),
            fast_window=defaults["fast"],
            slow_window=defaults["slow"],
            vol_window=defaults["vol"],
            jump_z=float(spec["jump_z"]),
            absolute_floor=float(spec["absolute_floor"]),
            test_start_year=args.test_start_year,
            min_train_rows=defaults["min_train_rows"],
            min_train_events=defaults["min_train_events"],
        )
        key = CacheKey(
            namespace="trend-persistence-v0-frame",
            asset=asset,
            timeframe="1h",
            dataset_fingerprint=fingerprints[asset],
            parameters=asdict(cfg),
            version="v0",
        )
        print(
            f"[{position}/{len(pending)}] asset={asset:<3} candidate={spec['candidate']:<10} "
            f"model={spec['model']:<8} features={spec['feature_set']}",
            flush=True,
        )
        started = time.perf_counter()
        try:
            frame, cache_hit = cache.get_or_build_frame(
                key,
                lambda cfg=cfg, asset=asset: discovery._build_frame(ohlcv_by_asset[asset], cfg),
                metadata={"experiment": "trend_persistence_v0", "source": str(mappings[asset])},
            )
            result = _run_with_features(frame, cfg, spec["model"], FEATURE_SETS[spec["feature_set"]])
            elapsed = time.perf_counter() - started
            payload = {
                "spec": spec,
                "config": asdict(cfg),
                "features": FEATURE_SETS[spec["feature_set"]],
                "cache_hit": cache_hit,
                "elapsed_seconds": elapsed,
                "result": result,
            }
            _atomic_json(results_dir / f"{spec_id}.json", payload)
            completed[spec_id] = {
                **spec,
                "feature_count": len(FEATURE_SETS[spec["feature_set"]]),
                "cache_hit": cache_hit,
                "elapsed_seconds": elapsed,
                **{key: value for key, value in result.items() if key != "folds"},
                **_year_metrics(result),
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            failed.pop(spec_id, None)
            _atomic_json(state_path, state)
            _refresh_outputs(run_dir, state)
            print(
                f"  status={result.get('status')} auc={result.get('roc_auc')} ap={result.get('average_precision')} "
                f"top5_lift={result.get('top5_lift')} cache={'hit' if cache_hit else 'miss'} "
                f"elapsed={elapsed / 60.0:.1f}m",
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
            print(f"  FAILED after {elapsed / 60.0:.1f}m: {exc!r}", flush=True)
            raise

    _refresh_outputs(run_dir, state)
    summary = pd.DataFrame(list(completed.values()))
    print()
    print("Trend Persistence targeted feature ablation complete")
    print(f"Out dir: {run_dir}")
    print("Best feature family by asset/candidate/model:")
    if not summary.empty:
        best = summary[summary["status"] == "PASS"].sort_values(
            ["top5_lift", "roc_auc"], ascending=[False, False], na_position="last"
        ).groupby(["asset", "candidate", "model"], as_index=False).head(1)
        for _, row in best.sort_values(["asset", "candidate", "model"]).iterrows():
            print(
                f"- asset={row['asset']:<3} candidate={row['candidate']:<10} model={row['model']:<8} "
                f"features={row['feature_set']:<20} auc={row['roc_auc']:.4f} "
                f"ap={row['average_precision']:.4f} lift={row['top5_lift']:.2f}x"
            )
    print()
    print("Reference files:")
    print(f"- {run_dir / 'trend_persistence_ablation_summary.csv'}")
    print(f"- {run_dir / 'trend_persistence_ablation_best.csv'}")
    print(f"- {run_dir / 'trend_persistence_ablation_vs_all_features.csv'}")
    print(f"- {manifest_path}")
    print(f"- {state_path}")


if __name__ == "__main__":
    main()
