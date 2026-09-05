from __future__ import annotations

import argparse
import hashlib
import json
import math
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research.ml_lab import cross_sectional_v1 as exp5




from research.ml_lab.macro_v1 import (
    FRED_SERIES,
    FRED_URL,
    MEMORY_SCHEMES,
    MACRO_STATES,
    INTERACTION_BASES,
    PRICE_FEATURES,
    INTERACTION_FEATURES,
    AUGMENTED_FEATURES,
    MIN_MACRO_ROLL,
    POST_START_YEAR,
    _sha256,
    _download_once,
    _load_fred,
    _load_vix,
    _rolling_percentile,
    _align_to_calendar,
    _build_macro_frame,
    _augment_panel,
    _training_slice,
    _anchor_metric,
    _summary,
)

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ML Lab Experiment 009: macro/rate state cross-sectional ranking")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--output-dir", default="artifacts/ml_lab_experiment_009")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    out_dir = Path(args.output_dir)
    cache_dir = out_dir / "source_cache"
    out_dir.mkdir(parents=True, exist_ok=True)

    source_paths = {series: _download_once(series, cache_dir) for series in FRED_SERIES}
    fred = {series: _load_fred(path, series) for series, path in source_paths.items()}
    vix_path = data_dir / "VIX_1D.csv"
    vix = _load_vix(vix_path)

    frames = exp5._load_universe(data_dir)
    calendar = exp5._common_calendar(frames)
    base_panel = exp5._build_panel(frames, calendar)
    macro_frame = _build_macro_frame(calendar, fred, vix)
    panel = _augment_panel(base_panel, macro_frame)

    predictions: list[pd.DataFrame] = []
    importance_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []

    years = sorted(y for y in panel["timestamp"].dt.year.unique() if y <= 2024)
    for year in years:
        test = panel[panel["timestamp"].dt.year == year].copy()
        if test.empty:
            continue
        test_start = test["timestamp"].min()

        for memory_name, memory_years in MEMORY_SCHEMES.items():
            train = _training_slice(panel, test_start, memory_years)
            eligible = len(train) >= exp5.MIN_TRAIN_ROWS and train["timestamp"].nunique() >= 50
            support_rows.append(
                {
                    "test_year": year,
                    "memory_scheme": memory_name,
                    "train_rows": int(len(train)),
                    "train_anchors": int(train["timestamp"].nunique()),
                    "test_rows": int(len(test)),
                    "test_anchors": int(test["timestamp"].nunique()),
                    "test_start": str(test_start.date()),
                    "max_train_target_end": str(train["target_end_date"].max().date()) if len(train) else None,
                    "eligible": bool(eligible),
                }
            )
            if not eligible:
                continue

            variants = {
                "price_ridge": (exp5._ridge(), PRICE_FEATURES, "ridge"),
                "price_gbm": (exp5._gbm(), PRICE_FEATURES, "gbm"),
                "macro_ridge": (exp5._ridge(), AUGMENTED_FEATURES, "ridge"),
                "macro_gbm": (exp5._gbm(), AUGMENTED_FEATURES, "gbm"),
            }
            for variant, (model, features, family) in variants.items():
                model.fit(train[list(features)].astype(float), train["target_rank"].astype(float))
                if variant.startswith("macro_"):
                    for feature, value in exp5._importance(model, family).items() if False else []:
                        pass
                    if family == "ridge":
                        vals = np.abs(model.named_steps["model"].coef_)
                    else:
                        vals = model.feature_importances_
                    for feature, value in zip(features, vals, strict=True):
                        importance_rows.append(
                            {
                                "test_year": year,
                                "memory_scheme": memory_name,
                                "model": variant,
                                "feature": feature,
                                "importance": float(value),
                            }
                        )

                p = test[["timestamp", "ticker", "target_raw", "target_rank"]].copy()
                p["test_year"] = year
                p["memory_scheme"] = memory_name
                p["model"] = variant
                p["score"] = model.predict(test[list(features)].astype(float))
                predictions.append(p)

    if not predictions:
        raise ValueError("NO_ELIGIBLE_OOS_FOLDS")

    pred = pd.concat(predictions, ignore_index=True)
    support = pd.DataFrame(support_rows)
    importance = pd.DataFrame(importance_rows)

    anchor_metrics = pd.DataFrame(
        [_anchor_metric(g) for _, g in pred.groupby(["timestamp", "memory_scheme", "model"], sort=True)]
    )
    yearly = (
        anchor_metrics.groupby(["test_year", "memory_scheme", "model"])
        .agg(
            anchors=("rank_ic", "size"),
            mean_rank_ic=("rank_ic", "mean"),
            median_rank_ic=("rank_ic", "median"),
            positive_ic_fraction=("rank_ic", lambda s: float((s > 0).mean())),
            mean_top_minus_bottom_raw_target=("top_minus_bottom_raw_target", "mean"),
        )
        .reset_index()
    )

    summary_rows: list[dict[str, Any]] = []
    for (memory_name, model_name), g in anchor_metrics.groupby(["memory_scheme", "model"]):
        row = {"memory_scheme": memory_name, "model": model_name}
        row.update(_summary(g))
        summary_rows.append(row)

    post_rows: list[dict[str, Any]] = []
    post = anchor_metrics[anchor_metrics["test_year"] >= POST_START_YEAR]
    for (memory_name, model_name), g in post.groupby(["memory_scheme", "model"]):
        row = {"memory_scheme": memory_name, "model": model_name}
        row.update(_summary(g))
        post_rows.append(row)

    increment_rows: list[dict[str, Any]] = []
    for period_name, frame in (("all", anchor_metrics), ("post_2022_2024", post)):
        s = pd.DataFrame(
            [
                {"memory_scheme": mem, "model": model, **_summary(g)}
                for (mem, model), g in frame.groupby(["memory_scheme", "model"])
            ]
        )
        for memory_name in MEMORY_SCHEMES:
            lookup = {r["model"]: r for _, r in s[s["memory_scheme"] == memory_name].iterrows()}
            for macro_name, price_name in (("macro_ridge", "price_ridge"), ("macro_gbm", "price_gbm")):
                if macro_name in lookup and price_name in lookup:
                    increment_rows.append(
                        {
                            "period": period_name,
                            "memory_scheme": memory_name,
                            "comparison": f"{macro_name}_minus_{price_name}",
                            "mean_ic_increment": float(lookup[macro_name]["mean_rank_ic"] - lookup[price_name]["mean_rank_ic"]),
                            "tail_spread_increment": float(
                                lookup[macro_name]["mean_top_minus_bottom_raw_target"]
                                - lookup[price_name]["mean_top_minus_bottom_raw_target"]
                            ),
                        }
                    )
            if "macro_gbm" in lookup and "macro_ridge" in lookup:
                increment_rows.append(
                    {
                        "period": period_name,
                        "memory_scheme": memory_name,
                        "comparison": "macro_gbm_minus_macro_ridge",
                        "mean_ic_increment": float(lookup["macro_gbm"]["mean_rank_ic"] - lookup["macro_ridge"]["mean_rank_ic"]),
                        "tail_spread_increment": float(
                            lookup["macro_gbm"]["mean_top_minus_bottom_raw_target"]
                            - lookup["macro_ridge"]["mean_top_minus_bottom_raw_target"]
                        ),
                    }
                )

    macro_importance_summary: dict[str, Any] = {}
    if not importance.empty:
        for (memory_name, model_name), g in importance.groupby(["memory_scheme", "model"]):
            s = g.groupby("feature")["importance"].mean().sort_values(ascending=False)
            macro_importance_summary[f"{memory_name}:{model_name}"] = {
                "top10": [{"feature": k, "importance": float(v)} for k, v in s.head(10).items()],
                "macro_or_interaction_share": float(
                    s[[k for k in s.index if k in MACRO_STATES or "__x__" in k]].sum()
                ),
            }

    pred.to_csv(out_dir / "experiment_009_oos_predictions.csv", index=False)
    anchor_metrics.to_csv(out_dir / "experiment_009_anchor_metrics.csv", index=False)
    yearly.to_csv(out_dir / "experiment_009_yearly_metrics.csv", index=False)
    support.to_csv(out_dir / "experiment_009_fold_support.csv", index=False)
    importance.to_csv(out_dir / "experiment_009_feature_importance_by_fold.csv", index=False)
    macro_frame.reset_index().to_csv(out_dir / "experiment_009_macro_state.csv", index=False)
    pd.DataFrame(increment_rows).to_csv(out_dir / "experiment_009_macro_increment.csv", index=False)

    report = {
        "experiment": "ML_LAB_EXPERIMENT_009_MACRO_RATE_STATE_CROSS_SECTIONAL",
        "status": "EXPLORATORY_NONCONFIRMATORY",
        "boundary": "Exploratory ML Lab only; no Core/runtime/portfolio/capital implication.",
        "design": {
            "source_experiment_family": "ML_LAB_EXPERIMENT_005_TO_008",
            "memory_schemes": MEMORY_SCHEMES,
            "primary_memory_scheme": "trailing_3y",
            "price_feature_count": len(PRICE_FEATURES),
            "macro_state_features": list(MACRO_STATES),
            "interaction_bases": list(INTERACTION_BASES),
            "interaction_feature_count": len(INTERACTION_FEATURES),
            "augmented_feature_count": len(AUGMENTED_FEATURES),
            "target_changed": False,
            "model_hyperparameters_changed": False,
            "annual_target_embargo": True,
            "reserved_2025_campaign50_holdout_used": False,
            "last_allowed_date": str(exp5.LAST_ALLOWED_DATE.date()),
        },
        "sources": {
            "fred": {
                series: {
                    "cache_file": str(source_paths[series]),
                    "sha256": _sha256(source_paths[series]),
                    "rows": int(len(fred[series])),
                    "first": str(fred[series].index.min().date()),
                    "last": str(fred[series].index.max().date()),
                }
                for series in FRED_SERIES
            },
            "vix": {
                "path": str(vix_path),
                "sha256": _sha256(vix_path),
                "rows": int(len(vix)),
                "first": str(vix.index.min().date()),
                "last": str(vix.index.max().date()),
            },
        },
        "calendar": {
            "common_etf_sessions": int(len(calendar)),
            "eligible_panel_rows": int(len(panel)),
            "eligible_panel_anchors": int(panel["timestamp"].nunique()),
            "first_eligible_anchor": str(panel["timestamp"].min().date()),
            "last_eligible_anchor": str(panel["timestamp"].max().date()),
        },
        "full_model_summary": summary_rows,
        "post_2022_2024_model_summary": post_rows,
        "macro_increment_summary": increment_rows,
        "macro_feature_importance": macro_importance_summary,
        "artifact_files": {
            "oos_predictions": "experiment_009_oos_predictions.csv",
            "anchor_metrics": "experiment_009_anchor_metrics.csv",
            "yearly_metrics": "experiment_009_yearly_metrics.csv",
            "fold_support": "experiment_009_fold_support.csv",
            "feature_importance_by_fold": "experiment_009_feature_importance_by_fold.csv",
            "macro_state": "experiment_009_macro_state.csv",
            "macro_increment": "experiment_009_macro_increment.csv",
        },
    }
    (out_dir / "experiment_009_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

