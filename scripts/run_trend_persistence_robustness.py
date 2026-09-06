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
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

REPO_ROOT = Path(__file__).resolve().parent.parent

import scripts.run_trend_persistence_research as discovery
from research.jump_risk_engine.lab import read_ohlcv
from research.research_engine.cache import CacheKey, ResearchCache, fingerprint_file
from scripts.run_trend_persistence_ablation import FEATURE_SETS


LOCKED_CANDIDATES: dict[str, dict[str, Any]] = {
    "btc_immediate": {
        "asset": "BTC",
        "model": "logistic",
        "feature_set": "momentum_volatility",
        "center_horizon": 3,
        "horizons": [2, 3, 4, 5],
        "z_grid": [0.75, 1.0, 1.25],
        "floor_grid": [0.02, 0.03, 0.04],
    },
    "eth_immediate": {
        "asset": "ETH",
        "model": "logistic",
        "feature_set": "all_features",
        "center_horizon": 3,
        "horizons": [2, 3, 4, 5],
        "z_grid": [0.75, 1.0, 1.25],
        "floor_grid": [0.02, 0.03, 0.04],
    },
    "btc_medium": {
        "asset": "BTC",
        "model": "logistic",
        "feature_set": "all_features",
        "center_horizon": 60,
        "horizons": [48, 60, 72],
        "z_grid": [1.5, 2.0, 2.5],
        "floor_grid": [0.015, 0.02, 0.025],
    },
    "btc_long": {
        "asset": "BTC",
        "model": "logistic",
        "feature_set": "all_features",
        "center_horizon": 120,
        "horizons": [108, 120, 132],
        "z_grid": [1.5, 2.0, 2.5],
        "floor_grid": [0.015, 0.02, 0.025],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Targeted robustness and promotion-gate study for Trend Persistence v0.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--asset-data", action="append", required=True, metavar="ASSET=PATH")
    parser.add_argument("--test-start-year", type=int, default=2020)
    parser.add_argument("--bootstrap-samples", type=int, default=500)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--out-dir", default="artifacts/trend_persistence_v0")
    parser.add_argument("--cache-dir", default="artifacts/research_engine_v1/cache")
    parser.add_argument("--run-name", default="trend-persistence-robustness-v0")
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
        if asset not in {"BTC", "ETH"}:
            raise ValueError(f"Only BTC and ETH are supported; received {asset!r}")
        if not path.exists():
            raise FileNotFoundError(f"Missing dataset for {asset}: {path}")
        mappings[asset] = path
    required = {spec["asset"] for spec in LOCKED_CANDIDATES.values()}
    missing = required - set(mappings)
    if missing:
        raise ValueError(f"Missing required asset mappings: {sorted(missing)}")
    return mappings


def _atomic_json(path: Path, payload: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temp.replace(path)


def _spec_id(spec: dict[str, Any]) -> str:
    return (
        f"{spec['candidate']}__h{spec['horizon_bars']}__z{spec['jump_z']:g}__floor{spec['absolute_floor']:g}"
    ).lower().replace(".", "p")


def _run_with_predictions(
    frame: pd.DataFrame,
    cfg: discovery.ExperimentConfig,
    model_name: str,
    features: list[str],
) -> tuple[dict[str, Any], pd.DataFrame]:
    folds: list[dict[str, Any]] = []
    prediction_parts: list[pd.DataFrame] = []
    for year in sorted(y for y in frame.index.year.unique() if y >= cfg.test_start_year):
        train = frame[frame.index.year < year]
        test = frame[frame.index.year == year]
        train_events = int(train["continuation"].sum())
        train_nonevents = int((train["continuation"] == 0).sum())
        if (
            len(train) < cfg.min_train_rows
            or train_events < cfg.min_train_events
            or train_nonevents < cfg.min_train_events
            or test.empty
        ):
            folds.append(
                {
                    "test_year": int(year),
                    "status": "SKIP_LOW_SAMPLE",
                    "train_rows": int(len(train)),
                    "train_events": train_events,
                    "test_rows": int(len(test)),
                    "test_events": int(test["continuation"].sum()),
                }
            )
            continue
        estimator = discovery._model(model_name)
        estimator.fit(train[features].astype(float), train["continuation"].astype(int))
        probabilities = estimator.predict_proba(test[features].astype(float))[:, 1]
        y = test["continuation"].astype(int).to_numpy()
        p = np.asarray(probabilities, dtype=float)
        fold_auc = float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else None
        fold_ap = float(average_precision_score(y, p)) if int(y.sum()) > 0 else None
        fold_brier = float(brier_score_loss(y, p)) if len(np.unique(y)) > 1 else None
        top_n = max(1, int(round(len(y) * 0.05)))
        order = np.argsort(-p)
        top_y = y[order[:top_n]]
        base_rate = float(y.mean())
        top_rate = float(top_y.mean())
        folds.append(
            {
                "test_year": int(year),
                "status": "PASS",
                "train_rows": int(len(train)),
                "train_events": train_events,
                "test_rows": int(len(test)),
                "test_events": int(y.sum()),
                "event_rate": base_rate,
                "roc_auc": fold_auc,
                "average_precision": fold_ap,
                "brier": fold_brier,
                "top5_n": int(top_n),
                "top5_events": int(top_y.sum()),
                "top5_event_rate": top_rate,
                "top5_lift": float(top_rate / base_rate) if base_rate > 0 else None,
            }
        )
        prediction_parts.append(
            pd.DataFrame(
                {
                    "timestamp": test.index,
                    "test_year": int(year),
                    "label": y,
                    "probability": p,
                }
            )
        )

    if not prediction_parts:
        return {"status": "PARTIAL", "reason": "no valid walk-forward folds", "folds": folds}, pd.DataFrame()

    predictions = pd.concat(prediction_parts, ignore_index=True).sort_values("timestamp")
    y_all = predictions["label"].to_numpy(dtype=int)
    p_all = predictions["probability"].to_numpy(dtype=float)
    top_n = max(1, int(round(len(predictions) * 0.05)))
    order = np.argsort(-p_all)
    top_y = y_all[order[:top_n]]
    base_rate = float(y_all.mean())
    top_rate = float(top_y.mean())
    result = {
        "status": "PASS",
        "rows": int(len(predictions)),
        "events": int(y_all.sum()),
        "event_rate": base_rate,
        "roc_auc": float(roc_auc_score(y_all, p_all)) if len(np.unique(y_all)) > 1 else None,
        "average_precision": float(average_precision_score(y_all, p_all)) if int(y_all.sum()) > 0 else None,
        "brier": float(brier_score_loss(y_all, p_all)) if len(np.unique(y_all)) > 1 else None,
        "top5_n": int(top_n),
        "top5_events": int(top_y.sum()),
        "top5_event_rate": top_rate,
        "top5_lift": float(top_rate / base_rate) if base_rate > 0 else None,
        "folds": folds,
    }
    return result, predictions


def _calibration_table(predictions: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
    if predictions.empty:
        return pd.DataFrame()
    frame = predictions.copy()
    frame["bin"] = pd.cut(frame["probability"], bins=np.linspace(0.0, 1.0, bins + 1), include_lowest=True)
    grouped = frame.groupby("bin", observed=True)
    return grouped.agg(
        rows=("label", "size"),
        predicted_probability=("probability", "mean"),
        observed_event_rate=("label", "mean"),
        events=("label", "sum"),
    ).reset_index().assign(bin=lambda x: x["bin"].astype(str))


def _bootstrap_metrics(
    predictions: pd.DataFrame,
    samples: int,
    seed: int,
) -> dict[str, float | None]:
    if predictions.empty or samples <= 0:
        return {}
    rng = np.random.default_rng(seed)
    y = predictions["label"].to_numpy(dtype=int)
    p = predictions["probability"].to_numpy(dtype=float)
    n = len(predictions)
    aucs: list[float] = []
    top_rates: list[float] = []
    lifts: list[float] = []
    for _ in range(samples):
        idx = rng.integers(0, n, size=n)
        y_b = y[idx]
        p_b = p[idx]
        if len(np.unique(y_b)) > 1:
            aucs.append(float(roc_auc_score(y_b, p_b)))
        top_n = max(1, int(round(n * 0.05)))
        order = np.argsort(-p_b)
        top_rate = float(y_b[order[:top_n]].mean())
        base_rate = float(y_b.mean())
        top_rates.append(top_rate)
        if base_rate > 0:
            lifts.append(float(top_rate / base_rate))

    def interval(values: list[float], prefix: str) -> dict[str, float | None]:
        if not values:
            return {f"{prefix}_p025": None, f"{prefix}_median": None, f"{prefix}_p975": None}
        array = np.asarray(values, dtype=float)
        return {
            f"{prefix}_p025": float(np.quantile(array, 0.025)),
            f"{prefix}_median": float(np.quantile(array, 0.5)),
            f"{prefix}_p975": float(np.quantile(array, 0.975)),
        }

    return {
        **interval(aucs, "bootstrap_auc"),
        **interval(top_rates, "bootstrap_top5_event_rate"),
        **interval(lifts, "bootstrap_top5_lift"),
    }


def _year_metrics(result: dict[str, Any]) -> dict[str, Any]:
    passed = [fold for fold in result.get("folds", []) if fold.get("status") == "PASS"]
    aucs = [float(fold["roc_auc"]) for fold in passed if fold.get("roc_auc") is not None]
    aps = [float(fold["average_precision"]) for fold in passed if fold.get("average_precision") is not None]
    lifts = [float(fold["top5_lift"]) for fold in passed if fold.get("top5_lift") is not None]
    event_counts = [int(fold.get("test_events", 0)) for fold in passed]
    top_events = [int(fold.get("top5_events", 0)) for fold in passed]
    return {
        "passed_years": len(passed),
        "avg_year_auc": float(np.mean(aucs)) if aucs else None,
        "min_year_auc": float(np.min(aucs)) if aucs else None,
        "avg_year_ap": float(np.mean(aps)) if aps else None,
        "min_year_ap": float(np.min(aps)) if aps else None,
        "avg_year_top5_lift": float(np.mean(lifts)) if lifts else None,
        "min_year_top5_lift": float(np.min(lifts)) if lifts else None,
        "min_year_events": min(event_counts) if event_counts else None,
        "min_year_top5_events": min(top_events) if top_events else None,
    }


def _promotion_grade(row: pd.Series) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if row.get("status") != "PASS":
        return "REJECT", ["no valid aggregate result"]
    if int(row.get("events", 0)) < 100:
        reasons.append("fewer than 100 aggregate OOS events")
    if int(row.get("top5_events", 0)) < 15:
        reasons.append("fewer than 15 aggregate top-5% events")
    if int(row.get("passed_years", 0)) < 5:
        reasons.append("fewer than 5 valid yearly folds")
    if float(row.get("roc_auc", 0.0) or 0.0) < 0.62:
        reasons.append("aggregate AUC below 0.62")
    if float(row.get("top5_lift", 0.0) or 0.0) < 2.0:
        reasons.append("aggregate top-5% lift below 2.0x")
    if float(row.get("min_year_auc", 0.0) or 0.0) < 0.52:
        reasons.append("worst-year AUC below 0.52")
    if float(row.get("bootstrap_auc_p025", 0.0) or 0.0) <= 0.50:
        reasons.append("bootstrap AUC lower bound does not exceed 0.50")
    if float(row.get("bootstrap_top5_lift_p025", 0.0) or 0.0) <= 1.0:
        reasons.append("bootstrap lift lower bound does not exceed 1.0x")
    if not reasons:
        return "VALID", []
    if len(reasons) <= 2 and int(row.get("events", 0)) >= 40:
        return "WARN", reasons
    return "INVALID", reasons


def _refresh_outputs(run_dir: Path, state: dict[str, Any]) -> None:
    summary = pd.DataFrame(list(state.get("completed", {}).values()))
    summary_path = run_dir / "trend_persistence_robustness_summary.csv"
    audit_path = run_dir / "trend_persistence_robustness_audit.csv"
    centers_path = run_dir / "trend_persistence_center_scorecard.csv"
    summary.to_csv(summary_path, index=False)
    if summary.empty:
        pd.DataFrame().to_csv(audit_path, index=False)
        pd.DataFrame().to_csv(centers_path, index=False)
        return

    audit = summary.copy()
    grades = audit.apply(_promotion_grade, axis=1)
    audit["audit_grade"] = [grade for grade, _ in grades]
    audit["audit_reasons"] = ["; ".join(reasons) for _, reasons in grades]
    audit.to_csv(audit_path, index=False)

    centers = audit[
        (audit["horizon_bars"] == audit["center_horizon"])
        & (audit["jump_z"] == audit["center_z"])
        & (audit["absolute_floor"] == audit["center_floor"])
    ].copy()
    centers.to_csv(centers_path, index=False)


def main() -> None:
    args = parse_args()
    mappings = _parse_asset_data(args.asset_data)
    defaults = discovery._defaults("1h")

    specs: list[dict[str, Any]] = []
    for candidate, locked in LOCKED_CANDIDATES.items():
        center_z = 1.0 if "immediate" in candidate else 2.0
        center_floor = 0.03 if "immediate" in candidate else 0.02
        for horizon in locked["horizons"]:
            for jump_z in locked["z_grid"]:
                for floor in locked["floor_grid"]:
                    specs.append(
                        {
                            "candidate": candidate,
                            "asset": locked["asset"],
                            "model": locked["model"],
                            "feature_set": locked["feature_set"],
                            "center_horizon": int(locked["center_horizon"]),
                            "center_z": float(center_z),
                            "center_floor": float(center_floor),
                            "horizon_bars": int(horizon),
                            "jump_z": float(jump_z),
                            "absolute_floor": float(floor),
                        }
                    )

    if args.resume_dir:
        run_dir = Path(args.resume_dir)
        if not run_dir.exists():
            raise FileNotFoundError(f"Resume directory does not exist: {run_dir}")
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = Path(args.out_dir) / "robustness" / f"{timestamp}_{args.run_name}"
        run_dir.mkdir(parents=True, exist_ok=False)

    results_dir = run_dir / "results"
    calibration_dir = run_dir / "calibration"
    yearly_dir = run_dir / "yearly"
    results_dir.mkdir(parents=True, exist_ok=True)
    calibration_dir.mkdir(parents=True, exist_ok=True)
    yearly_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / "state.json"
    manifest_path = run_dir / "manifest.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"completed": {}, "failed": {}}
    completed = state.setdefault("completed", {})
    failed = state.setdefault("failed", {})

    manifest = {
        "experiment": "trend_persistence_targeted_robustness_v0",
        "research_only": True,
        "runtime_integration_allowed": False,
        "timeframe": "1h",
        "assets": {asset: str(path) for asset, path in mappings.items()},
        "locked_candidates": LOCKED_CANDIDATES,
        "test_start_year": args.test_start_year,
        "bootstrap_samples": args.bootstrap_samples,
        "configuration_count": len(specs),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "resume_command": (
            "python .\\scripts\\run_trend_persistence_robustness.py "
            + " ".join(f'--asset-data "{asset}={path}"' for asset, path in mappings.items())
            + f' --resume-dir "{run_dir}"'
        ),
    }
    _atomic_json(manifest_path, manifest)
    _atomic_json(state_path, state)

    pending = [spec for spec in specs if _spec_id(spec) not in completed]
    print("Trend Persistence targeted robustness")
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
            f"[{position}/{len(pending)}] candidate={spec['candidate']:<13} asset={asset} "
            f"h={spec['horizon_bars']:<3} z={spec['jump_z']:<4g} floor={spec['absolute_floor']:<5g}",
            flush=True,
        )
        started = time.perf_counter()
        try:
            frame, cache_hit = cache.get_or_build_frame(
                key,
                lambda cfg=cfg, asset=asset: discovery._build_frame(ohlcv_by_asset[asset], cfg),
                metadata={"experiment": "trend_persistence_v0", "source": str(mappings[asset])},
            )
            result, predictions = _run_with_predictions(
                frame,
                cfg,
                spec["model"],
                FEATURE_SETS[spec["feature_set"]],
            )
            bootstrap = _bootstrap_metrics(
                predictions,
                samples=args.bootstrap_samples,
                seed=args.random_seed + position,
            )
            elapsed = time.perf_counter() - started
            calibration = _calibration_table(predictions)
            calibration.to_csv(calibration_dir / f"{spec_id}.csv", index=False)
            pd.DataFrame(result.get("folds", [])).to_csv(yearly_dir / f"{spec_id}.csv", index=False)
            payload = {
                "spec": spec,
                "config": asdict(cfg),
                "features": FEATURE_SETS[spec["feature_set"]],
                "cache_hit": cache_hit,
                "elapsed_seconds": elapsed,
                "result": result,
                "bootstrap": bootstrap,
            }
            _atomic_json(results_dir / f"{spec_id}.json", payload)
            completed[spec_id] = {
                **spec,
                "feature_count": len(FEATURE_SETS[spec["feature_set"]]),
                "cache_hit": cache_hit,
                "elapsed_seconds": elapsed,
                **{key: value for key, value in result.items() if key != "folds"},
                **_year_metrics(result),
                **bootstrap,
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            failed.pop(spec_id, None)
            _atomic_json(state_path, state)
            _refresh_outputs(run_dir, state)
            print(
                f"  status={result.get('status')} events={result.get('events')} top5_events={result.get('top5_events')} "
                f"auc={result.get('roc_auc')} lift={result.get('top5_lift')} elapsed={elapsed / 60.0:.1f}m",
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
    audit = pd.read_csv(run_dir / "trend_persistence_robustness_audit.csv")
    print()
    print("Trend Persistence targeted robustness complete")
    print(f"Out dir: {run_dir}")
    print("Audit counts:")
    for grade, count in audit["audit_grade"].value_counts().sort_index().items():
        print(f"- {grade}: {count}")
    print("Center candidate scorecard:")
    centers = pd.read_csv(run_dir / "trend_persistence_center_scorecard.csv")
    for _, row in centers.sort_values("candidate").iterrows():
        print(
            f"- candidate={row['candidate']:<13} grade={row['audit_grade']:<7} "
            f"events={int(row['events']):<5} top5_events={int(row['top5_events']):<4} "
            f"auc={row['roc_auc']:.4f} lift={row['top5_lift']:.2f}x"
        )
    print()
    print("Reference files:")
    print(f"- {run_dir / 'trend_persistence_robustness_summary.csv'}")
    print(f"- {run_dir / 'trend_persistence_robustness_audit.csv'}")
    print(f"- {run_dir / 'trend_persistence_center_scorecard.csv'}")
    print(f"- {manifest_path}")
    print(f"- {state_path}")


if __name__ == "__main__":
    main()
