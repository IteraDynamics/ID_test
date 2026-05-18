#!/usr/bin/env python
"""Equity Core Plus Lab v1.

Research-only strategic blending lab for Equity Core + beta/signal overlays.

Promotion discipline for this lab:
    A candidate is passable only if it improves CAGR versus BASE_EQUITY_CORE
    while keeping max drawdown no worse than the configured fund threshold
    (default: -20%).

Candidate families:
  - Core + controlled QQQ beta tilt
  - Core + episodic signal sleeves
  - Core + composite signal sleeve
  - volatility-matched signal diagnostics

No fund target book changes, crypto target stream changes, live trading, broker
integration, paper-broker execution, order generation, fill simulation, runtime
integration, dashboard deployment, or dynamic fund allocation are made.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd


DEFAULT_OUT = "artifacts/equity_core_plus_lab_v1"
START_CAPITAL = 100_000.0
TRADING_DAYS = 252.0
CANDIDATES = [
    "BASE_EQUITY_CORE",
    "CORE_90_QQQ_10",
    "CORE_80_QQQ_20",
    "CORE_70_QQQ_30",
    "CORE_PLUS_10_MEAN_REVERSION_1D",
    "CORE_PLUS_20_MEAN_REVERSION_1D",
    "CORE_PLUS_10_SELL_OFF_BOUNCE_RSI2",
    "CORE_PLUS_20_SELL_OFF_BOUNCE_RSI2",
    "CORE_PLUS_10_SIGNAL_COMPOSITE",
    "CORE_PLUS_20_SIGNAL_COMPOSITE",
    "CORE_PLUS_10_VOL_MATCHED_COMPOSITE",
    "CORE_PLUS_20_VOL_MATCHED_COMPOSITE",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run Equity Core Plus strategic overlay lab",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--equity-core-window", type=int, default=175)
    p.add_argument("--trend-window", type=int, default=200)
    p.add_argument("--rsi2-threshold", type=float, default=10.0)
    p.add_argument("--rsi5-threshold", type=float, default=25.0)
    p.add_argument("--mr-1d-threshold", type=float, default=-0.02)
    p.add_argument("--mr-3d-threshold", type=float, default=-0.04)
    p.add_argument("--crash-5d-threshold", type=float, default=-0.08)
    p.add_argument("--crash-10d-threshold", type=float, default=-0.12)
    p.add_argument("--compression-window", type=int, default=20)
    p.add_argument("--compression-quantile-window", type=int, default=252)
    p.add_argument("--compression-quantile", type=float, default=0.25)
    p.add_argument("--max-dd-threshold", type=float, default=-20.0, help="Maximum acceptable drawdown percentage for pass/fail gating.")
    p.add_argument("--capital", type=float, default=START_CAPITAL)
    p.add_argument("--accounting-tolerance", type=float, default=1e-6)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    return p.parse_args()


def _detect_time_col(df: pd.DataFrame) -> str:
    lower = {str(c).lower(): c for c in df.columns}
    for name in ["timestamp", "date", "datetime", "time", "unnamed: 0"]:
        if name in lower:
            return str(lower[name])
    return str(df.columns[0])


def _read_price_csv(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label} data file: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty {label} data file: {path}")
    time_col = _detect_time_col(df)
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).set_index(time_col).sort_index()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.rename(columns={"adj close": "close", "adj_close": "close", "adjusted_close": "close"})
    required = ["open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{label} data missing required OHLC columns: {missing}. Got {list(df.columns)}")
    cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    out = df[cols].copy()
    for col in out.columns:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close"])
    return out


def _load_panel(spy_path: Path, qqq_path: Path, bil_path: Path) -> pd.DataFrame:
    spy = _read_price_csv(spy_path, "SPY").add_prefix("SPY_")
    qqq = _read_price_csv(qqq_path, "QQQ").add_prefix("QQQ_")
    bil = _read_price_csv(bil_path, "BIL").add_prefix("BIL_")
    return pd.concat([spy, qqq, bil], axis=1).sort_index().ffill().dropna(subset=["SPY_close", "QQQ_close", "BIL_close"])


def _rsi(series: pd.Series, window: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(window, min_periods=window).mean()
    avg_loss = loss.rolling(window, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)


def _price_frame(panel: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"SPY": panel["SPY_close"], "QQQ": panel["QQQ_close"], "BIL": panel["BIL_close"]}, index=panel.index)


def _build_base_weights(panel: pd.DataFrame, window: int) -> pd.DataFrame:
    spy_sma = panel["SPY_close"].rolling(window, min_periods=window).mean()
    qqq_sma = panel["QQQ_close"].rolling(window, min_periods=window).mean()
    weights = pd.DataFrame(0.0, index=panel.index, columns=["SPY", "QQQ", "BIL"])
    weights["SPY"] = 0.5 * (panel["SPY_close"] > spy_sma).astype(float)
    weights["QQQ"] = 0.5 * (panel["QQQ_close"] > qqq_sma).astype(float)
    weights["BIL"] = 1.0 - weights["SPY"] - weights["QQQ"]
    return weights


def _normalize(weights: pd.DataFrame) -> pd.DataFrame:
    out = weights.copy().fillna(0.0).clip(lower=0.0)
    risky = out[["SPY", "QQQ"]].sum(axis=1)
    overflow = risky > 1.0
    if overflow.any():
        out.loc[overflow, ["SPY", "QQQ"]] = out.loc[overflow, ["SPY", "QQQ"]].div(risky.loc[overflow], axis=0)
    out["BIL"] = 1.0 - out["SPY"] - out["QQQ"]
    return out


def _build_signal_panel(panel: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    sig = pd.DataFrame(index=panel.index)
    qqq_ret_1d = panel["QQQ_close"].pct_change(fill_method=None)
    qqq_ret_3d = panel["QQQ_close"].pct_change(3, fill_method=None)
    qqq_ret_5d = panel["QQQ_close"].pct_change(5, fill_method=None)
    qqq_ret_10d = panel["QQQ_close"].pct_change(10, fill_method=None)
    qqq_ret_20d = panel["QQQ_close"].pct_change(20, fill_method=None)
    qqq_sma = panel["QQQ_close"].rolling(args.trend_window, min_periods=args.trend_window).mean()
    spy_sma = panel["SPY_close"].rolling(args.trend_window, min_periods=args.trend_window).mean()
    qqq_trend = panel["QQQ_close"] > qqq_sma
    spy_trend = panel["SPY_close"] > spy_sma

    sig["qqq_ret_1d"] = qqq_ret_1d
    sig["qqq_ret_3d"] = qqq_ret_3d
    sig["qqq_ret_5d"] = qqq_ret_5d
    sig["qqq_ret_10d"] = qqq_ret_10d
    sig["qqq_rsi2"] = _rsi(panel["QQQ_close"], 2)
    sig["qqq_rsi5"] = _rsi(panel["QQQ_close"], 5)
    sig["qqq_trend"] = qqq_trend
    sig["spy_trend"] = spy_trend

    vol20 = qqq_ret_1d.rolling(args.compression_window, min_periods=args.compression_window).std(ddof=0)
    vol_threshold = vol20.rolling(args.compression_quantile_window, min_periods=args.compression_quantile_window).quantile(args.compression_quantile)
    prior_high = panel["QQQ_close"].rolling(args.compression_window, min_periods=args.compression_window).max().shift(1)
    sig["vol_compressed"] = vol20 < vol_threshold
    sig["breakout"] = panel["QQQ_close"] > prior_high

    sig["MEAN_REVERSION_1D"] = (qqq_ret_1d <= args.mr_1d_threshold) & qqq_trend
    sig["MEAN_REVERSION_3D"] = (qqq_ret_3d <= args.mr_3d_threshold) & qqq_trend
    sig["SELL_OFF_BOUNCE_RSI2"] = (sig["qqq_rsi2"] <= args.rsi2_threshold) & qqq_trend
    sig["SELL_OFF_BOUNCE_RSI5"] = (sig["qqq_rsi5"] <= args.rsi5_threshold) & qqq_trend
    sig["VOL_COMPRESSION_BREAKOUT"] = sig["vol_compressed"].shift(1).fillna(False).astype(bool) & sig["breakout"] & qqq_trend
    sig["TREND_CONTINUATION_PULLBACK"] = qqq_trend & spy_trend & (qqq_ret_5d < 0.0) & (qqq_ret_20d > 0.0)
    sig["CRASH_RECOVERY_5D"] = (qqq_ret_5d <= args.crash_5d_threshold) & (panel["QQQ_close"] > panel["QQQ_close"].shift(1))
    sig["CRASH_RECOVERY_10D"] = (qqq_ret_10d <= args.crash_10d_threshold) & (panel["QQQ_close"] > panel["QQQ_close"].shift(1))
    sig["COMPOSITE_SIGNAL"] = sig[[
        "MEAN_REVERSION_1D",
        "MEAN_REVERSION_3D",
        "SELL_OFF_BOUNCE_RSI2",
        "SELL_OFF_BOUNCE_RSI5",
        "VOL_COMPRESSION_BREAKOUT",
        "TREND_CONTINUATION_PULLBACK",
        "CRASH_RECOVERY_5D",
        "CRASH_RECOVERY_10D",
    ]].any(axis=1)
    return sig


def _qqq_beta_blend(base: pd.DataFrame, qqq_share: float) -> pd.DataFrame:
    qqq_hold = pd.DataFrame(0.0, index=base.index, columns=["SPY", "QQQ", "BIL"])
    qqq_hold["QQQ"] = 1.0
    return _normalize((1.0 - qqq_share) * base + qqq_share * qqq_hold)


def _core_plus_signal(base: pd.DataFrame, signal: pd.Series, alpha_share: float) -> pd.DataFrame:
    out = base.copy()
    signal = signal.reindex(out.index).fillna(False).astype(bool)
    for ts in out.index[signal]:
        bil = float(out.loc[ts, "BIL"])
        use_cash = min(alpha_share, bil)
        residual = alpha_share - use_cash
        if use_cash > 0.0:
            out.loc[ts, "BIL"] -= use_cash
            out.loc[ts, "QQQ"] += use_cash
        if residual > 0.0:
            risky = float(out.loc[ts, "SPY"] + out.loc[ts, "QQQ"])
            if risky > 1e-12:
                scale = max(risky - residual, 0.0) / risky
                out.loc[ts, "SPY"] *= scale
                out.loc[ts, "QQQ"] *= scale
                out.loc[ts, "QQQ"] += residual
    return _normalize(out)


def _vol_matched_core_plus_signal(prices: pd.DataFrame, base: pd.DataFrame, signal: pd.Series, target_alpha_share: float, base_vol: float) -> pd.DataFrame:
    # Estimate signal sleeve vol at full exposure, then scale the overlay so it is not just a hidden beta spike.
    signal_weights = pd.DataFrame(0.0, index=base.index, columns=["SPY", "QQQ", "BIL"])
    signal_bool = signal.reindex(base.index).fillna(False).astype(bool)
    signal_weights.loc[signal_bool, "QQQ"] = 1.0
    signal_weights.loc[~signal_bool, "BIL"] = 1.0
    _, signal_rets = _curve_from_weights(prices, _normalize(signal_weights), 1.0)
    sig_vol = float(signal_rets.std(ddof=0) * math.sqrt(TRADING_DAYS))
    if sig_vol <= 1e-12 or base_vol <= 1e-12:
        scale = 0.0
    else:
        scale = min(1.0, base_vol / sig_vol)
    return _core_plus_signal(base, signal, target_alpha_share * scale)


def _apply_candidates(prices: pd.DataFrame, base: pd.DataFrame, signal_panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    _, base_rets = _curve_from_weights(prices, base, 1.0)
    base_vol = float(base_rets.std(ddof=0) * math.sqrt(TRADING_DAYS))
    candidates: dict[str, pd.DataFrame] = {"BASE_EQUITY_CORE": base}
    candidates["CORE_90_QQQ_10"] = _qqq_beta_blend(base, 0.10)
    candidates["CORE_80_QQQ_20"] = _qqq_beta_blend(base, 0.20)
    candidates["CORE_70_QQQ_30"] = _qqq_beta_blend(base, 0.30)
    candidates["CORE_PLUS_10_MEAN_REVERSION_1D"] = _core_plus_signal(base, signal_panel["MEAN_REVERSION_1D"], 0.10)
    candidates["CORE_PLUS_20_MEAN_REVERSION_1D"] = _core_plus_signal(base, signal_panel["MEAN_REVERSION_1D"], 0.20)
    candidates["CORE_PLUS_10_SELL_OFF_BOUNCE_RSI2"] = _core_plus_signal(base, signal_panel["SELL_OFF_BOUNCE_RSI2"], 0.10)
    candidates["CORE_PLUS_20_SELL_OFF_BOUNCE_RSI2"] = _core_plus_signal(base, signal_panel["SELL_OFF_BOUNCE_RSI2"], 0.20)
    candidates["CORE_PLUS_10_SIGNAL_COMPOSITE"] = _core_plus_signal(base, signal_panel["COMPOSITE_SIGNAL"], 0.10)
    candidates["CORE_PLUS_20_SIGNAL_COMPOSITE"] = _core_plus_signal(base, signal_panel["COMPOSITE_SIGNAL"], 0.20)
    candidates["CORE_PLUS_10_VOL_MATCHED_COMPOSITE"] = _vol_matched_core_plus_signal(prices, base, signal_panel["COMPOSITE_SIGNAL"], 0.10, base_vol)
    candidates["CORE_PLUS_20_VOL_MATCHED_COMPOSITE"] = _vol_matched_core_plus_signal(prices, base, signal_panel["COMPOSITE_SIGNAL"], 0.20, base_vol)
    return {name: _normalize(weights) for name, weights in candidates.items()}


def _curve_from_weights(prices: pd.DataFrame, weights: pd.DataFrame, capital: float) -> tuple[pd.Series, pd.Series]:
    data = prices.reindex(weights.index).dropna()
    w = weights.reindex(data.index).fillna(0.0)
    rets = data[["SPY", "QQQ", "BIL"]].pct_change(fill_method=None).fillna(0.0)
    exec_w = w.shift(1).fillna({"SPY": 0.0, "QQQ": 0.0, "BIL": 1.0})
    port_rets = (exec_w * rets).sum(axis=1)
    curve = capital * (1.0 + port_rets).cumprod()
    return curve, port_rets


def _bars_per_year(index: pd.DatetimeIndex) -> float:
    if len(index) < 3:
        return TRADING_DAYS
    deltas = index.to_series().diff().dropna().dt.total_seconds()
    if deltas.empty:
        return TRADING_DAYS
    med = float(deltas.median())
    if med <= 0 or med >= 20 * 3600:
        return TRADING_DAYS
    return float(365.25 * 24 * 3600 / med)


def _max_time_underwater_days(eq: pd.Series) -> float:
    eq = eq.dropna().astype(float)
    dd = eq / eq.cummax() - 1.0
    start = None
    max_days = 0.0
    for ts, flag in (dd < 0).items():
        if flag and start is None:
            start = ts
        elif not flag and start is not None:
            max_days = max(max_days, (ts - start).total_seconds() / 86400.0)
            start = None
    if start is not None and len(eq):
        max_days = max(max_days, (eq.index[-1] - start).total_seconds() / 86400.0)
    return float(max_days)


def _sortino(eq: pd.Series) -> float:
    rets = eq.dropna().astype(float).pct_change(fill_method=None).dropna()
    if rets.empty:
        return 0.0
    downside = np.minimum(rets, 0.0)
    downside_dev = float(np.sqrt(np.mean(np.square(downside))))
    if downside_dev <= 1e-12:
        return 0.0
    return float((rets.mean() / downside_dev) * math.sqrt(_bars_per_year(eq.index)))


def _perf(eq: pd.Series) -> dict[str, float]:
    eq = eq.dropna().astype(float)
    if len(eq) < 2:
        return {k: 0.0 for k in ["total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar", "ann_vol_pct", "worst_90d_return_pct", "worst_180d_return_pct", "max_time_underwater_days"]}
    rets = eq.pct_change(fill_method=None).dropna()
    years = max((eq.index[-1] - eq.index[0]).total_seconds() / (365.25 * 24 * 3600), 1e-9)
    total = float(eq.iloc[-1] / eq.iloc[0] - 1.0)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0)
    dd = eq / eq.cummax() - 1.0
    max_dd = float(dd.min())
    std = float(rets.std(ddof=0))
    bpy = _bars_per_year(eq.index)
    sharpe = float((rets.mean() / std) * math.sqrt(bpy)) if std > 1e-12 else 0.0
    ann_vol = float(std * math.sqrt(bpy)) if std > 0 else 0.0
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0
    worst_90 = float(eq.pct_change(90, fill_method=None).dropna().min()) if len(eq) > 90 else 0.0
    worst_180 = float(eq.pct_change(180, fill_method=None).dropna().min()) if len(eq) > 180 else 0.0
    return {
        "total_return_pct": total * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe": sharpe,
        "sortino": _sortino(eq),
        "calmar": calmar,
        "ann_vol_pct": ann_vol * 100.0,
        "worst_90d_return_pct": worst_90 * 100.0,
        "worst_180d_return_pct": worst_180 * 100.0,
        "max_time_underwater_days": _max_time_underwater_days(eq),
    }


def _monthly_returns(rets: pd.Series) -> pd.Series:
    if rets.empty:
        return pd.Series(dtype=float)
    return (1.0 + rets).resample("ME").prod() - 1.0


def _excess_metrics(candidate_rets: pd.Series, base_rets: pd.Series, candidate_eq: pd.Series, base_eq: pd.Series) -> dict[str, float]:
    aligned = pd.concat([candidate_rets.rename("candidate"), base_rets.rename("base")], axis=1).dropna()
    if aligned.empty:
        return {k: 0.0 for k in ["active_return_ann_pct", "tracking_error_pct", "information_ratio", "daily_win_rate_vs_base_pct", "monthly_win_rate_vs_base_pct", "excess_total_return_vs_base_pct", "excess_cagr_vs_base_pct"]}
    active = aligned["candidate"] - aligned["base"]
    bpy = _bars_per_year(aligned.index)
    tracking_error = float(active.std(ddof=0) * math.sqrt(bpy))
    active_ann = float(active.mean() * bpy)
    info = float(active_ann / tracking_error) if tracking_error > 1e-12 else 0.0
    daily_win = float((active > 0.0).mean() * 100.0)
    monthly = pd.concat([_monthly_returns(aligned["candidate"]).rename("candidate"), _monthly_returns(aligned["base"]).rename("base")], axis=1).dropna()
    monthly_win = float((monthly["candidate"] > monthly["base"]).mean() * 100.0) if not monthly.empty else 0.0
    cand_perf = _perf(candidate_eq)
    base_perf = _perf(base_eq)
    return {
        "active_return_ann_pct": active_ann * 100.0,
        "tracking_error_pct": tracking_error * 100.0,
        "information_ratio": info,
        "daily_win_rate_vs_base_pct": daily_win,
        "monthly_win_rate_vs_base_pct": monthly_win,
        "excess_total_return_vs_base_pct": cand_perf["total_return_pct"] - base_perf["total_return_pct"],
        "excess_cagr_vs_base_pct": cand_perf["cagr_pct"] - base_perf["cagr_pct"],
    }


def _exposure_stats(weights: pd.DataFrame) -> dict[str, float]:
    equity = weights["SPY"] + weights["QQQ"]
    turnover = weights[["SPY", "QQQ", "BIL"]].diff().abs().sum(axis=1).fillna(0.0)
    return {
        "avg_spy_weight_pct": float(weights["SPY"].mean() * 100.0),
        "avg_qqq_weight_pct": float(weights["QQQ"].mean() * 100.0),
        "avg_bil_weight_pct": float(weights["BIL"].mean() * 100.0),
        "avg_equity_weight_pct": float(equity.mean() * 100.0),
        "time_full_equity_pct": float((equity >= 0.999).mean() * 100.0),
        "avg_daily_turnover_proxy_pct": float(turnover.mean() * 100.0),
        "total_turnover_proxy": float(turnover.sum()),
    }


def _build_diagnostics(candidates: dict[str, pd.DataFrame], signal_panel: pd.DataFrame, tol: float) -> pd.DataFrame:
    frames = []
    for name, weights in candidates.items():
        diag = pd.DataFrame(index=weights.index)
        diag["candidate_name"] = name
        diag["target_spy_weight"] = weights["SPY"]
        diag["target_qqq_weight"] = weights["QQQ"]
        diag["target_bil_weight"] = weights["BIL"]
        diag["total_accounted_weight"] = weights[["SPY", "QQQ", "BIL"]].sum(axis=1)
        diag["accounting_error"] = diag["total_accounted_weight"] - 1.0
        diag["accounting_ok"] = diag["accounting_error"].abs() <= tol
        diag["mean_reversion_1d"] = signal_panel["MEAN_REVERSION_1D"].reindex(weights.index).fillna(False).astype(bool)
        diag["sell_off_bounce_rsi2"] = signal_panel["SELL_OFF_BOUNCE_RSI2"].reindex(weights.index).fillna(False).astype(bool)
        diag["composite_signal"] = signal_panel["COMPOSITE_SIGNAL"].reindex(weights.index).fillna(False).astype(bool)
        diag["qqq_rsi2"] = signal_panel["qqq_rsi2"].reindex(weights.index)
        diag["qqq_ret_1d"] = signal_panel["qqq_ret_1d"].reindex(weights.index)
        diag["qqq_ret_3d"] = signal_panel["qqq_ret_3d"].reindex(weights.index)
        diag["qqq_ret_5d"] = signal_panel["qqq_ret_5d"].reindex(weights.index)
        frames.append(diag.reset_index(names="timestamp"))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _readiness_summary(summary: pd.DataFrame, diagnostics: pd.DataFrame, max_dd_threshold: float) -> pd.DataFrame:
    rows = []
    for _, row in summary.iterrows():
        candidate = row["candidate_name"]
        cand_diag = diagnostics[diagnostics["candidate_name"] == candidate]
        accounting_ok_pct = float(cand_diag["accounting_ok"].mean() * 100.0) if not cand_diag.empty else 0.0
        cagr_improved = bool(row["excess_cagr_vs_base_pct"] > 0.0)
        maxdd_ok = bool(row["max_drawdown_pct"] >= max_dd_threshold)
        pass_gate = bool(cagr_improved and maxdd_ok and accounting_ok_pct >= 99.999)
        rows.append({
            "candidate_name": candidate,
            "research_ready": bool(accounting_ok_pct >= 99.999 and row["bars"] > 0),
            "core_plus_pass_gate": pass_gate,
            "cagr_improved_vs_base": cagr_improved,
            "maxdd_within_threshold": maxdd_ok,
            "max_dd_threshold_pct": max_dd_threshold,
            "broker_ready": False,
            "promotion_eligible": False,
            "readiness_state": "equity_core_plus_lab_diagnostic_only",
            "accounting_ok_pct": accounting_ok_pct,
            "readiness_reason": "Research-only Core Plus candidate. Pass gate requires positive excess CAGR and max drawdown within threshold. No promotion, broker mapping, order generation, live trading, or fund book modification is approved.",
        })
    return pd.DataFrame(rows)


def _fmt_md_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    if pd.isna(value):
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    if max_rows is not None:
        df = df.head(max_rows)
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(_fmt_md_value(row[c]) for c in df.columns) + " |")
    return "\n".join(lines)


def _write_summary_md(path: Path, summary: pd.DataFrame, readiness: pd.DataFrame, args: argparse.Namespace) -> None:
    lines = [
        "# Equity Core Plus Lab v1",
        "",
        "Research-only strategic blending lab for Equity Core + beta/signal overlays.",
        "",
        "## Pass Gate",
        "",
        "```text",
        "Candidate passes only if:",
        "1. CAGR improves versus BASE_EQUITY_CORE", 
        f"2. Max drawdown stays within threshold: {args.max_dd_threshold:.2f}%", 
        "3. Accounting remains valid", 
        "```",
        "",
        "## Candidate Summary",
        "",
        _md_table(summary, max_rows=120),
        "",
        "## Readiness Summary",
        "",
        _md_table(readiness, max_rows=120),
        "",
        "## Guardrail",
        "",
        "```text",
        "Research only. No fund target book changes, crypto target stream changes, live trading, broker integration, paper-broker execution, order generation, fill simulation, runtime deployment, dashboard integration, dynamic allocator changes, or equity core replacement are approved.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ["equity_core_window", "trend_window", "compression_window", "compression_quantile_window"]:
        if int(getattr(args, name)) < 2:
            raise ValueError(f"{name} must be >= 2")

    panel = _load_panel(Path(args.spy_data), Path(args.qqq_data), Path(args.bil_data))
    prices = _price_frame(panel)
    base_weights = _build_base_weights(panel, args.equity_core_window)
    signal_panel = _build_signal_panel(panel, args)
    candidates = _apply_candidates(prices, base_weights, signal_panel)

    curves: dict[str, pd.Series] = {}
    returns: dict[str, pd.Series] = {}
    for name in CANDIDATES:
        curve, rets = _curve_from_weights(prices, candidates[name], args.capital)
        curves[name] = curve.rename(name)
        returns[name] = rets.rename(name)

    base_curve = curves["BASE_EQUITY_CORE"]
    base_rets = returns["BASE_EQUITY_CORE"]
    summary_rows: list[dict[str, Any]] = []
    for name in CANDIDATES:
        clean = curves[name].dropna()
        summary_rows.append({
            "candidate_name": name,
            "start": str(clean.index[0]) if len(clean) else "n/a",
            "end": str(clean.index[-1]) if len(clean) else "n/a",
            "bars": int(len(clean)),
            **_perf(clean),
            **_excess_metrics(returns[name], base_rets, clean, base_curve),
            **_exposure_stats(candidates[name]),
            "complexity_flags": "baseline" if name == "BASE_EQUITY_CORE" else "core_plus_lab_only",
            "fund_level_compatibility": "diagnostic_only_not_promoted",
        })

    summary = pd.DataFrame(summary_rows)
    summary = summary.sort_values(["excess_cagr_vs_base_pct", "max_drawdown_pct", "information_ratio"], ascending=[False, False, False])
    diagnostics = _build_diagnostics(candidates, signal_panel, args.accounting_tolerance)
    readiness = _readiness_summary(summary, diagnostics, args.max_dd_threshold)
    curves_df = pd.concat(curves.values(), axis=1)
    returns_df = pd.concat(returns.values(), axis=1)

    summary.to_csv(out_dir / "equity_core_plus_summary.csv", index=False)
    curves_df.to_csv(out_dir / "equity_core_plus_candidate_curves.csv")
    returns_df.to_csv(out_dir / "equity_core_plus_candidate_returns.csv")
    diagnostics.to_csv(out_dir / "equity_core_plus_diagnostics.csv", index=False)
    readiness.to_csv(out_dir / "equity_core_plus_readiness_summary.csv", index=False)

    payload = {
        "research_status": "research_only_equity_core_plus_lab_v1",
        "readiness_state": "equity_core_plus_lab_diagnostic_only",
        "pass_gate": {
            "requires_positive_excess_cagr": True,
            "max_drawdown_threshold_pct": args.max_dd_threshold,
            "requires_accounting_ok": True,
        },
        "inputs": vars(args),
        "outputs": {
            "summary_csv": str(out_dir / "equity_core_plus_summary.csv"),
            "candidate_curves": str(out_dir / "equity_core_plus_candidate_curves.csv"),
            "candidate_returns": str(out_dir / "equity_core_plus_candidate_returns.csv"),
            "diagnostics": str(out_dir / "equity_core_plus_diagnostics.csv"),
            "readiness_summary": str(out_dir / "equity_core_plus_readiness_summary.csv"),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "decision": {
            "status": "core_plus_discovery_only_not_promoted",
            "broker_ready": False,
            "promotion_eligible": False,
            "not_approved": ["fund_target_book_change", "crypto_target_stream_change", "equity_core_replacement", "live_trading", "broker_integration", "paper_broker_execution", "order_generation", "fill_simulation", "runtime_deployment", "dashboard_integration", "dynamic_fund_allocator"],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", summary, readiness, args)

    with pd.option_context("display.max_columns", None, "display.width", 900, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY CORE PLUS LAB V1 ===")
        print("\nCandidate Summary:")
        print(summary.to_string(index=False))
        print("\nReadiness Summary:")
        print(readiness.to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
