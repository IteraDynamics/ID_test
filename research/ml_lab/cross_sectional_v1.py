"""Frozen Experiment 005 definitions extracted without numerical changes.

Private names remain compatibility exports; public aliases below are intended
for new callers. Changes to formulas/defaults require a new version.
"""
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


from research.ml_lab.ohlcv_v1 import read_ohlcv

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


load_universe = _load_universe

common_calendar = _common_calendar

asset_features = _asset_features

build_panel = _build_panel

ridge = _ridge

gbm = _gbm

importance = _importance

anchor_metrics = _anchor_metrics
