"""Frozen Experiment 009 definitions extracted without numerical changes.

Private names remain compatibility exports; public aliases below are intended
for new callers. Changes to formulas/defaults require a new version.
"""
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

from research.ml_lab import cross_sectional_v1 as exp5

from research.ml_lab.acquisition_v1 import (
    FRED_SERIES, FRED_URL, _download_once, _load_fred, _load_vix,
)
from research.ml_lab.evidence import sha256_file as _sha256
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


sha256 = _sha256

download_once = _download_once

load_fred = _load_fred

load_vix = _load_vix

rolling_percentile = _rolling_percentile

align_to_calendar = _align_to_calendar

build_macro_frame = _build_macro_frame

augment_panel = _augment_panel

training_slice = _training_slice

anchor_metric = _anchor_metric

summary = _summary
