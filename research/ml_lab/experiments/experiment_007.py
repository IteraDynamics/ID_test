from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research.ml_lab import cross_sectional_v1 as exp5

MEMORY_SCHEMES: dict[str, int | None] = {
    "expanding": None,
    "trailing_5y": 5,
    "trailing_3y": 3,
}
PRE_END_YEAR = 2021
POST_START_YEAR = 2022


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ML Lab Experiment 007: training-memory adaptivity")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--output-dir", default="artifacts/ml_lab_experiment_007")
    return p.parse_args()


def _training_slice(panel: pd.DataFrame, test_start: pd.Timestamp, years: int | None) -> pd.DataFrame:
    # Preserve Experiment 005's strict target-end embargo for every memory scheme.
    eligible = panel[(panel["timestamp"] < test_start) & (panel["target_end_date"] < test_start)].copy()
    if years is not None:
        lower = test_start - pd.DateOffset(years=years)
        eligible = eligible[eligible["timestamp"] >= lower].copy()
    return eligible


def _summary(group: pd.DataFrame) -> dict[str, Any]:
    return {
        "anchors": int(len(group)),
        "mean_rank_ic": float(group["rank_ic"].mean()),
        "median_rank_ic": float(group["rank_ic"].median()),
        "positive_ic_fraction": float((group["rank_ic"] > 0).mean()),
        "mean_top_minus_bottom_raw_target": float(group["top_minus_bottom_raw_target"].mean()),
        "median_top_minus_bottom_raw_target": float(group["top_minus_bottom_raw_target"].median()),
    }


def _period_label(year: int) -> str:
    return "pre_2012_2021" if year <= PRE_END_YEAR else "post_2022_2024"


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    frames = exp5._load_universe(data_dir)
    calendar = exp5._common_calendar(frames)
    panel = exp5._build_panel(frames, calendar)

    predictions: list[pd.DataFrame] = []
    importance_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []

    years = sorted(y for y in panel["timestamp"].dt.year.unique() if exp5.TEST_START_YEAR <= y <= 2024)

    for year in years:
        test = panel[panel["timestamp"].dt.year == year].copy()
        if test.empty:
            continue
        test_start = test["timestamp"].min()

        # Memory-independent naive reference, emitted once.
        naive = test[["timestamp", "ticker", "target_raw", "target_rank"]].copy()
        naive["test_year"] = year
        naive["memory_scheme"] = "not_applicable"
        naive["model"] = "naive_momentum"
        naive["score"] = test["ret_60d_xrank"].to_numpy()
        predictions.append(naive)

        for memory_name, memory_years in MEMORY_SCHEMES.items():
            train = _training_slice(panel, test_start, memory_years)
            eligible = len(train) >= exp5.MIN_TRAIN_ROWS and train["timestamp"].nunique() >= 50
            support_rows.append(
                {
                    "test_year": year,
                    "memory_scheme": memory_name,
                    "memory_years": memory_years,
                    "train_rows": int(len(train)),
                    "train_anchors": int(train["timestamp"].nunique()),
                    "test_rows": int(len(test)),
                    "test_anchors": int(test["timestamp"].nunique()),
                    "test_start": str(test_start.date()),
                    "min_train_anchor": str(train["timestamp"].min().date()) if len(train) else None,
                    "max_train_anchor": str(train["timestamp"].max().date()) if len(train) else None,
                    "max_train_target_end": str(train["target_end_date"].max().date()) if len(train) else None,
                    "eligible": bool(eligible),
                }
            )
            if not eligible:
                continue

            fitted = {"ridge": exp5._ridge(), "gbm": exp5._gbm()}
            for model_name, model in fitted.items():
                model.fit(train[exp5.FEATURES].astype(float), train["target_rank"].astype(float))
                for feature, value in exp5._importance(model, model_name).items():
                    importance_rows.append(
                        {
                            "test_year": year,
                            "memory_scheme": memory_name,
                            "model": model_name,
                            "feature": feature,
                            "importance": value,
                        }
                    )

                p = test[["timestamp", "ticker", "target_raw", "target_rank"]].copy()
                p["test_year"] = year
                p["memory_scheme"] = memory_name
                p["model"] = model_name
                p["score"] = model.predict(test[exp5.FEATURES].astype(float))
                predictions.append(p)

    if not predictions:
        raise ValueError("NO_ELIGIBLE_OOS_FOLDS")

    pred = pd.concat(predictions, ignore_index=True)
    importance = pd.DataFrame(importance_rows)
    support = pd.DataFrame(support_rows)

    anchor_rows: list[dict[str, Any]] = []
    for (timestamp, memory_scheme, model_name), group in pred.groupby(
        ["timestamp", "memory_scheme", "model"], sort=True
    ):
        score_rank = group["score"].rank(method="average", pct=True)
        ic = float(score_rank.corr(group["target_rank"], method="spearman"))
        n_q = max(1, int(np.ceil(len(group) * 0.25)))
        ordered = group.assign(score_rank=score_rank).sort_values("score_rank")
        spread = float(
            ordered.tail(n_q)["target_raw"].mean() - ordered.head(n_q)["target_raw"].mean()
        )
        anchor_rows.append(
            {
                "timestamp": timestamp,
                "test_year": int(pd.Timestamp(timestamp).year),
                "period": _period_label(int(pd.Timestamp(timestamp).year)),
                "memory_scheme": memory_scheme,
                "model": model_name,
                "rank_ic": ic,
                "top_minus_bottom_raw_target": spread,
                "assets": int(len(group)),
            }
        )
    anchor_metrics = pd.DataFrame(anchor_rows)

    yearly = (
        anchor_metrics.groupby(["test_year", "period", "memory_scheme", "model"])
        .agg(
            anchors=("rank_ic", "size"),
            mean_rank_ic=("rank_ic", "mean"),
            median_rank_ic=("rank_ic", "median"),
            positive_ic_fraction=("rank_ic", lambda s: float((s > 0).mean())),
            mean_top_minus_bottom_raw_target=("top_minus_bottom_raw_target", "mean"),
        )
        .reset_index()
    )

    full_summary_rows: list[dict[str, Any]] = []
    for (memory_scheme, model_name), group in anchor_metrics.groupby(["memory_scheme", "model"]):
        row = {"memory_scheme": memory_scheme, "model": model_name}
        row.update(_summary(group))
        full_summary_rows.append(row)

    period_summary_rows: list[dict[str, Any]] = []
    for (period, memory_scheme, model_name), group in anchor_metrics.groupby(
        ["period", "memory_scheme", "model"]
    ):
        row = {"period": period, "memory_scheme": memory_scheme, "model": model_name}
        row.update(_summary(group))
        period_summary_rows.append(row)

    yearly_delta_rows: list[dict[str, Any]] = []
    learned_yearly = yearly[yearly["model"].isin(["ridge", "gbm"])].copy()
    for memory_name in MEMORY_SCHEMES:
        subset = learned_yearly[learned_yearly["memory_scheme"] == memory_name]
        pivot = subset.pivot(index="test_year", columns="model", values="mean_rank_ic")
        if "gbm" not in pivot.columns or "ridge" not in pivot.columns:
            continue
        for year, row in pivot.iterrows():
            yearly_delta_rows.append(
                {
                    "test_year": int(year),
                    "period": _period_label(int(year)),
                    "memory_scheme": memory_name,
                    "gbm_mean_ic_minus_ridge": float(row["gbm"] - row["ridge"]),
                }
            )

    # Direct adaptivity comparison to the expanding baseline, by model and period.
    adaptivity_rows: list[dict[str, Any]] = []
    period_df = pd.DataFrame(period_summary_rows)
    for period in ("pre_2012_2021", "post_2022_2024"):
        for model_name in ("ridge", "gbm"):
            base = period_df[
                (period_df["period"] == period)
                & (period_df["memory_scheme"] == "expanding")
                & (period_df["model"] == model_name)
            ]
            if base.empty:
                continue
            base_ic = float(base.iloc[0]["mean_rank_ic"])
            base_spread = float(base.iloc[0]["mean_top_minus_bottom_raw_target"])
            for memory_name in ("trailing_5y", "trailing_3y"):
                cand = period_df[
                    (period_df["period"] == period)
                    & (period_df["memory_scheme"] == memory_name)
                    & (period_df["model"] == model_name)
                ]
                if cand.empty:
                    continue
                adaptivity_rows.append(
                    {
                        "period": period,
                        "model": model_name,
                        "memory_scheme": memory_name,
                        "mean_ic_minus_expanding": float(cand.iloc[0]["mean_rank_ic"] - base_ic),
                        "tail_spread_minus_expanding": float(
                            cand.iloc[0]["mean_top_minus_bottom_raw_target"] - base_spread
                        ),
                    }
                )

    # Post-2021 GBM minus Ridge within each memory scheme is the central diagnostic.
    post_gbm_minus_ridge: list[dict[str, Any]] = []
    post = period_df[period_df["period"] == "post_2022_2024"]
    for memory_name in MEMORY_SCHEMES:
        g = post[(post["memory_scheme"] == memory_name) & (post["model"] == "gbm")]
        r = post[(post["memory_scheme"] == memory_name) & (post["model"] == "ridge")]
        if g.empty or r.empty:
            continue
        post_gbm_minus_ridge.append(
            {
                "memory_scheme": memory_name,
                "gbm_mean_ic_minus_ridge": float(g.iloc[0]["mean_rank_ic"] - r.iloc[0]["mean_rank_ic"]),
                "gbm_tail_spread_minus_ridge": float(
                    g.iloc[0]["mean_top_minus_bottom_raw_target"]
                    - r.iloc[0]["mean_top_minus_bottom_raw_target"]
                ),
            }
        )

    feature_summary: dict[str, Any] = {}
    for memory_name in MEMORY_SCHEMES:
        feature_summary[memory_name] = {}
        for model_name in ("ridge", "gbm"):
            s = (
                importance[
                    (importance["memory_scheme"] == memory_name)
                    & (importance["model"] == model_name)
                ]
                .groupby("feature")["importance"]
                .mean()
                .sort_values(ascending=False)
            )
            feature_summary[memory_name][model_name] = {
                "mean_importance": {k: float(v) for k, v in s.items()},
                "top5": list(s.head(5).index),
            }

    pred.to_csv(out_dir / "experiment_007_oos_predictions.csv", index=False)
    anchor_metrics.to_csv(out_dir / "experiment_007_anchor_metrics.csv", index=False)
    yearly.to_csv(out_dir / "experiment_007_yearly_metrics.csv", index=False)
    importance.to_csv(out_dir / "experiment_007_feature_importance_by_fold.csv", index=False)
    support.to_csv(out_dir / "experiment_007_fold_support.csv", index=False)
    pd.DataFrame(adaptivity_rows).to_csv(out_dir / "experiment_007_adaptivity_vs_expanding.csv", index=False)
    pd.DataFrame(yearly_delta_rows).to_csv(out_dir / "experiment_007_gbm_vs_ridge_yearly_delta.csv", index=False)

    report = {
        "experiment": "ML_LAB_EXPERIMENT_007_TRAINING_MEMORY_ADAPTIVITY",
        "status": "EXPLORATORY_NONCONFIRMATORY",
        "boundary": "Exploratory ML Lab only; no Core/runtime/portfolio/capital implication.",
        "design": {
            "source_experiment": "ML_LAB_EXPERIMENT_005_CROSS_SECTIONAL_RANKING",
            "diagnostic_motivation": "Experiment 006 relationship shift and model brittleness",
            "memory_schemes": MEMORY_SCHEMES,
            "features_changed": False,
            "target_changed": False,
            "model_families_changed": False,
            "hyperparameters_changed": False,
            "annual_target_embargo": True,
            "reserved_2025_campaign50_holdout_used": False,
            "last_allowed_date": str(exp5.LAST_ALLOWED_DATE.date()),
            "test_start_year": exp5.TEST_START_YEAR,
            "features": exp5.FEATURES,
            "models": {
                "ridge": "StandardScaler + Ridge(alpha=10.0)",
                "gbm": "GradientBoostingRegressor(n_estimators=200,max_depth=2,learning_rate=0.04,random_state=42)",
                "naive_momentum": "cross-sectional trailing 60-session return rank; memory-independent reference",
            },
        },
        "calendar": {
            "common_sessions": int(len(calendar)),
            "first_common_session": str(calendar.min().date()),
            "last_common_session": str(calendar.max().date()),
            "panel_rows": int(len(panel)),
            "panel_anchors": int(panel["timestamp"].nunique()),
        },
        "full_model_summary": full_summary_rows,
        "period_model_summary": period_summary_rows,
        "post_2022_2024_gbm_vs_ridge": post_gbm_minus_ridge,
        "adaptivity_vs_expanding": adaptivity_rows,
        "gbm_vs_ridge_yearly_delta": yearly_delta_rows,
        "feature_importance": feature_summary,
        "artifact_files": {
            "oos_predictions": "experiment_007_oos_predictions.csv",
            "anchor_metrics": "experiment_007_anchor_metrics.csv",
            "yearly_metrics": "experiment_007_yearly_metrics.csv",
            "feature_importance_by_fold": "experiment_007_feature_importance_by_fold.csv",
            "fold_support": "experiment_007_fold_support.csv",
            "adaptivity_vs_expanding": "experiment_007_adaptivity_vs_expanding.csv",
            "gbm_vs_ridge_yearly_delta": "experiment_007_gbm_vs_ridge_yearly_delta.csv",
        },
    }
    (out_dir / "experiment_007_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
