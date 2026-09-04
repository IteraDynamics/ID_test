from __future__ import annotations

import argparse
import hashlib
import json
import math
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import run_ml_lab_experiment_005 as exp5

FRED_SERIES = ("DGS2", "DGS10", "DGS3MO")
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
MEMORY_SCHEMES: dict[str, int | None] = {"expanding": None, "trailing_3y": 3}
MACRO_STATES = ("rate2_pct252", "curve_10y2y_pct252", "rate2_chg20", "vix_pct252")
INTERACTION_BASES = (
    "ret_120d_xrank",
    "vol_60d_xrank",
    "vol_ratio_20_60_xrank",
    "drawdown_120_xrank",
)
PRICE_FEATURES = tuple(exp5.FEATURES)
INTERACTION_FEATURES = tuple(f"{m}__x__{p}" for m in MACRO_STATES for p in INTERACTION_BASES)
AUGMENTED_FEATURES = PRICE_FEATURES + MACRO_STATES + INTERACTION_FEATURES
MIN_MACRO_ROLL = 126
POST_START_YEAR = 2022


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ML Lab Experiment 009: macro/rate state cross-sectional ranking")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--output-dir", default="artifacts/ml_lab_experiment_009")
    return p.parse_args()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_once(series: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{series}.csv"
    if path.exists():
        return path
    url = FRED_URL.format(series=series)
    tmp = path.with_suffix(".tmp")
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read()
    except Exception as exc:  # fail closed
        raise RuntimeError(f"FRED_ACQUISITION_FAILURE:{series}:{exc}") from exc
    if not data:
        raise RuntimeError(f"FRED_EMPTY_RESPONSE:{series}")
    tmp.write_bytes(data)
    tmp.replace(path)
    return path


def _load_fred(path: Path, series: str) -> pd.Series:
    raw = pd.read_csv(path)
    if raw.shape[1] < 2:
        raise ValueError(f"FRED_SCHEMA_FAILURE:{series}")
    date_col = raw.columns[0]
    value_col = series if series in raw.columns else raw.columns[1]
    idx = pd.to_datetime(raw[date_col], errors="coerce", utc=True)
    values = pd.to_numeric(raw[value_col].replace(".", np.nan), errors="coerce")
    out = pd.Series(values.to_numpy(dtype=float), index=pd.DatetimeIndex(idx), name=series).dropna()
    out = out[~out.index.duplicated(keep="last")].sort_index()
    if len(out) < 500:
        raise ValueError(f"FRED_COVERAGE_FAILURE:{series}:{len(out)}")
    return out


def _load_vix(path: Path) -> pd.Series:
    if not path.exists():
        raise FileNotFoundError(f"MISSING_VIX_SOURCE:{path}")
    frame = exp5.read_ohlcv(path).sort_index()
    close = frame["close"].astype(float).rename("VIX")
    if len(close) < 500:
        raise ValueError(f"VIX_COVERAGE_FAILURE:{len(close)}")
    return close


def _rolling_percentile(series: pd.Series, window: int = 252) -> pd.Series:
    def pct(arr: np.ndarray) -> float:
        a = np.asarray(arr, dtype=float)
        a = a[np.isfinite(a)]
        if len(a) < MIN_MACRO_ROLL:
            return np.nan
        last = a[-1]
        return float(np.mean(a <= last))

    return series.rolling(window, min_periods=MIN_MACRO_ROLL).apply(pct, raw=True)


def _align_to_calendar(series: pd.Series, calendar: pd.DatetimeIndex) -> pd.Series:
    s = series.sort_index()
    # Reindex to the union, forward-fill only from past observations, then select ETF sessions.
    union = s.index.union(calendar).sort_values()
    aligned = s.reindex(union).ffill().reindex(calendar)
    return aligned


def _build_macro_frame(
    calendar: pd.DatetimeIndex,
    fred: dict[str, pd.Series],
    vix: pd.Series,
) -> pd.DataFrame:
    dgs2 = _align_to_calendar(fred["DGS2"], calendar)
    dgs10 = _align_to_calendar(fred["DGS10"], calendar)
    dgs3mo = _align_to_calendar(fred["DGS3MO"], calendar)
    vix_a = _align_to_calendar(vix, calendar)
    curve = dgs10 - dgs2

    frame = pd.DataFrame(index=calendar)
    frame["rate2_pct252"] = _rolling_percentile(dgs2)
    frame["curve_10y2y_pct252"] = _rolling_percentile(curve)
    frame["rate2_chg20"] = dgs2.diff(20)
    frame["vix_pct252"] = _rolling_percentile(vix_a)

    # Diagnostic-only raw states retained in output, not model features.
    frame["DGS2"] = dgs2
    frame["DGS10"] = dgs10
    frame["DGS3MO"] = dgs3mo
    frame["curve_10y2y"] = curve
    frame["VIX"] = vix_a
    return frame.replace([np.inf, -np.inf], np.nan)


def _augment_panel(panel: pd.DataFrame, macro: pd.DataFrame) -> pd.DataFrame:
    m = macro.reset_index().rename(columns={macro.index.name or "index": "timestamp"})
    out = panel.merge(m, on="timestamp", how="left", validate="many_to_one")
    for macro_name in MACRO_STATES:
        for price_name in INTERACTION_BASES:
            out[f"{macro_name}__x__{price_name}"] = out[macro_name] * out[price_name]
    needed = list(AUGMENTED_FEATURES)
    out = out.dropna(subset=needed).copy()
    if out.empty:
        raise ValueError("NO_COMPLETE_MACRO_ANCHORS")
    return out.sort_values(["timestamp", "ticker"]).reset_index(drop=True)


def _training_slice(panel: pd.DataFrame, test_start: pd.Timestamp, years: int | None) -> pd.DataFrame:
    eligible = panel[(panel["timestamp"] < test_start) & (panel["target_end_date"] < test_start)].copy()
    if years is not None:
        eligible = eligible[eligible["timestamp"] >= test_start - pd.DateOffset(years=years)].copy()
    return eligible


def _anchor_metric(group: pd.DataFrame) -> dict[str, Any]:
    score_rank = group["score"].rank(method="average", pct=True)
    ic = float(score_rank.corr(group["target_rank"], method="spearman"))
    n_q = max(1, int(math.ceil(len(group) * 0.25)))
    ordered = group.assign(score_rank=score_rank).sort_values("score_rank")
    spread = float(ordered.tail(n_q)["target_raw"].mean() - ordered.head(n_q)["target_raw"].mean())
    return {
        "timestamp": group["timestamp"].iloc[0],
        "test_year": int(group["test_year"].iloc[0]),
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


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    out_dir = Path(args.output_dir)
    cache_dir = out_dir / "source_cache"
    out_dir.mkdir(parents=True, exist_ok=True)

    source_paths = {series: _download_once(series, cache_dir) for series in FRED_SERIES}
    fred = {series: _load_fred(path, series) for series, path in source_paths.items()}
    vix_path = data_dir / "VIX_1D.csv"
    vix = _load_vix(vix_path)

    frames = exp5._load_universe(data_dir)
    calendar = exp5._common_calendar(frames)
    base_panel = exp5._build_panel(frames, calendar)
    macro_frame = _build_macro_frame(calendar, fred, vix)
    panel = _augment_panel(base_panel, macro_frame)

    predictions: list[pd.DataFrame] = []
    importance_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []

    years = sorted(y for y in panel["timestamp"].dt.year.unique() if y <= 2024)
    for year in years:
        test = panel[panel["timestamp"].dt.year == year].copy()
        if test.empty:
            continue
        test_start = test["timestamp"].min()

        for memory_name, memory_years in MEMORY_SCHEMES.items():
            train = _training_slice(panel, test_start, memory_years)
            eligible = len(train) >= exp5.MIN_TRAIN_ROWS and train["timestamp"].nunique() >= 50
            support_rows.append(
                {
                    "test_year": year,
                    "memory_scheme": memory_name,
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

            variants = {
                "price_ridge": (exp5._ridge(), PRICE_FEATURES, "ridge"),
                "price_gbm": (exp5._gbm(), PRICE_FEATURES, "gbm"),
                "macro_ridge": (exp5._ridge(), AUGMENTED_FEATURES, "ridge"),
                "macro_gbm": (exp5._gbm(), AUGMENTED_FEATURES, "gbm"),
            }
            for variant, (model, features, family) in variants.items():
                model.fit(train[list(features)].astype(float), train["target_rank"].astype(float))
                if variant.startswith("macro_"):
                    for feature, value in exp5._importance(model, family).items() if False else []:
                        pass
                    if family == "ridge":
                        vals = np.abs(model.named_steps["model"].coef_)
                    else:
                        vals = model.feature_importances_
                    for feature, value in zip(features, vals, strict=True):
                        importance_rows.append(
                            {
                                "test_year": year,
                                "memory_scheme": memory_name,
                                "model": variant,
                                "feature": feature,
                                "importance": float(value),
                            }
                        )

                p = test[["timestamp", "ticker", "target_raw", "target_rank"]].copy()
                p["test_year"] = year
                p["memory_scheme"] = memory_name
                p["model"] = variant
                p["score"] = model.predict(test[list(features)].astype(float))
                predictions.append(p)

    if not predictions:
        raise ValueError("NO_ELIGIBLE_OOS_FOLDS")

    pred = pd.concat(predictions, ignore_index=True)
    support = pd.DataFrame(support_rows)
    importance = pd.DataFrame(importance_rows)

    anchor_metrics = pd.DataFrame(
        [_anchor_metric(g) for _, g in pred.groupby(["timestamp", "memory_scheme", "model"], sort=True)]
    )
    yearly = (
        anchor_metrics.groupby(["test_year", "memory_scheme", "model"])
        .agg(
            anchors=("rank_ic", "size"),
            mean_rank_ic=("rank_ic", "mean"),
            median_rank_ic=("rank_ic", "median"),
            positive_ic_fraction=("rank_ic", lambda s: float((s > 0).mean())),
            mean_top_minus_bottom_raw_target=("top_minus_bottom_raw_target", "mean"),
        )
        .reset_index()
    )

    summary_rows: list[dict[str, Any]] = []
    for (memory_name, model_name), g in anchor_metrics.groupby(["memory_scheme", "model"]):
        row = {"memory_scheme": memory_name, "model": model_name}
        row.update(_summary(g))
        summary_rows.append(row)

    post_rows: list[dict[str, Any]] = []
    post = anchor_metrics[anchor_metrics["test_year"] >= POST_START_YEAR]
    for (memory_name, model_name), g in post.groupby(["memory_scheme", "model"]):
        row = {"memory_scheme": memory_name, "model": model_name}
        row.update(_summary(g))
        post_rows.append(row)

    increment_rows: list[dict[str, Any]] = []
    for period_name, frame in (("all", anchor_metrics), ("post_2022_2024", post)):
        s = pd.DataFrame(
            [
                {"memory_scheme": mem, "model": model, **_summary(g)}
                for (mem, model), g in frame.groupby(["memory_scheme", "model"])
            ]
        )
        for memory_name in MEMORY_SCHEMES:
            lookup = {r["model"]: r for _, r in s[s["memory_scheme"] == memory_name].iterrows()}
            for macro_name, price_name in (("macro_ridge", "price_ridge"), ("macro_gbm", "price_gbm")):
                if macro_name in lookup and price_name in lookup:
                    increment_rows.append(
                        {
                            "period": period_name,
                            "memory_scheme": memory_name,
                            "comparison": f"{macro_name}_minus_{price_name}",
                            "mean_ic_increment": float(lookup[macro_name]["mean_rank_ic"] - lookup[price_name]["mean_rank_ic"]),
                            "tail_spread_increment": float(
                                lookup[macro_name]["mean_top_minus_bottom_raw_target"]
                                - lookup[price_name]["mean_top_minus_bottom_raw_target"]
                            ),
                        }
                    )
            if "macro_gbm" in lookup and "macro_ridge" in lookup:
                increment_rows.append(
                    {
                        "period": period_name,
                        "memory_scheme": memory_name,
                        "comparison": "macro_gbm_minus_macro_ridge",
                        "mean_ic_increment": float(lookup["macro_gbm"]["mean_rank_ic"] - lookup["macro_ridge"]["mean_rank_ic"]),
                        "tail_spread_increment": float(
                            lookup["macro_gbm"]["mean_top_minus_bottom_raw_target"]
                            - lookup["macro_ridge"]["mean_top_minus_bottom_raw_target"]
                        ),
                    }
                )

    macro_importance_summary: dict[str, Any] = {}
    if not importance.empty:
        for (memory_name, model_name), g in importance.groupby(["memory_scheme", "model"]):
            s = g.groupby("feature")["importance"].mean().sort_values(ascending=False)
            macro_importance_summary[f"{memory_name}:{model_name}"] = {
                "top10": [{"feature": k, "importance": float(v)} for k, v in s.head(10).items()],
                "macro_or_interaction_share": float(
                    s[[k for k in s.index if k in MACRO_STATES or "__x__" in k]].sum()
                ),
            }

    pred.to_csv(out_dir / "experiment_009_oos_predictions.csv", index=False)
    anchor_metrics.to_csv(out_dir / "experiment_009_anchor_metrics.csv", index=False)
    yearly.to_csv(out_dir / "experiment_009_yearly_metrics.csv", index=False)
    support.to_csv(out_dir / "experiment_009_fold_support.csv", index=False)
    importance.to_csv(out_dir / "experiment_009_feature_importance_by_fold.csv", index=False)
    macro_frame.reset_index().to_csv(out_dir / "experiment_009_macro_state.csv", index=False)
    pd.DataFrame(increment_rows).to_csv(out_dir / "experiment_009_macro_increment.csv", index=False)

    report = {
        "experiment": "ML_LAB_EXPERIMENT_009_MACRO_RATE_STATE_CROSS_SECTIONAL",
        "status": "EXPLORATORY_NONCONFIRMATORY",
        "boundary": "Exploratory ML Lab only; no Core/runtime/portfolio/capital implication.",
        "design": {
            "source_experiment_family": "ML_LAB_EXPERIMENT_005_TO_008",
            "memory_schemes": MEMORY_SCHEMES,
            "primary_memory_scheme": "trailing_3y",
            "price_feature_count": len(PRICE_FEATURES),
            "macro_state_features": list(MACRO_STATES),
            "interaction_bases": list(INTERACTION_BASES),
            "interaction_feature_count": len(INTERACTION_FEATURES),
            "augmented_feature_count": len(AUGMENTED_FEATURES),
            "target_changed": False,
            "model_hyperparameters_changed": False,
            "annual_target_embargo": True,
            "reserved_2025_campaign50_holdout_used": False,
            "last_allowed_date": str(exp5.LAST_ALLOWED_DATE.date()),
        },
        "sources": {
            "fred": {
                series: {
                    "cache_file": str(source_paths[series]),
                    "sha256": _sha256(source_paths[series]),
                    "rows": int(len(fred[series])),
                    "first": str(fred[series].index.min().date()),
                    "last": str(fred[series].index.max().date()),
                }
                for series in FRED_SERIES
            },
            "vix": {
                "path": str(vix_path),
                "sha256": _sha256(vix_path),
                "rows": int(len(vix)),
                "first": str(vix.index.min().date()),
                "last": str(vix.index.max().date()),
            },
        },
        "calendar": {
            "common_etf_sessions": int(len(calendar)),
            "eligible_panel_rows": int(len(panel)),
            "eligible_panel_anchors": int(panel["timestamp"].nunique()),
            "first_eligible_anchor": str(panel["timestamp"].min().date()),
            "last_eligible_anchor": str(panel["timestamp"].max().date()),
        },
        "full_model_summary": summary_rows,
        "post_2022_2024_model_summary": post_rows,
        "macro_increment_summary": increment_rows,
        "macro_feature_importance": macro_importance_summary,
        "artifact_files": {
            "oos_predictions": "experiment_009_oos_predictions.csv",
            "anchor_metrics": "experiment_009_anchor_metrics.csv",
            "yearly_metrics": "experiment_009_yearly_metrics.csv",
            "fold_support": "experiment_009_fold_support.csv",
            "feature_importance_by_fold": "experiment_009_feature_importance_by_fold.csv",
            "macro_state": "experiment_009_macro_state.csv",
            "macro_increment": "experiment_009_macro_increment.csv",
        },
    }
    (out_dir / "experiment_009_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
