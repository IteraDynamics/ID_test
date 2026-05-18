#!/usr/bin/env python
"""Equity Alpha Lab v1.

Research-only lab for testing breadth, concentration, equal-weight confirmation,
and sector participation diagnostics against the promoted Equity Core baseline:
SPY / QQQ SMA175 with BIL as defensive/risk-off substitute.

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


DEFAULT_OUT = "artifacts/equity_alpha_lab_v1"
DEFAULT_SECTORS = "XLK,XLV,XLF,XLE,XLY,XLP,XLI,XLU,XLB,XLRE,XLC"
START_CAPITAL = 100_000.0
TRADING_DAYS = 252.0
REQUIRED_ASSETS = ["SPY", "QQQ", "BIL"]
OPTIONAL_BREADTH_ASSETS = ["RSP", "QQQE"]
CANDIDATES = [
    "BASE_EQUITY_CORE",
    "BREADTH_CONFIRMATION",
    "NARROW_LEADERSHIP_REDUCE",
    "BROAD_MARKET_CONFIRM_ALLOW",
    "SECTOR_PARTICIPATION_FILTER",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run Equity Alpha Lab v1 breadth/concentration diagnostics",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--sectors", default=DEFAULT_SECTORS)
    p.add_argument("--equity-core-window", type=int, default=175)
    p.add_argument("--breadth-window", type=int, default=126)
    p.add_argument("--sector-window", type=int, default=200)
    p.add_argument("--reduce-scale", type=float, default=0.75)
    p.add_argument("--narrow-qqq-scale", type=float, default=0.50)
    p.add_argument("--sector-min-available", type=int, default=3)
    p.add_argument("--sector-confirm-threshold", type=float, default=0.50)
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


def _load_optional_assets(assets: Iterable[str], data_dir: Path, min_bars: int, asset_type: str) -> tuple[dict[str, pd.Series], pd.DataFrame]:
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
        except Exception as exc:  # pragma: no cover - defensive reporting path
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


def _build_signal_panel(
    spy: pd.Series,
    qqq: pd.Series,
    optional: dict[str, pd.Series],
    sectors: dict[str, pd.Series],
    index: pd.DatetimeIndex,
    breadth_window: int,
    sector_window: int,
) -> pd.DataFrame:
    panel = pd.DataFrame(index=index)
    panel["spy_close"] = spy.reindex(index).ffill()
    panel["qqq_close"] = qqq.reindex(index).ffill()

    if "RSP" in optional:
        rsp = optional["RSP"].reindex(index).ffill()
        panel["rsp_close"] = rsp
        panel["rsp_spy_ratio"] = rsp / panel["spy_close"]
        ratio_sma = panel["rsp_spy_ratio"].rolling(breadth_window, min_periods=breadth_window).mean()
        panel["rsp_spy_confirmed"] = panel["rsp_spy_ratio"] > ratio_sma
    else:
        panel["rsp_close"] = np.nan
        panel["rsp_spy_ratio"] = np.nan
        panel["rsp_spy_confirmed"] = True

    if "QQQE" in optional:
        qqqe = optional["QQQE"].reindex(index).ffill()
        panel["qqqe_close"] = qqqe
        panel["qqqe_qqq_ratio"] = qqqe / panel["qqq_close"]
        ratio_sma = panel["qqqe_qqq_ratio"].rolling(breadth_window, min_periods=breadth_window).mean()
        panel["qqqe_qqq_confirmed"] = panel["qqqe_qqq_ratio"] > ratio_sma
    else:
        panel["qqqe_close"] = np.nan
        panel["qqqe_qqq_ratio"] = np.nan
        panel["qqqe_qqq_confirmed"] = True

    sector_count_available = len(sectors)
    if sectors:
        sector_prices = pd.concat(sectors.values(), axis=1).reindex(index).ffill()
        sector_sma = sector_prices.rolling(sector_window, min_periods=sector_window).mean()
        sector_above = sector_prices > sector_sma
        panel["sector_count_available"] = sector_count_available
        panel["sector_count_above_trend"] = sector_above.sum(axis=1)
        panel["sector_participation_pct"] = sector_above.mean(axis=1)
    else:
        panel["sector_count_available"] = 0
        panel["sector_count_above_trend"] = 0
        panel["sector_participation_pct"] = np.nan

    panel["breadth_confirmed"] = panel["rsp_spy_confirmed"].fillna(False) & panel["qqqe_qqq_confirmed"].fillna(False)
    panel["broad_market_confirmed"] = panel["breadth_confirmed"]
    if sectors:
        panel["broad_market_confirmed"] = panel["broad_market_confirmed"] & (panel["sector_participation_pct"] >= 0.50)
    panel["narrow_leadership_flag"] = panel["qqqe_qqq_confirmed"].eq(False)
    panel["sector_participation_confirmed"] = panel["sector_participation_pct"] >= 0.50
    return panel


def _renormalize_to_bil(weights: pd.DataFrame) -> pd.DataFrame:
    out = weights.copy()
    out["SPY"] = out["SPY"].clip(lower=0.0, upper=1.0)
    out["QQQ"] = out["QQQ"].clip(lower=0.0, upper=1.0)
    active = out["SPY"] + out["QQQ"]
    overflow = active > 1.0
    if overflow.any():
        out.loc[overflow, ["SPY", "QQQ"]] = out.loc[overflow, ["SPY", "QQQ"]].div(active.loc[overflow], axis=0)
    out["BIL"] = 1.0 - out["SPY"] - out["QQQ"]
    return out[["SPY", "QQQ", "BIL"]]


def _apply_candidates(
    base: pd.DataFrame,
    panel: pd.DataFrame,
    reduce_scale: float,
    narrow_qqq_scale: float,
    sector_min_available: int,
    sector_confirm_threshold: float,
) -> dict[str, pd.DataFrame]:
    p = panel.reindex(base.index)
    candidates: dict[str, pd.DataFrame] = {"BASE_EQUITY_CORE": base.copy()}

    breadth = base.copy()
    weak_breadth = p["breadth_confirmed"].eq(False)
    breadth.loc[weak_breadth, ["SPY", "QQQ"]] *= reduce_scale
    candidates["BREADTH_CONFIRMATION"] = _renormalize_to_bil(breadth)

    narrow = base.copy()
    narrow_flag = p["narrow_leadership_flag"].fillna(False) & (base["QQQ"] > 0.0)
    narrow.loc[narrow_flag, "QQQ"] *= narrow_qqq_scale
    candidates["NARROW_LEADERSHIP_REDUCE"] = _renormalize_to_bil(narrow)

    broad = base.copy()
    weak_broad = p["broad_market_confirmed"].eq(False)
    broad.loc[weak_broad, ["SPY", "QQQ"]] *= reduce_scale
    candidates["BROAD_MARKET_CONFIRM_ALLOW"] = _renormalize_to_bil(broad)

    sector = base.copy()
    usable_sector = p["sector_count_available"].fillna(0) >= sector_min_available
    weak_sector = usable_sector & (p["sector_participation_pct"] < sector_confirm_threshold)
    sector.loc[weak_sector, ["SPY", "QQQ"]] *= reduce_scale
    candidates["SECTOR_PARTICIPATION_FILTER"] = _renormalize_to_bil(sector)
    return candidates


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
        return {
            "total_return_pct": 0.0,
            "cagr_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "calmar": 0.0,
            "ann_vol_pct": 0.0,
            "worst_90d_return_pct": 0.0,
            "worst_180d_return_pct": 0.0,
            "max_time_underwater_days": 0.0,
        }
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
    equity_weight = weights["SPY"] + weights["QQQ"]
    turnover = weights[["SPY", "QQQ", "BIL"]].diff().abs().sum(axis=1).fillna(0.0)
    return {
        "avg_spy_weight_pct": float(weights["SPY"].mean() * 100.0),
        "avg_qqq_weight_pct": float(weights["QQQ"].mean() * 100.0),
        "avg_bil_weight_pct": float(weights["BIL"].mean() * 100.0),
        "avg_equity_weight_pct": float(equity_weight.mean() * 100.0),
        "time_full_equity_pct": float((equity_weight >= 0.999).mean() * 100.0),
        "time_full_risk_off_pct": float((weights["BIL"] >= 0.999).mean() * 100.0),
        "avg_daily_turnover_proxy_pct": float(turnover.mean() * 100.0),
        "total_turnover_proxy": float(turnover.sum()),
    }


def _build_diagnostics(candidates: dict[str, pd.DataFrame], panel: pd.DataFrame, base: pd.DataFrame, tol: float) -> pd.DataFrame:
    frames = []
    spy_signal = base["SPY"] > 0.0
    qqq_signal = base["QQQ"] > 0.0
    for name, weights in candidates.items():
        p = panel.reindex(weights.index)
        diag = pd.DataFrame(index=weights.index)
        diag["candidate_name"] = name
        diag["spy_signal"] = spy_signal.reindex(weights.index).fillna(False).astype(bool)
        diag["qqq_signal"] = qqq_signal.reindex(weights.index).fillna(False).astype(bool)
        diag["rsp_spy_ratio"] = p["rsp_spy_ratio"]
        diag["qqqe_qqq_ratio"] = p["qqqe_qqq_ratio"]
        diag["breadth_confirmed"] = p["breadth_confirmed"].fillna(False).astype(bool)
        diag["narrow_leadership_flag"] = p["narrow_leadership_flag"].fillna(False).astype(bool)
        diag["sector_participation_pct"] = p["sector_participation_pct"]
        diag["sector_count_available"] = p["sector_count_available"].fillna(0).astype(int)
        diag["target_spy_weight"] = weights["SPY"]
        diag["target_qqq_weight"] = weights["QQQ"]
        diag["target_bil_weight"] = weights["BIL"]
        diag["total_accounted_weight"] = weights[["SPY", "QQQ", "BIL"]].sum(axis=1)
        diag["accounting_error"] = diag["total_accounted_weight"] - 1.0
        diag["accounting_ok"] = diag["accounting_error"].abs() <= tol
        frames.append(diag.reset_index(names="timestamp"))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _readiness_summary(
    summary: pd.DataFrame,
    diagnostics: pd.DataFrame,
    loaded_optional: dict[str, pd.Series],
    loaded_sectors: dict[str, pd.Series],
    skipped: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for _, row in summary.iterrows():
        candidate = row["candidate_name"]
        cand_diag = diagnostics[diagnostics["candidate_name"] == candidate]
        accounting_ok_pct = float(cand_diag["accounting_ok"].mean() * 100.0) if not cand_diag.empty else 0.0
        rows.append(
            {
                "candidate_name": candidate,
                "research_ready": bool(accounting_ok_pct >= 99.999 and row["bars"] > 0),
                "broker_ready": False,
                "promotion_eligible": False,
                "readiness_state": "equity_alpha_lab_diagnostic_only",
                "accounting_ok_pct": accounting_ok_pct,
                "loaded_breadth_assets": ",".join(loaded_optional.keys()) if loaded_optional else "none",
                "loaded_sector_count": len(loaded_sectors),
                "skipped_asset_count": int(len(skipped)),
                "readiness_reason": "Research-only diagnostic candidate. No promotion, broker mapping, order generation, live trading, or fund book modification is approved.",
            }
        )
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


def _write_summary_md(
    path: Path,
    summary: pd.DataFrame,
    readiness: pd.DataFrame,
    skipped: pd.DataFrame,
    args: argparse.Namespace,
) -> None:
    lines = [
        "# Equity Alpha Lab v1",
        "",
        "Research-only breadth, concentration, equal-weight confirmation, and sector participation diagnostics against Equity Core SMA175 + BIL.",
        "",
        "## Inputs",
        "",
        "```text",
        f"SPY data: {args.spy_data}",
        f"QQQ data: {args.qqq_data}",
        f"BIL data: {args.bil_data}",
        f"Data dir: {args.data_dir}",
        f"Sectors: {args.sectors}",
        f"Equity core window: {args.equity_core_window}",
        f"Breadth window: {args.breadth_window}",
        f"Sector window: {args.sector_window}",
        f"Reduce scale: {args.reduce_scale}",
        f"Narrow QQQ scale: {args.narrow_qqq_scale}",
        "```",
        "",
        "## Candidate Performance Summary",
        "",
        _md_table(summary, max_rows=80),
        "",
        "## Readiness Summary",
        "",
        _md_table(readiness, max_rows=80),
        "",
        "## Skipped Optional Assets",
        "",
        _md_table(skipped, max_rows=40),
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

    for name in ["reduce_scale", "narrow_qqq_scale", "sector_confirm_threshold"]:
        value = float(getattr(args, name))
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1, got {value}")
    if args.equity_core_window < 2 or args.breadth_window < 2 or args.sector_window < 2:
        raise ValueError("window values must be >= 2")
    if args.accounting_tolerance < 0:
        raise ValueError("accounting-tolerance must be non-negative")

    sectors = _parse_csv_list(args.sectors)
    spy = _load_close(Path(args.spy_data), "SPY")
    qqq = _load_close(Path(args.qqq_data), "QQQ")
    bil = _load_close(Path(args.bil_data), "BIL")

    loaded_optional, skipped_optional = _load_optional_assets(OPTIONAL_BREADTH_ASSETS, Path(args.data_dir), args.breadth_window, "breadth")
    loaded_sectors, skipped_sectors = _load_optional_assets(sectors, Path(args.data_dir), args.sector_window, "sector")
    skipped = pd.concat([skipped_optional, skipped_sectors], ignore_index=True) if not skipped_optional.empty or not skipped_sectors.empty else pd.DataFrame(columns=["asset", "asset_type", "path", "reason"])

    base_weights = _build_base_weights(spy, qqq, bil, args.equity_core_window)
    prices = pd.concat([spy.rename("SPY"), qqq.rename("QQQ"), bil.rename("BIL")], axis=1).dropna().reindex(base_weights.index).dropna()
    base_weights = base_weights.reindex(prices.index).dropna()
    panel = _build_signal_panel(spy, qqq, loaded_optional, loaded_sectors, prices.index, args.breadth_window, args.sector_window)

    candidates = _apply_candidates(
        base=base_weights,
        panel=panel,
        reduce_scale=args.reduce_scale,
        narrow_qqq_scale=args.narrow_qqq_scale,
        sector_min_available=args.sector_min_available,
        sector_confirm_threshold=args.sector_confirm_threshold,
    )

    curves: dict[str, pd.Series] = {}
    summary_rows: list[dict[str, Any]] = []
    for name in CANDIDATES:
        weights = candidates[name]
        curve, _ = _curve_from_weights(prices, weights, args.capital)
        curve.name = name
        curves[name] = curve
        clean = curve.dropna()
        base_perf = {
            "candidate_name": name,
            "start": str(clean.index[0]) if len(clean) else "n/a",
            "end": str(clean.index[-1]) if len(clean) else "n/a",
            "bars": int(len(clean)),
            **_perf(clean),
            **_exposure_stats(weights),
            "complexity_flags": "baseline" if name == "BASE_EQUITY_CORE" else "overlay_lab_only",
            "fund_level_compatibility": "diagnostic_only_not_promoted",
        }
        summary_rows.append(base_perf)

    summary = pd.DataFrame(summary_rows)
    base_row = summary[summary["candidate_name"] == "BASE_EQUITY_CORE"].iloc[0]
    for col in ["cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar", "worst_90d_return_pct", "worst_180d_return_pct", "avg_daily_turnover_proxy_pct"]:
        summary[f"delta_vs_base_{col}"] = summary[col] - float(base_row[col])

    curves_df = pd.concat(curves.values(), axis=1)
    diagnostics = _build_diagnostics(candidates, panel, base_weights, args.accounting_tolerance)
    readiness = _readiness_summary(summary, diagnostics, loaded_optional, loaded_sectors, skipped)

    summary.to_csv(out_dir / "equity_alpha_lab_summary.csv", index=False)
    curves_df.to_csv(out_dir / "equity_alpha_candidate_curves.csv")
    diagnostics.to_csv(out_dir / "equity_alpha_diagnostics.csv", index=False)
    readiness.to_csv(out_dir / "equity_alpha_readiness_summary.csv", index=False)
    skipped.to_csv(out_dir / "skipped_assets.csv", index=False)

    payload = {
        "research_status": "research_only_equity_alpha_lab_v1",
        "readiness_state": "equity_alpha_lab_diagnostic_only",
        "inputs": {
            "spy_data": args.spy_data,
            "qqq_data": args.qqq_data,
            "bil_data": args.bil_data,
            "data_dir": args.data_dir,
            "sectors": sectors,
            "loaded_breadth_assets": list(loaded_optional.keys()),
            "loaded_sectors": list(loaded_sectors.keys()),
            "equity_core_window": args.equity_core_window,
            "breadth_window": args.breadth_window,
            "sector_window": args.sector_window,
            "reduce_scale": args.reduce_scale,
            "narrow_qqq_scale": args.narrow_qqq_scale,
            "sector_confirm_threshold": args.sector_confirm_threshold,
        },
        "outputs": {
            "equity_alpha_lab_summary": str(out_dir / "equity_alpha_lab_summary.csv"),
            "equity_alpha_candidate_curves": str(out_dir / "equity_alpha_candidate_curves.csv"),
            "equity_alpha_diagnostics": str(out_dir / "equity_alpha_diagnostics.csv"),
            "equity_alpha_readiness_summary": str(out_dir / "equity_alpha_readiness_summary.csv"),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "decision": {
            "status": "diagnostic_lab_only_not_promoted",
            "broker_ready": False,
            "promotion_eligible": False,
            "not_approved": [
                "fund_target_book_change",
                "crypto_target_stream_change",
                "equity_core_replacement",
                "live_trading",
                "broker_integration",
                "paper_broker_execution",
                "order_generation",
                "fill_simulation",
                "runtime_deployment",
                "dashboard_integration",
                "dynamic_fund_allocator",
            ],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", summary, readiness, skipped, args)

    with pd.option_context("display.max_columns", None, "display.width", 520, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY ALPHA LAB V1 ===")
        print(f"Loaded breadth assets: {', '.join(loaded_optional.keys()) if loaded_optional else 'none'}")
        print(f"Loaded sectors ({len(loaded_sectors)}): {', '.join(loaded_sectors.keys()) if loaded_sectors else 'none'}")
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
