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
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parent.parent

from research.jump_risk_engine.lab import read_ohlcv


FEATURES = [
    "ret_1h",
    "ret_24h",
    "ret_72h",
    "ret_168h",
    "trend_strength_24_168",
    "trend_acceleration_24_168",
    "realized_vol_24h",
    "realized_vol_168h",
    "vol_ratio_24_168",
    "distance_sma_24h",
    "drawdown_from_high_168h",
    "range_position_168h",
]

HORIZONS = (24, 72)
ABSOLUTE_FLOORS = {24: 0.01, 72: 0.02}
TEST_START_YEAR = 2020
MIN_TRAIN_ROWS = 5000
MIN_TRAIN_EVENTS = 40
RANDOM_STATE = 42


@dataclass(frozen=True)
class FoldMetrics:
    horizon_hours: int
    test_year: int
    role: str
    model: str
    rows: int
    events: int
    event_rate: float
    roc_auc: float | None
    average_precision: float | None
    brier: float | None
    top5_rows: int
    top5_events: int
    top5_rate: float | None
    top5_lift: float | None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ML Lab Experiment 001: continuation nonlinearity probe")
    p.add_argument(
        "--btc",
        default="data/btcusd_3600s_2018-01-01_to_2025-12-31.csv",
        help="BTC hourly OHLCV CSV",
    )
    p.add_argument(
        "--eth",
        default="data/ethusd_3600s_2018-01-01_to_2025-12-31.csv",
        help="ETH hourly OHLCV CSV",
    )
    p.add_argument("--output-dir", default="artifacts/ml_lab_experiment_001")
    return p.parse_args()


def _future_return(close: pd.Series, horizon: int) -> pd.Series:
    return close.shift(-horizon) / close - 1.0


def _build_frame(ohlcv: pd.DataFrame, horizon: int, asset: str) -> pd.DataFrame:
    close = ohlcv["close"].astype(float)
    high = ohlcv["high"].astype(float)
    low = ohlcv["low"].astype(float)
    log_ret = np.log(close).diff()

    sma_24 = close.rolling(24, min_periods=24).mean()
    sma_168 = close.rolling(168, min_periods=168).mean()
    high_168 = high.rolling(168, min_periods=168).max()
    low_168 = low.rolling(168, min_periods=168).min()

    ret_1 = close.pct_change(1)
    ret_24 = close.pct_change(24)
    ret_72 = close.pct_change(72)
    ret_168 = close.pct_change(168)

    vol_24 = log_ret.rolling(24, min_periods=24).std()
    vol_168 = log_ret.rolling(168, min_periods=168).std()

    future_return = _future_return(close, horizon)
    trend_direction = np.sign(ret_24).replace(0, np.nan)
    magnitude_floor = np.maximum(
        ABSOLUTE_FLOORS[horizon],
        vol_24 * math.sqrt(horizon),
    )
    signed_future = future_return * trend_direction
    continuation = (signed_future >= magnitude_floor).astype(int)

    frame = pd.DataFrame(
        {
            "asset": asset,
            "close": close,
            "ret_1h": ret_1,
            "ret_24h": ret_24,
            "ret_72h": ret_72,
            "ret_168h": ret_168,
            "trend_strength_24_168": sma_24 / sma_168 - 1.0,
            "trend_acceleration_24_168": ret_24 - ret_168,
            "realized_vol_24h": vol_24,
            "realized_vol_168h": vol_168,
            "vol_ratio_24_168": vol_24 / vol_168,
            "distance_sma_24h": close / sma_24 - 1.0,
            "drawdown_from_high_168h": close / high_168 - 1.0,
            "range_position_168h": (close - low_168) / (high_168 - low_168).replace(0, np.nan),
            "trend_direction": trend_direction,
            "future_return": future_return,
            "magnitude_floor": magnitude_floor,
            "continuation": continuation,
        },
        index=ohlcv.index,
    )
    frame.index.name = "timestamp"
    return frame.replace([np.inf, -np.inf], np.nan).dropna()


def _logistic() -> Pipeline:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    C=0.25,
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def _gbm() -> Pipeline:
    return Pipeline(
        [
            (
                "model",
                GradientBoostingClassifier(
                    n_estimators=200,
                    max_depth=2,
                    learning_rate=0.04,
                    random_state=RANDOM_STATE,
                ),
            )
        ]
    )


def _safe_auc(y: pd.Series, p: pd.Series) -> float | None:
    return None if y.nunique() < 2 else float(roc_auc_score(y, p))


def _safe_ap(y: pd.Series, p: pd.Series) -> float | None:
    return None if int(y.sum()) == 0 else float(average_precision_score(y, p))


def _top5(y: pd.Series, p: pd.Series) -> tuple[int, int, float | None, float | None]:
    joined = pd.DataFrame({"y": y.astype(int), "p": p.astype(float)}).dropna().sort_values("p", ascending=False)
    if joined.empty:
        return 0, 0, None, None
    n = max(1, int(round(len(joined) * 0.05)))
    top = joined.head(n)
    events = int(top["y"].sum())
    rate = float(top["y"].mean())
    base = float(joined["y"].mean())
    lift = None if base <= 0 else float(rate / base)
    return n, events, rate, lift


def _metrics(horizon: int, year: int, role: str, model_name: str, y: pd.Series, p: pd.Series) -> FoldMetrics:
    top_n, top_events, top_rate, top_lift = _top5(y, p)
    return FoldMetrics(
        horizon_hours=horizon,
        test_year=year,
        role=role,
        model=model_name,
        rows=int(len(y)),
        events=int(y.sum()),
        event_rate=float(y.mean()),
        roc_auc=_safe_auc(y, p),
        average_precision=_safe_ap(y, p),
        brier=float(brier_score_loss(y, p)) if len(y) else None,
        top5_rows=top_n,
        top5_events=top_events,
        top5_rate=top_rate,
        top5_lift=top_lift,
    )


def _importance(estimator: Pipeline, model_name: str) -> dict[str, float]:
    if model_name == "logistic":
        coef = estimator.named_steps["model"].coef_[0]
        return {feature: float(abs(value)) for feature, value in zip(FEATURES, coef, strict=True)}
    if model_name == "gbm":
        values = estimator.named_steps["model"].feature_importances_
        return {feature: float(value) for feature, value in zip(FEATURES, values, strict=True)}
    raise ValueError(model_name)


def _pooled_metrics(predictions: pd.DataFrame, horizon: int, role: str, model_name: str) -> dict[str, Any]:
    subset = predictions[
        (predictions["horizon_hours"] == horizon)
        & (predictions["role"] == role)
        & (predictions["model"] == model_name)
    ]
    if subset.empty:
        return {
            "horizon_hours": horizon,
            "role": role,
            "model": model_name,
            "rows": 0,
        }
    y = subset["y"].astype(int)
    p = subset["p"].astype(float)
    top_n, top_events, top_rate, top_lift = _top5(y, p)
    return {
        "horizon_hours": horizon,
        "role": role,
        "model": model_name,
        "rows": int(len(subset)),
        "events": int(y.sum()),
        "event_rate": float(y.mean()),
        "roc_auc": _safe_auc(y, p),
        "average_precision": _safe_ap(y, p),
        "brier": float(brier_score_loss(y, p)),
        "top5_rows": top_n,
        "top5_events": top_events,
        "top5_rate": top_rate,
        "top5_lift": top_lift,
    }


def _delta_summary(folds: pd.DataFrame, horizon: int, role: str) -> dict[str, Any]:
    pivot = folds[(folds["horizon_hours"] == horizon) & (folds["role"] == role)].pivot(
        index="test_year", columns="model", values="roc_auc"
    )
    if "gbm" not in pivot.columns or "logistic" not in pivot.columns:
        return {"horizon_hours": horizon, "role": role, "eligible_years": 0}
    pivot = pivot.dropna(subset=["gbm", "logistic"]).copy()
    if pivot.empty:
        return {"horizon_hours": horizon, "role": role, "eligible_years": 0}
    delta = pivot["gbm"] - pivot["logistic"]
    return {
        "horizon_hours": horizon,
        "role": role,
        "eligible_years": int(len(delta)),
        "gbm_auc_minus_logistic_mean": float(delta.mean()),
        "gbm_auc_minus_logistic_median": float(delta.median()),
        "gbm_wins": int((delta > 0).sum()),
        "logistic_wins": int((delta < 0).sum()),
        "ties": int((delta == 0).sum()),
        "year_deltas": {str(int(year)): float(value) for year, value in delta.items()},
    }


def run_horizon(btc: pd.DataFrame, eth: pd.DataFrame, horizon: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    btc_frame = _build_frame(btc, horizon, "BTC")
    eth_frame = _build_frame(eth, horizon, "ETH")

    fold_records: list[dict[str, Any]] = []
    prediction_records: list[dict[str, Any]] = []
    importance_records: list[dict[str, Any]] = []

    years = sorted(y for y in btc_frame.index.year.unique() if y >= TEST_START_YEAR)
    for year in years:
        train = btc_frame[btc_frame.index.year < year]
        btc_test = btc_frame[btc_frame.index.year == year]
        eth_test = eth_frame[eth_frame.index.year == year]

        train_events = int(train["continuation"].sum())
        train_nonevents = int((train["continuation"] == 0).sum())
        if (
            len(train) < MIN_TRAIN_ROWS
            or train_events < MIN_TRAIN_EVENTS
            or train_nonevents < MIN_TRAIN_EVENTS
            or btc_test.empty
            or eth_test.empty
        ):
            continue

        train_rate = float(train["continuation"].mean())

        naive_btc = pd.Series(train_rate, index=btc_test.index, dtype=float)
        naive_eth = pd.Series(train_rate, index=eth_test.index, dtype=float)
        for role, test, probs in (
            ("btc_oos", btc_test, naive_btc),
            ("eth_transfer", eth_test, naive_eth),
        ):
            m = _metrics(horizon, int(year), role, "naive", test["continuation"].astype(int), probs)
            fold_records.append(m.__dict__)
            for ts, y_value, p_value in zip(test.index, test["continuation"], probs, strict=True):
                prediction_records.append(
                    {
                        "timestamp": str(ts),
                        "horizon_hours": horizon,
                        "test_year": int(year),
                        "role": role,
                        "model": "naive",
                        "y": int(y_value),
                        "p": float(p_value),
                    }
                )

        for model_name, factory in (("logistic", _logistic), ("gbm", _gbm)):
            estimator = factory()
            estimator.fit(train[FEATURES].astype(float), train["continuation"].astype(int))

            importance = _importance(estimator, model_name)
            importance_records.append(
                {
                    "horizon_hours": horizon,
                    "test_year": int(year),
                    "model": model_name,
                    **importance,
                }
            )

            for role, test in (("btc_oos", btc_test), ("eth_transfer", eth_test)):
                probs = pd.Series(
                    estimator.predict_proba(test[FEATURES].astype(float))[:, 1],
                    index=test.index,
                    dtype=float,
                )
                y = test["continuation"].astype(int)
                m = _metrics(horizon, int(year), role, model_name, y, probs)
                fold_records.append(m.__dict__)
                for ts, y_value, p_value in zip(test.index, y, probs, strict=True):
                    prediction_records.append(
                        {
                            "timestamp": str(ts),
                            "horizon_hours": horizon,
                            "test_year": int(year),
                            "role": role,
                            "model": model_name,
                            "y": int(y_value),
                            "p": float(p_value),
                        }
                    )

    return fold_records, prediction_records, importance_records


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    btc_path = Path(args.btc)
    eth_path = Path(args.eth)
    if not btc_path.exists() or not eth_path.exists():
        missing = [str(p) for p in (btc_path, eth_path) if not p.exists()]
        raise FileNotFoundError(f"Missing required dataset(s): {missing}")

    btc = read_ohlcv(btc_path)
    eth = read_ohlcv(eth_path)

    all_folds: list[dict[str, Any]] = []
    all_predictions: list[dict[str, Any]] = []
    all_importance: list[dict[str, Any]] = []

    for horizon in HORIZONS:
        folds, predictions, importance = run_horizon(btc, eth, horizon)
        all_folds.extend(folds)
        all_predictions.extend(predictions)
        all_importance.extend(importance)

    folds_df = pd.DataFrame(all_folds)
    predictions_df = pd.DataFrame(all_predictions)
    importance_df = pd.DataFrame(all_importance)

    if folds_df.empty or predictions_df.empty:
        raise RuntimeError("No eligible walk-forward folds were produced")

    pooled = []
    for horizon in HORIZONS:
        for role in ("btc_oos", "eth_transfer"):
            for model_name in ("naive", "logistic", "gbm"):
                pooled.append(_pooled_metrics(predictions_df, horizon, role, model_name))

    deltas = []
    for horizon in HORIZONS:
        for role in ("btc_oos", "eth_transfer"):
            deltas.append(_delta_summary(folds_df, horizon, role))

    importance_summary: dict[str, Any] = {}
    if not importance_df.empty:
        for horizon in HORIZONS:
            importance_summary[str(horizon)] = {}
            subset_h = importance_df[importance_df["horizon_hours"] == horizon]
            for model_name in ("logistic", "gbm"):
                subset = subset_h[subset_h["model"] == model_name]
                if subset.empty:
                    continue
                means = subset[FEATURES].mean().sort_values(ascending=False)
                importance_summary[str(horizon)][model_name] = {
                    "mean_importance": {feature: float(value) for feature, value in means.items()},
                    "top5": [str(x) for x in means.head(5).index],
                }

    report = {
        "experiment": "ML_LAB_EXPERIMENT_001_CONTINUATION_NONLINEARITY",
        "status": "EXPLORATORY_NONCONFIRMATORY",
        "boundary": "Exploratory ML Lab only; no Core/runtime/portfolio/capital implication.",
        "data": {"btc": str(btc_path), "eth": str(eth_path)},
        "design": {
            "horizons_hours": list(HORIZONS),
            "absolute_floors": {str(k): v for k, v in ABSOLUTE_FLOORS.items()},
            "test_start_year": TEST_START_YEAR,
            "features": FEATURES,
            "models": {
                "naive": "BTC training event-rate constant",
                "logistic": "StandardScaler + LogisticRegression(C=0.25,class_weight=balanced,max_iter=2000,random_state=42)",
                "gbm": "GradientBoostingClassifier(n_estimators=200,max_depth=2,learning_rate=0.04,random_state=42)",
            },
            "transfer": "Each yearly model is fit on pre-year BTC only, then applied unchanged to ETH in the same test year.",
        },
        "pooled_metrics": pooled,
        "fold_delta_summary": deltas,
        "feature_importance": importance_summary,
    }

    folds_df.to_csv(out_dir / "experiment_001_fold_metrics.csv", index=False)
    predictions_df.to_csv(out_dir / "experiment_001_oos_predictions.csv", index=False)
    importance_df.to_csv(out_dir / "experiment_001_feature_importance_by_fold.csv", index=False)
    (out_dir / "experiment_001_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
