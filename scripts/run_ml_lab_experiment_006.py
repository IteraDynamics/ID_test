from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import scripts.run_ml_lab_experiment_005 as exp005

TOP_FEATURES = [
    "vol_60d_xrank",
    "ret_120d_xrank",
    "vol_ratio_20_60_xrank",
    "drawdown_120_xrank",
    "vol_20d_xrank",
]
PRE_YEARS = set(range(2012, 2022))
POST_YEARS = {2022, 2023, 2024}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ML Lab Experiment 006: cross-sectional nonlinear stability audit")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--exp005-dir", default="artifacts/ml_lab_experiment_005")
    p.add_argument("--output-dir", default="artifacts/ml_lab_experiment_006")
    return p.parse_args()


def _load_exp005_artifacts(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    required = {
        "pred": root / "experiment_005_oos_predictions.csv",
        "importance": root / "experiment_005_feature_importance_by_fold.csv",
        "yearly": root / "experiment_005_yearly_metrics.csv",
        "asset": root / "experiment_005_asset_diagnostics.csv",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("MISSING_EXPERIMENT_005_ARTIFACTS:\n" + "\n".join(missing))

    pred = pd.read_csv(required["pred"])
    pred["timestamp"] = pd.to_datetime(pred["timestamp"], utc=True)
    importance = pd.read_csv(required["importance"])
    yearly = pd.read_csv(required["yearly"])
    asset = pd.read_csv(required["asset"])
    return pred, importance, yearly, asset


def _rebuild_panel(data_dir: Path) -> pd.DataFrame:
    frames = exp005._load_universe(data_dir)
    calendar = exp005._common_calendar(frames)
    panel = exp005._build_panel(frames, calendar)
    panel["timestamp"] = pd.to_datetime(panel["timestamp"], utc=True)
    panel["target_end_date"] = pd.to_datetime(panel["target_end_date"], utc=True)
    panel["test_year"] = panel["timestamp"].dt.year.astype(int)
    return panel[(panel["test_year"] >= 2012) & (panel["test_year"] <= 2024)].copy()


def _safe_spearman(x: pd.Series, y: pd.Series) -> float | None:
    if len(x) < 3 or x.nunique() < 2 or y.nunique() < 2:
        return None
    value = x.corr(y, method="spearman")
    return None if pd.isna(value) else float(value)


def _feature_ic_by_year(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year in sorted(panel["test_year"].unique()):
        year_frame = panel[panel["test_year"] == year]
        for feature in exp005.FEATURES:
            anchor_ics: list[float] = []
            for _, g in year_frame.groupby("timestamp", sort=True):
                ic = _safe_spearman(g[feature].astype(float), g["target_rank"].astype(float))
                if ic is not None:
                    anchor_ics.append(ic)
            rows.append(
                {
                    "test_year": int(year),
                    "feature": feature,
                    "anchors": int(len(anchor_ics)),
                    "mean_rank_ic": float(np.mean(anchor_ics)) if anchor_ics else None,
                    "median_rank_ic": float(np.median(anchor_ics)) if anchor_ics else None,
                    "positive_ic_fraction": float(np.mean(np.array(anchor_ics) > 0)) if anchor_ics else None,
                }
            )
    return pd.DataFrame(rows)


def _feature_ic_pre_post(feature_ic: pd.DataFrame) -> pd.DataFrame:
    f = feature_ic.copy()
    f["period"] = np.where(f["test_year"].isin(PRE_YEARS), "pre_2012_2021", "post_2022_2024")
    return (
        f.groupby(["feature", "period"])
        .agg(
            years=("test_year", "size"),
            mean_yearly_rank_ic=("mean_rank_ic", "mean"),
            median_yearly_rank_ic=("mean_rank_ic", "median"),
            positive_year_fraction=("mean_rank_ic", lambda s: float((s > 0).mean())),
        )
        .reset_index()
    )


def _importance_evolution(importance: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    annual = importance.copy()
    annual["test_year"] = annual["test_year"].astype(int)
    annual["period"] = np.where(annual["test_year"].isin(PRE_YEARS), "pre_2012_2021", "post_2022_2024")
    summary = (
        annual.groupby(["model", "feature", "period"])
        .agg(mean_importance=("importance", "mean"), median_importance=("importance", "median"), years=("test_year", "size"))
        .reset_index()
    )
    pivot = summary.pivot_table(index=["model", "feature"], columns="period", values="mean_importance").reset_index()
    for col in ("pre_2012_2021", "post_2022_2024"):
        if col not in pivot.columns:
            pivot[col] = np.nan
    pivot["post_minus_pre"] = pivot["post_2022_2024"] - pivot["pre_2012_2021"]
    pivot["abs_change"] = pivot["post_minus_pre"].abs()
    return annual, pivot.sort_values(["model", "abs_change"], ascending=[True, False])


def _conditional_geometry(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for period_name, years in (("pre_2012_2021", PRE_YEARS), ("post_2022_2024", POST_YEARS)):
        subset = panel[panel["test_year"].isin(years)].copy()
        for feature in TOP_FEATURES:
            # Features are already cross-sectional percentile ranks. Use fixed quintile edges.
            q = np.minimum(5, np.maximum(1, np.ceil(subset[feature].astype(float) * 5).astype(int)))
            tmp = subset[["timestamp", "ticker", feature, "target_rank", "target_raw"]].copy()
            tmp["quintile"] = q
            for quintile, g in tmp.groupby("quintile", sort=True):
                rows.append(
                    {
                        "period": period_name,
                        "feature": feature,
                        "quintile": int(quintile),
                        "rows": int(len(g)),
                        "anchors": int(g["timestamp"].nunique()),
                        "feature_mean": float(g[feature].mean()),
                        "mean_target_rank": float(g["target_rank"].mean()),
                        "mean_target_raw": float(g["target_raw"].mean()),
                    }
                )
    return pd.DataFrame(rows)


def _prediction_enrichment(pred: pd.DataFrame) -> pd.DataFrame:
    p = pred.copy()
    p["test_year"] = p["test_year"].astype(int)
    p["period"] = np.where(p["test_year"].isin(PRE_YEARS), "pre_2012_2021", "post_2022_2024")
    p["score_rank"] = p.groupby(["timestamp", "model"])["score"].rank(method="average", pct=True)
    p["rank_error"] = p["score_rank"] - p["target_rank"]
    p["rank_error_abs"] = p["rank_error"].abs()
    p["centered_product"] = (p["score_rank"] - 0.5) * (p["target_rank"] - 0.5)
    return p


def _asset_concentration(pred: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = (
        pred.groupby(["period", "model", "ticker"])
        .agg(
            rows=("ticker", "size"),
            mean_abs_rank_error=("rank_error_abs", "mean"),
            mean_centered_rank_product=("centered_product", "mean"),
            mean_signed_rank_error=("rank_error", "mean"),
        )
        .reset_index()
    )

    pivot = summary[summary["model"].isin(["gbm", "ridge"])].pivot_table(
        index=["period", "ticker"], columns="model", values="mean_abs_rank_error"
    ).reset_index()
    pivot["gbm_minus_ridge_error"] = pivot["gbm"] - pivot["ridge"]
    by_period = pivot.pivot(index="ticker", columns="period", values="gbm_minus_ridge_error").reset_index()
    for col in ("pre_2012_2021", "post_2022_2024"):
        if col not in by_period.columns:
            by_period[col] = np.nan
    by_period["deterioration_post_minus_pre"] = by_period["post_2022_2024"] - by_period["pre_2012_2021"]
    positive = by_period["deterioration_post_minus_pre"].clip(lower=0)
    denom = float(positive.sum())
    by_period["share_of_positive_deterioration"] = positive / denom if denom > 0 else 0.0
    return summary, by_period.sort_values("deterioration_post_minus_pre", ascending=False)


def _dispersion(pred: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    anchor = (
        pred.groupby(["timestamp", "test_year", "period", "model"])
        .agg(
            score_std=("score", "std"),
            score_range=("score", lambda s: float(s.max() - s.min())),
            target_rank_std=("target_rank", "std"),
        )
        .reset_index()
    )
    yearly = (
        anchor.groupby(["test_year", "model"])
        .agg(
            anchors=("timestamp", "size"),
            mean_score_std=("score_std", "mean"),
            median_score_std=("score_std", "median"),
            mean_score_range=("score_range", "mean"),
            mean_target_rank_std=("target_rank_std", "mean"),
        )
        .reset_index()
    )
    return anchor, yearly


def _tail_error(pred: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    for (ts, year, period, model), g in pred.groupby(["timestamp", "test_year", "period", "model"], sort=True):
        g = g.sort_values("score_rank")
        n_q = max(1, int(math.ceil(len(g) * 0.25)))
        bottom = g.head(n_q)
        top = g.tail(n_q)
        extreme = pd.concat([bottom, top], ignore_index=True)
        rows.append(
            {
                "timestamp": ts,
                "test_year": int(year),
                "period": period,
                "model": model,
                "top_actual_target_rank": float(top["target_rank"].mean()),
                "bottom_actual_target_rank": float(bottom["target_rank"].mean()),
                "top_minus_bottom_target_rank": float(top["target_rank"].mean() - bottom["target_rank"].mean()),
                "extreme_mean_abs_rank_error": float(extreme["rank_error_abs"].mean()),
                "extreme_large_error_rate": float((extreme["rank_error_abs"] >= 0.50).mean()),
            }
        )
    anchor = pd.DataFrame(rows)
    yearly = (
        anchor.groupby(["test_year", "model"])
        .agg(
            anchors=("timestamp", "size"),
            mean_top_actual_target_rank=("top_actual_target_rank", "mean"),
            mean_bottom_actual_target_rank=("bottom_actual_target_rank", "mean"),
            mean_top_minus_bottom_target_rank=("top_minus_bottom_target_rank", "mean"),
            mean_extreme_abs_rank_error=("extreme_mean_abs_rank_error", "mean"),
            mean_extreme_large_error_rate=("extreme_large_error_rate", "mean"),
        )
        .reset_index()
    )
    return anchor, yearly


def _period_model_summary(pred: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (period, model), g in pred.groupby(["period", "model"]):
        anchor_ics: list[float] = []
        anchor_spreads: list[float] = []
        for _, a in g.groupby("timestamp"):
            ic = _safe_spearman(a["score_rank"], a["target_rank"])
            if ic is not None:
                anchor_ics.append(ic)
            n_q = max(1, int(math.ceil(len(a) * 0.25)))
            ordered = a.sort_values("score_rank")
            anchor_spreads.append(float(ordered.tail(n_q)["target_rank"].mean() - ordered.head(n_q)["target_rank"].mean()))
        rows.append(
            {
                "period": period,
                "model": model,
                "anchors": int(len(anchor_ics)),
                "mean_rank_ic": float(np.mean(anchor_ics)) if anchor_ics else None,
                "median_rank_ic": float(np.median(anchor_ics)) if anchor_ics else None,
                "positive_ic_fraction": float(np.mean(np.array(anchor_ics) > 0)) if anchor_ics else None,
                "mean_top_minus_bottom_target_rank": float(np.mean(anchor_spreads)) if anchor_spreads else None,
            }
        )
    return pd.DataFrame(rows)


def _diagnostic_flags(feature_prepost: pd.DataFrame, asset_det: pd.DataFrame, period_models: pd.DataFrame, tail_yearly: pd.DataFrame) -> dict[str, Any]:
    top = feature_prepost[feature_prepost["feature"].isin(TOP_FEATURES)].pivot_table(
        index="feature", columns="period", values="mean_yearly_rank_ic"
    )
    top_changes: dict[str, float] = {}
    sign_flips = 0
    for feature, row in top.iterrows():
        pre = row.get("pre_2012_2021", np.nan)
        post = row.get("post_2022_2024", np.nan)
        if pd.notna(pre) and pd.notna(post):
            top_changes[str(feature)] = float(post - pre)
            if np.sign(pre) != 0 and np.sign(post) != 0 and np.sign(pre) != np.sign(post):
                sign_flips += 1

    pm = period_models.pivot(index="period", columns="model", values="mean_rank_ic")
    pre_gap = float(pm.loc["pre_2012_2021", "gbm"] - pm.loc["pre_2012_2021", "ridge"])
    post_gap = float(pm.loc["post_2022_2024", "gbm"] - pm.loc["post_2022_2024", "ridge"])

    top_asset_share = float(asset_det["share_of_positive_deterioration"].head(3).sum()) if len(asset_det) else 0.0

    ty = tail_yearly.pivot(index="test_year", columns="model", values="mean_top_minus_bottom_target_rank")
    post_tail_gap = float((ty.loc[ty.index.isin(POST_YEARS), "gbm"] - ty.loc[ty.index.isin(POST_YEARS), "ridge"]).mean())

    flags: list[str] = []
    if sign_flips >= 2 or sum(abs(v) >= 0.05 for v in top_changes.values()) >= 2:
        flags.append("RELATIONSHIP_SHIFT")
    if pre_gap > 0 and post_gap < 0:
        flags.append("MODEL_BRITTLENESS")
    if top_asset_share >= 0.60:
        flags.append("ASSET_CONCENTRATION")
    if post_tail_gap < -0.03:
        flags.append("TAIL_FAILURE")
    if not flags:
        flags.append("MIXED_OR_UNRESOLVED")

    return {
        "flags": flags,
        "criteria_are_descriptive_not_validation_gates": True,
        "pre_gbm_minus_ridge_mean_ic": pre_gap,
        "post_gbm_minus_ridge_mean_ic": post_gap,
        "top_feature_post_minus_pre_ic_changes": top_changes,
        "top_feature_sign_flips": int(sign_flips),
        "top3_asset_share_of_positive_deterioration": top_asset_share,
        "post_gbm_minus_ridge_tail_spread": post_tail_gap,
    }


def main() -> None:
    args = parse_args()
    exp005_dir = Path(args.exp005_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pred_raw, importance, yearly005, asset005 = _load_exp005_artifacts(exp005_dir)
    panel = _rebuild_panel(Path(args.data_dir))

    # Guard the Campaign #50 reserved year explicitly.
    if panel["timestamp"].max() >= pd.Timestamp("2025-01-01", tz="UTC"):
        raise ValueError("RESERVED_2025_HOLDOUT_EXPOSURE")
    if pred_raw["timestamp"].max() >= pd.Timestamp("2025-01-01", tz="UTC"):
        raise ValueError("EXPERIMENT_005_ARTIFACT_CONTAINS_RESERVED_2025")

    feature_ic = _feature_ic_by_year(panel)
    feature_prepost = _feature_ic_pre_post(feature_ic)
    importance_annual, importance_shift = _importance_evolution(importance)
    conditional = _conditional_geometry(panel)

    pred = _prediction_enrichment(pred_raw)
    asset_period, asset_deterioration = _asset_concentration(pred)
    dispersion_anchor, dispersion_yearly = _dispersion(pred)
    tail_anchor, tail_yearly = _tail_error(pred)
    period_models = _period_model_summary(pred)
    diagnostic = _diagnostic_flags(feature_prepost, asset_deterioration, period_models, tail_yearly)

    feature_ic.to_csv(out_dir / "experiment_006_feature_ic_by_year.csv", index=False)
    feature_prepost.to_csv(out_dir / "experiment_006_feature_ic_pre_post.csv", index=False)
    importance_annual.to_csv(out_dir / "experiment_006_importance_by_year.csv", index=False)
    importance_shift.to_csv(out_dir / "experiment_006_importance_pre_post_shift.csv", index=False)
    conditional.to_csv(out_dir / "experiment_006_conditional_feature_geometry.csv", index=False)
    asset_period.to_csv(out_dir / "experiment_006_asset_period_diagnostics.csv", index=False)
    asset_deterioration.to_csv(out_dir / "experiment_006_asset_deterioration_attribution.csv", index=False)
    dispersion_anchor.to_csv(out_dir / "experiment_006_dispersion_by_anchor.csv", index=False)
    dispersion_yearly.to_csv(out_dir / "experiment_006_dispersion_by_year.csv", index=False)
    tail_anchor.to_csv(out_dir / "experiment_006_tail_error_by_anchor.csv", index=False)
    tail_yearly.to_csv(out_dir / "experiment_006_tail_error_by_year.csv", index=False)
    period_models.to_csv(out_dir / "experiment_006_period_model_summary.csv", index=False)

    top_feature_period = feature_prepost[feature_prepost["feature"].isin(TOP_FEATURES)].to_dict(orient="records")
    top_asset_records = asset_deterioration.head(8).to_dict(orient="records")
    importance_top_changes = {
        model: importance_shift[importance_shift["model"] == model].head(8).to_dict(orient="records")
        for model in ("ridge", "gbm")
    }

    report = {
        "experiment": "ML_LAB_EXPERIMENT_006_CROSS_SECTIONAL_STABILITY_AUDIT",
        "status": "EXPLORATORY_DIAGNOSTIC_NONCONFIRMATORY",
        "boundary": "No model refit, no tuning, no 2025 holdout use, no Core/runtime/portfolio/capital implication.",
        "design": {
            "source_experiment": "ML_LAB_EXPERIMENT_005_CROSS_SECTIONAL_RANKING",
            "model_refit_performed": False,
            "hyperparameters_changed": False,
            "training_window_changed": False,
            "features_changed": False,
            "target_changed": False,
            "reserved_2025_campaign50_holdout_used": False,
            "pre_period": "2012-2021",
            "post_period": "2022-2024",
            "top_features_audited": TOP_FEATURES,
        },
        "diagnostic_summary": diagnostic,
        "period_model_summary": period_models.to_dict(orient="records"),
        "top_feature_pre_post_ic": top_feature_period,
        "top_asset_deterioration_attribution": top_asset_records,
        "largest_importance_changes": importance_top_changes,
        "artifact_files": {
            "feature_ic_by_year": "experiment_006_feature_ic_by_year.csv",
            "feature_ic_pre_post": "experiment_006_feature_ic_pre_post.csv",
            "importance_by_year": "experiment_006_importance_by_year.csv",
            "importance_pre_post_shift": "experiment_006_importance_pre_post_shift.csv",
            "conditional_feature_geometry": "experiment_006_conditional_feature_geometry.csv",
            "asset_period_diagnostics": "experiment_006_asset_period_diagnostics.csv",
            "asset_deterioration_attribution": "experiment_006_asset_deterioration_attribution.csv",
            "dispersion_by_anchor": "experiment_006_dispersion_by_anchor.csv",
            "dispersion_by_year": "experiment_006_dispersion_by_year.csv",
            "tail_error_by_anchor": "experiment_006_tail_error_by_anchor.csv",
            "tail_error_by_year": "experiment_006_tail_error_by_year.csv",
            "period_model_summary": "experiment_006_period_model_summary.csv",
        },
    }
    (out_dir / "experiment_006_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
