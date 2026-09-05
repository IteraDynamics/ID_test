from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


from research.ml_lab.ohlcv_v1 import read_ohlcv




from research.ml_lab.cross_sectional_v1 import (
    UNIVERSE,
    FEATURES,
    TARGET_HORIZON,
    ANCHOR_STEP,
    TEST_START_YEAR,
    LAST_ALLOWED_DATE,
    MIN_TRAIN_ROWS,
    RANDOM_STATE,
    _load_universe,
    _common_calendar,
    _asset_features,
    _build_panel,
    _ridge,
    _gbm,
    _importance,
    _anchor_metrics,
)

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ML Lab Experiment 005: cross-sectional ETF ranking")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--output-dir", default="artifacts/ml_lab_experiment_005")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    frames = _load_universe(data_dir)
    calendar = _common_calendar(frames)
    panel = _build_panel(frames, calendar)

    predictions: list[pd.DataFrame] = []
    importance_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []

    years = sorted(y for y in panel["timestamp"].dt.year.unique() if TEST_START_YEAR <= y <= 2024)
    for year in years:
        test = panel[panel["timestamp"].dt.year == year].copy()
        if test.empty:
            continue
        test_start = test["timestamp"].min()
        train = panel[(panel["timestamp"] < test_start) & (panel["target_end_date"] < test_start)].copy()
        eligible = len(train) >= MIN_TRAIN_ROWS and train["timestamp"].nunique() >= 50
        support_rows.append(
            {
                "test_year": year,
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

        fitted = {"ridge": _ridge(), "gbm": _gbm()}
        for name, model in fitted.items():
            model.fit(train[FEATURES].astype(float), train["target_rank"].astype(float))
            for feature, value in _importance(model, name).items():
                importance_rows.append(
                    {"test_year": year, "model": name, "feature": feature, "importance": value}
                )

        for model_name in ("naive_momentum", "ridge", "gbm"):
            p = test[["timestamp", "ticker", "target_raw", "target_rank"]].copy()
            p["test_year"] = year
            p["model"] = model_name
            if model_name == "naive_momentum":
                p["score"] = test["ret_60d_xrank"].to_numpy()
            else:
                p["score"] = fitted[model_name].predict(test[FEATURES].astype(float))
            predictions.append(p)

    if not predictions:
        raise ValueError("NO_ELIGIBLE_OOS_FOLDS")

    pred = pd.concat(predictions, ignore_index=True)
    importance = pd.DataFrame(importance_rows)
    support = pd.DataFrame(support_rows)

    anchor_rows: list[dict[str, Any]] = []
    for (_, _), group in pred.groupby(["timestamp", "model"], sort=True):
        model_name = str(group["model"].iloc[0])
        anchor_rows.append(_anchor_metrics(group, model_name))
    anchor_metrics = pd.DataFrame(anchor_rows)

    summary_rows: list[dict[str, Any]] = []
    for model_name, group in anchor_metrics.groupby("model"):
        summary_rows.append(
            {
                "model": model_name,
                "anchors": int(len(group)),
                "mean_rank_ic": float(group["rank_ic"].mean()),
                "median_rank_ic": float(group["rank_ic"].median()),
                "positive_ic_fraction": float((group["rank_ic"] > 0).mean()),
                "mean_top_minus_bottom_raw_target": float(group["top_minus_bottom_raw_target"].mean()),
                "median_top_minus_bottom_raw_target": float(group["top_minus_bottom_raw_target"].median()),
            }
        )

    yearly = (
        anchor_metrics.groupby(["test_year", "model"])
        .agg(
            anchors=("rank_ic", "size"),
            mean_rank_ic=("rank_ic", "mean"),
            median_rank_ic=("rank_ic", "median"),
            positive_ic_fraction=("rank_ic", lambda s: float((s > 0).mean())),
            mean_top_minus_bottom_raw_target=("top_minus_bottom_raw_target", "mean"),
        )
        .reset_index()
    )

    pivot = yearly.pivot(index="test_year", columns="model", values="mean_rank_ic")
    delta_rows: list[dict[str, Any]] = []
    if "gbm" in pivot.columns and "ridge" in pivot.columns:
        for year, row in pivot.iterrows():
            delta_rows.append(
                {
                    "test_year": int(year),
                    "gbm_mean_ic_minus_ridge": float(row["gbm"] - row["ridge"]),
                }
            )

    asset_diag = pred.copy()
    asset_diag["score_rank"] = asset_diag.groupby(["timestamp", "model"])["score"].rank(method="average", pct=True)
    asset_diag["rank_error_abs"] = (asset_diag["score_rank"] - asset_diag["target_rank"]).abs()
    asset_diag["centered_product"] = (asset_diag["score_rank"] - 0.5) * (asset_diag["target_rank"] - 0.5)
    asset_summary = (
        asset_diag.groupby(["model", "ticker"])
        .agg(
            rows=("ticker", "size"),
            mean_abs_rank_error=("rank_error_abs", "mean"),
            mean_centered_rank_product=("centered_product", "mean"),
        )
        .reset_index()
    )

    feature_summary: dict[str, Any] = {}
    for model_name in ("ridge", "gbm"):
        s = (
            importance[importance["model"] == model_name]
            .groupby("feature")["importance"]
            .mean()
            .sort_values(ascending=False)
        )
        feature_summary[model_name] = {
            "mean_importance": {k: float(v) for k, v in s.items()},
            "top5": list(s.head(5).index),
        }

    pred.to_csv(out_dir / "experiment_005_oos_predictions.csv", index=False)
    anchor_metrics.to_csv(out_dir / "experiment_005_anchor_metrics.csv", index=False)
    yearly.to_csv(out_dir / "experiment_005_yearly_metrics.csv", index=False)
    importance.to_csv(out_dir / "experiment_005_feature_importance_by_fold.csv", index=False)
    support.to_csv(out_dir / "experiment_005_fold_support.csv", index=False)
    asset_summary.to_csv(out_dir / "experiment_005_asset_diagnostics.csv", index=False)

    report = {
        "experiment": "ML_LAB_EXPERIMENT_005_CROSS_SECTIONAL_RANKING",
        "status": "EXPLORATORY_NONCONFIRMATORY",
        "boundary": "Exploratory ML Lab only; no Core/runtime/portfolio/capital implication.",
        "universe": UNIVERSE,
        "design": {
            "last_allowed_date": str(LAST_ALLOWED_DATE.date()),
            "reserved_2025_campaign50_holdout_used": False,
            "anchor_step_common_sessions": ANCHOR_STEP,
            "target_horizon_common_sessions": TARGET_HORIZON,
            "target": "within-anchor percentile rank of forward 20-session return divided by trailing 60-session vol * sqrt(20)",
            "features": FEATURES,
            "models": {
                "naive_momentum": "cross-sectional trailing 60-session return rank",
                "ridge": "StandardScaler + Ridge(alpha=10.0)",
                "gbm": "GradientBoostingRegressor(n_estimators=200,max_depth=2,learning_rate=0.04,random_state=42)",
            },
            "test_start_year": TEST_START_YEAR,
            "annual_target_embargo": True,
        },
        "calendar": {
            "common_sessions": int(len(calendar)),
            "first_common_session": str(calendar.min().date()),
            "last_common_session": str(calendar.max().date()),
            "panel_rows": int(len(panel)),
            "panel_anchors": int(panel["timestamp"].nunique()),
        },
        "pooled_model_summary": summary_rows,
        "gbm_vs_ridge_yearly_delta": delta_rows,
        "feature_importance": feature_summary,
        "artifact_files": {
            "oos_predictions": "experiment_005_oos_predictions.csv",
            "anchor_metrics": "experiment_005_anchor_metrics.csv",
            "yearly_metrics": "experiment_005_yearly_metrics.csv",
            "feature_importance_by_fold": "experiment_005_feature_importance_by_fold.csv",
            "fold_support": "experiment_005_fold_support.csv",
            "asset_diagnostics": "experiment_005_asset_diagnostics.csv",
        },
    }
    (out_dir / "experiment_005_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

