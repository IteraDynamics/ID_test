#!/usr/bin/env python
"""Equity Excess Alpha Lab v1.

Research-only excess-return alpha discovery against the promoted Equity Core
baseline: SPY / QQQ SMA175 with BIL as defensive/risk-off substitute.

Unlike the universe allocation lab, this script is explicitly focused on alpha
metrics versus Equity Core:
  - excess CAGR / total return
  - active return
  - tracking error
  - information ratio
  - daily and monthly win rate versus base
  - up/down capture versus base

The lab tests standalone alpha sleeves and no-leverage core-plus-alpha sleeves.
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


DEFAULT_OUT = "artifacts/equity_excess_alpha_lab_v1"
DEFAULT_UNIVERSE = "SPY,QQQ,IWM,MDY,IJR,VTV,VUG,IWD,IWF,QUAL,MTUM,USMV,SPLV,EFA,EEM,VEA,VWO,SMH,IGV,XBI,XLV,XLP,XLU,VIG,SCHD"
DEFAULT_GROWTH = "QQQ,VUG,IWF,SMH,IGV,XLK"
DEFAULT_HIGH_BETA = "QQQ,IWM,SMH,IGV,XBI,EEM"
START_CAPITAL = 100_000.0
TRADING_DAYS = 252.0
CANDIDATES = [
    "BASE_EQUITY_CORE",
    "ALPHA_TOP1_MOMENTUM",
    "ALPHA_TOP2_MOMENTUM",
    "ALPHA_TOP3_MOMENTUM",
    "ALPHA_TOP1_RISK_ADJ_MOMENTUM",
    "ALPHA_TOP2_RISK_ADJ_MOMENTUM",
    "ALPHA_TOP3_RISK_ADJ_MOMENTUM",
    "ALPHA_GROWTH_TOP2_MOMENTUM",
    "ALPHA_HIGH_BETA_TOP2_MOMENTUM",
    "CORE_80_ALPHA20_TOP1_MOMENTUM",
    "CORE_80_ALPHA20_TOP2_MOMENTUM",
    "CORE_80_ALPHA20_RISK_ADJ_TOP2",
    "CORE_70_ALPHA30_TOP2_MOMENTUM",
    "CORE_70_ALPHA30_RISK_ADJ_TOP2",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run equity excess alpha discovery candidates",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--universe", default=DEFAULT_UNIVERSE)
    p.add_argument("--growth-universe", default=DEFAULT_GROWTH)
    p.add_argument("--high-beta-universe", default=DEFAULT_HIGH_BETA)
    p.add_argument("--equity-core-window", type=int, default=175)
    p.add_argument("--momentum-lookback", type=int, default=126)
    p.add_argument("--trend-window", type=int, default=200)
    p.add_argument("--vol-lookback", type=int, default=63)
    p.add_argument("--min-assets", type=int, default=2)
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


def _standalone_alpha(base: pd.DataFrame, prices: pd.DataFrame, score: pd.DataFrame, trend: pd.DataFrame, assets: list[str], top_n: int) -> pd.DataFrame:
    out = _base_frame(base, assets)
    out.loc[:, :] = 0.0
    usable = [a for a in assets if a in prices.columns]
    if len(usable) < top_n:
        out["BIL"] = 1.0
        return out
    for ts in out.index:
        row = score.loc[ts, usable].dropna()
        if trend is not None and not row.empty:
            trend_row = trend.loc[ts, row.index].fillna(False)
            row = row[trend_row]
        if len(row) < top_n:
            out.loc[ts, "BIL"] = 1.0
            continue
        chosen = list(row.sort_values(ascending=False).head(top_n).index)
        out.loc[ts, chosen] = 1.0 / float(top_n)
        out.loc[ts, "BIL"] = 0.0
    return _normalize(out)


def _core_plus_alpha(base: pd.DataFrame, prices: pd.DataFrame, score: pd.DataFrame, trend: pd.DataFrame, assets: list[str], top_n: int, alpha_share: float) -> pd.DataFrame:
    out = _base_frame(base, assets)
    usable = [a for a in assets if a in prices.columns]
    if len(usable) < top_n:
        return out
    for ts in out.index:
        base_equity = float(base.loc[ts, ["SPY", "QQQ"]].sum())
        alpha_budget = min(alpha_share, base_equity)
        if alpha_budget <= 0.0:
            continue
        row = score.loc[ts, usable].dropna()
        if trend is not None and not row.empty:
            trend_row = trend.loc[ts, row.index].fillna(False)
            row = row[trend_row]
        if len(row) < top_n:
            continue
        chosen = list(row.sort_values(ascending=False).head(top_n).index)
        scale = max(base_equity - alpha_budget, 0.0) / max(base_equity, 1e-12)
        out.loc[ts, "SPY"] = float(base.loc[ts, "SPY"]) * scale
        out.loc[ts, "QQQ"] = float(base.loc[ts, "QQQ"]) * scale
        out.loc[ts, chosen] = alpha_budget / float(top_n)
        out.loc[ts, "BIL"] = 1.0 - out.loc[ts, [c for c in out.columns if c != "BIL"]].sum()
    return _normalize(out)


def _apply_candidates(base: pd.DataFrame, prices: pd.DataFrame, momentum: pd.DataFrame, risk_adj: pd.DataFrame, trend: pd.DataFrame, universe: list[str], growth: list[str], high_beta: list[str], min_assets: int) -> dict[str, pd.DataFrame]:
    candidates: dict[str, pd.DataFrame] = {"BASE_EQUITY_CORE": _base_frame(base, universe)}
    loaded_universe = [a for a in universe if a in prices.columns]
    loaded_growth = [a for a in growth if a in prices.columns]
    loaded_high_beta = [a for a in high_beta if a in prices.columns]

    if len(loaded_universe) >= min_assets:
        candidates["ALPHA_TOP1_MOMENTUM"] = _standalone_alpha(base, prices, momentum, trend, loaded_universe, 1)
        candidates["ALPHA_TOP2_MOMENTUM"] = _standalone_alpha(base, prices, momentum, trend, loaded_universe, 2)
        candidates["ALPHA_TOP3_MOMENTUM"] = _standalone_alpha(base, prices, momentum, trend, loaded_universe, 3)
        candidates["ALPHA_TOP1_RISK_ADJ_MOMENTUM"] = _standalone_alpha(base, prices, risk_adj, trend, loaded_universe, 1)
        candidates["ALPHA_TOP2_RISK_ADJ_MOMENTUM"] = _standalone_alpha(base, prices, risk_adj, trend, loaded_universe, 2)
        candidates["ALPHA_TOP3_RISK_ADJ_MOMENTUM"] = _standalone_alpha(base, prices, risk_adj, trend, loaded_universe, 3)
        candidates["CORE_80_ALPHA20_TOP1_MOMENTUM"] = _core_plus_alpha(base, prices, momentum, trend, loaded_universe, 1, 0.20)
        candidates["CORE_80_ALPHA20_TOP2_MOMENTUM"] = _core_plus_alpha(base, prices, momentum, trend, loaded_universe, 2, 0.20)
        candidates["CORE_80_ALPHA20_RISK_ADJ_TOP2"] = _core_plus_alpha(base, prices, risk_adj, trend, loaded_universe, 2, 0.20)
        candidates["CORE_70_ALPHA30_TOP2_MOMENTUM"] = _core_plus_alpha(base, prices, momentum, trend, loaded_universe, 2, 0.30)
        candidates["CORE_70_ALPHA30_RISK_ADJ_TOP2"] = _core_plus_alpha(base, prices, risk_adj, trend, loaded_universe, 2, 0.30)
    if len(loaded_growth) >= 2:
        candidates["ALPHA_GROWTH_TOP2_MOMENTUM"] = _standalone_alpha(base, prices, momentum, trend, loaded_growth, 2)
    if len(loaded_high_beta) >= 2:
        candidates["ALPHA_HIGH_BETA_TOP2_MOMENTUM"] = _standalone_alpha(base, prices, momentum, trend, loaded_high_beta, 2)

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
    top_mom = momentum.apply(lambda row: row.dropna().idxmax() if row.notna().any() else "", axis=1)
    top_risk = risk_adj.apply(lambda row: row.dropna().idxmax() if row.notna().any() else "", axis=1)
    for name, weights in candidates.items():
        diag = pd.DataFrame(index=weights.index)
        diag["candidate_name"] = name
        diag["target_spy_weight"] = weights.get("SPY", pd.Series(0.0, index=weights.index))
        diag["target_qqq_weight"] = weights.get("QQQ", pd.Series(0.0, index=weights.index))
        diag["target_bil_weight"] = weights.get("BIL", pd.Series(0.0, index=weights.index))
        diag["target_non_core_weight"] = weights[[c for c in weights.columns if c not in ["SPY", "QQQ", "BIL"]]].sum(axis=1)
        diag["top_momentum_asset"] = top_mom.reindex(weights.index)
        diag["top_risk_adjusted_asset"] = top_risk.reindex(weights.index)
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
        positive_excess = bool(row.get("excess_cagr_vs_base_pct", 0.0) > 0.0 and row.get("information_ratio", 0.0) > 0.0)
        rows.append({
            "candidate_name": candidate,
            "research_ready": bool(accounting_ok_pct >= 99.999 and row["bars"] > 0),
            "positive_excess_alpha_candidate": positive_excess,
            "broker_ready": False,
            "promotion_eligible": False,
            "readiness_state": "equity_excess_alpha_lab_diagnostic_only",
            "accounting_ok_pct": accounting_ok_pct,
            "loaded_asset_count": len(loaded_assets),
            "loaded_assets": ",".join(loaded_assets),
            "skipped_asset_count": int(len(skipped)),
            "readiness_reason": "Research-only excess alpha candidate. No promotion, broker mapping, order generation, live trading, or fund book modification is approved.",
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
        "# Equity Excess Alpha Lab v1",
        "",
        "Research-only excess alpha discovery against Equity Core SMA175 + BIL.",
        "",
        "## Inputs",
        "",
        "```text",
        f"Universe: {args.universe}",
        f"Growth universe: {args.growth_universe}",
        f"High beta universe: {args.high_beta_universe}",
        f"Equity core window: {args.equity_core_window}",
        f"Momentum lookback: {args.momentum_lookback}",
        f"Trend window: {args.trend_window}",
        f"Vol lookback: {args.vol_lookback}",
        "```",
        "",
        "## Candidate Excess Alpha Summary",
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
    for name in ["equity_core_window", "momentum_lookback", "trend_window", "vol_lookback"]:
        if int(getattr(args, name)) < 2:
            raise ValueError(f"{name} must be >= 2")

    universe = _parse_csv_list(args.universe)
    growth = _parse_csv_list(args.growth_universe)
    high_beta = _parse_csv_list(args.high_beta_universe)
    required_min_bars = max(args.momentum_lookback, args.trend_window, args.vol_lookback) + 5

    spy = _load_close(Path(args.spy_data), "SPY")
    qqq = _load_close(Path(args.qqq_data), "QQQ")
    bil = _load_close(Path(args.bil_data), "BIL")
    optional_assets = [a for a in universe if a not in ["SPY", "QQQ", "BIL"]]
    loaded_optional, skipped = _load_assets(optional_assets, Path(args.data_dir), required_min_bars, "equity_excess_alpha")

    asset_series = {"SPY": spy, "QQQ": qqq, "BIL": bil, **loaded_optional}
    loaded_assets = list(asset_series.keys())
    prices = pd.concat(asset_series.values(), axis=1).sort_index().ffill().dropna(subset=["SPY", "QQQ", "BIL"])
    base_weights = _build_base_weights(spy, qqq, bil, args.equity_core_window).reindex(prices.index).dropna()
    prices = prices.reindex(base_weights.index).ffill().dropna(subset=["SPY", "QQQ", "BIL"])
    base_weights = base_weights.reindex(prices.index).dropna()

    score_prices = prices[[c for c in prices.columns if c != "BIL"]]
    momentum, trend, risk_adj = _score_panels(score_prices, args.momentum_lookback, args.trend_window, args.vol_lookback)
    candidates = _apply_candidates(base_weights, prices, momentum, risk_adj, trend, universe, growth, high_beta, args.min_assets)

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
        curve = curves[name]
        rets = returns[name]
        clean = curve.dropna()
        summary_rows.append({
            "candidate_name": name,
            "start": str(clean.index[0]) if len(clean) else "n/a",
            "end": str(clean.index[-1]) if len(clean) else "n/a",
            "bars": int(len(clean)),
            **_perf(clean),
            **_excess_metrics(rets, base_rets, clean, base_curve),
            **_exposure_stats(candidates[name]),
            "complexity_flags": "baseline" if name == "BASE_EQUITY_CORE" else "excess_alpha_lab_only",
            "fund_level_compatibility": "diagnostic_only_not_promoted",
        })

    summary = pd.DataFrame(summary_rows)
    summary = summary.sort_values(["excess_cagr_vs_base_pct", "information_ratio", "active_return_ann_pct"], ascending=[False, False, False])
    curves_df = pd.concat(curves.values(), axis=1)
    returns_df = pd.concat(returns.values(), axis=1)
    diagnostics = _build_diagnostics(candidates, momentum, risk_adj, args.accounting_tolerance)
    readiness = _readiness_summary(summary, diagnostics, loaded_assets, skipped)

    summary.to_csv(out_dir / "equity_excess_alpha_summary.csv", index=False)
    curves_df.to_csv(out_dir / "equity_excess_alpha_candidate_curves.csv")
    returns_df.to_csv(out_dir / "equity_excess_alpha_candidate_returns.csv")
    diagnostics.to_csv(out_dir / "equity_excess_alpha_diagnostics.csv", index=False)
    readiness.to_csv(out_dir / "equity_excess_alpha_readiness_summary.csv", index=False)
    skipped.to_csv(out_dir / "skipped_assets.csv", index=False)

    payload = {
        "research_status": "research_only_equity_excess_alpha_lab_v1",
        "readiness_state": "equity_excess_alpha_lab_diagnostic_only",
        "inputs": vars(args),
        "loaded_assets": loaded_assets,
        "outputs": {
            "summary_csv": str(out_dir / "equity_excess_alpha_summary.csv"),
            "candidate_curves": str(out_dir / "equity_excess_alpha_candidate_curves.csv"),
            "candidate_returns": str(out_dir / "equity_excess_alpha_candidate_returns.csv"),
            "diagnostics": str(out_dir / "equity_excess_alpha_diagnostics.csv"),
            "readiness_summary": str(out_dir / "equity_excess_alpha_readiness_summary.csv"),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "decision": {
            "status": "excess_alpha_discovery_only_not_promoted",
            "broker_ready": False,
            "promotion_eligible": False,
            "not_approved": ["fund_target_book_change", "crypto_target_stream_change", "equity_core_replacement", "live_trading", "broker_integration", "paper_broker_execution", "order_generation", "fill_simulation", "runtime_deployment", "dashboard_integration", "dynamic_fund_allocator"],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", summary, readiness, skipped, args)

    with pd.option_context("display.max_columns", None, "display.width", 900, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY EXCESS ALPHA LAB V1 ===")
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
