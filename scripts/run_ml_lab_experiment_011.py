from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import run_ml_lab_experiment_005 as exp5
import run_ml_lab_experiment_009 as exp9

DESTINATION_UNIVERSE = (
    "EWA", "EWC", "EWG", "EWH", "EWI", "EWJ", "EWL",
    "EWM", "EWW", "EWP", "EWS", "EWT", "EWU", "EWZ",
)
MEMORY_SCHEMES: dict[str, int | None] = {"expanding": None, "trailing_3y": 3}
MODEL_VARIANTS = {
    "price_ridge": (exp5._ridge, exp9.PRICE_FEATURES),
    "price_gbm": (exp5._gbm, exp9.PRICE_FEATURES),
    "macro_ridge": (exp5._ridge, exp9.AUGMENTED_FEATURES),
    "macro_gbm": (exp5._gbm, exp9.AUGMENTED_FEATURES),
}
PARITY_TOLERANCE = 1e-8


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ML Lab Experiment 011: cross-universe transfer")
    p.add_argument("--source-data-dir", default="data")
    p.add_argument("--destination-data-dir", default="data/ml_lab_transfer_011")
    p.add_argument("--experiment-009-dir", default="artifacts/ml_lab_experiment_009")
    p.add_argument("--output-dir", default="artifacts/ml_lab_experiment_011")
    return p.parse_args()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_destination(data_dir: Path) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for ticker in DESTINATION_UNIVERSE:
        path = data_dir / f"{ticker}_1D.csv"
        if not path.exists():
            missing.append(str(path))
            continue
        frame = exp5.read_ohlcv(path).sort_index()
        frame = frame.loc[frame.index <= exp5.LAST_ALLOWED_DATE].copy()
        if frame.empty:
            raise ValueError(f"EMPTY_DESTINATION_SOURCE_AFTER_CUTOFF:{ticker}")
        if len(frame) < 2000:
            raise ValueError(f"DESTINATION_SOURCE_COVERAGE_FAILURE:{ticker}:{len(frame)}")
        frames[ticker] = frame
    if missing:
        raise FileNotFoundError("MISSING_DESTINATION_SOURCES:\n" + "\n".join(missing))
    return frames


def _common_calendar(frames: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    common: pd.DatetimeIndex | None = None
    for frame in frames.values():
        idx = pd.DatetimeIndex(frame.index)
        common = idx if common is None else common.intersection(idx)
    if common is None or len(common) < 2500:
        raise ValueError(f"DESTINATION_COMMON_CALENDAR_TOO_SHORT:{0 if common is None else len(common)}")
    common = common.sort_values()
    return common[common <= exp5.LAST_ALLOWED_DATE]


def _build_panel(frames: dict[str, pd.DataFrame], calendar: pd.DatetimeIndex) -> pd.DataFrame:
    by_asset = {
        ticker: exp5._asset_features(frame, calendar, ticker)
        for ticker, frame in frames.items()
    }
    close_matrix = pd.DataFrame(
        {ticker: by_asset[ticker]["close"] for ticker in DESTINATION_UNIVERSE},
        index=calendar,
    )
    vol60_matrix = pd.DataFrame(
        {ticker: by_asset[ticker]["vol_60d"] for ticker in DESTINATION_UNIVERSE},
        index=calendar,
    )
    raw_feature_names = [name.replace("_xrank", "") for name in exp5.FEATURES]
    rows: list[pd.DataFrame] = []

    for pos in range(120, len(calendar) - exp5.TARGET_HORIZON, exp5.ANCHOR_STEP):
        ts = calendar[pos]
        end_ts = calendar[pos + exp5.TARGET_HORIZON]
        if end_ts > exp5.LAST_ALLOWED_DATE:
            continue
        feature_slice = pd.DataFrame(
            {
                ticker: by_asset[ticker].loc[ts, raw_feature_names]
                for ticker in DESTINATION_UNIVERSE
            }
        ).T
        if feature_slice.isna().any().any():
            continue
        xrank = feature_slice.rank(axis=0, method="average", pct=True)
        xrank.columns = [f"{c}_xrank" for c in xrank.columns]

        current_close = close_matrix.loc[ts]
        future_close = close_matrix.loc[end_ts]
        trailing_vol = vol60_matrix.loc[ts]
        raw_target = (
            (future_close / current_close - 1.0)
            / (trailing_vol * math.sqrt(exp5.TARGET_HORIZON))
        )
        if raw_target.isna().any() or np.isinf(raw_target.to_numpy()).any():
            continue
        target_rank = raw_target.rank(method="average", pct=True)

        block = xrank.copy()
        block["ticker"] = block.index
        block["timestamp"] = ts
        block["target_end_date"] = end_ts
        block["target_raw"] = raw_target.reindex(block.index).to_numpy()
        block["target_rank"] = target_rank.reindex(block.index).to_numpy()
        rows.append(block.reset_index(drop=True))

    if not rows:
        raise ValueError("NO_ELIGIBLE_DESTINATION_ANCHORS")
    panel = pd.concat(rows, ignore_index=True)
    panel["timestamp"] = pd.to_datetime(panel["timestamp"], utc=True)
    panel["target_end_date"] = pd.to_datetime(panel["target_end_date"], utc=True)
    return panel.sort_values(["timestamp", "ticker"]).reset_index(drop=True)


def _load_macro_state(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"MISSING_EXPERIMENT_009_MACRO_STATE:{path}")
    macro = pd.read_csv(path)
    if macro.empty:
        raise ValueError("EMPTY_EXPERIMENT_009_MACRO_STATE")
    if "timestamp" not in macro.columns:
        macro = macro.rename(columns={macro.columns[0]: "timestamp"})
    macro["timestamp"] = pd.to_datetime(macro["timestamp"], errors="coerce", utc=True)
    if macro["timestamp"].isna().any():
        raise ValueError("MACRO_TIMESTAMP_PARSE_FAILURE")
    if macro["timestamp"].duplicated().any():
        raise ValueError("MACRO_DUPLICATE_TIMESTAMP_FAILURE")
    macro = macro.set_index("timestamp").sort_index()
    needed = list(exp9.MACRO_STATES) + ["DGS2", "DGS10", "DGS3MO", "curve_10y2y", "VIX"]
    missing = [c for c in needed if c not in macro.columns]
    if missing:
        raise ValueError(f"MACRO_COLUMNS_MISSING:{missing}")
    return macro


def _training_slice(panel: pd.DataFrame, test_start: pd.Timestamp, years: int | None) -> pd.DataFrame:
    train = panel[
        (panel["timestamp"] < test_start)
        & (panel["target_end_date"] < test_start)
    ].copy()
    if years is not None:
        train = train[train["timestamp"] >= test_start - pd.DateOffset(years=years)].copy()
    return train


def _period(year: int) -> str:
    return "pre_2022" if year <= 2021 else "post_2022_2024"


def _anchor_metric(group: pd.DataFrame) -> dict[str, Any]:
    score_rank = group["score"].rank(method="average", pct=True)
    ic = float(score_rank.corr(group["target_rank"], method="spearman"))
    n_q = max(1, int(math.ceil(len(group) * 0.25)))
    ordered = group.assign(score_rank=score_rank).sort_values("score_rank")
    spread = float(
        ordered.tail(n_q)["target_raw"].mean()
        - ordered.head(n_q)["target_raw"].mean()
    )
    year = int(group["test_year"].iloc[0])
    return {
        "timestamp": group["timestamp"].iloc[0],
        "test_year": year,
        "period": _period(year),
        "memory_scheme": group["memory_scheme"].iloc[0],
        "model": group["model"].iloc[0],
        "rank_ic": ic,
        "top_minus_bottom_raw_target": spread,
        "assets": int(len(group)),
    }


def _summary(group: pd.DataFrame) -> dict[str, Any]:
    return {
        "anchors": int(len(group)),
        "mean_rank_ic": float(group["rank_ic"].mean()),
        "median_rank_ic": float(group["rank_ic"].median()),
        "positive_ic_fraction": float((group["rank_ic"] > 0).mean()),
        "mean_top_minus_bottom_raw_target": float(group["top_minus_bottom_raw_target"].mean()),
        "median_top_minus_bottom_raw_target": float(group["top_minus_bottom_raw_target"].median()),
    }


def _parity_check(
    saved: pd.DataFrame,
    source_test: pd.DataFrame,
    scores: np.ndarray,
    year: int,
    memory: str,
    model_name: str,
) -> dict[str, Any]:
    expected = saved[
        (saved["test_year"].astype(int) == year)
        & (saved["memory_scheme"] == memory)
        & (saved["model"] == model_name)
    ][["timestamp", "ticker", "score"]].copy()
    expected["timestamp"] = pd.to_datetime(expected["timestamp"], utc=True)
    actual = source_test[["timestamp", "ticker"]].copy()
    actual["score_replayed"] = scores
    merged = expected.merge(actual, on=["timestamp", "ticker"], how="outer", indicator=True)
    if len(merged) != len(expected) or len(merged) != len(actual) or not (merged["_merge"] == "both").all():
        raise ValueError(f"SOURCE_PARITY_ROW_FAILURE:{year}:{memory}:{model_name}")
    delta = (merged["score"] - merged["score_replayed"]).abs()
    max_abs = float(delta.max()) if len(delta) else 0.0
    if not np.isfinite(max_abs) or max_abs > PARITY_TOLERANCE:
        raise ValueError(
            f"SOURCE_PARITY_SCORE_FAILURE:{year}:{memory}:{model_name}:{max_abs}"
        )
    return {
        "test_year": year,
        "memory_scheme": memory,
        "model": model_name,
        "rows": int(len(merged)),
        "max_abs_score_delta": max_abs,
        "passed": True,
    }


def _increment_table(summary: pd.DataFrame, scope: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    comparisons = (
        ("macro_gbm", "price_gbm"),
        ("macro_ridge", "price_ridge"),
        ("macro_gbm", "macro_ridge"),
        ("price_gbm", "price_ridge"),
    )
    for (period, memory), g in summary.groupby(["period", "memory_scheme"], sort=True):
        lookup = {r["model"]: r for _, r in g.iterrows()}
        for lhs, rhs in comparisons:
            if lhs not in lookup or rhs not in lookup:
                continue
            rows.append(
                {
                    "scope": scope,
                    "period": period,
                    "memory_scheme": memory,
                    "comparison": f"{lhs}_minus_{rhs}",
                    "mean_ic_increment": float(
                        lookup[lhs]["mean_rank_ic"] - lookup[rhs]["mean_rank_ic"]
                    ),
                    "tail_spread_increment": float(
                        lookup[lhs]["mean_top_minus_bottom_raw_target"]
                        - lookup[rhs]["mean_top_minus_bottom_raw_target"]
                    ),
                }
            )
    return rows


def _asset_concentration(pred: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    g = pred[pred["model"].isin(["price_gbm", "macro_gbm"])].copy()
    g["score_rank"] = g.groupby(["timestamp", "memory_scheme", "model"])["score"].rank(
        method="average", pct=True
    )
    g["centered_product"] = (g["score_rank"] - 0.5) * (g["target_rank"] - 0.5)
    wide = g.pivot_table(
        index=["timestamp", "ticker", "test_year", "period", "memory_scheme"],
        columns="model",
        values="centered_product",
        aggfunc="first",
    ).reset_index()
    if "macro_gbm" not in wide.columns or "price_gbm" not in wide.columns:
        raise ValueError("DESTINATION_ASSET_ATTRIBUTION_PIVOT_FAILURE")
    wide["macro_improvement"] = wide["macro_gbm"] - wide["price_gbm"]
    summary = (
        wide.groupby(["memory_scheme", "period", "ticker"])
        .agg(rows=("ticker", "size"), mean_macro_improvement=("macro_improvement", "mean"))
        .reset_index()
    )
    diag: dict[str, Any] = {}
    for (memory, period), s in summary.groupby(["memory_scheme", "period"], sort=True):
        positive = s[s["mean_macro_improvement"] > 0].copy()
        total = float(positive["mean_macro_improvement"].sum())
        top = positive.nlargest(3, "mean_macro_improvement")
        diag[f"{memory}:{period}"] = {
            "positive_tickers": int(len(positive)),
            "top3_share_of_positive_improvement": (
                float(top["mean_macro_improvement"].sum() / total) if total > 0 else None
            ),
            "top_positive_tickers": list(top["ticker"]),
        }
    return summary, diag


def main() -> None:
    args = parse_args()
    source_data_dir = Path(args.source_data_dir)
    destination_data_dir = Path(args.destination_data_dir)
    exp9_dir = Path(args.experiment_009_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    saved_pred_path = exp9_dir / "experiment_009_oos_predictions.csv"
    saved_anchor_path = exp9_dir / "experiment_009_anchor_metrics.csv"
    macro_path = exp9_dir / "experiment_009_macro_state.csv"
    for path in (saved_pred_path, saved_anchor_path, macro_path):
        if not path.exists():
            raise FileNotFoundError(f"MISSING_EXPERIMENT_009_ARTIFACT:{path}")

    saved_pred = pd.read_csv(saved_pred_path)
    saved_pred["timestamp"] = pd.to_datetime(saved_pred["timestamp"], utc=True)
    saved_anchor = pd.read_csv(saved_anchor_path)
    saved_anchor["timestamp"] = pd.to_datetime(saved_anchor["timestamp"], utc=True)
    if saved_pred["test_year"].astype(int).max() > 2024:
        raise ValueError("SOURCE_HOLDOUT_BOUNDARY_FAILURE")

    macro = _load_macro_state(macro_path)

    source_frames = exp5._load_universe(source_data_dir)
    source_calendar = exp5._common_calendar(source_frames)
    source_base = exp5._build_panel(source_frames, source_calendar)
    source_panel = exp9._augment_panel(source_base, macro)

    destination_frames = _load_destination(destination_data_dir)
    destination_calendar = _common_calendar(destination_frames)
    destination_base = _build_panel(destination_frames, destination_calendar)
    destination_panel = exp9._augment_panel(destination_base, macro)

    if destination_panel["target_end_date"].max() > exp5.LAST_ALLOWED_DATE:
        raise ValueError("DESTINATION_HOLDOUT_BOUNDARY_FAILURE")

    predictions: list[pd.DataFrame] = []
    parity_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []

    years = sorted(
        set(source_panel["timestamp"].dt.year.unique())
        & set(destination_panel["timestamp"].dt.year.unique())
    )
    years = [int(y) for y in years if int(y) <= 2024]

    for year in years:
        source_test = source_panel[source_panel["timestamp"].dt.year == year].copy()
        if source_test.empty:
            continue
        source_test_start = source_test["timestamp"].min()
        destination_test = destination_panel[
            (destination_panel["timestamp"].dt.year == year)
            & (destination_panel["timestamp"] >= source_test_start)
        ].copy()
        if destination_test.empty:
            continue

        for memory_name, memory_years in MEMORY_SCHEMES.items():
            train = _training_slice(source_panel, source_test_start, memory_years)
            eligible = len(train) >= exp5.MIN_TRAIN_ROWS and train["timestamp"].nunique() >= 50
            support_rows.append(
                {
                    "test_year": year,
                    "memory_scheme": memory_name,
                    "source_train_rows": int(len(train)),
                    "source_train_anchors": int(train["timestamp"].nunique()),
                    "source_test_rows": int(len(source_test)),
                    "source_test_anchors": int(source_test["timestamp"].nunique()),
                    "destination_test_rows": int(len(destination_test)),
                    "destination_test_anchors": int(destination_test["timestamp"].nunique()),
                    "source_test_start": str(source_test_start.date()),
                    "max_source_train_target_end": (
                        str(train["target_end_date"].max().date()) if len(train) else None
                    ),
                    "eligible": bool(eligible),
                }
            )
            if not eligible:
                continue

            for model_name, (factory, features) in MODEL_VARIANTS.items():
                model = factory()
                model.fit(train[list(features)].astype(float), train["target_rank"].astype(float))

                source_scores = model.predict(source_test[list(features)].astype(float))
                parity_rows.append(
                    _parity_check(
                        saved_pred,
                        source_test,
                        source_scores,
                        year,
                        memory_name,
                        model_name,
                    )
                )

                p = destination_test[["timestamp", "ticker", "target_raw", "target_rank"]].copy()
                p["test_year"] = year
                p["period"] = _period(year)
                p["memory_scheme"] = memory_name
                p["model"] = model_name
                p["score"] = model.predict(destination_test[list(features)].astype(float))
                predictions.append(p)

    if not predictions:
        raise ValueError("NO_ELIGIBLE_TRANSFER_FOLDS")

    pred = pd.concat(predictions, ignore_index=True)
    parity = pd.DataFrame(parity_rows)
    support = pd.DataFrame(support_rows)

    anchor_metrics = pd.DataFrame(
        [
            _anchor_metric(g)
            for _, g in pred.groupby(["timestamp", "memory_scheme", "model"], sort=True)
        ]
    )
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

    destination_summary_rows: list[dict[str, Any]] = []
    for (period, memory, model_name), g in anchor_metrics.groupby(
        ["period", "memory_scheme", "model"], sort=True
    ):
        row = {"period": period, "memory_scheme": memory, "model": model_name}
        row.update(_summary(g))
        destination_summary_rows.append(row)
    destination_summary = pd.DataFrame(destination_summary_rows)

    transfer_years = sorted(anchor_metrics["test_year"].astype(int).unique())
    source_reference = saved_anchor[
        saved_anchor["test_year"].astype(int).isin(transfer_years)
        & saved_anchor["memory_scheme"].isin(MEMORY_SCHEMES)
        & saved_anchor["model"].isin(MODEL_VARIANTS)
    ].copy()
    source_reference["period"] = source_reference["test_year"].astype(int).map(_period)
    source_summary_rows: list[dict[str, Any]] = []
    for (period, memory, model_name), g in source_reference.groupby(
        ["period", "memory_scheme", "model"], sort=True
    ):
        row = {"period": period, "memory_scheme": memory, "model": model_name}
        row.update(_summary(g))
        source_summary_rows.append(row)
    source_summary = pd.DataFrame(source_summary_rows)

    destination_increments = pd.DataFrame(_increment_table(destination_summary, "destination_transfer"))
    source_increments = pd.DataFrame(_increment_table(source_summary, "source_us"))

    retention_rows: list[dict[str, Any]] = []
    d = destination_increments[
        destination_increments["comparison"] == "macro_gbm_minus_price_gbm"
    ]
    s = source_increments[
        source_increments["comparison"] == "macro_gbm_minus_price_gbm"
    ]
    for _, dr in d.iterrows():
        sr = s[
            (s["period"] == dr["period"])
            & (s["memory_scheme"] == dr["memory_scheme"])
        ]
        if sr.empty:
            continue
        source_ic = float(sr.iloc[0]["mean_ic_increment"])
        source_spread = float(sr.iloc[0]["tail_spread_increment"])
        retention_rows.append(
            {
                "period": dr["period"],
                "memory_scheme": dr["memory_scheme"],
                "source_macro_gbm_ic_increment": source_ic,
                "destination_macro_gbm_ic_increment": float(dr["mean_ic_increment"]),
                "ic_transfer_retention_ratio": (
                    float(dr["mean_ic_increment"] / source_ic) if source_ic != 0 else None
                ),
                "source_macro_gbm_spread_increment": source_spread,
                "destination_macro_gbm_spread_increment": float(dr["tail_spread_increment"]),
                "spread_transfer_retention_ratio": (
                    float(dr["tail_spread_increment"] / source_spread)
                    if source_spread != 0 else None
                ),
            }
        )

    asset_summary, asset_concentration = _asset_concentration(pred)

    source_manifest_path = destination_data_dir / "experiment_011_source_manifest.json"
    source_manifest_sha = _sha256(source_manifest_path) if source_manifest_path.exists() else None
    source_records: dict[str, Any] = {}
    for ticker in DESTINATION_UNIVERSE:
        path = destination_data_dir / f"{ticker}_1D.csv"
        frame = destination_frames[ticker]
        source_records[ticker] = {
            "path": str(path),
            "sha256": _sha256(path),
            "rows": int(len(frame)),
            "first": str(frame.index.min().date()),
            "last": str(frame.index.max().date()),
        }

    pred.to_csv(out_dir / "experiment_011_transfer_predictions.csv", index=False)
    anchor_metrics.to_csv(out_dir / "experiment_011_anchor_metrics.csv", index=False)
    yearly.to_csv(out_dir / "experiment_011_yearly_metrics.csv", index=False)
    parity.to_csv(out_dir / "experiment_011_source_parity.csv", index=False)
    support.to_csv(out_dir / "experiment_011_fold_support.csv", index=False)
    destination_summary.to_csv(out_dir / "experiment_011_destination_summary.csv", index=False)
    pd.concat([source_increments, destination_increments], ignore_index=True).to_csv(
        out_dir / "experiment_011_increment_comparison.csv", index=False
    )
    asset_summary.to_csv(out_dir / "experiment_011_asset_attribution.csv", index=False)

    report = {
        "experiment": "ML_LAB_EXPERIMENT_011_CROSS_UNIVERSE_TRANSFER",
        "status": "EXPLORATORY_NONCONFIRMATORY",
        "boundary": "Source models trained only on original U.S. universe; destination is prediction-only. No tuning, no 2025 holdout use, no Core/runtime/portfolio/capital implication.",
        "design": {
            "source_universe": list(exp5.UNIVERSE),
            "destination_universe": list(DESTINATION_UNIVERSE),
            "destination_training_performed": False,
            "memory_schemes": MEMORY_SCHEMES,
            "models": list(MODEL_VARIANTS),
            "price_features": list(exp9.PRICE_FEATURES),
            "macro_states": list(exp9.MACRO_STATES),
            "interaction_bases": list(exp9.INTERACTION_BASES),
            "augmented_feature_count": len(exp9.AUGMENTED_FEATURES),
            "target_changed": False,
            "hyperparameters_changed": False,
            "source_parity_tolerance": PARITY_TOLERANCE,
            "reserved_2025_campaign50_holdout_used": False,
            "last_allowed_date": str(exp5.LAST_ALLOWED_DATE.date()),
        },
        "calendar": {
            "source_common_sessions": int(len(source_calendar)),
            "destination_common_sessions": int(len(destination_calendar)),
            "source_panel_anchors": int(source_panel["timestamp"].nunique()),
            "destination_panel_anchors": int(destination_panel["timestamp"].nunique()),
            "transfer_test_years": transfer_years,
            "destination_first_anchor": str(destination_panel["timestamp"].min().date()),
            "destination_last_anchor": str(destination_panel["timestamp"].max().date()),
        },
        "source_parity": {
            "checks": int(len(parity)),
            "all_passed": bool(parity["passed"].all()),
            "max_abs_score_delta": float(parity["max_abs_score_delta"].max()),
        },
        "destination_model_summary": destination_summary_rows,
        "source_us_increment_summary": source_increments.to_dict(orient="records"),
        "destination_increment_summary": destination_increments.to_dict(orient="records"),
        "macro_gbm_transfer_retention": retention_rows,
        "destination_asset_concentration": asset_concentration,
        "destination_sources": source_records,
        "source_manifest": {
            "path": str(source_manifest_path),
            "sha256": source_manifest_sha,
        },
        "artifact_files": {
            "transfer_predictions": "experiment_011_transfer_predictions.csv",
            "anchor_metrics": "experiment_011_anchor_metrics.csv",
            "yearly_metrics": "experiment_011_yearly_metrics.csv",
            "source_parity": "experiment_011_source_parity.csv",
            "fold_support": "experiment_011_fold_support.csv",
            "destination_summary": "experiment_011_destination_summary.csv",
            "increment_comparison": "experiment_011_increment_comparison.csv",
            "asset_attribution": "experiment_011_asset_attribution.csv",
        },
    }
    (out_dir / "experiment_011_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
