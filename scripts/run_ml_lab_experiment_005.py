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

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from research.jump_risk_engine.lab import read_ohlcv

UNIVERSE = [
    "RSP", "MDY", "IWM", "IWD", "IWF",
    "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY",
]
FEATURES = [
    "ret_5d_xrank",
    "ret_20d_xrank",
    "ret_60d_xrank",
    "ret_120d_xrank",
    "vol_20d_xrank",
    "vol_60d_xrank",
    "vol_ratio_20_60_xrank",
    "distance_sma_20_xrank",
    "distance_sma_120_xrank",
    "drawdown_120_xrank",
    "range_position_120_xrank",
    "volume_z_60_xrank",
]
TARGET_HORIZON = 20
ANCHOR_STEP = 5
TEST_START_YEAR = 2012
LAST_ALLOWED_DATE = pd.Timestamp("2024-12-31", tz="UTC")
MIN_TRAIN_ROWS = 1000
RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ML Lab Experiment 005: cross-sectional ETF ranking")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--output-dir", default="artifacts/ml_lab_experiment_005")
    return p.parse_args()


def _load_universe(data_dir: Path) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for ticker in UNIVERSE:
        path = data_dir / f"{ticker}_1D.csv"
        if not path.exists():
            missing.append(str(path))
            continue
        frame = read_ohlcv(path).sort_index()
        frame = frame.loc[frame.index <= LAST_ALLOWED_DATE].copy()
        if frame.empty:
            raise ValueError(f"EMPTY_SOURCE_AFTER_CUTOFF: {ticker}")
        frames[ticker] = frame
    if missing:
        raise FileNotFoundError("MISSING_UNIVERSE_SOURCES:\n" + "\n".join(missing))
    return frames


def _common_calendar(frames: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    common: pd.DatetimeIndex | None = None
    for frame in frames.values():
        idx = pd.DatetimeIndex(frame.index)
        common = idx if common is None else common.intersection(idx)
    if common is None or len(common) < 500:
        raise ValueError("COMMON_CALENDAR_TOO_SHORT")
    common = common.sort_values()
    return common[common <= LAST_ALLOWED_DATE]


def _asset_features(frame: pd.DataFrame, calendar: pd.DatetimeIndex, ticker: str) -> pd.DataFrame:
    f = frame.reindex(calendar)
    close = f["close"].astype(float)
    high = f["high"].astype(float)
    low = f["low"].astype(float)
    log_ret = np.log(close).diff()

    sma20 = close.rolling(20, min_periods=20).mean()
    sma120 = close.rolling(120, min_periods=120).mean()
    high120 = high.rolling(120, min_periods=120).max()
    low120 = low.rolling(120, min_periods=120).min()
    vol20 = log_ret.rolling(20, min_periods=20).std()
    vol60 = log_ret.rolling(60, min_periods=60).std()

    volume = np.log(f["volume"].astype(float).replace(0, np.nan))
    vol_mean = volume.rolling(60, min_periods=60).mean()
    vol_std = volume.rolling(60, min_periods=60).std()

    out = pd.DataFrame(
        {
            "ticker": ticker,
            "close": close,
            "ret_5d": close.pct_change(5),
            "ret_20d": close.pct_change(20),
            "ret_60d": close.pct_change(60),
            "ret_120d": close.pct_change(120),
            "vol_20d": vol20,
            "vol_60d": vol60,
            "vol_ratio_20_60": vol20 / vol60,
            "distance_sma_20": close / sma20 - 1.0,
            "distance_sma_120": close / sma120 - 1.0,
            "drawdown_120": close / high120 - 1.0,
            "range_position_120": (close - low120) / (high120 - low120).replace(0, np.nan),
            "volume_z_60": (volume - vol_mean) / vol_std,
        },
        index=calendar,
    )
    out.index.name = "timestamp"
    return out.replace([np.inf, -np.inf], np.nan)


def _build_panel(
    frames: dict[str, pd.DataFrame],
    calendar: pd.DatetimeIndex,
    *,
    universe: list[str] | tuple[str, ...] | None = None,
) -> pd.DataFrame:
    # Existing callers retain the source universe; transfer callers supply their frozen list.
    universe = UNIVERSE if universe is None else universe
    by_asset = {ticker: _asset_features(frame, calendar, ticker) for ticker, frame in frames.items()}
    close_matrix = pd.DataFrame({ticker: by_asset[ticker]["close"] for ticker in universe}, index=calendar)
    vol60_matrix = pd.DataFrame({ticker: by_asset[ticker]["vol_60d"] for ticker in universe}, index=calendar)

    valid_positions = range(120, len(calendar) - TARGET_HORIZON, ANCHOR_STEP)
    rows: list[pd.DataFrame] = []
    raw_feature_names = [name.replace("_xrank", "") for name in FEATURES]

    for pos in valid_positions:
        ts = calendar[pos]
        end_ts = calendar[pos + TARGET_HORIZON]
        if end_ts > LAST_ALLOWED_DATE:
            continue

        feature_slice = pd.DataFrame(
            {ticker: by_asset[ticker].loc[ts, raw_feature_names] for ticker in universe}
        ).T
        if feature_slice.isna().any().any():
            continue

        xrank = feature_slice.rank(axis=0, method="average", pct=True)
        xrank.columns = [f"{c}_xrank" for c in xrank.columns]

        current_close = close_matrix.loc[ts]
        future_close = close_matrix.loc[end_ts]
        trailing_vol = vol60_matrix.loc[ts]
        raw_target = (future_close / current_close - 1.0) / (trailing_vol * math.sqrt(TARGET_HORIZON))
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
        raise ValueError("NO_ELIGIBLE_ANCHORS")
    panel = pd.concat(rows, ignore_index=True)
    panel["timestamp"] = pd.to_datetime(panel["timestamp"])
    panel["target_end_date"] = pd.to_datetime(panel["target_end_date"])
    return panel.sort_values(["timestamp", "ticker"]).reset_index(drop=True)


def _ridge() -> Pipeline:
    return Pipeline([("scale", StandardScaler()), ("model", Ridge(alpha=10.0))])


def _gbm() -> GradientBoostingRegressor:
    return GradientBoostingRegressor(
        n_estimators=200,
        max_depth=2,
        learning_rate=0.04,
        random_state=RANDOM_STATE,
    )


def _importance(model: Any, name: str) -> dict[str, float]:
    if name == "ridge":
        values = np.abs(model.named_steps["model"].coef_)
    else:
        values = model.feature_importances_
    return {feature: float(value) for feature, value in zip(FEATURES, values, strict=True)}


def _anchor_metrics(group: pd.DataFrame, model_name: str) -> dict[str, Any]:
    g = group[group["model"] == model_name].copy()
    score_rank = g["score"].rank(method="average", pct=True)
    ic = float(score_rank.corr(g["target_rank"], method="spearman"))
    n_q = max(1, int(math.ceil(len(g) * 0.25)))
    order = g.assign(score_rank=score_rank).sort_values("score_rank")
    bottom = order.head(n_q)["target_raw"].mean()
    top = order.tail(n_q)["target_raw"].mean()
    return {
        "timestamp": g["timestamp"].iloc[0],
        "test_year": int(g["timestamp"].iloc[0].year),
        "model": model_name,
        "rank_ic": ic,
        "top_minus_bottom_raw_target": float(top - bottom),
        "assets": int(len(g)),
    }


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
