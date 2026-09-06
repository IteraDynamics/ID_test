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
from scripts.run_trend_persistence_ablation import FEATURE_SETS


# Locked from the completed targeted feature ablation. Only horizon varies here.
LOCKED_SPECS: dict[str, list[dict[str, Any]]] = {
    "BTC": [
        {
            "candidate": "short",
            "model": "logistic",
            "feature_set": "momentum_volatility",
            "jump_z": 1.0,
            "absolute_floor": 0.03,
            "horizons": [3, 4, 5, 6, 8, 10, 12],
        },
        {
            "candidate": "medium_long",
            "model": "logistic",
            "feature_set": "all_features",
            "jump_z": 2.0,
            "absolute_floor": 0.02,
            "horizons": [48, 60, 72, 84, 96],
        },
        {
            "candidate": "long",
            "model": "logistic",
            "feature_set": "all_features",
            "jump_z": 2.0,
            "absolute_floor": 0.02,
            "horizons": [96, 108, 120, 132, 144, 168],
        },
    ],
    "ETH": [
        {
            "candidate": "short",
            "model": "logistic",
            "feature_set": "all_features",
            "jump_z": 1.0,
            "absolute_floor": 0.03,
            "horizons": [3, 4, 5, 6, 8, 10, 12],
        },
        {
            "candidate": "medium_long",
            "model": "logistic",
            "feature_set": "baseline_volatility",
            "jump_z": 2.0,
            "absolute_floor": 0.02,
            "horizons": [48, 60, 72, 84, 96],
        },
        {
            "candidate": "long",
            "model": "gbm",
            "feature_set": "all_features",
            "jump_z": 2.0,
            "absolute_floor": 0.02,
            "horizons": [96, 108, 120, 132, 144, 168],
        },
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Targeted horizon refinement for locked Trend Persistence v0 candidates.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--asset-data", action="append", required=True, metavar="ASSET=PATH")
    parser.add_argument("--test-start-year", type=int, default=2020)
    parser.add_argument("--out-dir", default="artifacts/trend_persistence_v0")
    parser.add_argument("--cache-dir", default="artifacts/research_engine_v1/cache")
    parser.add_argument("--run-name", default="trend-persistence-horizon-refinement-v0")
    parser.add_argument("--resume-dir")
    return parser.parse_args()


def _parse_asset_data(values: list[str]) -> dict[str, Path]:
    mappings: dict[str, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"Expected ASSET=PATH, received {raw!r}")
        asset_raw, path_raw = raw.split("=", 1)
        asset = asset_raw.strip().upper()
        path = Path(path_raw.strip())
        if asset not in LOCKED_SPECS:
            raise ValueError(f"Supported assets are {sorted(LOCKED_SPECS)}; received {asset!r}")
        if not path.exists():
            raise FileNotFoundError(f"Missing dataset for {asset}: {path}")
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
        f"{spec['asset']}__{spec['candidate']}__h{spec['horizon_bars']}__"
        f"{spec['model']}__{spec['feature_set']}__z{spec['jump_z']:g}__floor{spec['absolute_floor']:g}"
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
    event_counts = [int(fold.get("test_events", 0)) for fold in passed]
    return {
        "passed_years": len(passed),
        "avg_year_auc": float(np.mean(aucs)) if aucs else None,
        "min_year_auc": float(np.min(aucs)) if aucs else None,
        "avg_year_ap": float(np.mean(aps)) if aps else None,
        "min_year_ap": float(np.min(aps)) if aps else None,
        "min_year_events": min(event_counts) if event_counts else None,
    }


def _refresh_outputs(run_dir: Path, state: dict[str, Any]) -> None:
    summary = pd.DataFrame(list(state.get("completed", {}).values()))
    summary_path = run_dir / "trend_persistence_horizon_summary.csv"
    best_path = run_dir / "trend_persistence_horizon_best.csv"
    plateau_path = run_dir / "trend_persistence_horizon_plateaus.csv"
    summary.to_csv(summary_path, index=False)
    if summary.empty:
        pd.DataFrame().to_csv(best_path, index=False)
        pd.DataFrame().to_csv(plateau_path, index=False)
        return

    valid = summary[summary["status"] == "PASS"].copy()
    ranked = valid.sort_values(
        ["top5_lift", "roc_auc", "events"], ascending=[False, False, False], na_position="last"
    )
    best = ranked.groupby(["asset", "candidate"], as_index=False).head(1)
    best.to_csv(best_path, index=False)

    best_keys = best[["asset", "candidate", "top5_lift", "roc_auc"]].rename(
        columns={"top5_lift": "best_top5_lift", "roc_auc": "best_roc_auc"}
    )
    plateau = valid.merge(best_keys, on=["asset", "candidate"], how="left")
    plateau["lift_ratio_to_best"] = plateau["top5_lift"] / plateau["best_top5_lift"]
    plateau["auc_delta_to_best"] = plateau["roc_auc"] - plateau["best_roc_auc"]
    plateau["within_90pct_best_lift"] = plateau["lift_ratio_to_best"] >= 0.90
    plateau.sort_values(["asset", "candidate", "horizon_bars"]).to_csv(plateau_path, index=False)


def main() -> None:
    args = parse_args()
    mappings = _parse_asset_data(args.asset_data)
    defaults = discovery._defaults("1h")

    specs: list[dict[str, Any]] = []
    for asset in mappings:
        for locked in LOCKED_SPECS[asset]:
            for horizon in locked["horizons"]:
                specs.append(
                    {
                        "asset": asset,
                        "candidate": locked["candidate"],
                        "horizon_bars": int(horizon),
                        "model": locked["model"],
                        "feature_set": locked["feature_set"],
                        "jump_z": float(locked["jump_z"]),
                        "absolute_floor": float(locked["absolute_floor"]),
                    }
                )

    if args.resume_dir:
        run_dir = Path(args.resume_dir)
        if not run_dir.exists():
            raise FileNotFoundError(f"Resume directory does not exist: {run_dir}")
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = Path(args.out_dir) / "horizon_refinement" / f"{timestamp}_{args.run_name}"
        run_dir.mkdir(parents=True, exist_ok=False)

    results_dir = run_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "state.json"
    manifest_path = run_dir / "manifest.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"completed": {}, "failed": {}}
    completed = state.setdefault("completed", {})
    failed = state.setdefault("failed", {})

    manifest = {
        "experiment": "trend_persistence_targeted_horizon_refinement_v0",
        "research_only": True,
        "timeframe": "1h",
        "assets": {asset: str(path) for asset, path in mappings.items()},
        "locked_specs": {asset: LOCKED_SPECS[asset] for asset in mappings},
        "test_start_year": args.test_start_year,
        "configuration_count": len(specs),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "resume_command": (
            "python .\\scripts\\run_trend_persistence_horizon_refinement.py "
            + " ".join(f'--asset-data "{asset}={path}"' for asset, path in mappings.items())
            + f' --resume-dir "{run_dir}"'
        ),
    }
    _atomic_json(manifest_path, manifest)
    _atomic_json(state_path, state)

    pending = [spec for spec in specs if _spec_id(spec) not in completed]
    print("Trend Persistence targeted horizon refinement")
    print(f"Assets: {list(mappings)}")
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
            f"[{position}/{len(pending)}] asset={asset:<3} candidate={spec['candidate']:<11} "
            f"h={spec['horizon_bars']:<3} model={spec['model']:<8} features={spec['feature_set']}",
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
    print("Trend Persistence targeted horizon refinement complete")
    print(f"Out dir: {run_dir}")
    print("Best horizon by asset/candidate:")
    if not summary.empty:
        best = summary[summary["status"] == "PASS"].sort_values(
            ["top5_lift", "roc_auc", "events"], ascending=[False, False, False], na_position="last"
        ).groupby(["asset", "candidate"], as_index=False).head(1)
        for _, row in best.sort_values(["asset", "candidate"]).iterrows():
            print(
                f"- asset={row['asset']:<3} candidate={row['candidate']:<11} h={int(row['horizon_bars']):<3} "
                f"model={row['model']:<8} features={row['feature_set']:<20} "
                f"auc={row['roc_auc']:.4f} ap={row['average_precision']:.4f} lift={row['top5_lift']:.2f}x"
            )
    print()
    print("Reference files:")
    print(f"- {run_dir / 'trend_persistence_horizon_summary.csv'}")
    print(f"- {run_dir / 'trend_persistence_horizon_best.csv'}")
    print(f"- {run_dir / 'trend_persistence_horizon_plateaus.csv'}")
    print(f"- {manifest_path}")
    print(f"- {state_path}")


if __name__ == "__main__":
    main()
