#!/usr/bin/env python
"""Equity Universe Alpha Lab v1.

Research-only broad equity universe alpha discovery against the promoted Equity
Core baseline: SPY / QQQ SMA175 with BIL as defensive/risk-off substitute.

This lab expands beyond SPY/QQQ and sector ETFs into size, style, factor,
international, thematic, and defensive equity ETFs when local CSV data is
available. Missing optional assets are skipped and reported.

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
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd


DEFAULT_OUT = "artifacts/equity_universe_alpha_lab_v1"
DEFAULT_UNIVERSE = "SPY,QQQ,IWM,MDY,IJR,VTV,VUG,IWD,IWF,QUAL,MTUM,USMV,SPLV,EFA,EEM,VEA,VWO,SMH,IGV,XBI,XLV,XLP,XLU,VIG,SCHD"
DEFAULT_STYLE = "SPY,QQQ,IWM,MDY,VTV,VUG,IWD,IWF,QUAL,MTUM,USMV,SPLV"
DEFAULT_DEFENSIVE = "XLV,XLP,XLU,USMV,SPLV,VIG,SCHD"
START_CAPITAL = 100_000.0
TRADING_DAYS = 252.0
CANDIDATES = [
    "BASE_EQUITY_CORE",
    "TOP3_MOMENTUM_UNIVERSE",
    "TOP5_MOMENTUM_UNIVERSE",
    "TOP3_RISK_ADJUSTED_MOMENTUM",
    "TOP5_RISK_ADJUSTED_MOMENTUM",
    "CORE_PLUS_TOP3_MOMENTUM_50",
    "CORE_PLUS_TOP5_MOMENTUM_50",
    "STYLE_ROTATION_TOP3",
    "RISK_OFF_ENHANCED_DEFENSIVE_25",
    "RISK_OFF_ENHANCED_DEFENSIVE_50",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run broad equity universe alpha discovery candidates",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--universe", default=DEFAULT_UNIVERSE)
    p.add_argument("--style-universe", default=DEFAULT_STYLE)
    p.add_argument("--defensive-universe", default=DEFAULT_DEFENSIVE)
    p.add_argument("--equity-core-window", type=int, default=175)
    p.add_argument("--momentum-lookback", type=int, default=126)
    p.add_argument("--trend-window", type=int, default=200)
    p.add_argument("--vol-lookback", type=int, default=63)
    p.add_argument("--core-plus-share", type=float, default=0.50)
    p.add_argument("--risk-off-defensive-share-25", type=float, default=0.25)
    p.add_argument("--risk-off-defensive-share-50", type=float, default=0.50)
    p.add_argument("--min-assets", type=int, default=3)
    p.add_argument("--capital", type=float, default=START_CAPITAL)
    p.add_argument("--accounting-tolerance", type=float, default=1e-6)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    return p.parse_args()


def _parse_csv_list(raw: str) -> list[str]:
    values = []
    for piece in str(raw).split(","):
        value = piece.strip().upper()
        if value:
            values.append(value)
    return list(dict.fromkeys(values))


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
    close_col = None
    for candidate in ["adj close", "adj_close", "adjusted_close", "close"]:
        if candidate in df.columns:
            close_col = candidate
            break
    if close_col is None:
        raise ValueError(f"{label} data missing close/adjusted close column; got {list(df.columns)}")
    out = df[[close_col]].rename(columns={close_col: "close"})
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=["close"])
    return out


def _load_close(path: Path, label: str) -> pd.Series:
    return _read_price_csv(path, label)["close"].rename(label.upper())


def _load_assets(assets: Iterable[str], data_dir: Path, min_bars: int, asset_type: str) -> tuple[dict[str, pd.Series], pd.DataFrame]:
    loaded: dict[str, pd.Series] = {}
    skipped: list[dict[str, Any]] = []
    for asset in assets:
        path = data_dir / f"{asset}_1D.csv"
        if not path.exists():
            skipped.append({"asset": asset, "asset_type": asset_type, "path": str(path), "reason": "missing_file"})
            continue
        try:
            close = _load_close(path, asset)
            if len(close) < min_bars:
                skipped.append({"asset": asset, "asset_type": asset_type, "path": str(path), "reason": f"insufficient_bars:{len(close)}"})
                continue
            loaded[asset] = close
        except Exception as exc:  # pragma: no cover
            skipped.append({"asset": asset, "asset_type": asset_type, "path": str(path), "reason": f"load_error:{exc}"})
    return loaded, pd.DataFrame(skipped)


def _build_base_weights(spy: pd.Series, qqq: pd.Series, bil: pd.Series, window: int) -> pd.DataFrame:
    prices = pd.concat([spy.rename("SPY"), qqq.rename("QQQ")], axis=1).dropna().sort_index()
    spy_sma = prices["SPY"].rolling(window, min_periods=window).mean()
    qqq_sma = prices["QQQ"].rolling(window, min_periods=window).mean()
    weights = pd.DataFrame(index=prices.index)
    weights["SPY"] = 0.5 * (prices["SPY"] > spy_sma).astype(float)
    weights["QQQ"] = 0.5 * (prices["QQQ"] > qqq_sma).astype(float)
    weights["BIL"] = 1.0 - weights["SPY"] - weights["QQQ"]
    bil_overlap = pd.concat([weights, bil.rename("BIL_PRICE")], axis=1).dropna().index
    return weights.reindex(bil_overlap).sort_index()


def _base_frame(base: pd.DataFrame, assets: list[str]) -> pd.DataFrame:
    cols = list(dict.fromkeys(["SPY", "QQQ", "BIL"] + assets))
    frame = pd.DataFrame(0.0, index=base.index, columns=cols)
    frame[["SPY", "QQQ", "BIL"]] = base[["SPY", "QQQ", "BIL"]]
    return frame


def _normalize(weights: pd.DataFrame) -> pd.DataFrame:
    out = weights.copy().fillna(0.0).clip(lower=0.0)
    risky_cols = [c for c in out.columns if c != "BIL"]
    risky = out[risky_cols].sum(axis=1)
    overflow = risky > 1.0
    if overflow.any():
        out.loc[overflow, risky_cols] = out.loc[overflow, risky_cols].div(risky.loc[overflow], axis=0)
    out["BIL"] = 1.0 - out[risky_cols].sum(axis=1)
    return out


def _score_panels(prices: pd.DataFrame, momentum_lookback: int, trend_window: int, vol_lookback: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    momentum = prices / prices.shift(momentum_lookback) - 1.0
    trend = prices > prices.rolling(trend_window, min_periods=trend_window).mean()
    vol = prices.pct_change(fill_method=None).rolling(vol_lookback, min_periods=vol_lookback).std(ddof=0) * math.sqrt(TRADING_DAYS)
    risk_adj = momentum / vol.replace(0.0, np.nan)
    return momentum, trend, risk_adj


def _top_n_weights(base: pd.DataFrame, prices: pd.DataFrame, score: pd.DataFrame, trend: pd.DataFrame, assets: list[str], top_n: int) -> pd.DataFrame:
    out = _base_frame(base, assets)
    usable = [a for a in assets if a in prices.columns]
    if len(usable) < top_n:
        return out
    for ts in out.index:
        equity = float(base.loc[ts, ["SPY", "QQQ"]].sum())
        if equity <= 0.0:
            continue
        row = score.loc[ts, usable].dropna()
        if trend is not None:
            trend_row = trend.loc[ts, row.index].fillna(False)
            row = row[trend_row]
        if len(row) < top_n:
            continue
        chosen = list(row.sort_values(ascending=False).head(top_n).index)
        out.loc[ts, :] = 0.0
        out.loc[ts, chosen] = equity / float(top_n)
        out.loc[ts, "BIL"] = 1.0 - equity
    return _normalize(out)


def _core_plus_top_n(base: pd.DataFrame, prices: pd.DataFrame, score: pd.DataFrame, trend: pd.DataFrame, assets: list[str], top_n: int, sleeve_share: float) -> pd.DataFrame:
    out = _base_frame(base, assets)
    usable = [a for a in assets if a in prices.columns]
    if len(usable) < top_n:
        return out
    for ts in out.index:
        equity = float(base.loc[ts, ["SPY", "QQQ"]].sum())
        if equity <= 0.0:
            continue
        row = score.loc[ts, usable].dropna()
        if trend is not None:
            trend_row = trend.loc[ts, row.index].fillna(False)
            row = row[trend_row]
        if len(row) < top_n:
            continue
        chosen = list(row.sort_values(ascending=False).head(top_n).index)
        alpha_alloc = equity * sleeve_share
        core_alloc = equity - alpha_alloc
        base_spy = float(base.loc[ts, "SPY"])
        base_qqq = float(base.loc[ts, "QQQ"])
        base_equity = max(base_spy + base_qqq, 1e-12)
        out.loc[ts, :] = 0.0
        out.loc[ts, "SPY"] = core_alloc * base_spy / base_equity
        out.loc[ts, "QQQ"] = core_alloc * base_qqq / base_equity
        out.loc[ts, chosen] = alpha_alloc / float(top_n)
        out.loc[ts, "BIL"] = 1.0 - equity
    return _normalize(out)


def _risk_off_enhanced(base: pd.DataFrame, prices: pd.DataFrame, score: pd.DataFrame, trend: pd.DataFrame, defensive_assets: list[str], share: float) -> pd.DataFrame:
    assets = [a for a in defensive_assets if a in prices.columns]
    out = _base_frame(base, assets)
    if not assets:
        return out
    risk_off = base["BIL"] >= 0.999
    for ts in out.index[risk_off]:
        row = score.loc[ts, assets].dropna()
        trend_row = trend.loc[ts, row.index].fillna(False) if not row.empty else pd.Series(dtype=bool)
        row = row[trend_row]
        if row.empty:
            continue
        chosen = list(row.sort_values(ascending=False).head(min(3, len(row))).index)
        out.loc[ts, "BIL"] = 1.0 - share
        out.loc[ts, chosen] = share / float(len(chosen))
    return _normalize(out)


def _apply_candidates(base: pd.DataFrame, prices: pd.DataFrame, momentum: pd.DataFrame, risk_adj: pd.DataFrame, trend: pd.DataFrame, universe: list[str], style: list[str], defensive: list[str], core_plus_share: float, defensive_share_25: float, defensive_share_50: float, min_assets: int) -> dict[str, pd.DataFrame]:
    candidates: dict[str, pd.DataFrame] = {}
    candidates["BASE_EQUITY_CORE"] = _base_frame(base, universe)
    loaded_universe = [a for a in universe if a in prices.columns]
    loaded_style = [a for a in style if a in prices.columns]
    loaded_defensive = [a for a in defensive if a in prices.columns]

    if len(loaded_universe) >= min_assets:
        candidates["TOP3_MOMENTUM_UNIVERSE"] = _top_n_weights(base, prices, momentum, trend, loaded_universe, 3)
        candidates["TOP5_MOMENTUM_UNIVERSE"] = _top_n_weights(base, prices, momentum, trend, loaded_universe, 5)
        candidates["TOP3_RISK_ADJUSTED_MOMENTUM"] = _top_n_weights(base, prices, risk_adj, trend, loaded_universe, 3)
        candidates["TOP5_RISK_ADJUSTED_MOMENTUM"] = _top_n_weights(base, prices, risk_adj, trend, loaded_universe, 5)
        candidates["CORE_PLUS_TOP3_MOMENTUM_50"] = _core_plus_top_n(base, prices, momentum, trend, loaded_universe, 3, core_plus_share)
        candidates["CORE_PLUS_TOP5_MOMENTUM_50"] = _core_plus_top_n(base, prices, momentum, trend, loaded_universe, 5, core_plus_share)
    if len(loaded_style) >= min_assets:
        candidates["STYLE_ROTATION_TOP3"] = _top_n_weights(base, prices, momentum, trend, loaded_style, 3)
    if loaded_defensive:
        candidates["RISK_OFF_ENHANCED_DEFENSIVE_25"] = _risk_off_enhanced(base, prices, risk_adj, trend, loaded_defensive, defensive_share_25)
        candidates["RISK_OFF_ENHANCED_DEFENSIVE_50"] = _risk_off_enhanced(base, prices, risk_adj, trend, loaded_defensive, defensive_share_50)

    for name in CANDIDATES:
        candidates.setdefault(name, _base_frame(base, universe))
    return candidates


def _curve_from_weights(prices: pd.DataFrame, weights: pd.DataFrame, capital: float) -> tuple[pd.Series, pd.Series]:
    data = prices.reindex(weights.index).ffill().dropna(subset=["SPY", "QQQ", "BIL"])
    cols = [c for c in weights.columns if c in data.columns]
    w = weights.reindex(data.index).fillna(0.0)
    rets = data[cols].pct_change(fill_method=None).fillna(0.0)
    exec_w = w[cols].shift(1).fillna(0.0)
    if "BIL" in exec_w.columns:
        exec_w.loc[exec_w.index[0], "BIL"] = 1.0
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


def _exposure_stats(weights: pd.DataFrame) -> dict[str, float]:
    risky_cols = [c for c in weights.columns if c != "BIL"]
    risky = weights[risky_cols].sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
    return {
        "avg_equity_weight_pct": float(risky.mean() * 100.0),
        "avg_bil_weight_pct": float(weights.get("BIL", 0.0).mean() * 100.0),
        "time_full_equity_pct": float((risky >= 0.999).mean() * 100.0),
        "time_full_risk_off_pct": float((weights.get("BIL", 0.0) >= 0.999).mean() * 100.0),
        "avg_daily_turnover_proxy_pct": float(turnover.mean() * 100.0),
        "total_turnover_proxy": float(turnover.sum()),
        "avg_non_core_weight_pct": float(weights[[c for c in weights.columns if c not in ["SPY", "QQQ", "BIL"]]].sum(axis=1).mean() * 100.0),
    }


def _build_diagnostics(candidates: dict[str, pd.DataFrame], momentum: pd.DataFrame, risk_adj: pd.DataFrame, tol: float) -> pd.DataFrame:
    frames = []
    for name, weights in candidates.items():
        diag = pd.DataFrame(index=weights.index)
        diag["candidate_name"] = name
        diag["target_spy_weight"] = weights.get("SPY", pd.Series(0.0, index=weights.index))
        diag["target_qqq_weight"] = weights.get("QQQ", pd.Series(0.0, index=weights.index))
        diag["target_bil_weight"] = weights.get("BIL", pd.Series(0.0, index=weights.index))
        diag["target_non_core_weight"] = weights[[c for c in weights.columns if c not in ["SPY", "QQQ", "BIL"]]].sum(axis=1)
        diag["top_momentum_asset"] = momentum.reindex(weights.index).idxmax(axis=1)
        diag["top_risk_adjusted_asset"] = risk_adj.reindex(weights.index).idxmax(axis=1)
        diag["total_accounted_weight"] = weights.sum(axis=1)
        diag["accounting_error"] = diag["total_accounted_weight"] - 1.0
        diag["accounting_ok"] = diag["accounting_error"].abs() <= tol
        frames.append(diag.reset_index(names="timestamp"))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _readiness_summary(summary: pd.DataFrame, diagnostics: pd.DataFrame, loaded_assets: list[str], skipped: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in summary.iterrows():
        candidate = row["candidate_name"]
        cand_diag = diagnostics[diagnostics["candidate_name"] == candidate]
        accounting_ok_pct = float(cand_diag["accounting_ok"].mean() * 100.0) if not cand_diag.empty else 0.0
        rows.append({
            "candidate_name": candidate,
            "research_ready": bool(accounting_ok_pct >= 99.999 and row["bars"] > 0),
            "broker_ready": False,
            "promotion_eligible": False,
            "readiness_state": "equity_universe_alpha_lab_diagnostic_only",
            "accounting_ok_pct": accounting_ok_pct,
            "loaded_asset_count": len(loaded_assets),
            "loaded_assets": ",".join(loaded_assets),
            "skipped_asset_count": int(len(skipped)),
            "readiness_reason": "Research-only broad equity universe alpha candidate. No promotion, broker mapping, order generation, live trading, or fund book modification is approved.",
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


def _write_summary_md(path: Path, summary: pd.DataFrame, readiness: pd.DataFrame, skipped: pd.DataFrame, args: argparse.Namespace) -> None:
    lines = [
        "# Equity Universe Alpha Lab v1",
        "",
        "Research-only broad equity universe alpha discovery against Equity Core SMA175 + BIL.",
        "",
        "## Inputs",
        "",
        "```text",
        f"Universe: {args.universe}",
        f"Style universe: {args.style_universe}",
        f"Defensive universe: {args.defensive_universe}",
        f"Equity core window: {args.equity_core_window}",
        f"Momentum lookback: {args.momentum_lookback}",
        f"Trend window: {args.trend_window}",
        f"Vol lookback: {args.vol_lookback}",
        f"Core plus share: {args.core_plus_share}",
        "```",
        "",
        "## Candidate Performance Summary",
        "",
        _md_table(summary, max_rows=120),
        "",
        "## Readiness Summary",
        "",
        _md_table(readiness, max_rows=120),
        "",
        "## Skipped Assets",
        "",
        _md_table(skipped, max_rows=80),
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
    for name in ["core_plus_share", "risk_off_defensive_share_25", "risk_off_defensive_share_50"]:
        value = float(getattr(args, name))
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1, got {value}")
    for name in ["equity_core_window", "momentum_lookback", "trend_window", "vol_lookback"]:
        if int(getattr(args, name)) < 2:
            raise ValueError(f"{name} must be >= 2")

    universe = _parse_csv_list(args.universe)
    style = _parse_csv_list(args.style_universe)
    defensive = _parse_csv_list(args.defensive_universe)
    required_min_bars = max(args.momentum_lookback, args.trend_window, args.vol_lookback) + 5

    spy = _load_close(Path(args.spy_data), "SPY")
    qqq = _load_close(Path(args.qqq_data), "QQQ")
    bil = _load_close(Path(args.bil_data), "BIL")
    optional_assets = [a for a in universe if a not in ["SPY", "QQQ", "BIL"]]
    loaded_optional, skipped = _load_assets(optional_assets, Path(args.data_dir), required_min_bars, "equity_universe")

    asset_series = {"SPY": spy, "QQQ": qqq, "BIL": bil, **loaded_optional}
    loaded_assets = list(asset_series.keys())
    prices = pd.concat(asset_series.values(), axis=1).sort_index().ffill().dropna(subset=["SPY", "QQQ", "BIL"])
    base_weights = _build_base_weights(spy, qqq, bil, args.equity_core_window).reindex(prices.index).dropna()
    prices = prices.reindex(base_weights.index).ffill().dropna(subset=["SPY", "QQQ", "BIL"])
    base_weights = base_weights.reindex(prices.index).dropna()

    momentum, trend, risk_adj = _score_panels(prices[[c for c in prices.columns if c != "BIL"]], args.momentum_lookback, args.trend_window, args.vol_lookback)
    candidates = _apply_candidates(base_weights, prices, momentum, risk_adj, trend, universe, style, defensive, args.core_plus_share, args.risk_off_defensive_share_25, args.risk_off_defensive_share_50, args.min_assets)

    curves: dict[str, pd.Series] = {}
    summary_rows: list[dict[str, Any]] = []
    for name in CANDIDATES:
        weights = candidates[name]
        curve, _ = _curve_from_weights(prices, weights, args.capital)
        curve.name = name
        curves[name] = curve
        clean = curve.dropna()
        summary_rows.append({
            "candidate_name": name,
            "start": str(clean.index[0]) if len(clean) else "n/a",
            "end": str(clean.index[-1]) if len(clean) else "n/a",
            "bars": int(len(clean)),
            **_perf(clean),
            **_exposure_stats(weights),
            "complexity_flags": "baseline" if name == "BASE_EQUITY_CORE" else "broad_universe_alpha_lab_only",
            "fund_level_compatibility": "diagnostic_only_not_promoted",
        })

    summary = pd.DataFrame(summary_rows)
    base_row = summary[summary["candidate_name"] == "BASE_EQUITY_CORE"].iloc[0]
    for col in ["cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar", "worst_90d_return_pct", "worst_180d_return_pct", "avg_daily_turnover_proxy_pct"]:
        summary[f"delta_vs_base_{col}"] = summary[col] - float(base_row[col])
    summary = summary.sort_values(["calmar", "sharpe", "cagr_pct"], ascending=[False, False, False])

    curves_df = pd.concat(curves.values(), axis=1)
    diagnostics = _build_diagnostics(candidates, momentum, risk_adj, args.accounting_tolerance)
    readiness = _readiness_summary(summary, diagnostics, loaded_assets, skipped)

    summary.to_csv(out_dir / "equity_universe_alpha_summary.csv", index=False)
    curves_df.to_csv(out_dir / "equity_universe_alpha_candidate_curves.csv")
    diagnostics.to_csv(out_dir / "equity_universe_alpha_diagnostics.csv", index=False)
    readiness.to_csv(out_dir / "equity_universe_alpha_readiness_summary.csv", index=False)
    skipped.to_csv(out_dir / "skipped_assets.csv", index=False)

    payload = {
        "research_status": "research_only_equity_universe_alpha_lab_v1",
        "readiness_state": "equity_universe_alpha_lab_diagnostic_only",
        "inputs": vars(args),
        "loaded_assets": loaded_assets,
        "outputs": {
            "summary_csv": str(out_dir / "equity_universe_alpha_summary.csv"),
            "candidate_curves": str(out_dir / "equity_universe_alpha_candidate_curves.csv"),
            "diagnostics": str(out_dir / "equity_universe_alpha_diagnostics.csv"),
            "readiness_summary": str(out_dir / "equity_universe_alpha_readiness_summary.csv"),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "decision": {
            "status": "broad_universe_alpha_discovery_only_not_promoted",
            "broker_ready": False,
            "promotion_eligible": False,
            "not_approved": ["fund_target_book_change", "crypto_target_stream_change", "equity_core_replacement", "live_trading", "broker_integration", "paper_broker_execution", "order_generation", "fill_simulation", "runtime_deployment", "dashboard_integration", "dynamic_fund_allocator"],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", summary, readiness, skipped, args)

    with pd.option_context("display.max_columns", None, "display.width", 720, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY UNIVERSE ALPHA LAB V1 ===")
        print(f"Loaded assets ({len(loaded_assets)}): {', '.join(loaded_assets)}")
        if not skipped.empty:
            print("\nSkipped optional assets:")
            print(skipped.to_string(index=False))
        print("\nCandidate Summary:")
        print(summary.to_string(index=False))
        print("\nReadiness Summary:")
        print(readiness.to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
