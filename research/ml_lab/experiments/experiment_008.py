from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

MEMORY_SCHEMES = ("expanding", "trailing_5y", "trailing_3y")
TAIL_DEFS: dict[str, str] = {
    "top3": "fixed 3 assets per tail",
    "quartile": "ceil(N*0.25) assets per tail",
}
PRE_END_YEAR = 2021
POST_START_YEAR = 2022
MAX_YEAR = 2024
REQUIRED_COLUMNS = {
    "timestamp",
    "ticker",
    "target_raw",
    "target_rank",
    "test_year",
    "memory_scheme",
    "model",
    "score",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ML Lab Experiment 008: no-refit tail increment audit")
    p.add_argument(
        "--predictions",
        default="artifacts/ml_lab_experiment_007/experiment_007_oos_predictions.csv",
    )
    p.add_argument("--output-dir", default="artifacts/ml_lab_experiment_008")
    return p.parse_args()


def _period(year: int) -> str:
    return "pre_2012_2021" if year <= PRE_END_YEAR else "post_2022_2024"


def _mean(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def _jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    return float(len(a & b) / len(union)) if union else 1.0


def _tail_n(n_assets: int, tail_def: str) -> int:
    if tail_def == "top3":
        return min(3, n_assets)
    if tail_def == "quartile":
        return max(1, int(math.ceil(n_assets * 0.25)))
    raise ValueError(f"UNKNOWN_TAIL_DEF: {tail_def}")


def _load_predictions(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"MISSING_EXPERIMENT_007_PREDICTIONS: {path}")
    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"MISSING_REQUIRED_COLUMNS: {sorted(missing)}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["test_year"] = df["test_year"].astype(int)
    df = df[
        df["model"].isin(["ridge", "gbm"])
        & df["memory_scheme"].isin(MEMORY_SCHEMES)
        & (df["test_year"] <= MAX_YEAR)
    ].copy()
    if df.empty:
        raise ValueError("NO_ELIGIBLE_EXPERIMENT_007_PREDICTIONS")
    if (df["test_year"] >= 2025).any():
        raise ValueError("RESERVED_2025_HOLDOUT_PRESENT")
    return df


def _wide_anchor(group: pd.DataFrame) -> pd.DataFrame:
    duplicated = group.duplicated(["ticker", "model"]).any()
    if duplicated:
        raise ValueError("DUPLICATE_TICKER_MODEL_WITHIN_ANCHOR")

    meta = (
        group.groupby("ticker")[["target_raw", "target_rank"]]
        .agg(lambda s: s.iloc[0])
        .copy()
    )
    consistency = group.groupby("ticker")[["target_raw", "target_rank"]].nunique(dropna=False)
    if (consistency > 1).any().any():
        raise ValueError("TARGET_MISMATCH_BETWEEN_MODELS")

    scores = group.pivot(index="ticker", columns="model", values="score")
    if "gbm" not in scores.columns or "ridge" not in scores.columns:
        raise ValueError("MISSING_MODEL_WITHIN_ANCHOR")
    wide = meta.join(scores[["gbm", "ridge"]], how="inner")
    if len(wide) < 4:
        raise ValueError("ANCHOR_TOO_NARROW")
    return wide


def _set_mean(wide: pd.DataFrame, members: set[str], column: str) -> float | None:
    if not members:
        return None
    return float(wide.loc[sorted(members), column].mean())


def _anchor_audit(
    wide: pd.DataFrame,
    timestamp: pd.Timestamp,
    memory_scheme: str,
    test_year: int,
    tail_def: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    n_assets = len(wide)
    n_tail = _tail_n(n_assets, tail_def)

    gbm_order = wide["gbm"].sort_values()
    ridge_order = wide["ridge"].sort_values()

    gbm_bottom = set(gbm_order.head(n_tail).index)
    gbm_top = set(gbm_order.tail(n_tail).index)
    ridge_bottom = set(ridge_order.head(n_tail).index)
    ridge_top = set(ridge_order.tail(n_tail).index)

    both_top = gbm_top & ridge_top
    both_bottom = gbm_bottom & ridge_bottom
    gbm_only_top = gbm_top - ridge_top
    ridge_only_top = ridge_top - gbm_top
    gbm_only_bottom = gbm_bottom - ridge_bottom
    ridge_only_bottom = ridge_bottom - gbm_bottom

    gbm_only_top_raw = _set_mean(wide, gbm_only_top, "target_raw")
    ridge_only_top_raw = _set_mean(wide, ridge_only_top, "target_raw")
    gbm_only_bottom_raw = _set_mean(wide, gbm_only_bottom, "target_raw")
    ridge_only_bottom_raw = _set_mean(wide, ridge_only_bottom, "target_raw")

    gbm_only_top_rank = _set_mean(wide, gbm_only_top, "target_rank")
    ridge_only_top_rank = _set_mean(wide, ridge_only_top, "target_rank")
    gbm_only_bottom_rank = _set_mean(wide, gbm_only_bottom, "target_rank")
    ridge_only_bottom_rank = _set_mean(wide, ridge_only_bottom, "target_rank")

    upside_increment_raw = (
        gbm_only_top_raw - ridge_only_top_raw
        if gbm_only_top_raw is not None and ridge_only_top_raw is not None
        else None
    )
    downside_increment_raw = (
        ridge_only_bottom_raw - gbm_only_bottom_raw
        if ridge_only_bottom_raw is not None and gbm_only_bottom_raw is not None
        else None
    )
    combined_increment_raw = (
        upside_increment_raw + downside_increment_raw
        if upside_increment_raw is not None and downside_increment_raw is not None
        else None
    )

    upside_increment_rank = (
        gbm_only_top_rank - ridge_only_top_rank
        if gbm_only_top_rank is not None and ridge_only_top_rank is not None
        else None
    )
    downside_increment_rank = (
        ridge_only_bottom_rank - gbm_only_bottom_rank
        if ridge_only_bottom_rank is not None and gbm_only_bottom_rank is not None
        else None
    )
    combined_increment_rank = (
        upside_increment_rank + downside_increment_rank
        if upside_increment_rank is not None and downside_increment_rank is not None
        else None
    )

    row: dict[str, Any] = {
        "timestamp": timestamp,
        "test_year": test_year,
        "period": _period(test_year),
        "memory_scheme": memory_scheme,
        "tail_def": tail_def,
        "assets": n_assets,
        "tail_n": n_tail,
        "top_overlap_count": len(both_top),
        "bottom_overlap_count": len(both_bottom),
        "top_jaccard": _jaccard(gbm_top, ridge_top),
        "bottom_jaccard": _jaccard(gbm_bottom, ridge_bottom),
        "gbm_only_top_count": len(gbm_only_top),
        "ridge_only_top_count": len(ridge_only_top),
        "gbm_only_bottom_count": len(gbm_only_bottom),
        "ridge_only_bottom_count": len(ridge_only_bottom),
        "both_top_target_raw": _set_mean(wide, both_top, "target_raw"),
        "both_bottom_target_raw": _set_mean(wide, both_bottom, "target_raw"),
        "gbm_only_top_target_raw": gbm_only_top_raw,
        "ridge_only_top_target_raw": ridge_only_top_raw,
        "gbm_only_bottom_target_raw": gbm_only_bottom_raw,
        "ridge_only_bottom_target_raw": ridge_only_bottom_raw,
        "upside_increment_raw": upside_increment_raw,
        "downside_increment_raw": downside_increment_raw,
        "combined_increment_raw": combined_increment_raw,
        "upside_increment_rank": upside_increment_rank,
        "downside_increment_rank": downside_increment_rank,
        "combined_increment_rank": combined_increment_rank,
        "upside_disagreement_eligible": upside_increment_raw is not None,
        "downside_disagreement_eligible": downside_increment_raw is not None,
        "combined_disagreement_eligible": combined_increment_raw is not None,
    }

    attribution: list[dict[str, Any]] = []
    role_sets = {
        "gbm_only_top": gbm_only_top,
        "ridge_only_top": ridge_only_top,
        "gbm_only_bottom": gbm_only_bottom,
        "ridge_only_bottom": ridge_only_bottom,
    }
    role_sign = {
        "gbm_only_top": 1.0,
        "ridge_only_top": -1.0,
        "gbm_only_bottom": -1.0,
        "ridge_only_bottom": 1.0,
    }
    for role, members in role_sets.items():
        for ticker in sorted(members):
            target_raw = float(wide.loc[ticker, "target_raw"])
            attribution.append(
                {
                    "timestamp": timestamp,
                    "test_year": test_year,
                    "period": _period(test_year),
                    "memory_scheme": memory_scheme,
                    "tail_def": tail_def,
                    "role": role,
                    "ticker": ticker,
                    "target_raw": target_raw,
                    "target_rank": float(wide.loc[ticker, "target_rank"]),
                    "signed_increment_contribution": role_sign[role] * target_raw,
                }
            )
    return row, attribution


def _summary_rows(anchor: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in anchor.groupby(group_cols, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {col: value for col, value in zip(group_cols, keys, strict=True)}
        row.update(
            {
                "anchors": int(len(group)),
                "mean_top_jaccard": float(group["top_jaccard"].mean()),
                "mean_bottom_jaccard": float(group["bottom_jaccard"].mean()),
            }
        )
        for metric in (
            "upside_increment_raw",
            "downside_increment_raw",
            "combined_increment_raw",
            "upside_increment_rank",
            "downside_increment_rank",
            "combined_increment_rank",
        ):
            s = group[metric].dropna()
            row[f"{metric}_eligible_anchors"] = int(len(s))
            row[f"mean_{metric}"] = float(s.mean()) if len(s) else None
            row[f"median_{metric}"] = float(s.median()) if len(s) else None
            row[f"positive_{metric}_fraction"] = float((s > 0).mean()) if len(s) else None
        rows.append(row)
    return pd.DataFrame(rows)


def _asset_summary(attribution: pd.DataFrame) -> pd.DataFrame:
    if attribution.empty:
        return pd.DataFrame()
    return (
        attribution.groupby(["period", "memory_scheme", "tail_def", "role", "ticker"])
        .agg(
            selections=("ticker", "size"),
            mean_target_raw=("target_raw", "mean"),
            mean_target_rank=("target_rank", "mean"),
            signed_increment_contribution=("signed_increment_contribution", "sum"),
        )
        .reset_index()
    )


def _top3_positive_share(asset_summary: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if asset_summary.empty:
        return rows
    grouped = asset_summary.groupby(["period", "memory_scheme", "tail_def"], sort=True)
    for (period, memory_scheme, tail_def), group in grouped:
        by_ticker = group.groupby("ticker")["signed_increment_contribution"].sum()
        positive = by_ticker[by_ticker > 0].sort_values(ascending=False)
        total = float(positive.sum())
        share = float(positive.head(3).sum() / total) if total > 0 else None
        rows.append(
            {
                "period": period,
                "memory_scheme": memory_scheme,
                "tail_def": tail_def,
                "positive_tickers": int(len(positive)),
                "top3_asset_share_of_positive_increment": share,
                "top_positive_tickers": [str(x) for x in positive.head(3).index],
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    pred_path = Path(args.predictions)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pred = _load_predictions(pred_path)

    anchor_rows: list[dict[str, Any]] = []
    attribution_rows: list[dict[str, Any]] = []

    for (timestamp, memory_scheme), group in pred.groupby(["timestamp", "memory_scheme"], sort=True):
        test_years = group["test_year"].unique()
        if len(test_years) != 1:
            raise ValueError("ANCHOR_TEST_YEAR_MISMATCH")
        test_year = int(test_years[0])
        wide = _wide_anchor(group)
        for tail_def in TAIL_DEFS:
            row, attrib = _anchor_audit(wide, pd.Timestamp(timestamp), str(memory_scheme), test_year, tail_def)
            anchor_rows.append(row)
            attribution_rows.extend(attrib)

    anchor = pd.DataFrame(anchor_rows)
    attribution = pd.DataFrame(attribution_rows)
    if anchor.empty:
        raise ValueError("NO_ELIGIBLE_TAIL_AUDIT_ROWS")

    period_summary = _summary_rows(anchor, ["period", "memory_scheme", "tail_def"])
    yearly_summary = _summary_rows(anchor, ["test_year", "period", "memory_scheme", "tail_def"])
    overlap_summary = (
        anchor.groupby(["period", "memory_scheme", "tail_def"])
        .agg(
            anchors=("timestamp", "size"),
            mean_top_overlap_count=("top_overlap_count", "mean"),
            mean_bottom_overlap_count=("bottom_overlap_count", "mean"),
            mean_top_jaccard=("top_jaccard", "mean"),
            mean_bottom_jaccard=("bottom_jaccard", "mean"),
            identical_top_fraction=("gbm_only_top_count", lambda s: float((s == 0).mean())),
            identical_bottom_fraction=("gbm_only_bottom_count", lambda s: float((s == 0).mean())),
        )
        .reset_index()
    )
    asset_summary = _asset_summary(attribution)
    concentration = _top3_positive_share(asset_summary)

    anchor.to_csv(out_dir / "experiment_008_anchor_tail_audit.csv", index=False)
    period_summary.to_csv(out_dir / "experiment_008_period_tail_summary.csv", index=False)
    yearly_summary.to_csv(out_dir / "experiment_008_yearly_tail_summary.csv", index=False)
    asset_summary.to_csv(out_dir / "experiment_008_asset_attribution.csv", index=False)
    overlap_summary.to_csv(out_dir / "experiment_008_overlap_summary.csv", index=False)

    post_focus = period_summary[period_summary["period"] == "post_2022_2024"].to_dict("records")
    pre_focus = period_summary[period_summary["period"] == "pre_2012_2021"].to_dict("records")

    report = {
        "experiment": "ML_LAB_EXPERIMENT_008_TAIL_INCREMENT_AUDIT",
        "status": "EXPLORATORY_DIAGNOSTIC_NONCONFIRMATORY",
        "boundary": "No model refit, no tuning, no feature/target/model/memory changes, no 2025 holdout use, no Core/runtime/portfolio/capital implication.",
        "design": {
            "source_predictions": str(pred_path).replace("\\", "/"),
            "source_experiment": "ML_LAB_EXPERIMENT_007_TRAINING_MEMORY_ADAPTIVITY",
            "model_refit_performed": False,
            "features_changed": False,
            "target_changed": False,
            "hyperparameters_changed": False,
            "memory_schemes_changed": False,
            "reserved_2025_campaign50_holdout_used": False,
            "memory_schemes": list(MEMORY_SCHEMES),
            "tail_definitions": TAIL_DEFS,
            "pre_period": "2012-2021",
            "post_period": "2022-2024",
            "increment_signs": {
                "upside": "GBM-only top minus Ridge-only top; positive favors GBM",
                "downside": "Ridge-only bottom minus GBM-only bottom; positive favors GBM",
                "combined": "upside plus downside; descriptive only",
            },
        },
        "source_rows": int(len(pred)),
        "audited_anchors": int(anchor["timestamp"].nunique()),
        "period_tail_summary": period_summary.to_dict("records"),
        "pre_2012_2021_focus": pre_focus,
        "post_2022_2024_focus": post_focus,
        "asset_concentration": concentration,
        "artifact_files": {
            "anchor_tail_audit": "experiment_008_anchor_tail_audit.csv",
            "period_tail_summary": "experiment_008_period_tail_summary.csv",
            "yearly_tail_summary": "experiment_008_yearly_tail_summary.csv",
            "asset_attribution": "experiment_008_asset_attribution.csv",
            "overlap_summary": "experiment_008_overlap_summary.csv",
        },
    }
    (out_dir / "experiment_008_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
