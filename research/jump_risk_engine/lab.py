from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, precision_recall_fscore_support, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


FEATURE_COLS = [
    "ret_1",
    "abs_ret_1",
    "ret_3",
    "ret_12",
    "ret_fast",
    "ret_slow",
    "realized_vol",
    "fast_vol",
    "slow_vol",
    "vol_ratio_fast_slow",
    "vol_rank",
    "atr_proxy",
    "range_rank",
    "vol_of_vol",
    "skew",
    "kurt",
    "volume_z",
    "distance_sma_fast",
    "distance_sma_slow",
    "trend_fast_gt_slow",
    "hour_utc",
    "day_of_week",
]


@dataclass(frozen=True)
class JumpRiskConfig:
    """Configuration for the research-only discontinuity-risk lab.

    The label is intentionally empirical rather than theoretical: a future
    window is a jump event when its largest absolute return exceeds both an
    absolute-return floor and a rolling-volatility multiple. The feature row
    at t uses only information available at or before t; the label uses the
    following horizon bars.
    """

    asset: str
    horizon_bars: int = 24
    vol_window: int = 96
    fast_window: int = 24
    slow_window: int = 240
    jump_z: float = 3.0
    absolute_jump: float = 0.05
    min_train_rows: int = 500
    min_train_events: int = 20
    test_start_year: int = 2020
    probability_buckets: tuple[float, ...] = (0.0, 0.05, 0.10, 0.20, 0.35, 0.50, 1.01)


def _normalise_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    cols = {c.lower().strip(): c for c in df.columns}
    ts_col = cols.get("timestamp") or cols.get("date") or cols.get("datetime") or cols.get("time")
    if ts_col is None:
        # Many research CSVs use the timestamp as the unnamed first column.
        first = df.columns[0]
        parsed = pd.to_datetime(df[first], utc=True, errors="coerce")
        if parsed.notna().mean() > 0.8:
            ts_col = first
        else:
            raise ValueError("CSV must include a timestamp/date/datetime/time column or timestamp-like first column")

    out = df.copy()
    out["timestamp"] = pd.to_datetime(out[ts_col], utc=True, errors="coerce")
    out = out.dropna(subset=["timestamp"]).sort_values("timestamp")
    out = out.drop_duplicates("timestamp").set_index("timestamp")

    rename = {}
    for name in ("open", "high", "low", "close", "volume"):
        if name in cols:
            rename[cols[name]] = name
    out = out.rename(columns=rename)
    missing = [c for c in ("open", "high", "low", "close") if c not in out.columns]
    if missing:
        raise ValueError(f"Missing OHLC columns: {missing}")
    if "volume" not in out.columns:
        out["volume"] = np.nan
    out = out[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
    return out.dropna(subset=["open", "high", "low", "close"])


def read_ohlcv(path: str | Path) -> pd.DataFrame:
    return _normalise_ohlcv(pd.read_csv(path))


def _future_window_stat(series: pd.Series, horizon: int, fn: str) -> pd.Series:
    """Future rolling statistic over bars t+1 through t+horizon.

    Implemented with reverse rolling so the current bar is not part of the
    forward label window. This keeps labels strictly out-of-sample relative to
    the feature row at t.
    """
    forward = series.shift(-1)
    rev = forward.iloc[::-1]
    rolled = rev.rolling(horizon, min_periods=horizon)
    if fn == "max":
        out = rolled.max()
    elif fn == "min":
        out = rolled.min()
    else:
        raise ValueError(fn)
    return out.iloc[::-1]


def build_feature_label_frame(df: pd.DataFrame, cfg: JumpRiskConfig) -> pd.DataFrame:
    px = df["close"].astype(float)
    ret = np.log(px).diff()
    simple_ret = px.pct_change()
    high_low = np.log(df["high"] / df["low"]).replace([np.inf, -np.inf], np.nan)

    realized_vol = ret.rolling(cfg.vol_window, min_periods=cfg.vol_window // 2).std()
    fast_vol = ret.rolling(cfg.fast_window, min_periods=max(5, cfg.fast_window // 2)).std()
    slow_vol = ret.rolling(cfg.slow_window, min_periods=max(20, cfg.slow_window // 2)).std()
    atr_proxy = high_low.rolling(cfg.vol_window, min_periods=cfg.vol_window // 2).mean()

    sma_fast = px.rolling(cfg.fast_window, min_periods=max(5, cfg.fast_window // 2)).mean()
    sma_slow = px.rolling(cfg.slow_window, min_periods=max(20, cfg.slow_window // 2)).mean()

    vol_rank = realized_vol.rolling(cfg.slow_window, min_periods=max(20, cfg.slow_window // 2)).rank(pct=True)
    range_rank = high_low.rolling(cfg.slow_window, min_periods=max(20, cfg.slow_window // 2)).rank(pct=True)

    vol_of_vol = realized_vol.pct_change().replace([np.inf, -np.inf], np.nan).rolling(cfg.fast_window, min_periods=5).std()
    skew = ret.rolling(cfg.vol_window, min_periods=cfg.vol_window // 2).skew()
    kurt = ret.rolling(cfg.vol_window, min_periods=cfg.vol_window // 2).kurt()

    if df["volume"].notna().sum() > 0:
        volume = df["volume"].astype(float).replace(0, np.nan)
        log_volume = np.log(volume).replace([np.inf, -np.inf], np.nan)
        volume_z = (log_volume - log_volume.rolling(cfg.slow_window, min_periods=20).mean()) / log_volume.rolling(
            cfg.slow_window, min_periods=20
        ).std()
    else:
        volume_z = pd.Series(0.0, index=df.index)

    future_max = _future_window_stat(px, cfg.horizon_bars, "max")
    future_min = _future_window_stat(px, cfg.horizon_bars, "min")
    future_up = np.log(future_max / px)
    future_down = np.log(future_min / px)
    future_abs = pd.concat([future_up.abs(), future_down.abs()], axis=1).max(axis=1)

    threshold = np.maximum(cfg.absolute_jump, cfg.jump_z * realized_vol * np.sqrt(cfg.horizon_bars))
    label_any = (future_abs >= threshold).astype(int)
    label_down = (future_down <= -threshold).astype(int)
    label_up = (future_up >= threshold).astype(int)

    out = pd.DataFrame(
        {
            "asset": cfg.asset,
            "close": px,
            "ret_1": simple_ret,
            "abs_ret_1": simple_ret.abs(),
            "ret_3": px.pct_change(3),
            "ret_12": px.pct_change(12),
            "ret_fast": px.pct_change(cfg.fast_window),
            "ret_slow": px.pct_change(cfg.slow_window),
            "realized_vol": realized_vol,
            "fast_vol": fast_vol,
            "slow_vol": slow_vol,
            "vol_ratio_fast_slow": fast_vol / slow_vol,
            "vol_rank": vol_rank,
            "atr_proxy": atr_proxy,
            "range_rank": range_rank,
            "vol_of_vol": vol_of_vol,
            "skew": skew,
            "kurt": kurt,
            "volume_z": volume_z,
            "distance_sma_fast": px / sma_fast - 1.0,
            "distance_sma_slow": px / sma_slow - 1.0,
            "trend_fast_gt_slow": (sma_fast > sma_slow).astype(float),
            "hour_utc": df.index.hour.astype(float),
            "day_of_week": df.index.dayofweek.astype(float),
            "future_up": future_up,
            "future_down": future_down,
            "future_abs": future_abs,
            "jump_threshold": threshold,
            "jump_any": label_any,
            "jump_down": label_down,
            "jump_up": label_up,
        },
        index=df.index,
    )
    out.index.name = "timestamp"
    return out.replace([np.inf, -np.inf], np.nan).dropna()


def _make_model(model_name: str) -> Pipeline:
    if model_name == "logistic":
        return Pipeline(
            [
                ("scale", StandardScaler()),
                ("model", LogisticRegression(C=0.25, class_weight="balanced", max_iter=2000, random_state=42)),
            ]
        )
    if model_name == "rf":
        return Pipeline(
            [
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=250,
                        max_depth=5,
                        min_samples_leaf=25,
                        class_weight="balanced",
                        random_state=42,
                    ),
                ),
            ]
        )
    if model_name == "gbm":
        return Pipeline(
            [
                ("model", GradientBoostingClassifier(n_estimators=200, max_depth=2, learning_rate=0.04, random_state=42)),
            ]
        )
    raise ValueError(f"Unknown model_name={model_name!r}")


def _safe_auc(y: np.ndarray, p: np.ndarray) -> float | None:
    return None if len(set(y.tolist())) < 2 else float(roc_auc_score(y, p))


def _safe_ap(y: np.ndarray, p: np.ndarray) -> float | None:
    return None if int(y.sum()) == 0 else float(average_precision_score(y, p))


def _calibration_table(y: np.ndarray, p: np.ndarray, buckets: tuple[float, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cuts = list(buckets)
    base = float(y.mean()) if len(y) else 0.0
    for lo, hi in zip(cuts[:-1], cuts[1:]):
        mask = (p >= lo) & (p < hi)
        n = int(mask.sum())
        event_rate = float(y[mask].mean()) if n else None
        rows.append(
            {
                "bucket": f"[{lo:.2f},{hi:.2f})",
                "n": n,
                "avg_pred": float(p[mask].mean()) if n else None,
                "event_rate": event_rate,
                "lift_vs_unconditional": float(event_rate / base) if n and base > 0 and event_rate is not None else None,
            }
        )
    return rows


def _lift_at_top_quantiles(y: pd.Series, probs: pd.Series, quantiles: tuple[float, ...] = (0.01, 0.05, 0.10, 0.20)) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    joined = pd.DataFrame({"y": y.astype(int), "p": probs.astype(float)}).dropna().sort_values("p", ascending=False)
    base = float(joined["y"].mean()) if not joined.empty else 0.0
    for q in quantiles:
        n = max(1, int(round(len(joined) * q))) if not joined.empty else 0
        top = joined.head(n)
        rate = float(top["y"].mean()) if n else None
        rows.append(
            {
                "top_quantile": q,
                "n": n,
                "avg_pred": float(top["p"].mean()) if n else None,
                "event_rate": rate,
                "lift_vs_unconditional": float(rate / base) if rate is not None and base > 0 else None,
            }
        )
    return rows


def _window_rows(frame: pd.DataFrame, probs: pd.Series, label: pd.Series, mask: pd.Series, limit: int = 50) -> list[dict[str, Any]]:
    idx = probs[mask.reindex(probs.index).fillna(False)].sort_values(ascending=False).head(limit).index
    rows: list[dict[str, Any]] = []
    for ts in idx:
        r = frame.loc[ts]
        rows.append(
            {
                "timestamp": ts.isoformat(),
                "jump_probability": float(probs.loc[ts]),
                "label": int(label.loc[ts]),
                "close": float(r["close"]),
                "future_abs": float(r["future_abs"]),
                "future_up": float(r["future_up"]),
                "future_down": float(r["future_down"]),
                "threshold": float(r["jump_threshold"]),
                "realized_vol": float(r["realized_vol"]),
                "vol_rank": float(r["vol_rank"]),
                "range_rank": float(r["range_rank"]),
                "vol_ratio_fast_slow": float(r["vol_ratio_fast_slow"]),
                "distance_sma_fast": float(r["distance_sma_fast"]),
                "distance_sma_slow": float(r["distance_sma_slow"]),
                "ret_fast": float(r["ret_fast"]),
                "ret_slow": float(r["ret_slow"]),
            }
        )
    return rows


def _feature_profile(frame: pd.DataFrame, idx: pd.Index, baseline_idx: pd.Index) -> list[dict[str, Any]]:
    if len(idx) == 0:
        return []
    subset = frame.loc[idx, FEATURE_COLS]
    baseline = frame.loc[baseline_idx, FEATURE_COLS]
    rows: list[dict[str, Any]] = []
    for col in FEATURE_COLS:
        b_std = float(baseline[col].std()) if len(baseline) > 1 else 0.0
        rows.append(
            {
                "feature": col,
                "subset_mean": float(subset[col].mean()),
                "baseline_mean": float(baseline[col].mean()),
                "mean_diff": float(subset[col].mean() - baseline[col].mean()),
                "std_units": float((subset[col].mean() - baseline[col].mean()) / b_std) if b_std and not np.isnan(b_std) else None,
            }
        )
    rows.sort(key=lambda r: abs(r["std_units"] or 0.0), reverse=True)
    return rows


def _diagnostics(frame: pd.DataFrame, probs: pd.Series, labels: pd.Series, threshold: float) -> dict[str, Any]:
    common = probs.index.intersection(labels.index).intersection(frame.index)
    p = probs.loc[common]
    y = labels.loc[common].astype(int)
    pred = p >= threshold
    top_decile_cut = float(p.quantile(0.90)) if len(p) else 1.0
    top_decile_idx = p[p >= top_decile_cut].index
    positive_idx = y[y == 1].index

    tp = pred & (y == 1)
    fp = pred & (y == 0)
    fn = (~pred) & (y == 1)

    return {
        "policy_threshold": threshold,
        "top_decile_probability_cutoff": top_decile_cut,
        "lift_at_top_quantiles": _lift_at_top_quantiles(y, p),
        "true_positive_windows": _window_rows(frame.loc[common], p, y, tp, limit=50),
        "false_positive_windows": _window_rows(frame.loc[common], p, y, fp, limit=50),
        "false_negative_windows": _window_rows(frame.loc[common], p, y, fn, limit=50),
        "feature_profiles": {
            "top_decile_vs_all": _feature_profile(frame, top_decile_idx, common),
            "actual_jump_vs_all": _feature_profile(frame, positive_idx, common),
        },
    }


def _feature_importance(model: Pipeline, cols: list[str]) -> list[dict[str, Any]]:
    est = model.named_steps["model"]
    values = None
    if hasattr(est, "feature_importances_"):
        values = np.asarray(est.feature_importances_, dtype=float)
    elif hasattr(est, "coef_"):
        values = np.abs(np.asarray(est.coef_, dtype=float).ravel())
    if values is None:
        return []
    order = np.argsort(values)[::-1]
    return [{"feature": cols[i], "importance": float(values[i])} for i in order[:20]]


def run_walk_forward(frame: pd.DataFrame, cfg: JumpRiskConfig, target: str, model_name: str) -> dict[str, Any]:
    y_col = f"jump_{target}"
    if y_col not in frame.columns:
        raise ValueError(f"Unknown target {target!r}; expected one of any/down/up")

    years = sorted(y for y in frame.index.year.unique() if y >= cfg.test_start_year)
    folds: list[dict[str, Any]] = []
    all_probs: list[pd.Series] = []
    all_y: list[pd.Series] = []

    for year in years:
        train = frame[frame.index.year < year]
        test = frame[frame.index.year == year]
        if train.empty or test.empty:
            continue
        if len(train) < cfg.min_train_rows or int(train[y_col].sum()) < cfg.min_train_events or int((train[y_col] == 0).sum()) < cfg.min_train_events:
            folds.append(
                {
                    "test_year": int(year),
                    "status": "SKIP_LOW_SAMPLE",
                    "train_rows": int(len(train)),
                    "train_events": int(train[y_col].sum()),
                    "test_rows": int(len(test)),
                    "test_events": int(test[y_col].sum()),
                }
            )
            continue

        model = _make_model(model_name)
        model.fit(train[FEATURE_COLS].astype(float), train[y_col].astype(int))
        p = model.predict_proba(test[FEATURE_COLS].astype(float))[:, 1]
        y = test[y_col].astype(int).to_numpy()
        unconditional = float(train[y_col].mean())
        policy_threshold = max(0.50, unconditional * 2.0)
        pred_class = (p >= policy_threshold).astype(int)
        precision, recall, f1, _ = precision_recall_fscore_support(y, pred_class, average="binary", zero_division=0)

        folds.append(
            {
                "test_year": int(year),
                "status": "PASS",
                "train_rows": int(len(train)),
                "train_events": int(train[y_col].sum()),
                "test_rows": int(len(test)),
                "test_events": int(test[y_col].sum()),
                "train_unconditional_event_rate": unconditional,
                "test_event_rate": float(test[y_col].mean()),
                "roc_auc": _safe_auc(y, p),
                "average_precision": _safe_ap(y, p),
                "brier": float(brier_score_loss(y, p)) if len(set(y.tolist())) > 1 else None,
                "precision_at_policy_threshold": float(precision),
                "recall_at_policy_threshold": float(recall),
                "f1_at_policy_threshold": float(f1),
                "policy_threshold": float(policy_threshold),
                "top_feature_importance": _feature_importance(model, FEATURE_COLS),
            }
        )
        all_probs.append(pd.Series(p, index=test.index))
        all_y.append(test[y_col].astype(int))

    if all_probs:
        probs = pd.concat(all_probs).sort_index()
        y_all = pd.concat(all_y).sort_index()
        y_arr = y_all.to_numpy(dtype=int)
        p_arr = probs.to_numpy(dtype=float)
        base_rate = float(y_all.mean())
        policy_threshold = max(0.50, base_rate * 2.0)
        diag = _diagnostics(frame.loc[probs.index], probs, y_all, policy_threshold)
        aggregate = {
            "status": "PASS" if len(folds) and any(f.get("status") == "PASS" for f in folds) else "PARTIAL",
            "rows": int(len(y_all)),
            "events": int(y_all.sum()),
            "event_rate": base_rate,
            "roc_auc": _safe_auc(y_arr, p_arr),
            "average_precision": _safe_ap(y_arr, p_arr),
            "brier": float(brier_score_loss(y_arr, p_arr)) if len(set(y_arr.tolist())) > 1 else None,
            "calibration": _calibration_table(y_arr, p_arr, cfg.probability_buckets),
            "diagnostics": diag,
        }
        pred_frame = frame.loc[probs.index, ["asset", "close", "future_abs", "future_up", "future_down", "jump_threshold", y_col, *FEATURE_COLS]].copy()
        pred_frame["target"] = target
        pred_frame["model"] = model_name
        pred_frame["jump_probability"] = probs
        pred_frame["probability_rank_pct"] = probs.rank(pct=True)
        pred_frame["policy_prediction"] = (probs >= policy_threshold).astype(int)
    else:
        aggregate = {"status": "PARTIAL", "reason": "no walk-forward fold had enough samples/classes"}
        pred_frame = pd.DataFrame()

    return {"target": target, "model": model_name, "folds": folds, "aggregate": aggregate, "_predictions": pred_frame}


def run_jump_risk_lab(
    data_path: str | Path,
    cfg: JumpRiskConfig,
    out_dir: str | Path,
    models: tuple[str, ...] = ("logistic", "gbm"),
    targets: tuple[str, ...] = ("any", "down", "up"),
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    ohlcv = read_ohlcv(data_path)
    frame = build_feature_label_frame(ohlcv, cfg)
    if frame.empty:
        raise ValueError("No usable rows after feature/label construction")

    label_summary = {
        "asset": cfg.asset,
        "rows": int(len(frame)),
        "start": frame.index.min().isoformat(),
        "end": frame.index.max().isoformat(),
        "horizon_bars": cfg.horizon_bars,
        "jump_z": cfg.jump_z,
        "absolute_jump": cfg.absolute_jump,
        "jump_any_rate": float(frame["jump_any"].mean()),
        "jump_down_rate": float(frame["jump_down"].mean()),
        "jump_up_rate": float(frame["jump_up"].mean()),
        "median_threshold": float(frame["jump_threshold"].median()),
        "p90_future_abs": float(frame["future_abs"].quantile(0.90)),
        "p99_future_abs": float(frame["future_abs"].quantile(0.99)),
    }

    runs: list[dict[str, Any]] = []
    prediction_paths: list[str] = []
    stem = f"{cfg.asset.lower()}_h{cfg.horizon_bars}_z{cfg.jump_z:g}_abs{cfg.absolute_jump:g}".replace(".", "p")

    for target in targets:
        for model in models:
            run = run_walk_forward(frame, cfg, target, model)
            pred_frame = run.pop("_predictions", pd.DataFrame())
            if not pred_frame.empty:
                pred_path = out / f"{stem}_{target}_{model}_oos_predictions.csv"
                pred_frame.reset_index().to_csv(pred_path, index=False)
                prediction_paths.append(str(pred_path))
                run["aggregate"]["oos_predictions_csv"] = str(pred_path)
            runs.append(run)

    report = {"config": asdict(cfg), "label_summary": label_summary, "prediction_csvs": prediction_paths, "runs": runs}

    (out / f"{stem}_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    frame.reset_index().to_csv(out / f"{stem}_dataset.csv", index=False)

    summary_rows: list[dict[str, Any]] = []
    lift_rows: list[dict[str, Any]] = []
    profile_rows: list[dict[str, Any]] = []
    for run in runs:
        agg = run["aggregate"]
        summary_rows.append(
            {
                "asset": cfg.asset,
                "target": run["target"],
                "model": run["model"],
                "status": agg.get("status"),
                "rows": agg.get("rows"),
                "events": agg.get("events"),
                "event_rate": agg.get("event_rate"),
                "roc_auc": agg.get("roc_auc"),
                "average_precision": agg.get("average_precision"),
                "brier": agg.get("brier"),
                "reason": agg.get("reason"),
                "oos_predictions_csv": agg.get("oos_predictions_csv"),
            }
        )
        diag = agg.get("diagnostics") or {}
        for row in diag.get("lift_at_top_quantiles", []):
            lift_rows.append({"asset": cfg.asset, "target": run["target"], "model": run["model"], **row})
        for group_name, rows in (diag.get("feature_profiles") or {}).items():
            for row in rows:
                profile_rows.append({"asset": cfg.asset, "target": run["target"], "model": run["model"], "group": group_name, **row})

    pd.DataFrame(summary_rows).to_csv(out / f"{stem}_summary.csv", index=False)
    pd.DataFrame(lift_rows).to_csv(out / f"{stem}_lift.csv", index=False)
    pd.DataFrame(profile_rows).to_csv(out / f"{stem}_feature_profiles.csv", index=False)
    return report
