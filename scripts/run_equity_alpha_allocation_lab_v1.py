#!/usr/bin/env python
"""Equity Allocation Alpha Lab v1.

Research-only alpha discovery lab for testing equity allocation edges against the
promoted Equity Core baseline: SPY / QQQ SMA175 with BIL as defensive/risk-off
substitute.

This script searches for alpha through composition, not only de-risking:
  - QQQ/SPY relative-strength tilts
  - top-N sector momentum baskets
  - core-plus-sector momentum blends
  - equal-weight confirmation tilts
  - defensive sector rotation when Equity Core is risk-off

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


DEFAULT_OUT = "artifacts/equity_alpha_allocation_lab_v1"
DEFAULT_SECTORS = "XLK,XLV,XLF,XLE,XLY,XLP,XLI,XLU,XLB,XLRE,XLC"
START_CAPITAL = 100_000.0
TRADING_DAYS = 252.0
OPTIONAL_BREADTH_ASSETS = ["RSP", "QQQE"]
DEFENSIVE_SECTORS = ["XLV", "XLP", "XLU"]
CANDIDATES = [
    "BASE_EQUITY_CORE",
    "QQQ_SPY_RS_TILT",
    "EQUAL_WEIGHT_CONFIRM_TILT",
    "SECTOR_MOMENTUM_TOP3",
    "SECTOR_MOMENTUM_TOP5",
    "CORE_PLUS_SECTOR_MOMENTUM_TOP3",
    "CORE_PLUS_SECTOR_MOMENTUM_TOP5",
    "SECTOR_BREADTH_WEIGHTED_TOP3",
    "DEFENSIVE_SECTOR_ROTATION_WHEN_RISK_OFF",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run Equity Allocation Alpha Lab v1 discovery candidates",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--sectors", default=DEFAULT_SECTORS)
    p.add_argument("--equity-core-window", type=int, default=175)
    p.add_argument("--rs-lookback", type=int, default=126)
    p.add_argument("--breadth-lookback", type=int, default=126)
    p.add_argument("--sector-momentum-lookback", type=int, default=126)
    p.add_argument("--sector-trend-window", type=int, default=200)
    p.add_argument("--rs-tilt-size", type=float, default=0.15)
    p.add_argument("--core-plus-sector-share", type=float, default=0.50)
    p.add_argument("--sector-min-available", type=int, default=5)
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


def _base_asset_frame(base: pd.DataFrame, sectors: dict[str, pd.Series]) -> pd.DataFrame:
    cols = ["SPY", "QQQ", "BIL"] + list(sectors.keys())
    frame = pd.DataFrame(0.0, index=base.index, columns=cols)
    frame[["SPY", "QQQ", "BIL"]] = base[["SPY", "QQQ", "BIL"]]
    return frame


def _normalize(weights: pd.DataFrame) -> pd.DataFrame:
    out = weights.copy().fillna(0.0)
    out = out.clip(lower=0.0)
    if "BIL" in out.columns:
        risky_cols = [c for c in out.columns if c != "BIL"]
        risky = out[risky_cols].sum(axis=1)
        overflow = risky > 1.0
        if overflow.any():
            out.loc[overflow, risky_cols] = out.loc[overflow, risky_cols].div(risky.loc[overflow], axis=0)
        out["BIL"] = 1.0 - out[risky_cols].sum(axis=1)
    else:
        total = out.sum(axis=1).replace(0.0, np.nan)
        out = out.div(total, axis=0).fillna(0.0)
    return out


def _build_signal_panel(
    spy: pd.Series,
    qqq: pd.Series,
    optional: dict[str, pd.Series],
    sectors: dict[str, pd.Series],
    index: pd.DatetimeIndex,
    rs_lookback: int,
    breadth_lookback: int,
    sector_trend_window: int,
    sector_mom_lookback: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = pd.DataFrame(index=index)
    panel["spy_close"] = spy.reindex(index).ffill()
    panel["qqq_close"] = qqq.reindex(index).ffill()
    panel["qqq_spy_ratio"] = panel["qqq_close"] / panel["spy_close"]
    panel["qqq_spy_rs"] = panel["qqq_spy_ratio"] / panel["qqq_spy_ratio"].shift(rs_lookback) - 1.0
    panel["qqq_spy_rs_positive"] = panel["qqq_spy_rs"] > 0.0

    if "RSP" in optional:
        rsp = optional["RSP"].reindex(index).ffill()
        panel["rsp_spy_ratio"] = rsp / panel["spy_close"]
        panel["rsp_spy_rs"] = panel["rsp_spy_ratio"] / panel["rsp_spy_ratio"].shift(breadth_lookback) - 1.0
        panel["rsp_spy_confirmed"] = panel["rsp_spy_rs"] > 0.0
    else:
        panel["rsp_spy_ratio"] = np.nan
        panel["rsp_spy_rs"] = np.nan
        panel["rsp_spy_confirmed"] = True

    if "QQQE" in optional:
        qqqe = optional["QQQE"].reindex(index).ffill()
        panel["qqqe_qqq_ratio"] = qqqe / panel["qqq_close"]
        panel["qqqe_qqq_rs"] = panel["qqqe_qqq_ratio"] / panel["qqqe_qqq_ratio"].shift(breadth_lookback) - 1.0
        panel["qqqe_qqq_confirmed"] = panel["qqqe_qqq_rs"] > 0.0
    else:
        panel["qqqe_qqq_ratio"] = np.nan
        panel["qqqe_qqq_rs"] = np.nan
        panel["qqqe_qqq_confirmed"] = True

    if sectors:
        sector_prices = pd.concat(sectors.values(), axis=1).reindex(index).ffill()
        sector_sma = sector_prices.rolling(sector_trend_window, min_periods=sector_trend_window).mean()
        sector_above = sector_prices > sector_sma
        sector_mom = sector_prices / sector_prices.shift(sector_mom_lookback) - 1.0
        panel["sector_count_available"] = len(sectors)
        panel["sector_count_above_trend"] = sector_above.sum(axis=1)
        panel["sector_participation_pct"] = sector_above.mean(axis=1)
        panel["top_sector_1"] = sector_mom.idxmax(axis=1)
        panel["top_sector_1_momentum"] = sector_mom.max(axis=1)
    else:
        sector_mom = pd.DataFrame(index=index)
        panel["sector_count_available"] = 0
        panel["sector_count_above_trend"] = 0
        panel["sector_participation_pct"] = np.nan
        panel["top_sector_1"] = ""
        panel["top_sector_1_momentum"] = np.nan

    panel["breadth_confirmed"] = panel["rsp_spy_confirmed"].fillna(False) & panel["qqqe_qqq_confirmed"].fillna(False)
    panel["narrow_leadership_flag"] = panel["qqq_spy_rs_positive"].fillna(False) & panel["qqqe_qqq_confirmed"].eq(False)
    return panel, sector_mom


def _sector_top_n(base: pd.DataFrame, sectors: dict[str, pd.Series], sector_mom: pd.DataFrame, top_n: int) -> pd.DataFrame:
    out = _base_asset_frame(base, sectors)
    sector_cols = list(sectors.keys())
    if len(sector_cols) < top_n:
        return out
    for ts in out.index:
        equity = float(base.loc[ts, ["SPY", "QQQ"]].sum())
        if equity <= 0.0:
            continue
        row = sector_mom.loc[ts, sector_cols].dropna()
        if len(row) < top_n:
            continue
        chosen = list(row.sort_values(ascending=False).head(top_n).index)
        out.loc[ts, ["SPY", "QQQ"]] = 0.0
        out.loc[ts, chosen] = equity / float(top_n)
        out.loc[ts, "BIL"] = 1.0 - equity
    return _normalize(out)


def _core_plus_sector(base: pd.DataFrame, sectors: dict[str, pd.Series], sector_mom: pd.DataFrame, top_n: int, sector_share: float) -> pd.DataFrame:
    out = _base_asset_frame(base, sectors)
    sector_cols = list(sectors.keys())
    if len(sector_cols) < top_n:
        return out
    for ts in out.index:
        equity = float(base.loc[ts, ["SPY", "QQQ"]].sum())
        if equity <= 0.0:
            continue
        row = sector_mom.loc[ts, sector_cols].dropna()
        if len(row) < top_n:
            continue
        chosen = list(row.sort_values(ascending=False).head(top_n).index)
        sector_alloc = equity * sector_share
        core_alloc = equity - sector_alloc
        base_spy = float(base.loc[ts, "SPY"])
        base_qqq = float(base.loc[ts, "QQQ"])
        base_equity = max(base_spy + base_qqq, 1e-12)
        out.loc[ts, "SPY"] = core_alloc * base_spy / base_equity
        out.loc[ts, "QQQ"] = core_alloc * base_qqq / base_equity
        out.loc[ts, chosen] = sector_alloc / float(top_n)
        out.loc[ts, "BIL"] = 1.0 - equity
    return _normalize(out)


def _apply_candidates(
    base: pd.DataFrame,
    panel: pd.DataFrame,
    sectors: dict[str, pd.Series],
    sector_mom: pd.DataFrame,
    rs_tilt_size: float,
    core_plus_sector_share: float,
    sector_min_available: int,
) -> dict[str, pd.DataFrame]:
    p = panel.reindex(base.index)
    candidates: dict[str, pd.DataFrame] = {"BASE_EQUITY_CORE": _base_asset_frame(base, sectors)}

    rs = _base_asset_frame(base, sectors)
    both_on = (base["SPY"] > 0.0) & (base["QQQ"] > 0.0)
    qqq_leads = both_on & p["qqq_spy_rs_positive"].fillna(False)
    spy_leads = both_on & ~p["qqq_spy_rs_positive"].fillna(False)
    rs.loc[qqq_leads, "SPY"] = 0.5 - rs_tilt_size
    rs.loc[qqq_leads, "QQQ"] = 0.5 + rs_tilt_size
    rs.loc[spy_leads, "SPY"] = 0.5 + rs_tilt_size
    rs.loc[spy_leads, "QQQ"] = 0.5 - rs_tilt_size
    candidates["QQQ_SPY_RS_TILT"] = _normalize(rs)

    ew = _base_asset_frame(base, sectors)
    broad_confirm = both_on & p["rsp_spy_confirmed"].fillna(False)
    narrow_confirm = both_on & p["qqqe_qqq_confirmed"].fillna(False)
    ew.loc[broad_confirm, "SPY"] = 0.5 + rs_tilt_size
    ew.loc[broad_confirm, "QQQ"] = 0.5 - rs_tilt_size
    ew.loc[narrow_confirm & ~broad_confirm, "SPY"] = 0.5 - rs_tilt_size
    ew.loc[narrow_confirm & ~broad_confirm, "QQQ"] = 0.5 + rs_tilt_size
    candidates["EQUAL_WEIGHT_CONFIRM_TILT"] = _normalize(ew)

    if len(sectors) >= sector_min_available:
        candidates["SECTOR_MOMENTUM_TOP3"] = _sector_top_n(base, sectors, sector_mom, 3)
        candidates["SECTOR_MOMENTUM_TOP5"] = _sector_top_n(base, sectors, sector_mom, 5)
        candidates["CORE_PLUS_SECTOR_MOMENTUM_TOP3"] = _core_plus_sector(base, sectors, sector_mom, 3, core_plus_sector_share)
        candidates["CORE_PLUS_SECTOR_MOMENTUM_TOP5"] = _core_plus_sector(base, sectors, sector_mom, 5, core_plus_sector_share)

        breadth_weighted = _core_plus_sector(base, sectors, sector_mom, 3, core_plus_sector_share)
        weak_sector = p["sector_participation_pct"].fillna(1.0) < 0.50
        strong_sector = p["sector_participation_pct"].fillna(0.0) >= 0.70
        more_sector = _core_plus_sector(base, sectors, sector_mom, 3, min(0.75, core_plus_sector_share + 0.25))
        less_sector = _core_plus_sector(base, sectors, sector_mom, 3, max(0.25, core_plus_sector_share - 0.25))
        breadth_weighted.loc[weak_sector] = more_sector.loc[weak_sector]
        breadth_weighted.loc[strong_sector] = less_sector.loc[strong_sector]
        candidates["SECTOR_BREADTH_WEIGHTED_TOP3"] = _normalize(breadth_weighted)

        defensive = _base_asset_frame(base, sectors)
        risk_off = base["BIL"] >= 0.999
        defensive_available = [s for s in DEFENSIVE_SECTORS if s in sectors]
        if defensive_available:
            for ts in defensive.index[risk_off]:
                row = sector_mom.loc[ts, defensive_available].dropna()
                if row.empty:
                    continue
                chosen = list(row.sort_values(ascending=False).head(min(2, len(row))).index)
                defensive.loc[ts, "BIL"] = 0.50
                defensive.loc[ts, chosen] = 0.50 / float(len(chosen))
        candidates["DEFENSIVE_SECTOR_ROTATION_WHEN_RISK_OFF"] = _normalize(defensive)
    else:
        for name in CANDIDATES:
            candidates.setdefault(name, _base_asset_frame(base, sectors))
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


def _exposure_stats(weights: pd.DataFrame, sector_cols: list[str]) -> dict[str, float]:
    equity_cols = [c for c in weights.columns if c != "BIL"]
    equity_weight = weights[equity_cols].sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
    return {
        "avg_spy_weight_pct": float(weights.get("SPY", 0.0).mean() * 100.0),
        "avg_qqq_weight_pct": float(weights.get("QQQ", 0.0).mean() * 100.0),
        "avg_sector_weight_pct": float(weights[sector_cols].sum(axis=1).mean() * 100.0) if sector_cols else 0.0,
        "avg_bil_weight_pct": float(weights.get("BIL", 0.0).mean() * 100.0),
        "avg_equity_weight_pct": float(equity_weight.mean() * 100.0),
        "time_full_equity_pct": float((equity_weight >= 0.999).mean() * 100.0),
        "time_full_risk_off_pct": float((weights.get("BIL", 0.0) >= 0.999).mean() * 100.0),
        "avg_daily_turnover_proxy_pct": float(turnover.mean() * 100.0),
        "total_turnover_proxy": float(turnover.sum()),
    }


def _build_diagnostics(candidates: dict[str, pd.DataFrame], panel: pd.DataFrame, base: pd.DataFrame, sector_cols: list[str], tol: float) -> pd.DataFrame:
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
        diag["qqq_spy_rs"] = p["qqq_spy_rs"]
        diag["breadth_confirmed"] = p["breadth_confirmed"].fillna(False).astype(bool)
        diag["narrow_leadership_flag"] = p["narrow_leadership_flag"].fillna(False).astype(bool)
        diag["sector_participation_pct"] = p["sector_participation_pct"]
        diag["sector_count_available"] = p["sector_count_available"].fillna(0).astype(int)
        diag["top_sector_1"] = p["top_sector_1"]
        diag["top_sector_1_momentum"] = p["top_sector_1_momentum"]
        diag["target_spy_weight"] = weights.get("SPY", pd.Series(0.0, index=weights.index))
        diag["target_qqq_weight"] = weights.get("QQQ", pd.Series(0.0, index=weights.index))
        diag["target_sector_weight"] = weights[sector_cols].sum(axis=1) if sector_cols else 0.0
        diag["target_bil_weight"] = weights.get("BIL", pd.Series(0.0, index=weights.index))
        diag["total_accounted_weight"] = weights.sum(axis=1)
        diag["accounting_error"] = diag["total_accounted_weight"] - 1.0
        diag["accounting_ok"] = diag["accounting_error"].abs() <= tol
        frames.append(diag.reset_index(names="timestamp"))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _readiness_summary(summary: pd.DataFrame, diagnostics: pd.DataFrame, loaded_optional: dict[str, pd.Series], loaded_sectors: dict[str, pd.Series], skipped: pd.DataFrame) -> pd.DataFrame:
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
            "readiness_state": "equity_alpha_allocation_lab_diagnostic_only",
            "accounting_ok_pct": accounting_ok_pct,
            "loaded_breadth_assets": ",".join(loaded_optional.keys()) if loaded_optional else "none",
            "loaded_sector_count": len(loaded_sectors),
            "skipped_asset_count": int(len(skipped)),
            "readiness_reason": "Research-only alpha discovery candidate. No promotion, broker mapping, order generation, live trading, or fund book modification is approved.",
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
        "# Equity Allocation Alpha Lab v1",
        "",
        "Research-only allocation-alpha discovery against Equity Core SMA175 + BIL.",
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
        f"RS lookback: {args.rs_lookback}",
        f"Breadth lookback: {args.breadth_lookback}",
        f"Sector momentum lookback: {args.sector_momentum_lookback}",
        f"RS tilt size: {args.rs_tilt_size}",
        f"Core plus sector share: {args.core_plus_sector_share}",
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

    for name in ["rs_tilt_size", "core_plus_sector_share"]:
        value = float(getattr(args, name))
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1, got {value}")
    for name in ["equity_core_window", "rs_lookback", "breadth_lookback", "sector_trend_window", "sector_momentum_lookback"]:
        if int(getattr(args, name)) < 2:
            raise ValueError(f"{name} must be >= 2")
    if args.accounting_tolerance < 0:
        raise ValueError("accounting-tolerance must be non-negative")

    sector_names = _parse_csv_list(args.sectors)
    spy = _load_close(Path(args.spy_data), "SPY")
    qqq = _load_close(Path(args.qqq_data), "QQQ")
    bil = _load_close(Path(args.bil_data), "BIL")
    loaded_optional, skipped_optional = _load_optional_assets(OPTIONAL_BREADTH_ASSETS, Path(args.data_dir), args.breadth_lookback, "breadth")
    loaded_sectors, skipped_sectors = _load_optional_assets(sector_names, Path(args.data_dir), args.sector_momentum_lookback, "sector")
    skipped = pd.concat([skipped_optional, skipped_sectors], ignore_index=True) if not skipped_optional.empty or not skipped_sectors.empty else pd.DataFrame(columns=["asset", "asset_type", "path", "reason"])

    base_weights = _build_base_weights(spy, qqq, bil, args.equity_core_window)
    price_series = {"SPY": spy, "QQQ": qqq, "BIL": bil, **loaded_sectors}
    prices = pd.concat(price_series.values(), axis=1).reindex(base_weights.index).ffill().dropna(subset=["SPY", "QQQ", "BIL"])
    base_weights = base_weights.reindex(prices.index).dropna()
    panel, sector_mom = _build_signal_panel(spy, qqq, loaded_optional, loaded_sectors, prices.index, args.rs_lookback, args.breadth_lookback, args.sector_trend_window, args.sector_momentum_lookback)

    candidates = _apply_candidates(base_weights, panel, loaded_sectors, sector_mom, args.rs_tilt_size, args.core_plus_sector_share, args.sector_min_available)
    sector_cols = list(loaded_sectors.keys())

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
            **_exposure_stats(weights, sector_cols),
            "complexity_flags": "baseline" if name == "BASE_EQUITY_CORE" else "allocation_alpha_lab_only",
            "fund_level_compatibility": "diagnostic_only_not_promoted",
        })

    summary = pd.DataFrame(summary_rows)
    base_row = summary[summary["candidate_name"] == "BASE_EQUITY_CORE"].iloc[0]
    for col in ["cagr_pct", "max_drawdown_pct", "sharpe", "sortino", "calmar", "worst_90d_return_pct", "worst_180d_return_pct", "avg_daily_turnover_proxy_pct"]:
        summary[f"delta_vs_base_{col}"] = summary[col] - float(base_row[col])
    summary = summary.sort_values(["calmar", "sharpe", "cagr_pct"], ascending=[False, False, False])

    curves_df = pd.concat(curves.values(), axis=1)
    diagnostics = _build_diagnostics(candidates, panel, base_weights, sector_cols, args.accounting_tolerance)
    readiness = _readiness_summary(summary, diagnostics, loaded_optional, loaded_sectors, skipped)

    summary.to_csv(out_dir / "equity_alpha_lab_summary.csv", index=False)
    curves_df.to_csv(out_dir / "equity_alpha_candidate_curves.csv")
    diagnostics.to_csv(out_dir / "equity_alpha_diagnostics.csv", index=False)
    readiness.to_csv(out_dir / "equity_alpha_readiness_summary.csv", index=False)
    skipped.to_csv(out_dir / "skipped_assets.csv", index=False)

    payload = {
        "research_status": "research_only_equity_alpha_allocation_lab_v1",
        "readiness_state": "equity_alpha_allocation_lab_diagnostic_only",
        "inputs": vars(args),
        "loaded_breadth_assets": list(loaded_optional.keys()),
        "loaded_sectors": list(loaded_sectors.keys()),
        "outputs": {
            "equity_alpha_lab_summary": str(out_dir / "equity_alpha_lab_summary.csv"),
            "equity_alpha_candidate_curves": str(out_dir / "equity_alpha_candidate_curves.csv"),
            "equity_alpha_diagnostics": str(out_dir / "equity_alpha_diagnostics.csv"),
            "equity_alpha_readiness_summary": str(out_dir / "equity_alpha_readiness_summary.csv"),
            "summary_md": str(out_dir / "summary.md"),
            "summary_json": str(out_dir / "summary.json"),
        },
        "decision": {
            "status": "alpha_discovery_lab_only_not_promoted",
            "broker_ready": False,
            "promotion_eligible": False,
            "not_approved": ["fund_target_book_change", "crypto_target_stream_change", "equity_core_replacement", "live_trading", "broker_integration", "paper_broker_execution", "order_generation", "fill_simulation", "runtime_deployment", "dashboard_integration", "dynamic_fund_allocator"],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", summary, readiness, skipped, args)

    with pd.option_context("display.max_columns", None, "display.width", 720, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY ALLOCATION ALPHA LAB V1 ===")
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
