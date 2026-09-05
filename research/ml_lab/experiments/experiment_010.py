from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research.ml_lab import cross_sectional_v1 as exp5

SOURCE_DIR_DEFAULT = "artifacts/ml_lab_experiment_009"
OUTPUT_DIR_DEFAULT = "artifacts/ml_lab_experiment_010"
MEMORY_SCHEMES = ("expanding", "trailing_3y")
MODELS = ("price_ridge", "price_gbm", "macro_ridge", "macro_gbm")
INTERACTION_BASES = (
    "ret_120d_xrank",
    "vol_60d_xrank",
    "vol_ratio_20_60_xrank",
    "drawdown_120_xrank",
)
MACRO_STATES = ("rate2_pct252", "curve_10y2y_pct252", "rate2_chg20", "vix_pct252")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ML Lab Experiment 010: macro interaction stability audit")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--source-dir", default=SOURCE_DIR_DEFAULT)
    p.add_argument("--output-dir", default=OUTPUT_DIR_DEFAULT)
    return p.parse_args()


def _read_csv_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"MISSING_SOURCE_ARTIFACT:{path}")
    out = pd.read_csv(path)
    if out.empty:
        raise ValueError(f"EMPTY_SOURCE_ARTIFACT:{path}")
    return out


def _normalize_timestamp(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "timestamp" not in out.columns:
        out = out.rename(columns={out.columns[0]: "timestamp"})
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce", utc=True)
    if out["timestamp"].isna().any():
        raise ValueError("TIMESTAMP_PARSE_FAILURE")
    return out


def _period(year: int) -> str:
    return "pre_2022" if year <= 2021 else "post_2022_2024"


def _rate_state(x: float) -> str:
    if x < 1.0 / 3.0:
        return "rate2_low"
    if x < 2.0 / 3.0:
        return "rate2_mid"
    return "rate2_high"


def _curve_state(x: float) -> str:
    if x < 0.0:
        return "curve_inverted"
    if x < 1.0:
        return "curve_flat"
    return "curve_steep"


def _build_regimes(macro: pd.DataFrame) -> pd.DataFrame:
    needed = ["timestamp", "rate2_pct252", "curve_10y2y", "vix_pct252", "DGS2"]
    missing = [c for c in needed if c not in macro.columns]
    if missing:
        raise ValueError(f"MACRO_STATE_COLUMNS_MISSING:{missing}")
    out = macro[needed].dropna().copy()
    out["rate_regime"] = out["rate2_pct252"].astype(float).map(_rate_state)
    out["curve_regime"] = out["curve_10y2y"].astype(float).map(_curve_state)
    out["vix_regime"] = np.where(out["vix_pct252"].astype(float) <= 0.5, "vix_low", "vix_high")
    out["zirp_regime"] = np.where(out["DGS2"].astype(float) < 0.5, "zirp_like", "non_zirp")
    return out


def _summary(g: pd.DataFrame) -> dict[str, Any]:
    return {
        "anchors": int(len(g)),
        "mean_rank_ic": float(g["rank_ic"].mean()),
        "median_rank_ic": float(g["rank_ic"].median()),
        "positive_ic_fraction": float((g["rank_ic"] > 0).mean()),
        "mean_top_minus_bottom_raw_target": float(g["top_minus_bottom_raw_target"].mean()),
        "median_top_minus_bottom_raw_target": float(g["top_minus_bottom_raw_target"].median()),
    }


def _regime_long(anchor: pd.DataFrame, regimes: pd.DataFrame) -> pd.DataFrame:
    merged = anchor.merge(regimes, on="timestamp", how="inner", validate="many_to_one")
    if merged.empty:
        raise ValueError("NO_ANCHOR_REGIME_MATCHES")
    parts = []
    for family, col in (
        ("rate", "rate_regime"),
        ("curve", "curve_regime"),
        ("vix", "vix_regime"),
        ("zirp", "zirp_regime"),
    ):
        p = merged.copy()
        p["regime_family"] = family
        p["regime"] = p[col]
        parts.append(p)
    return pd.concat(parts, ignore_index=True)


def _model_summary(regime_long: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (family, regime, memory, model), g in regime_long.groupby(
        ["regime_family", "regime", "memory_scheme", "model"], sort=True
    ):
        rows.append(
            {
                "regime_family": family,
                "regime": regime,
                "memory_scheme": memory,
                "model": model,
                **_summary(g),
            }
        )
    return pd.DataFrame(rows)


def _increment_summary(model_summary: pd.DataFrame) -> pd.DataFrame:
    comparisons = (
        ("macro_gbm", "price_gbm"),
        ("macro_ridge", "price_ridge"),
        ("macro_gbm", "macro_ridge"),
    )
    rows = []
    for (family, regime, memory), g in model_summary.groupby(
        ["regime_family", "regime", "memory_scheme"], sort=True
    ):
        lookup = {r["model"]: r for _, r in g.iterrows()}
        for lhs, rhs in comparisons:
            if lhs not in lookup or rhs not in lookup:
                continue
            rows.append(
                {
                    "regime_family": family,
                    "regime": regime,
                    "memory_scheme": memory,
                    "comparison": f"{lhs}_minus_{rhs}",
                    "mean_ic_increment": float(lookup[lhs]["mean_rank_ic"] - lookup[rhs]["mean_rank_ic"]),
                    "tail_spread_increment": float(
                        lookup[lhs]["mean_top_minus_bottom_raw_target"]
                        - lookup[rhs]["mean_top_minus_bottom_raw_target"]
                    ),
                    "anchors": int(min(lookup[lhs]["anchors"], lookup[rhs]["anchors"])),
                }
            )
    return pd.DataFrame(rows)


def _rebuild_base_panel(data_dir: Path, oos_timestamps: pd.Index) -> pd.DataFrame:
    frames = exp5._load_universe(data_dir)
    calendar = exp5._common_calendar(frames)
    panel = exp5._build_panel(frames, calendar)
    keep = ["timestamp", "ticker", "target_rank", *INTERACTION_BASES]
    panel = panel[keep].copy()
    panel["timestamp"] = pd.to_datetime(panel["timestamp"], utc=True)
    panel = panel[panel["timestamp"].isin(oos_timestamps)].copy()
    if panel.empty:
        raise ValueError("NO_REBUILT_OOS_PANEL_ROWS")
    return panel


def _feature_ic_by_regime(panel: pd.DataFrame, regimes: pd.DataFrame) -> pd.DataFrame:
    joined = panel.merge(regimes, on="timestamp", how="inner", validate="many_to_one")
    anchor_rows = []
    for ts, g in joined.groupby("timestamp", sort=True):
        base = {
            "timestamp": ts,
            "rate_regime": g["rate_regime"].iloc[0],
            "curve_regime": g["curve_regime"].iloc[0],
            "vix_regime": g["vix_regime"].iloc[0],
            "zirp_regime": g["zirp_regime"].iloc[0],
        }
        for feature in INTERACTION_BASES:
            anchor_rows.append(
                {
                    **base,
                    "feature": feature,
                    "rank_ic": float(g[feature].corr(g["target_rank"], method="spearman")),
                }
            )
    anchors = pd.DataFrame(anchor_rows)
    rows = []
    for family, col in (
        ("rate", "rate_regime"),
        ("curve", "curve_regime"),
        ("vix", "vix_regime"),
        ("zirp", "zirp_regime"),
    ):
        for (regime, feature), g in anchors.groupby([col, "feature"], sort=True):
            rows.append(
                {
                    "regime_family": family,
                    "regime": regime,
                    "feature": feature,
                    "anchors": int(len(g)),
                    "mean_rank_ic": float(g["rank_ic"].mean()),
                    "median_rank_ic": float(g["rank_ic"].median()),
                    "positive_ic_fraction": float((g["rank_ic"] > 0).mean()),
                }
            )
    return pd.DataFrame(rows)


def _importance_stability(importance: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    needed = ["test_year", "memory_scheme", "model", "feature", "importance"]
    missing = [c for c in needed if c not in importance.columns]
    if missing:
        raise ValueError(f"IMPORTANCE_COLUMNS_MISSING:{missing}")
    imp = importance.copy()
    imp["period"] = imp["test_year"].astype(int).map(_period)
    imp["feature_group"] = np.where(
        imp["feature"].str.contains("__x__", regex=False),
        "interaction",
        np.where(imp["feature"].isin(MACRO_STATES), "macro_state", "price_state"),
    )
    stability = (
        imp.groupby(["memory_scheme", "model", "period", "feature_group", "feature"])["importance"]
        .mean()
        .reset_index()
        .sort_values(["memory_scheme", "model", "period", "importance"], ascending=[True, True, True, False])
    )
    diagnostics: dict[str, Any] = {}
    for (memory, model, period), g in imp.groupby(["memory_scheme", "model", "period"], sort=True):
        macro = g[g["feature_group"].isin(["interaction", "macro_state"])].groupby("feature")["importance"].mean()
        total = float(macro.sum())
        top3 = float(macro.nlargest(3).sum()) if len(macro) else 0.0
        diagnostics[f"{memory}:{model}:{period}"] = {
            "macro_or_interaction_total_mean_importance": total,
            "top3_macro_interaction_share": float(top3 / total) if total > 0 else None,
            "top5_features": [
                {"feature": k, "importance": float(v)}
                for k, v in macro.sort_values(ascending=False).head(5).items()
            ],
        }
    return stability, diagnostics


def _asset_attribution(pred: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    learned = pred[pred["model"].isin(["price_gbm", "macro_gbm"])].copy()
    learned["score_rank"] = learned.groupby(["timestamp", "memory_scheme", "model"])["score"].rank(
        method="average", pct=True
    )
    learned["abs_rank_error"] = (learned["score_rank"] - learned["target_rank"]).abs()
    learned["centered_product"] = (learned["score_rank"] - 0.5) * (learned["target_rank"] - 0.5)
    wide = learned.pivot_table(
        index=["timestamp", "ticker", "test_year", "memory_scheme", "target_rank"],
        columns="model",
        values=["abs_rank_error", "centered_product"],
        aggfunc="first",
    ).reset_index()
    wide.columns = [
        "_".join(str(x) for x in c if str(x)) if isinstance(c, tuple) else str(c)
        for c in wide.columns
    ]
    required = [
        "abs_rank_error_price_gbm",
        "abs_rank_error_macro_gbm",
        "centered_product_price_gbm",
        "centered_product_macro_gbm",
    ]
    missing = [c for c in required if c not in wide.columns]
    if missing:
        raise ValueError(f"ASSET_ATTRIBUTION_PIVOT_FAILURE:{missing}")
    wide["period"] = wide["test_year"].astype(int).map(_period)
    wide["abs_error_improvement"] = wide["abs_rank_error_price_gbm"] - wide["abs_rank_error_macro_gbm"]
    wide["centered_product_improvement"] = wide["centered_product_macro_gbm"] - wide["centered_product_price_gbm"]
    summary = (
        wide.groupby(["memory_scheme", "period", "ticker"])
        .agg(
            rows=("ticker", "size"),
            mean_abs_error_improvement=("abs_error_improvement", "mean"),
            mean_centered_product_improvement=("centered_product_improvement", "mean"),
        )
        .reset_index()
    )
    concentration: dict[str, Any] = {}
    for (memory, period), g in summary.groupby(["memory_scheme", "period"], sort=True):
        positive = g[g["mean_centered_product_improvement"] > 0]
        total = float(positive["mean_centered_product_improvement"].sum())
        top = positive.nlargest(3, "mean_centered_product_improvement")
        concentration[f"{memory}:{period}"] = {
            "positive_tickers": int(len(positive)),
            "top3_share_of_positive_centered_improvement": (
                float(top["mean_centered_product_improvement"].sum() / total) if total > 0 else None
            ),
            "top_positive_tickers": list(top["ticker"]),
        }
    return summary, concentration


def _recurrence(increments: pd.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for memory in MEMORY_SCHEMES:
        target = increments[
            (increments["memory_scheme"] == memory)
            & (increments["comparison"] == "macro_gbm_minus_price_gbm")
        ]
        out[memory] = {}
        for family in ("rate", "curve", "vix", "zirp"):
            f = target[target["regime_family"] == family]
            out[memory][family] = {
                "regimes": int(len(f)),
                "positive_ic_regimes": int((f["mean_ic_increment"] > 0).sum()),
                "positive_spread_regimes": int((f["tail_spread_increment"] > 0).sum()),
                "details": [
                    {
                        "regime": r["regime"],
                        "mean_ic_increment": float(r["mean_ic_increment"]),
                        "tail_spread_increment": float(r["tail_spread_increment"]),
                        "anchors": int(r["anchors"]),
                    }
                    for _, r in f.iterrows()
                ],
            }
    return out


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    source_dir = Path(args.source_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pred = _normalize_timestamp(_read_csv_required(source_dir / "experiment_009_oos_predictions.csv"))
    anchor = _normalize_timestamp(_read_csv_required(source_dir / "experiment_009_anchor_metrics.csv"))
    macro = _normalize_timestamp(_read_csv_required(source_dir / "experiment_009_macro_state.csv"))
    importance = _read_csv_required(source_dir / "experiment_009_feature_importance_by_fold.csv")

    if pred["test_year"].astype(int).max() > 2024 or anchor["test_year"].astype(int).max() > 2024:
        raise ValueError("HOLDOUT_BOUNDARY_FAILURE:found test year after 2024")
    if set(pred["memory_scheme"].dropna().unique()) - set(MEMORY_SCHEMES):
        raise ValueError("UNEXPECTED_MEMORY_SCHEME")
    if set(pred["model"].dropna().unique()) - set(MODELS):
        raise ValueError("UNEXPECTED_MODEL")

    regimes = _build_regimes(macro)
    model_summary = _model_summary(_regime_long(anchor, regimes))
    increments = _increment_summary(model_summary)

    oos_timestamps = pd.Index(pred["timestamp"].drop_duplicates())
    panel = _rebuild_base_panel(data_dir, oos_timestamps)
    feature_ic = _feature_ic_by_regime(panel, regimes)
    importance_stability, importance_diag = _importance_stability(importance)
    asset_summary, asset_concentration = _asset_attribution(pred)
    zirp = increments[increments["regime_family"] == "zirp"].copy()

    model_summary.to_csv(out_dir / "experiment_010_regime_model_summary.csv", index=False)
    increments.to_csv(out_dir / "experiment_010_regime_increment_summary.csv", index=False)
    feature_ic.to_csv(out_dir / "experiment_010_feature_ic_by_regime.csv", index=False)
    importance_stability.to_csv(out_dir / "experiment_010_importance_stability.csv", index=False)
    asset_summary.to_csv(out_dir / "experiment_010_asset_attribution.csv", index=False)
    zirp.to_csv(out_dir / "experiment_010_zirp_diagnostic.csv", index=False)

    report = {
        "experiment": "ML_LAB_EXPERIMENT_010_MACRO_INTERACTION_STABILITY_AUDIT",
        "status": "EXPLORATORY_DIAGNOSTIC_NONCONFIRMATORY",
        "boundary": "No refit, no tuning, no feature/target/model/memory changes, no 2025 holdout use, no Core/runtime/portfolio/capital implication.",
        "design": {
            "source_experiment": "ML_LAB_EXPERIMENT_009_MACRO_RATE_STATE_CROSS_SECTIONAL",
            "model_refit_performed": False,
            "geometry_restricted_to_experiment_009_oos_anchors": True,
            "memory_schemes": list(MEMORY_SCHEMES),
            "models": list(MODELS),
            "interaction_bases": list(INTERACTION_BASES),
            "rate_regimes": {
                "rate2_low": "rate2_pct252 < 1/3",
                "rate2_mid": "1/3 <= rate2_pct252 < 2/3",
                "rate2_high": "rate2_pct252 >= 2/3",
            },
            "curve_regimes": {
                "curve_inverted": "DGS10-DGS2 < 0 percentage points",
                "curve_flat": "0 <= DGS10-DGS2 < 1 percentage point",
                "curve_steep": "DGS10-DGS2 >= 1 percentage point",
            },
            "vix_regimes": {"vix_low": "vix_pct252 <= 0.5", "vix_high": "vix_pct252 > 0.5"},
            "zirp_diagnostic": {"zirp_like": "DGS2 < 0.5%", "non_zirp": "DGS2 >= 0.5%"},
            "reserved_2025_campaign50_holdout_used": False,
        },
        "source_counts": {
            "prediction_rows": int(len(pred)),
            "anchor_metric_rows": int(len(anchor)),
            "macro_state_rows": int(len(macro)),
            "importance_rows": int(len(importance)),
            "rebuilt_oos_geometry_rows": int(len(panel)),
            "rebuilt_oos_geometry_anchors": int(panel["timestamp"].nunique()),
        },
        "macro_gbm_recurrence": _recurrence(increments),
        "zirp_focus": [
            {
                "memory_scheme": r["memory_scheme"],
                "regime": r["regime"],
                "comparison": r["comparison"],
                "mean_ic_increment": float(r["mean_ic_increment"]),
                "tail_spread_increment": float(r["tail_spread_increment"]),
                "anchors": int(r["anchors"]),
            }
            for _, r in zirp.iterrows()
        ],
        "importance_stability": importance_diag,
        "asset_concentration": asset_concentration,
        "artifact_files": {
            "regime_model_summary": "experiment_010_regime_model_summary.csv",
            "regime_increment_summary": "experiment_010_regime_increment_summary.csv",
            "feature_ic_by_regime": "experiment_010_feature_ic_by_regime.csv",
            "importance_stability": "experiment_010_importance_stability.csv",
            "asset_attribution": "experiment_010_asset_attribution.csv",
            "zirp_diagnostic": "experiment_010_zirp_diagnostic.csv",
        },
    }
    (out_dir / "experiment_010_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
