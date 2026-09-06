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
SEVERITY_THRESHOLDS = (1.25, 1.50, 1.75, 2.00)
TEST_START_YEAR = 2020
MIN_TRAIN_ROWS = 5000
MIN_TRAIN_EVENTS = 100
RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ML Lab Experiment 003: volatility-state geometry and tail severity")
    p.add_argument("--btc", default="data/btcusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--eth", default="data/ethusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--output-dir", default="artifacts/ml_lab_experiment_003")
    return p.parse_args()


def _future_realized_vol(log_ret: pd.Series, horizon: int = 24) -> pd.Series:
    # At t, rolling std ending at t+horizon contains log returns t+1 ... t+horizon.
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
            "expansion_ratio": future_vol_24 / vol_24,
        },
        index=ohlcv.index,
    )
    frame.index.name = "timestamp"
    return frame.replace([np.inf, -np.inf], np.nan).dropna()


def _logistic() -> Pipeline:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", LogisticRegression(C=0.25, max_iter=2000, random_state=RANDOM_STATE)),
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


def _tail_stats(y: pd.Series, p: pd.Series, frac: float) -> dict[str, Any]:
    joined = pd.DataFrame({"y": y.astype(int), "p": p.astype(float)}).dropna().sort_values("p", ascending=False)
    if joined.empty:
        return {"rows": 0, "events": 0, "rate": None, "lift": None}
    n = max(1, int(round(len(joined) * frac)))
    top = joined.head(n)
    base = float(joined.y.mean())
    rate = float(top.y.mean())
    return {
        "rows": int(n),
        "events": int(top.y.sum()),
        "rate": rate,
        "lift": float(rate / base) if base > 0 else None,
    }


def _metric_row(threshold: float, year: int, role: str, model: str, y: pd.Series, p: pd.Series) -> dict[str, Any]:
    t5 = _tail_stats(y, p, 0.05)
    t1 = _tail_stats(y, p, 0.01)
    return {
        "threshold": threshold,
        "test_year": year,
        "role": role,
        "model": model,
        "rows": int(len(y)),
        "events": int(y.sum()),
        "event_rate": float(y.mean()),
        "roc_auc": _safe_auc(y, p),
        "average_precision": _safe_ap(y, p),
        "brier": float(brier_score_loss(y, p)),
        "top5_rows": t5["rows"],
        "top5_events": t5["events"],
        "top5_rate": t5["rate"],
        "top5_lift": t5["lift"],
        "top1_rows": t1["rows"],
        "top1_events": t1["events"],
        "top1_rate": t1["rate"],
        "top1_lift": t1["lift"],
    }


def _importance(estimator: Pipeline, model_name: str) -> dict[str, float]:
    if model_name == "logistic":
        values = np.abs(estimator.named_steps["model"].coef_[0])
    else:
        values = estimator.named_steps["model"].feature_importances_
    return {f: float(v) for f, v in zip(FEATURES, values, strict=True)}


def _pooled_metrics(pred: pd.DataFrame, threshold: float, role: str, model: str) -> dict[str, Any]:
    s = pred[(pred.threshold == threshold) & (pred.role == role) & (pred.model == model)]
    y = s.y.astype(int)
    p = s.p.astype(float)
    t5 = _tail_stats(y, p, 0.05)
    t1 = _tail_stats(y, p, 0.01)
    return {
        "threshold": threshold,
        "role": role,
        "model": model,
        "rows": int(len(s)),
        "events": int(y.sum()),
        "event_rate": float(y.mean()) if len(y) else None,
        "roc_auc": _safe_auc(y, p) if len(y) else None,
        "average_precision": _safe_ap(y, p) if len(y) else None,
        "brier": float(brier_score_loss(y, p)) if len(y) else None,
        "top5_rows": t5["rows"],
        "top5_events": t5["events"],
        "top5_rate": t5["rate"],
        "top5_lift": t5["lift"],
        "top1_rows": t1["rows"],
        "top1_events": t1["events"],
        "top1_rate": t1["rate"],
        "top1_lift": t1["lift"],
    }


def _delta_summary(folds: pd.DataFrame, threshold: float, role: str) -> dict[str, Any]:
    subset = folds[(folds.threshold == threshold) & (folds.role == role)]
    out: dict[str, Any] = {"threshold": threshold, "role": role}
    for metric in ("roc_auc", "average_precision"):
        pivot = subset.pivot(index="test_year", columns="model", values=metric)
        if "gbm" not in pivot.columns or "logistic" not in pivot.columns:
            d = pd.Series(dtype=float)
        else:
            d = (pivot.gbm - pivot.logistic).dropna()
        prefix = "auc" if metric == "roc_auc" else "ap"
        out[f"eligible_{prefix}_years"] = int(len(d))
        out[f"gbm_{prefix}_wins"] = int((d > 0).sum())
        out[f"logistic_{prefix}_wins"] = int((d < 0).sum())
        out[f"{prefix}_mean_delta"] = float(d.mean()) if len(d) else None
        out[f"{prefix}_median_delta"] = float(d.median()) if len(d) else None
        out[f"{prefix}_year_deltas"] = {str(int(k)): float(v) for k, v in d.items()}
    return out


def _qbin(series: pd.Series, q: int) -> pd.Series:
    ranked = series.rank(method="first")
    return pd.qcut(ranked, q=q, labels=False, duplicates="drop")


def _one_dimensional_tables(frame: pd.DataFrame, asset: str) -> pd.DataFrame:
    sample = frame[frame.index.year >= TEST_START_YEAR].copy()
    rows: list[dict[str, Any]] = []
    for feature in ("vol_ratio_24_168", "realized_vol_24h", "range_position_168h"):
        sample["bucket"] = _qbin(sample[feature], 10)
        for threshold in SEVERITY_THRESHOLDS:
            event = sample.expansion_ratio >= threshold
            for bucket, group in sample.groupby("bucket", observed=True):
                y = event.loc[group.index]
                rows.append(
                    {
                        "asset": asset,
                        "feature": feature,
                        "threshold": threshold,
                        "bucket": int(bucket) + 1,
                        "rows": int(len(group)),
                        "feature_min": float(group[feature].min()),
                        "feature_median": float(group[feature].median()),
                        "feature_max": float(group[feature].max()),
                        "events": int(y.sum()),
                        "event_rate": float(y.mean()),
                    }
                )
    return pd.DataFrame(rows)


def _two_dimensional_tables(frame: pd.DataFrame, asset: str) -> pd.DataFrame:
    sample = frame[frame.index.year >= TEST_START_YEAR].copy()
    rows: list[dict[str, Any]] = []
    pairs = (
        ("vol_ratio_24_168", "realized_vol_24h"),
        ("vol_ratio_24_168", "range_position_168h"),
    )
    event = sample.expansion_ratio >= 1.25
    for x, z in pairs:
        xbin = _qbin(sample[x], 5)
        zbin = _qbin(sample[z], 5)
        tmp = sample[[x, z]].copy()
        tmp["xbin"] = xbin
        tmp["zbin"] = zbin
        tmp["event"] = event.astype(int)
        for (xb, zb), group in tmp.groupby(["xbin", "zbin"], observed=True):
            rows.append(
                {
                    "asset": asset,
                    "threshold": 1.25,
                    "x_feature": x,
                    "z_feature": z,
                    "x_quintile": int(xb) + 1,
                    "z_quintile": int(zb) + 1,
                    "rows": int(len(group)),
                    "events": int(group.event.sum()),
                    "event_rate": float(group.event.mean()),
                    "x_median": float(group[x].median()),
                    "z_median": float(group[z].median()),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    btc = _build_frame(read_ohlcv(args.btc), "BTC")
    eth = _build_frame(read_ohlcv(args.eth), "ETH")

    # Part A: explicitly descriptive state geometry.
    one_d = pd.concat([_one_dimensional_tables(btc, "BTC"), _one_dimensional_tables(eth, "ETH")], ignore_index=True)
    two_d = pd.concat([_two_dimensional_tables(btc, "BTC"), _two_dimensional_tables(eth, "ETH")], ignore_index=True)
    one_d.to_csv(out / "experiment_003_state_deciles.csv", index=False)
    two_d.to_csv(out / "experiment_003_state_interactions_5x5.csv", index=False)

    # Part B: chronological severity surface.
    folds: list[dict[str, Any]] = []
    predictions: list[pd.DataFrame] = []
    importances: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []

    years = sorted(y for y in btc.index.year.unique() if y >= TEST_START_YEAR)
    for threshold in SEVERITY_THRESHOLDS:
        for year in years:
            train = btc[btc.index.year < year]
            btc_test = btc[btc.index.year == year]
            eth_test = eth[eth.index.year == year]
            y_train = (train.expansion_ratio >= threshold).astype(int)
            events = int(y_train.sum())
            nonevents = int((y_train == 0).sum())
            eligible = len(train) >= MIN_TRAIN_ROWS and events >= MIN_TRAIN_EVENTS and nonevents >= MIN_TRAIN_EVENTS
            support_rows.append(
                {
                    "threshold": threshold,
                    "test_year": year,
                    "train_rows": int(len(train)),
                    "train_events": events,
                    "train_nonevents": nonevents,
                    "eligible": bool(eligible),
                }
            )
            if not eligible:
                continue

            naive_p = float(y_train.mean())
            fitted = {"logistic": _logistic(), "gbm": _gbm()}
            for name, estimator in fitted.items():
                estimator.fit(train[FEATURES].astype(float), y_train)
                for feature, value in _importance(estimator, name).items():
                    importances.append(
                        {
                            "threshold": threshold,
                            "test_year": year,
                            "model": name,
                            "feature": feature,
                            "importance": value,
                        }
                    )

            for role, test in (("btc_oos", btc_test), ("eth_transfer", eth_test)):
                if test.empty:
                    continue
                y = (test.expansion_ratio >= threshold).astype(int)
                probs: dict[str, pd.Series] = {"naive": pd.Series(naive_p, index=test.index)}
                for name, estimator in fitted.items():
                    probs[name] = pd.Series(estimator.predict_proba(test[FEATURES].astype(float))[:, 1], index=test.index)
                for name, p in probs.items():
                    folds.append(_metric_row(threshold, year, role, name, y, p))
                    predictions.append(
                        pd.DataFrame(
                            {
                                "timestamp": test.index,
                                "threshold": threshold,
                                "test_year": year,
                                "role": role,
                                "model": name,
                                "y": y.values,
                                "p": p.values,
                            }
                        )
                    )

    folds_df = pd.DataFrame(folds)
    pred_df = pd.concat(predictions, ignore_index=True)
    imp_df = pd.DataFrame(importances)
    support_df = pd.DataFrame(support_rows)

    folds_df.to_csv(out / "experiment_003_fold_metrics.csv", index=False)
    pred_df.to_csv(out / "experiment_003_oos_predictions.csv", index=False)
    imp_df.to_csv(out / "experiment_003_feature_importance_by_fold.csv", index=False)
    support_df.to_csv(out / "experiment_003_fold_support.csv", index=False)

    pooled = [
        _pooled_metrics(pred_df, threshold, role, model)
        for threshold in SEVERITY_THRESHOLDS
        for role in ("btc_oos", "eth_transfer")
        for model in ("naive", "logistic", "gbm")
    ]
    deltas = [
        _delta_summary(folds_df, threshold, role)
        for threshold in SEVERITY_THRESHOLDS
        for role in ("btc_oos", "eth_transfer")
    ]

    importance_summary: dict[str, Any] = {}
    for threshold in SEVERITY_THRESHOLDS:
        importance_summary[str(threshold)] = {}
        for model in ("logistic", "gbm"):
            s = (
                imp_df[(imp_df.threshold == threshold) & (imp_df.model == model)]
                .groupby("feature").importance.mean().sort_values(ascending=False)
            )
            importance_summary[str(threshold)][model] = {
                "mean_importance": {k: float(v) for k, v in s.items()},
                "top5": list(s.head(5).index),
            }

    # Compact state-geometry summary for stdout/JSON; full tables remain CSVs.
    state_summary: dict[str, Any] = {}
    for asset in ("BTC", "ETH"):
        state_summary[asset] = {}
        subset = one_d[(one_d.asset == asset) & (one_d.feature == "vol_ratio_24_168")]
        for threshold in SEVERITY_THRESHOLDS:
            s = subset[subset.threshold == threshold].sort_values("bucket")
            state_summary[asset][str(threshold)] = [
                {
                    "decile": int(r.bucket),
                    "vol_ratio_median": float(r.feature_median),
                    "rows": int(r.rows),
                    "event_rate": float(r.event_rate),
                }
                for r in s.itertuples(index=False)
            ]

    report = {
        "experiment": "ML_LAB_EXPERIMENT_003_VOLATILITY_STATE_GEOMETRY",
        "status": "EXPLORATORY_NONCONFIRMATORY",
        "boundary": "Exploratory ML Lab only; no Core/runtime/portfolio/capital implication.",
        "data": {"btc": args.btc, "eth": args.eth},
        "design": {
            "severity_thresholds": list(SEVERITY_THRESHOLDS),
            "target": "future 24h realized vol / trailing 24h realized vol >= threshold",
            "features": FEATURES,
            "test_start_year": TEST_START_YEAR,
            "models": {
                "naive": "BTC training event-rate constant",
                "logistic": "StandardScaler + LogisticRegression(C=0.25,max_iter=2000,random_state=42), unweighted",
                "gbm": "GradientBoostingClassifier(n_estimators=200,max_depth=2,learning_rate=0.04,random_state=42)",
            },
            "transfer": "Each yearly model is fit on pre-year BTC only and applied unchanged to ETH in the same test year.",
        },
        "pooled_metrics": pooled,
        "fold_delta_summary": deltas,
        "feature_importance": importance_summary,
        "vol_ratio_decile_summary": state_summary,
        "artifact_files": {
            "state_deciles": "experiment_003_state_deciles.csv",
            "state_interactions_5x5": "experiment_003_state_interactions_5x5.csv",
            "fold_metrics": "experiment_003_fold_metrics.csv",
            "oos_predictions": "experiment_003_oos_predictions.csv",
            "feature_importance_by_fold": "experiment_003_feature_importance_by_fold.csv",
            "fold_support": "experiment_003_fold_support.csv",
        },
    }

    (out / "experiment_003_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
