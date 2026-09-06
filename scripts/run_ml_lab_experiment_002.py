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
import sys
from dataclasses import asdict, dataclass
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
    "abs_ret_24h",
    "realized_vol_24h",
    "realized_vol_72h",
    "realized_vol_168h",
    "vol_ratio_24_168",
    "vol_ratio_72_168",
    "drawdown_from_high_168h",
    "range_position_168h",
]
TEST_START_YEAR = 2020
EXPANSION_RATIO_THRESHOLD = 1.25
MIN_TRAIN_ROWS = 5000
MIN_TRAIN_EVENTS = 100
RANDOM_STATE = 42


@dataclass(frozen=True)
class FoldMetrics:
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
    p = argparse.ArgumentParser(description="ML Lab Experiment 002: volatility expansion nonlinearity probe")
    p.add_argument("--btc", default="data/btcusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--eth", default="data/ethusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--output-dir", default="artifacts/ml_lab_experiment_002")
    return p.parse_args()


def _future_realized_vol(log_ret: pd.Series, horizon: int = 24) -> pd.Series:
    # At row t, use returns t+1 ... t+horizon only. Rolling result at t+horizon
    # is shifted back to t, so no return at/before t enters the target window.
    return log_ret.rolling(horizon, min_periods=horizon).std().shift(-horizon)


def _build_frame(ohlcv: pd.DataFrame, asset: str) -> pd.DataFrame:
    close = ohlcv["close"].astype(float)
    high = ohlcv["high"].astype(float)
    low = ohlcv["low"].astype(float)
    log_ret = np.log(close).diff()

    ret_1 = close.pct_change(1)
    ret_24 = close.pct_change(24)
    ret_72 = close.pct_change(72)
    ret_168 = close.pct_change(168)

    vol_24 = log_ret.rolling(24, min_periods=24).std()
    vol_72 = log_ret.rolling(72, min_periods=72).std()
    vol_168 = log_ret.rolling(168, min_periods=168).std()
    future_vol_24 = _future_realized_vol(log_ret, 24)
    expansion_ratio = future_vol_24 / vol_24
    expansion = (expansion_ratio >= EXPANSION_RATIO_THRESHOLD).astype(int)

    high_168 = high.rolling(168, min_periods=168).max()
    low_168 = low.rolling(168, min_periods=168).min()

    frame = pd.DataFrame(
        {
            "asset": asset,
            "ret_1h": ret_1,
            "ret_24h": ret_24,
            "ret_72h": ret_72,
            "ret_168h": ret_168,
            "abs_ret_24h": ret_24.abs(),
            "realized_vol_24h": vol_24,
            "realized_vol_72h": vol_72,
            "realized_vol_168h": vol_168,
            "vol_ratio_24_168": vol_24 / vol_168,
            "vol_ratio_72_168": vol_72 / vol_168,
            "drawdown_from_high_168h": close / high_168 - 1.0,
            "range_position_168h": (close - low_168) / (high_168 - low_168).replace(0, np.nan),
            "future_realized_vol_24h": future_vol_24,
            "expansion_ratio": expansion_ratio,
            "volatility_expansion": expansion,
        },
        index=ohlcv.index,
    )
    frame.index.name = "timestamp"
    return frame.replace([np.inf, -np.inf], np.nan).dropna()


def _logistic() -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("model", LogisticRegression(C=0.25, max_iter=2000, random_state=RANDOM_STATE)),
    ])


def _gbm() -> Pipeline:
    return Pipeline([
        ("model", GradientBoostingClassifier(
            n_estimators=200, max_depth=2, learning_rate=0.04, random_state=RANDOM_STATE
        )),
    ])


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
    return n, events, rate, (float(rate / base) if base > 0 else None)


def _metrics(year: int, role: str, model_name: str, y: pd.Series, p: pd.Series) -> FoldMetrics:
    top_n, top_events, top_rate, top_lift = _top5(y, p)
    return FoldMetrics(
        test_year=year,
        role=role,
        model=model_name,
        rows=int(len(y)),
        events=int(y.sum()),
        event_rate=float(y.mean()),
        roc_auc=_safe_auc(y, p),
        average_precision=_safe_ap(y, p),
        brier=float(brier_score_loss(y, p)),
        top5_rows=top_n,
        top5_events=top_events,
        top5_rate=top_rate,
        top5_lift=top_lift,
    )


def _importance(estimator: Pipeline, model_name: str) -> dict[str, float]:
    if model_name == "logistic":
        coef = estimator.named_steps["model"].coef_[0]
        return {f: float(abs(v)) for f, v in zip(FEATURES, coef, strict=True)}
    values = estimator.named_steps["model"].feature_importances_
    return {f: float(v) for f, v in zip(FEATURES, values, strict=True)}


def _pooled(pred: pd.DataFrame, role: str, model: str) -> dict[str, Any]:
    s = pred[(pred.role == role) & (pred.model == model)]
    y, p = s.y.astype(int), s.p.astype(float)
    top_n, top_events, top_rate, top_lift = _top5(y, p)
    return {
        "role": role, "model": model, "rows": int(len(s)), "events": int(y.sum()),
        "event_rate": float(y.mean()), "roc_auc": _safe_auc(y, p),
        "average_precision": _safe_ap(y, p), "brier": float(brier_score_loss(y, p)),
        "top5_rows": top_n, "top5_events": top_events, "top5_rate": top_rate, "top5_lift": top_lift,
    }


def main() -> None:
    args = parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    btc = _build_frame(read_ohlcv(args.btc), "BTC")
    eth = _build_frame(read_ohlcv(args.eth), "ETH")

    fold_rows: list[dict[str, Any]] = []
    prediction_rows: list[pd.DataFrame] = []
    importance_rows: list[dict[str, Any]] = []

    years = sorted(y for y in btc.index.year.unique() if y >= TEST_START_YEAR)
    for year in years:
        train = btc[btc.index.year < year]
        btc_test = btc[btc.index.year == year]
        eth_test = eth[eth.index.year == year]
        events = int(train.volatility_expansion.sum())
        nonevents = int((train.volatility_expansion == 0).sum())
        if len(train) < MIN_TRAIN_ROWS or events < MIN_TRAIN_EVENTS or nonevents < MIN_TRAIN_EVENTS:
            continue

        naive_p = float(train.volatility_expansion.mean())
        fitted = {"logistic": _logistic(), "gbm": _gbm()}
        for name, estimator in fitted.items():
            estimator.fit(train[FEATURES].astype(float), train.volatility_expansion.astype(int))
            imp = _importance(estimator, name)
            importance_rows.extend({"test_year": year, "model": name, "feature": f, "importance": v} for f, v in imp.items())

        for role, test in (("btc_oos", btc_test), ("eth_transfer", eth_test)):
            if test.empty:
                continue
            y = test.volatility_expansion.astype(int)
            probs: dict[str, pd.Series] = {"naive": pd.Series(naive_p, index=test.index)}
            for name, estimator in fitted.items():
                probs[name] = pd.Series(estimator.predict_proba(test[FEATURES].astype(float))[:, 1], index=test.index)
            for name, p in probs.items():
                fold_rows.append(asdict(_metrics(year, role, name, y, p)))
                prediction_rows.append(pd.DataFrame({
                    "timestamp": test.index, "test_year": year, "role": role,
                    "model": name, "y": y.values, "p": p.values,
                }))

    folds = pd.DataFrame(fold_rows)
    predictions = pd.concat(prediction_rows, ignore_index=True)
    importance = pd.DataFrame(importance_rows)
    folds.to_csv(out / "experiment_002_fold_metrics.csv", index=False)
    predictions.to_csv(out / "experiment_002_oos_predictions.csv", index=False)
    importance.to_csv(out / "experiment_002_feature_importance_by_fold.csv", index=False)

    pooled = [_pooled(predictions, role, model) for role in ("btc_oos", "eth_transfer") for model in ("naive", "logistic", "gbm")]
    deltas = []
    for role in ("btc_oos", "eth_transfer"):
        pivot = folds[folds.role == role].pivot(index="test_year", columns="model", values="roc_auc")
        d = (pivot.gbm - pivot.logistic).dropna()
        deltas.append({
            "role": role, "eligible_years": int(len(d)), "gbm_wins": int((d > 0).sum()),
            "logistic_wins": int((d < 0).sum()), "ties": int((d == 0).sum()),
            "gbm_auc_minus_logistic_mean": float(d.mean()), "gbm_auc_minus_logistic_median": float(d.median()),
            "year_deltas": {str(int(k)): float(v) for k, v in d.items()},
        })

    feature_summary: dict[str, Any] = {}
    for model in ("logistic", "gbm"):
        s = importance[importance.model == model].groupby("feature").importance.mean().sort_values(ascending=False)
        feature_summary[model] = {"mean_importance": {k: float(v) for k, v in s.items()}, "top5": list(s.head(5).index)}

    report = {
        "experiment": "ML_LAB_EXPERIMENT_002_VOLATILITY_EXPANSION",
        "status": "EXPLORATORY_NONCONFIRMATORY",
        "boundary": "Exploratory ML Lab only; no Core/runtime/portfolio/capital implication.",
        "data": {"btc": args.btc, "eth": args.eth},
        "design": {
            "target": "future 24h realized vol / trailing 24h realized vol >= 1.25",
            "expansion_ratio_threshold": EXPANSION_RATIO_THRESHOLD,
            "features": FEATURES,
            "test_start_year": TEST_START_YEAR,
            "transfer": "Each yearly model is fit on pre-year BTC only, then applied unchanged to ETH in the same test year.",
            "models": {
                "naive": "BTC training event-rate constant",
                "logistic": "StandardScaler + LogisticRegression(C=0.25,max_iter=2000,random_state=42), unweighted",
                "gbm": "GradientBoostingClassifier(n_estimators=200,max_depth=2,learning_rate=0.04,random_state=42)",
            },
        },
        "pooled_metrics": pooled,
        "fold_delta_summary": deltas,
        "feature_importance": feature_summary,
    }
    (out / "experiment_002_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
