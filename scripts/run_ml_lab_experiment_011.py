from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Resolve sibling imports for both direct-script and module execution.
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_ml_lab_experiment_005 as exp5
import run_ml_lab_experiment_009 as exp9

DESTINATION_UNIVERSE = (
    "EWA",
    "EWC",
    "EWG",
    "EWH",
    "EWI",
    "EWJ",
    "EWL",
    "EWM",
    "EWW",
    "EWP",
    "EWS",
    "EWT",
    "EWU",
    "EWZ",
)
MEMORY_SCHEMES: dict[str, int | None] = {"expanding": None, "trailing_3y": 3}
MODEL_VARIANTS = {
    "price_ridge": (
        lambda: Pipeline([("scale", StandardScaler()), ("ridge", Ridge(alpha=10.0))]),
        exp9.PRICE_FEATURES,
    ),
    "price_gbm": (
        lambda: GradientBoostingRegressor(
            n_estimators=200,
            max_depth=2,
            learning_rate=0.04,
            random_state=42,
        ),
        exp9.PRICE_FEATURES,
    ),
    "macro_ridge": (
        lambda: Pipeline([("scale", StandardScaler()), ("ridge", Ridge(alpha=10.0))]),
        exp9.AUGMENTED_FEATURES,
    ),
    "macro_gbm": (
        lambda: GradientBoostingRegressor(
            n_estimators=200,
            max_depth=2,
            learning_rate=0.04,
            random_state=42,
        ),
        exp9.AUGMENTED_FEATURES,
    ),
}
PARITY_TOLERANCE = 1e-10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-data-dir", default="data")
    parser.add_argument("--destination-data-dir", default="data/ml_lab_transfer_011")
    parser.add_argument("--experiment-009-dir", default="artifacts/ml_lab_experiment_009")
    parser.add_argument("--output-dir", default="artifacts/ml_lab_experiment_011")
    return parser.parse_args()


def _load_destination(data_dir: Path) -> dict[str, pd.DataFrame]:
    missing = [str(data_dir / f"{ticker}_1D.csv") for ticker in DESTINATION_UNIVERSE if not (data_dir / f"{ticker}_1D.csv").exists()]
    if missing:
        raise FileNotFoundError("MISSING_DESTINATION_SOURCES:\n" + "\n".join(missing))
    frames: dict[str, pd.DataFrame] = {}
    for ticker in DESTINATION_UNIVERSE:
        path = data_dir / f"{ticker}_1D.csv"
        frame = pd.read_csv(path)
        ts_col = "timestamp" if "timestamp" in frame.columns else frame.columns[0]
        frame[ts_col] = pd.to_datetime(frame[ts_col], utc=True, errors="coerce")
        frame = frame.dropna(subset=[ts_col]).set_index(ts_col).sort_index()
        frame = frame.loc[frame.index <= exp5.LAST_ALLOWED_DATE].copy()
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame["volume"] = pd.to_numeric(frame.get("volume", 0.0), errors="coerce").fillna(0.0)
        frame = frame.dropna(subset=["close"])
        if frame.empty:
            raise ValueError(f"EMPTY_DESTINATION_SOURCE:{ticker}")
        frames[ticker] = frame
    return frames


def _common_calendar(frames: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    common: pd.DatetimeIndex | None = None
    for frame in frames.values():
        idx = pd.DatetimeIndex(frame.index)
        common = idx if common is None else common.intersection(idx)
    if common is None or len(common) < 500:
        raise ValueError("INSUFFICIENT_DESTINATION_COMMON_CALENDAR")
    return common.sort_values()


def _build_panel(frames: dict[str, pd.DataFrame], calendar: pd.DatetimeIndex) -> pd.DataFrame:
    return exp5._build_panel(frames, calendar)


def _training_slice(panel: pd.DataFrame, test_start: pd.Timestamp, years: int | None) -> pd.DataFrame:
    train = panel[
        (panel["timestamp"] < test_start)
        & (panel["target_end_date"] < test_start)
    ].copy()
    if years is not None:
        cutoff = test_start - pd.DateOffset(years=years)
        train = train[train["timestamp"] >= cutoff].copy()
    return train


def _load_macro_state(path: Path) -> pd.DataFrame:
    macro = pd.read_csv(path)
    macro["timestamp"] = pd.to_datetime(macro["timestamp"], utc=True)
    return macro


def _anchor_metric(group: pd.DataFrame) -> dict[str, Any]:
    rank_ic = float(spearmanr(group["score"], group["target_rank"]).statistic)
    ranked = group.sort_values("score")
    k = max(1, int(np.ceil(len(ranked) * 0.25)))
    bottom = float(ranked.head(k)["target_raw"].mean())
    top = float(ranked.tail(k)["target_raw"].mean())
    return {
        "timestamp": group["timestamp"].iloc[0],
        "test_year": int(group["test_year"].iloc[0]),
        "period": group["period"].iloc[0],
        "memory_scheme": group["memory_scheme"].iloc[0],
        "model": group["model"].iloc[0],
        "rows": int(len(group)),
        "rank_ic": rank_ic,
        "top_minus_bottom_raw_target": top - bottom,
    }


def _summary(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "anchors": int(len(frame)),
        "mean_rank_ic": float(frame["rank_ic"].mean()),
        "median_rank_ic": float(frame["rank_ic"].median()),
        "positive_ic_fraction": float((frame["rank_ic"] > 0).mean()),
        "mean_top_minus_bottom_raw_target": float(frame["top_minus_bottom_raw_target"].mean()),
        "median_top_minus_bottom_raw_target": float(frame["top_minus_bottom_raw_target"].median()),
    }


def _increment_table(summary: pd.DataFrame, role: str) -> list[dict[str, Any]]:
    comparisons = (
        ("macro_ridge", "price_ridge", "macro_ridge_minus_price_ridge"),
        ("macro_gbm", "price_gbm", "macro_gbm_minus_price_gbm"),
        ("macro_gbm", "macro_ridge", "macro_gbm_minus_macro_ridge"),
    )
    rows: list[dict[str, Any]] = []
    for (period, memory), g in summary.groupby(["period", "memory_scheme"], sort=True):
        for lhs, rhs, name in comparisons:
            l = g[g["model"] == lhs]
            r = g[g["model"] == rhs]
            if l.empty or r.empty:
                continue
            rows.append(
                {
                    "role": role,
                    "period": period,
                    "memory_scheme": memory,
                    "comparison": name,
                    "mean_ic_increment": float(l.iloc[0]["mean_rank_ic"] - r.iloc[0]["mean_rank_ic"]),
                    "tail_spread_increment": float(
                        l.iloc[0]["mean_top_minus_bottom_raw_target"]
                        - r.iloc[0]["mean_top_minus_bottom_raw_target"]
                    ),
                }
            )
    return rows


def _period(year: int) -> str:
    return "pre_2022" if year <= 2021 else "post_2022_2024"


def _parity_check(
    saved: pd.DataFrame,
    source_test: pd.DataFrame,
    scores: np.ndarray,
    year: int,
    memory: str,
    model: str,
) -> dict[str, Any]:
    expected = saved[
        (saved["test_year"].astype(int) == year)
        & (saved["memory_scheme"] == memory)
        & (saved["model"] == model)
    ][["timestamp", "ticker", "score"]].copy()
    actual = source_test[["timestamp", "ticker"]].copy()
    actual["score_actual"] = scores
    expected = expected.rename(columns={"score": "score_expected"})
    merged = actual.merge(expected, on=["timestamp", "ticker"], how="inner", validate="one_to_one")
    if len(merged) != len(actual) or len(merged) != len(expected):
        raise ValueError(f"SOURCE_PARITY_ROW_MISMATCH:{year}:{memory}:{model}")
    max_delta = float((merged["score_actual"] - merged["score_expected"]).abs().max())
    passed = max_delta <= PARITY_TOLERANCE
    if not passed:
        raise ValueError(f"SOURCE_PARITY_FAILURE:{year}:{memory}:{model}:{max_delta}")
    return {
        "test_year": year,
        "memory_scheme": memory,
        "model": model,
        "rows": int(len(merged)),
        "max_abs_score_delta": max_delta,
        "passed": bool(passed),
    }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _asset_concentration(pred: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for (period, memory), g in pred.groupby(["period", "memory_scheme"], sort=True):
        mg = g[g["model"] == "macro_gbm"][["timestamp", "ticker", "score"]].rename(columns={"score": "macro_score"})
        pg = g[g["model"] == "price_gbm"][["timestamp", "ticker", "score"]].rename(columns={"score": "price_score"})
        base = mg.merge(pg, on=["timestamp", "ticker"], validate="one_to_one")
        target = g[g["model"] == "macro_gbm"][["timestamp", "ticker", "target_rank"]]
        base = base.merge(target, on=["timestamp", "ticker"], validate="one_to_one")
        base["macro_rank"] = base.groupby("timestamp")["macro_score"].rank(pct=True)
        base["price_rank"] = base.groupby("timestamp")["price_score"].rank(pct=True)
        base["centered_rank_delta"] = (base["macro_rank"] - base["price_rank"]) * (base["target_rank"] - 0.5)
        asset = base.groupby("ticker")["centered_rank_delta"].mean().sort_values(ascending=False)
        positive = asset[asset > 0]
        total_positive = float(positive.sum())
        top = positive.head(3)
        concentration = float(top.sum() / total_positive) if total_positive > 0 else None
        for ticker, value in asset.items():
            rows.append({"period": period, "memory_scheme": memory, "ticker": ticker, "centered_improvement": float(value)})
        summaries.append(
            {
                "period": period,
                "memory_scheme": memory,
                "positive_tickers": int(len(positive)),
                "top3_share_of_positive_improvement": concentration,
                "top_positive_tickers": list(top.index.astype(str)),
            }
        )
    return pd.DataFrame(rows), summaries


def _json_default(value: Any) -> Any:
    """Convert numpy/pandas scalar values in report payloads to stdlib JSON types."""
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(value))
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


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

    transfer_years = sorted(int(y) for y in anchor_metrics["test_year"].astype(int).unique())
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
    report_json = json.dumps(report, indent=2, sort_keys=True, default=_json_default)
    (out_dir / "experiment_011_report.json").write_text(report_json, encoding="utf-8")
    print(report_json)


if __name__ == "__main__":
    main()
