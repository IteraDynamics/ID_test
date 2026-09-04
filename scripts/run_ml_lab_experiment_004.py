from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from research.jump_risk_engine.lab import read_ohlcv

FEATURES = [
    "ret_1h", "ret_24h", "ret_72h", "ret_168h", "abs_ret_24h",
    "realized_vol_24h", "realized_vol_72h", "realized_vol_168h",
    "vol_ratio_24_168", "vol_ratio_72_168",
    "drawdown_from_high_168h", "range_position_168h",
]
THRESHOLDS = (1.00, 1.25, 1.50, 1.75)
TEST_START_YEAR = 2020
MIN_TRAIN_ROWS = 5000
MIN_TRAIN_EVENTS = 100
RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ML Lab Experiment 004: volatility target integrity probe")
    p.add_argument("--btc", default="data/btcusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--eth", default="data/ethusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--output-dir", default="artifacts/ml_lab_experiment_004")
    return p.parse_args()


def future_realized_vol(log_ret: pd.Series, horizon: int = 24) -> pd.Series:
    return log_ret.rolling(horizon, min_periods=horizon).std().shift(-horizon)


def build_frame(ohlcv: pd.DataFrame, asset: str) -> pd.DataFrame:
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
    fvol_24 = future_realized_vol(log_ret, 24)
    high_168 = high.rolling(168, min_periods=168).max()
    low_168 = low.rolling(168, min_periods=168).min()

    frame = pd.DataFrame({
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
        "future_realized_vol_24h": fvol_24,
        "target_ratio": fvol_24 / vol_168,
    }, index=ohlcv.index)
    frame.index.name = "timestamp"
    return frame.replace([np.inf, -np.inf], np.nan).dropna()


def logistic() -> Pipeline:
    return Pipeline([
        ("scale", StandardScaler()),
        ("model", LogisticRegression(C=0.25, max_iter=2000, random_state=RANDOM_STATE)),
    ])


def gbm() -> Pipeline:
    return Pipeline([
        ("model", GradientBoostingClassifier(
            n_estimators=200, max_depth=2, learning_rate=0.04, random_state=RANDOM_STATE
        )),
    ])


def safe_auc(y: pd.Series, p: pd.Series):
    return None if y.nunique() < 2 else float(roc_auc_score(y, p))


def safe_ap(y: pd.Series, p: pd.Series):
    return None if int(y.sum()) == 0 else float(average_precision_score(y, p))


def tail_stats(y: pd.Series, p: pd.Series, frac: float):
    j = pd.DataFrame({"y": y.astype(int), "p": p.astype(float)}).dropna().sort_values("p", ascending=False)
    n = max(1, int(round(len(j) * frac)))
    top = j.head(n)
    base = float(j.y.mean())
    rate = float(top.y.mean())
    return {"rows": int(n), "events": int(top.y.sum()), "rate": rate, "lift": float(rate/base) if base > 0 else None}


def metric_row(threshold, year, role, model, y, p):
    t5 = tail_stats(y, p, 0.05)
    t1 = tail_stats(y, p, 0.01)
    return {
        "threshold": threshold, "test_year": year, "role": role, "model": model,
        "rows": int(len(y)), "events": int(y.sum()), "event_rate": float(y.mean()),
        "roc_auc": safe_auc(y, p), "average_precision": safe_ap(y, p),
        "brier": float(brier_score_loss(y, p)),
        "top5_rows": t5["rows"], "top5_events": t5["events"], "top5_rate": t5["rate"], "top5_lift": t5["lift"],
        "top1_rows": t1["rows"], "top1_events": t1["events"], "top1_rate": t1["rate"], "top1_lift": t1["lift"],
    }


def importance(est, name):
    vals = np.abs(est.named_steps["model"].coef_[0]) if name == "logistic" else est.named_steps["model"].feature_importances_
    return {f: float(v) for f, v in zip(FEATURES, vals, strict=True)}


def pooled_metrics(pred, threshold, role, model):
    s = pred[(pred.threshold == threshold) & (pred.role == role) & (pred.model == model)]
    y, p = s.y.astype(int), s.p.astype(float)
    t5 = tail_stats(y, p, 0.05)
    t1 = tail_stats(y, p, 0.01)
    return {
        "threshold": threshold, "role": role, "model": model, "rows": int(len(s)),
        "events": int(y.sum()), "event_rate": float(y.mean()), "roc_auc": safe_auc(y,p),
        "average_precision": safe_ap(y,p), "brier": float(brier_score_loss(y,p)),
        "top5_rows": t5["rows"], "top5_events": t5["events"], "top5_rate": t5["rate"], "top5_lift": t5["lift"],
        "top1_rows": t1["rows"], "top1_events": t1["events"], "top1_rate": t1["rate"], "top1_lift": t1["lift"],
    }


def delta_summary(folds, threshold, role):
    subset = folds[(folds.threshold == threshold) & (folds.role == role)]
    out = {"threshold": threshold, "role": role}
    for metric, prefix in (("roc_auc","auc"),("average_precision","ap")):
        pivot = subset.pivot(index="test_year", columns="model", values=metric)
        d = (pivot.gbm - pivot.logistic).dropna()
        out[f"eligible_{prefix}_years"] = int(len(d))
        out[f"gbm_{prefix}_wins"] = int((d>0).sum())
        out[f"logistic_{prefix}_wins"] = int((d<0).sum())
        out[f"{prefix}_mean_delta"] = float(d.mean())
        out[f"{prefix}_median_delta"] = float(d.median())
        out[f"{prefix}_year_deltas"] = {str(int(k)): float(v) for k,v in d.items()}
    return out


def qbin(s: pd.Series, q: int):
    return pd.qcut(s.rank(method="first"), q=q, labels=False, duplicates="drop")


def decile_table(frame: pd.DataFrame, asset: str):
    sample = frame[frame.index.year >= TEST_START_YEAR].copy()
    sample["decile"] = qbin(sample["vol_ratio_24_168"], 10)
    rows = []
    for threshold in THRESHOLDS:
        event = sample.target_ratio >= threshold
        for decile, g in sample.groupby("decile", observed=True):
            y = event.loc[g.index]
            rows.append({
                "asset": asset, "threshold": threshold, "decile": int(decile)+1, "rows": int(len(g)),
                "vol_ratio_median": float(g.vol_ratio_24_168.median()), "event_rate": float(y.mean()), "events": int(y.sum())
            })
    return pd.DataFrame(rows)


def main():
    args = parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    btc = build_frame(read_ohlcv(args.btc), "BTC")
    eth = build_frame(read_ohlcv(args.eth), "ETH")

    deciles = pd.concat([decile_table(btc,"BTC"), decile_table(eth,"ETH")], ignore_index=True)
    deciles.to_csv(out / "experiment_004_state_deciles.csv", index=False)

    folds, preds, imps, support = [], [], [], []
    years = sorted(y for y in btc.index.year.unique() if y >= TEST_START_YEAR)

    for threshold in THRESHOLDS:
        for year in years:
            train = btc[btc.index.year < year]
            btc_test = btc[btc.index.year == year]
            eth_test = eth[eth.index.year == year]
            y_train = (train.target_ratio >= threshold).astype(int)
            events = int(y_train.sum()); nonevents = int((y_train==0).sum())
            eligible = len(train) >= MIN_TRAIN_ROWS and events >= MIN_TRAIN_EVENTS and nonevents >= MIN_TRAIN_EVENTS
            support.append({"threshold": threshold, "test_year": year, "train_rows": int(len(train)), "train_events": events, "train_nonevents": nonevents, "eligible": eligible})
            if not eligible:
                continue

            naive_p = float(y_train.mean())
            fitted = {"logistic": logistic(), "gbm": gbm()}
            for name, est in fitted.items():
                est.fit(train[FEATURES].astype(float), y_train)
                for f,v in importance(est,name).items():
                    imps.append({"threshold": threshold, "test_year": year, "model": name, "feature": f, "importance": v})

            for role, test in (("btc_oos", btc_test), ("eth_transfer", eth_test)):
                if test.empty:
                    continue
                y = (test.target_ratio >= threshold).astype(int)
                probs = {"naive": pd.Series(naive_p, index=test.index)}
                for name, est in fitted.items():
                    probs[name] = pd.Series(est.predict_proba(test[FEATURES].astype(float))[:,1], index=test.index)
                for name,p in probs.items():
                    folds.append(metric_row(threshold, year, role, name, y, p))
                    preds.append(pd.DataFrame({"timestamp": test.index, "threshold": threshold, "test_year": year, "role": role, "model": name, "y": y.values, "p": p.values}))

    folds = pd.DataFrame(folds)
    pred = pd.concat(preds, ignore_index=True)
    imp = pd.DataFrame(imps)
    support = pd.DataFrame(support)

    folds.to_csv(out / "experiment_004_fold_metrics.csv", index=False)
    pred.to_csv(out / "experiment_004_oos_predictions.csv", index=False)
    imp.to_csv(out / "experiment_004_feature_importance_by_fold.csv", index=False)
    support.to_csv(out / "experiment_004_fold_support.csv", index=False)

    pooled = [pooled_metrics(pred,t,r,m) for t in THRESHOLDS for r in ("btc_oos","eth_transfer") for m in ("naive","logistic","gbm")]
    deltas = [delta_summary(folds,t,r) for t in THRESHOLDS for r in ("btc_oos","eth_transfer")]

    feature_summary = {}
    for threshold in THRESHOLDS:
        feature_summary[str(threshold)] = {}
        for model in ("logistic","gbm"):
            s = imp[(imp.threshold==threshold) & (imp.model==model)].groupby("feature").importance.mean().sort_values(ascending=False)
            feature_summary[str(threshold)][model] = {"mean_importance": {k: float(v) for k,v in s.items()}, "top5": list(s.head(5).index)}

    decile_summary = {}
    for asset in ("BTC","ETH"):
        decile_summary[asset] = {}
        for threshold in THRESHOLDS:
            s = deciles[(deciles.asset==asset) & (deciles.threshold==threshold)]
            decile_summary[asset][str(threshold)] = s[["decile","rows","vol_ratio_median","event_rate"]].to_dict(orient="records")

    report = {
        "experiment": "ML_LAB_EXPERIMENT_004_TARGET_INTEGRITY",
        "status": "EXPLORATORY_NONCONFIRMATORY",
        "boundary": "Exploratory ML Lab only; no Core/runtime/portfolio/capital implication.",
        "data": {"btc": args.btc, "eth": args.eth},
        "design": {
            "target": "future 24h realized vol / trailing 168h realized vol >= threshold",
            "severity_thresholds": list(THRESHOLDS), "features": FEATURES, "test_start_year": TEST_START_YEAR,
            "transfer": "Each yearly model is fit on pre-year BTC only and applied unchanged to ETH in the same test year.",
        },
        "pooled_metrics": pooled,
        "fold_delta_summary": deltas,
        "feature_importance": feature_summary,
        "vol_ratio_decile_summary": decile_summary,
        "artifact_files": {
            "fold_metrics": "experiment_004_fold_metrics.csv",
            "oos_predictions": "experiment_004_oos_predictions.csv",
            "feature_importance_by_fold": "experiment_004_feature_importance_by_fold.csv",
            "fold_support": "experiment_004_fold_support.csv",
            "state_deciles": "experiment_004_state_deciles.csv",
        },
    }
    (out / "experiment_004_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
