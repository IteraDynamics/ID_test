#!/usr/bin/env python
"""Equity Signal Alpha Lab v1.

Research-only comparison harness for actual equity signal alpha families versus
baseline comparators. This lab tests signal logic rather than ETF substitution:
short-term mean reversion, selloff bounce, volatility compression breakout,
trend-continuation pullback, crash recovery, and overnight-style proxy signals.

Baseline comparators:
  - BASE_EQUITY_CORE: SPY/QQQ SMA175 with BIL risk-off
  - SPY_HOLD
  - QQQ_HOLD
  - SPY_QQQ_50_50

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


DEFAULT_OUT = "artifacts/equity_signal_alpha_lab_v1"
START_CAPITAL = 100_000.0
TRADING_DAYS = 252.0
CANDIDATES = [
    "BASE_EQUITY_CORE",
    "SPY_HOLD",
    "QQQ_HOLD",
    "SPY_QQQ_50_50",
    "MEAN_REVERSION_1D",
    "MEAN_REVERSION_3D",
    "MEAN_REVERSION_5D",
    "SELL_OFF_BOUNCE_RSI2",
    "SELL_OFF_BOUNCE_RSI5",
    "VOL_COMPRESSION_BREAKOUT",
    "TREND_CONTINUATION_PULLBACK",
    "CRASH_RECOVERY_5D",
    "CRASH_RECOVERY_10D",
    "OVERNIGHT_PROXY_CLOSE_TO_CLOSE_LIMITED",
    "COMPOSITE_SIGNAL_ALPHA_EQUAL_WEIGHT",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run equity signal alpha comparison lab",
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
    p.add_argument("--mr-5d-threshold", type=float, default=-0.06)
    p.add_argument("--crash-5d-threshold", type=float, default=-0.08)
    p.add_argument("--crash-10d-threshold", type=float, default=-0.12)
    p.add_argument("--compression-window", type=int, default=20)
    p.add_argument("--compression-quantile-window", type=int, default=252)
    p.add_argument("--compression-quantile", type=float, default=0.25)
    p.add_argument("--max-signal-exposure", type=float, default=1.0)
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
    rename = {
        "adj close": "close",
        "adj_close": "close",
        "adjusted_close": "close",
    }
    df = df.rename(columns=rename)
    required = ["open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{label} data missing required OHLC columns: {missing}. Got {list(df.columns)}")
    out = df[[c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]].copy()
    for col in out.columns:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close"])
    return out


def _load_panel(spy_path: Path, qqq_path: Path, bil_path: Path) -> pd.DataFrame:
    spy = _read_price_csv(spy_path, "SPY").add_prefix("SPY_")
    qqq = _read_price_csv(qqq_path, "QQQ").add_prefix("QQQ_")
    bil = _read_price_csv(bil_path, "BIL").add_prefix("BIL_")
    panel = pd.concat([spy, qqq, bil], axis=1).sort_index().ffill().dropna(subset=["SPY_close", "QQQ_close", "BIL_close"])
    return panel


def _rsi(series: pd.Series, window: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(window, min_periods=window).mean()
    avg_loss = loss.rolling(window, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def _build_base_weights(panel: pd.DataFrame, window: int) -> pd.DataFrame:
    spy_sma = panel["SPY_close"].rolling(window, min_periods=window).mean()
    qqq_sma = panel["QQQ_close"].rolling(window, min_periods=window).mean()
    weights = pd.DataFrame(index=panel.index, columns=["SPY", "QQQ", "BIL"], data=0.0)
    weights["SPY"] = 0.5 * (panel["SPY_close"] > spy_sma).astype(float)
    weights["QQQ"] = 0.5 * (panel["QQQ_close"] > qqq_sma).astype(float)
    weights["BIL"] = 1.0 - weights["SPY"] - weights["QQQ"]
    return weights


def _constant_weights(index: pd.DatetimeIndex, spy: float, qqq: float, bil: float) -> pd.DataFrame:
    return pd.DataFrame({"SPY": spy, "QQQ": qqq, "BIL": bil}, index=index)


def _signal_weights(index: pd.DatetimeIndex, signal: pd.Series, target_asset: str = "QQQ", exposure: float = 1.0) -> pd.DataFrame:
    signal = signal.reindex(index).fillna(False).astype(bool)
    weights = pd.DataFrame(0.0, index=index, columns=["SPY", "QQQ", "BIL"])
    weights[target_asset] = signal.astype(float) * exposure
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
    sig["vol20"] = vol20
    sig["vol_compressed"] = vol20 < vol_threshold
    sig["breakout"] = panel["QQQ_close"] > prior_high

    sig["MEAN_REVERSION_1D"] = (qqq_ret_1d <= args.mr_1d_threshold) & qqq_trend
    sig["MEAN_REVERSION_3D"] = (qqq_ret_3d <= args.mr_3d_threshold) & qqq_trend
    sig["MEAN_REVERSION_5D"] = (qqq_ret_5d <= args.mr_5d_threshold) & qqq_trend
    sig["SELL_OFF_BOUNCE_RSI2"] = (sig["qqq_rsi2"] <= args.rsi2_threshold) & qqq_trend
    sig["SELL_OFF_BOUNCE_RSI5"] = (sig["qqq_rsi5"] <= args.rsi5_threshold) & qqq_trend
    sig["VOL_COMPRESSION_BREAKOUT"] = sig["vol_compressed"].shift(1).fillna(False).astype(bool) & sig["breakout"] & qqq_trend
    sig["TREND_CONTINUATION_PULLBACK"] = qqq_trend & spy_trend & (qqq_ret_5d < 0.0) & (qqq_ret_20 := panel["QQQ_close"].pct_change(20, fill_method=None)).gt(0.0)
    sig["CRASH_RECOVERY_5D"] = (qqq_ret_5d <= args.crash_5d_threshold) & (panel["QQQ_close"] > panel["QQQ_close"].shift(1))
    sig["CRASH_RECOVERY_10D"] = (qqq_ret_10d <= args.crash_10d_threshold) & (panel["QQQ_close"] > panel["QQQ_close"].shift(1))
    sig["OVERNIGHT_PROXY_CLOSE_TO_CLOSE_LIMITED"] = qqq_trend & (panel["QQQ_close"] < panel["QQQ_open"]) & (qqq_ret_1d < 0.0)
    return sig


def _apply_candidates(panel: pd.DataFrame, base: pd.DataFrame, signal_panel: pd.DataFrame, args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    idx = panel.index
    candidates: dict[str, pd.DataFrame] = {
        "BASE_EQUITY_CORE": base,
        "SPY_HOLD": _constant_weights(idx, 1.0, 0.0, 0.0),
        "QQQ_HOLD": _constant_weights(idx, 0.0, 1.0, 0.0),
        "SPY_QQQ_50_50": _constant_weights(idx, 0.5, 0.5, 0.0),
    }
    for name in [
        "MEAN_REVERSION_1D",
        "MEAN_REVERSION_3D",
        "MEAN_REVERSION_5D",
        "SELL_OFF_BOUNCE_RSI2",
        "SELL_OFF_BOUNCE_RSI5",
        "VOL_COMPRESSION_BREAKOUT",
        "TREND_CONTINUATION_PULLBACK",
        "CRASH_RECOVERY_5D",
        "CRASH_RECOVERY_10D",
        "OVERNIGHT_PROXY_CLOSE_TO_CLOSE_LIMITED",
    ]:
        candidates[name] = _signal_weights(idx, signal_panel[name], target_asset="QQQ", exposure=args.max_signal_exposure)

    signal_names = [
        "MEAN_REVERSION_1D",
        "MEAN_REVERSION_3D",
        "SELL_OFF_BOUNCE_RSI2",
        "SELL_OFF_BOUNCE_RSI5",
        "VOL_COMPRESSION_BREAKOUT",
        "TREND_CONTINUATION_PULLBACK",
        "CRASH_RECOVERY_5D",
        "CRASH_RECOVERY_10D",
    ]
    composite = pd.DataFrame(0.0, index=idx, columns=["SPY", "QQQ", "BIL"])
    for name in signal_names:
        composite += candidates[name] / float(len(signal_names))
    candidates["COMPOSITE_SIGNAL_ALPHA_EQUAL_WEIGHT"] = _normalize(composite)
    return {name: _normalize(weights) for name, weights in candidates.items()}


def _price_frame(panel: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"SPY": panel["SPY_close"], "QQQ": panel["QQQ_close"], "BIL": panel["BIL_close"]}, index=panel.index)


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
        return {k: 0.0 for k in ["active_return_ann_pct", "tracking_error_pct", "information_ratio", "daily_win_rate_vs_base_pct", "monthly_win_rate_vs_base_pct", "up_capture_vs_base", "down_capture_vs_base", "excess_total_return_vs_base_pct", "excess_cagr_vs_base_pct"]}
    active = aligned["candidate"] - aligned["base"]
    bpy = _bars_per_year(aligned.index)
    tracking_error = float(active.std(ddof=0) * math.sqrt(bpy))
    active_ann = float(active.mean() * bpy)
    info = float(active_ann / tracking_error) if tracking_error > 1e-12 else 0.0
    daily_win = float((active > 0.0).mean() * 100.0)
    cand_m = _monthly_returns(aligned["candidate"])
    base_m = _monthly_returns(aligned["base"])
    monthly = pd.concat([cand_m.rename("candidate"), base_m.rename("base")], axis=1).dropna()
    monthly_win = float((monthly["candidate"] > monthly["base"]).mean() * 100.0) if not monthly.empty else 0.0
    up = aligned[aligned["base"] > 0.0]
    down = aligned[aligned["base"] < 0.0]
    up_capture = float(up["candidate"].sum() / up["base"].sum()) if not up.empty and abs(float(up["base"].sum())) > 1e-12 else 0.0
    down_capture = float(down["candidate"].sum() / down["base"].sum()) if not down.empty and abs(float(down["base"].sum())) > 1e-12 else 0.0
    cand_perf = _perf(candidate_eq)
    base_perf = _perf(base_eq)
    return {
        "active_return_ann_pct": active_ann * 100.0,
        "tracking_error_pct": tracking_error * 100.0,
        "information_ratio": info,
        "daily_win_rate_vs_base_pct": daily_win,
        "monthly_win_rate_vs_base_pct": monthly_win,
        "up_capture_vs_base": up_capture,
        "down_capture_vs_base": down_capture,
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
        "time_in_market_pct": float((equity > 1e-9).mean() * 100.0),
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
        if name in signal_panel.columns:
            diag["signal_active"] = signal_panel[name].reindex(weights.index).fillna(False).astype(bool)
        else:
            diag["signal_active"] = (weights["SPY"] + weights["QQQ"]) > 1e-9
        diag["qqq_rsi2"] = signal_panel["qqq_rsi2"].reindex(weights.index)
        diag["qqq_rsi5"] = signal_panel["qqq_rsi5"].reindex(weights.index)
        diag["qqq_ret_1d"] = signal_panel["qqq_ret_1d"].reindex(weights.index)
        diag["qqq_ret_3d"] = signal_panel["qqq_ret_3d"].reindex(weights.index)
        diag["qqq_ret_5d"] = signal_panel["qqq_ret_5d"].reindex(weights.index)
        diag["qqq_trend"] = signal_panel["qqq_trend"].reindex(weights.index).fillna(False).astype(bool)
        frames.append(diag.reset_index(names="timestamp"))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _readiness_summary(summary: pd.DataFrame, diagnostics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in summary.iterrows():
        candidate = row["candidate_name"]
        cand_diag = diagnostics[diagnostics["candidate_name"] == candidate]
        accounting_ok_pct = float(cand_diag["accounting_ok"].mean() * 100.0) if not cand_diag.empty else 0.0
        signal_days = float(cand_diag["signal_active"].mean() * 100.0) if not cand_diag.empty else 0.0
        positive_excess = bool(row.get("excess_cagr_vs_base_pct", 0.0) > 0.0 and row.get("information_ratio", 0.0) > 0.0)
        rows.append({
            "candidate_name": candidate,
            "research_ready": bool(accounting_ok_pct >= 99.999 and row["bars"] > 0),
            "positive_excess_alpha_candidate": positive_excess,
            "broker_ready": False,
            "promotion_eligible": False,
            "readiness_state": "equity_signal_alpha_lab_diagnostic_only",
            "accounting_ok_pct": accounting_ok_pct,
            "signal_active_days_pct": signal_days,
            "readiness_reason": "Research-only signal alpha candidate. No promotion, broker mapping, order generation, live trading, or fund book modification is approved.",
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
        "# Equity Signal Alpha Lab v1",
        "",
        "Research-only actual signal alpha comparison against Equity Core SMA175 + BIL.",
        "",
        "## Inputs",
        "",
        "```text",
        f"SPY data: {args.spy_data}",
        f"QQQ data: {args.qqq_data}",
        f"BIL data: {args.bil_data}",
        f"Equity core window: {args.equity_core_window}",
        f"Trend window: {args.trend_window}",
        f"RSI2 threshold: {args.rsi2_threshold}",
        f"RSI5 threshold: {args.rsi5_threshold}",
        "```",
        "",
        "## Candidate Signal Alpha Summary",
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
    if not 0.0 <= args.max_signal_exposure <= 1.0:
        raise ValueError("max-signal-exposure must be between 0 and 1")
    for name in ["equity_core_window", "trend_window", "compression_window", "compression_quantile_window"]:
        if int(getattr(args, name)) < 2:
            raise ValueError(f"{name} must be >= 2")

    panel = _load_panel(Path(args.spy_data), Path(args.qqq_data), Path(args.bil_data))
    prices = _price_frame(panel)
    base_weights = _build_base_weights(panel, args.equity_core_window)
    signal_panel = _build_signal_panel(panel, args)
    candidates = _apply_candidates(panel, base_weights, signal_panel, args)

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
            "complexity_flags": "baseline" if name == "BASE_EQUITY_CORE" else "signal_alpha_lab_only",
            "fund_level_compatibility": "diagnostic_only_not_promoted",
        })

    summary = pd.DataFrame(summary_rows).sort_values(["excess_cagr_vs_base_pct", "information_ratio", "cagr_pct"], ascending=[False, False, False])
    curves_df = pd.concat(curves.values(), axis=1)
    returns_df = pd.concat(returns.values(), axis=1)
    diagnostics = _build_diagnostics(candidates, signal_panel, args.accounting_tolerance)
    readiness = _readiness_summary(summary, diagnostics)

    summary.to_csv(out_dir / "equity_signal_alpha_summary.csv", index=False)
    curves_df.to_csv(out_dir / "equity_signal_alpha_candidate_curves.csv")
    returns_df.to_csv(out_dir / "equity_signal_alpha_candidate_returns.csv")
    diagnostics.to_csv(out_dir / "equity_signal_alpha_diagnostics.csv", index=False)
    readiness.to_csv(out_dir / "equity_signal_alpha_readiness_summary.csv", index=False)

    payload = {
        "research_status": "research_only_equity_signal_alpha_lab_v1",
        "readiness_state": "equity_signal_alpha_lab_diagnostic_only",
        "inputs": vars(args),
        "outputs": {
            "summary_csv": str(out_dir / "equity_signal_alpha_summary.csv"),
            "candidate_curves": str(out_dir / "equity_signal_alpha_candidate_curves.csv"),
            "candidate_returns": str(out_dir / "equity_signal_alpha_candidate_returns.csv"),
            "diagnostics": str(out_dir / "equity_signal_alpha_diagnostics.csv"),
            "readiness_summary": str(out_dir / "equity_signal_alpha_readiness_summary.csv"),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "decision": {
            "status": "signal_alpha_discovery_only_not_promoted",
            "broker_ready": False,
            "promotion_eligible": False,
            "not_approved": ["fund_target_book_change", "crypto_target_stream_change", "equity_core_replacement", "live_trading", "broker_integration", "paper_broker_execution", "order_generation", "fill_simulation", "runtime_deployment", "dashboard_integration", "dynamic_fund_allocator"],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", summary, readiness, args)

    with pd.option_context("display.max_columns", None, "display.width", 900, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY SIGNAL ALPHA LAB V1 ===")
        print("\nCandidate Summary:")
        print(summary.to_string(index=False))
        print("\nReadiness Summary:")
        print(readiness.to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
