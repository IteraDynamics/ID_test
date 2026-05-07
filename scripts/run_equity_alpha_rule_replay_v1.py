#!/usr/bin/env python
"""Equity Alpha Rule Replay v1.

Research-only replay that converts breadth / leadership / dispersion diagnostics
into simple overlays on Equity Core SMA175 + BIL.

No paper trading, live allocation, broker/execution, runtime, dashboard,
crypto allocator, or global allocator changes are made.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd


DEFAULT_OUT = "artifacts/equity_alpha_rule_replay_v1"
DEFAULT_SECTORS = "XLK,XLV,XLF,XLE,XLY,XLP,XLI,XLU,XLB,XLRE,XLC"
DEFAULT_OPTIONAL_ASSETS = "RSP,QQQE"
START_CAPITAL = 100_000.0
TRADING_DAYS = 252.0
WINDOWS = [
    ("FULL", "1900-01-01", "2100-01-01"),
    ("GFC_2007_2009", "2007-10-01", "2009-03-31"),
    ("COVID_2020", "2020-02-01", "2020-06-30"),
    ("BEAR_2022", "2022-01-01", "2022-12-31"),
    ("POST_2022_RECOVERY", "2023-01-01", "2024-12-31"),
    ("RECENT_2025_PLUS", "2025-01-01", "2100-01-01"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Replay breadth/leadership/correlation alpha overlays on Equity Core + BIL",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--bil-data", default="data/BIL_1D.csv")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--sectors", default=DEFAULT_SECTORS)
    p.add_argument("--optional-assets", default=DEFAULT_OPTIONAL_ASSETS)
    p.add_argument("--equity-core-window", type=int, default=175)
    p.add_argument("--sector-sma-window", type=int, default=200)
    p.add_argument("--momentum-lookback", type=int, default=126)
    p.add_argument("--correlation-lookback", type=int, default=63)
    p.add_argument("--reduce-scale", type=float, default=0.50)
    p.add_argument("--capital", type=float, default=START_CAPITAL)
    p.add_argument("--min-bars", type=int, default=252)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    return p.parse_args()


def _parse_csv_list(raw: str, upper: bool = True) -> list[str]:
    out = []
    for part in str(raw).split(","):
        value = part.strip()
        if upper:
            value = value.upper()
        if value:
            out.append(value)
    return list(dict.fromkeys(out))


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
    if "close" not in df.columns:
        raise ValueError(f"{label} data missing close column; got {list(df.columns)}")
    return df


def _load_close(path: Path, label: str) -> pd.Series:
    df = _read_price_csv(path, label)
    return pd.to_numeric(df["close"], errors="coerce").dropna().rename(label.upper())


def _load_assets(assets: Iterable[str], data_dir: Path, min_bars: int, asset_type: str) -> tuple[dict[str, pd.Series], pd.DataFrame]:
    loaded: dict[str, pd.Series] = {}
    skipped = []
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


def _quantile_bucket(s: pd.Series, labels: tuple[str, str, str] = ("low", "mid", "high")) -> pd.Series:
    valid = s.dropna()
    out = pd.Series(index=s.index, dtype="object")
    if valid.nunique() < 3 or len(valid) < 30:
        return out
    try:
        q = pd.qcut(valid, 3, labels=list(labels), duplicates="drop")
        out.loc[q.index] = q.astype(str)
    except ValueError:
        return out
    return out


def _rolling_avg_pairwise_corr(returns: pd.DataFrame, window: int) -> pd.Series:
    vals = []
    idx = []
    cols = list(returns.columns)
    for i in range(len(returns)):
        if i + 1 < window:
            continue
        sub = returns.iloc[i + 1 - window : i + 1]
        corr = sub.corr()
        if corr.empty:
            continue
        upper = []
        for a_i, a in enumerate(cols):
            for b in cols[a_i + 1 :]:
                value = corr.loc[a, b]
                if pd.notna(value):
                    upper.append(float(value))
        if upper:
            vals.append(float(np.mean(upper)))
            idx.append(returns.index[i])
    return pd.Series(vals, index=idx, name=f"sector_avg_pairwise_corr_{window}d")


def _build_signal_panel(
    spy: pd.Series,
    qqq: pd.Series,
    sectors: dict[str, pd.Series],
    optional: dict[str, pd.Series],
    sector_sma_window: int,
    momentum_lookback: int,
    corr_window: int,
) -> pd.DataFrame:
    sector_prices = pd.concat(sectors.values(), axis=1).sort_index().ffill()
    panel = pd.DataFrame(index=sector_prices.index)
    spy_aligned = spy.reindex(panel.index).ffill()
    qqq_aligned = qqq.reindex(panel.index).ffill()
    panel["SPY"] = spy_aligned
    panel["QQQ"] = qqq_aligned

    sector_sma = sector_prices.rolling(sector_sma_window, min_periods=sector_sma_window).mean()
    sector_mom = sector_prices / sector_prices.shift(momentum_lookback) - 1.0
    above = sector_prices > sector_sma
    positive_mom = sector_mom > 0
    panel["sector_count_above_sma"] = above.sum(axis=1)
    panel["sector_pct_above_sma"] = above.mean(axis=1)
    panel["sector_count_positive_mom"] = positive_mom.sum(axis=1)
    panel["sector_pct_positive_mom"] = positive_mom.mean(axis=1)

    sector_126 = sector_prices / sector_prices.shift(momentum_lookback) - 1.0
    panel[f"sector_return_dispersion_{momentum_lookback}d"] = sector_126.std(axis=1, ddof=0)
    panel[f"sector_mom_spread_{momentum_lookback}d"] = sector_126.max(axis=1) - sector_126.min(axis=1)
    daily_sector_rets = sector_prices.pct_change(fill_method=None)
    panel[f"sector_avg_pairwise_corr_{corr_window}d"] = _rolling_avg_pairwise_corr(daily_sector_rets, corr_window).reindex(panel.index)

    panel["QQQ_SPY_ratio"] = qqq_aligned / spy_aligned
    panel["QQQ_SPY_ratio_63d_change"] = panel["QQQ_SPY_ratio"] / panel["QQQ_SPY_ratio"].shift(63) - 1.0
    if "RSP" in optional:
        rsp = optional["RSP"].reindex(panel.index).ffill()
        panel["SPY_RSP_ratio"] = spy_aligned / rsp
        panel["SPY_RSP_ratio_63d_change"] = panel["SPY_RSP_ratio"] / panel["SPY_RSP_ratio"].shift(63) - 1.0
    if "QQQE" in optional:
        qqqe = optional["QQQE"].reindex(panel.index).ffill()
        panel["QQQ_QQQE_ratio"] = qqq_aligned / qqqe
        panel["QQQ_QQQE_ratio_63d_change"] = panel["QQQ_QQQE_ratio"] / panel["QQQ_QQQE_ratio"].shift(63) - 1.0

    panel["breadth_binary"] = np.where(panel["sector_pct_above_sma"] >= 0.5, "healthy_breadth", "weak_breadth")
    panel["qqq_leadership_bucket"] = _quantile_bucket(panel["QQQ_SPY_ratio_63d_change"], labels=("qqq_lagging", "qqq_neutral", "qqq_leading"))
    panel["fragility_state"] = panel["breadth_binary"].astype(str) + "__" + panel["qqq_leadership_bucket"].fillna("unknown")
    corr_col = f"sector_avg_pairwise_corr_{corr_window}d"
    panel["corr_bucket"] = _quantile_bucket(panel[corr_col], labels=("low_corr", "mid_corr", "high_corr"))
    return panel


def _base_weights(spy: pd.Series, qqq: pd.Series, bil: pd.Series, equity_core_window: int) -> pd.DataFrame:
    prices = pd.concat([spy.rename("SPY"), qqq.rename("QQQ"), bil.rename("BIL")], axis=1).dropna()
    spy_sma = prices["SPY"].rolling(equity_core_window, min_periods=equity_core_window).mean()
    qqq_sma = prices["QQQ"].rolling(equity_core_window, min_periods=equity_core_window).mean()
    w = pd.DataFrame(index=prices.index)
    w["SPY"] = 0.5 * (prices["SPY"] > spy_sma).astype(float)
    w["QQQ"] = 0.5 * (prices["QQQ"] > qqq_sma).astype(float)
    w["BIL"] = 1.0 - w["SPY"] - w["QQQ"]
    return w


def _force_full_equity(w: pd.DataFrame) -> pd.DataFrame:
    out = w.copy()
    out["SPY"] = 0.5
    out["QQQ"] = 0.5
    out["BIL"] = 0.0
    return out


def _reduce_equity(w: pd.DataFrame, scale: float) -> pd.DataFrame:
    out = w.copy()
    out["SPY"] = out["SPY"] * scale
    out["QQQ"] = out["QQQ"] * scale
    out["BIL"] = 1.0 - out["SPY"] - out["QQQ"]
    return out


def _apply_rules(base: pd.DataFrame, panel: pd.DataFrame, reduce_scale: float) -> dict[str, pd.DataFrame]:
    p = panel.reindex(base.index)
    weak_leading = p["fragility_state"].eq("weak_breadth__qqq_leading")
    weak_lagging = p["fragility_state"].eq("weak_breadth__qqq_lagging")
    high_corr = p["corr_bucket"].eq("high_corr")
    low_corr = p["corr_bucket"].eq("low_corr")

    rules: dict[str, pd.DataFrame] = {}
    rules["BASE_EQUITY_CORE_BIL"] = base.copy()

    a = base.copy()
    a.loc[weak_leading] = _force_full_equity(a.loc[weak_leading])
    rules["RULE_WEAK_BREADTH_QQQ_LEADING_ALLOW"] = a

    b = base.copy()
    b.loc[weak_lagging] = _reduce_equity(b.loc[weak_lagging], reduce_scale)
    rules["RULE_WEAK_BREADTH_QQQ_LAGGING_REDUCE"] = b

    c = base.copy()
    c.loc[high_corr] = _force_full_equity(c.loc[high_corr])
    rules["RULE_HIGH_CORR_ALLOW"] = c

    d = base.copy()
    bullish = weak_leading | high_corr
    caution = weak_lagging | low_corr
    d.loc[bullish] = _force_full_equity(d.loc[bullish])
    d.loc[caution] = _reduce_equity(base.loc[caution], reduce_scale)
    rules["RULE_COMBINED_NARROW_LEADERSHIP_AND_CORR"] = d

    return rules


def _curve_from_weights(prices: pd.DataFrame, weights: pd.DataFrame, capital: float) -> tuple[pd.Series, pd.Series]:
    data = prices.reindex(weights.index).dropna()
    w = weights.reindex(data.index).fillna(0.0)
    rets = data[["SPY", "QQQ", "BIL"]].pct_change(fill_method=None).fillna(0.0)
    exec_w = w.shift(1).fillna({"SPY": 0.0, "QQQ": 0.0, "BIL": 1.0})
    port_rets = (exec_w * rets).sum(axis=1)
    curve = capital * (1.0 + port_rets).cumprod()
    return curve, port_rets


def _asset_curve(price: pd.Series, capital: float, name: str) -> pd.Series:
    rets = price.dropna().pct_change(fill_method=None).fillna(0.0)
    return (capital * (1.0 + rets).cumprod()).rename(name)


def _passive_curve(spy: pd.Series, qqq: pd.Series, capital: float) -> pd.Series:
    prices = pd.concat([spy.rename("SPY"), qqq.rename("QQQ")], axis=1).dropna()
    rets = prices.pct_change(fill_method=None).fillna(0.0)
    return (capital * (1.0 + (0.5 * rets["SPY"] + 0.5 * rets["QQQ"])).cumprod()).rename("PASSIVE_SPY_QQQ_50_50")


def _bars_per_year(index: pd.DatetimeIndex) -> float:
    if len(index) < 3:
        return TRADING_DAYS
    deltas = index.to_series().diff().dropna().dt.total_seconds()
    if deltas.empty:
        return TRADING_DAYS
    med = float(deltas.median())
    if med <= 0:
        return TRADING_DAYS
    if med >= 20 * 3600:
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
    if start is not None:
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
        return {}
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


def _slice(eq: pd.Series, start: str, end: str) -> pd.Series:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    return eq.loc[(eq.index >= start_ts) & (eq.index <= end_ts)].dropna()


def _exposure_summary(weights: pd.DataFrame, name: str) -> dict[str, float | str]:
    equity_weight = weights["SPY"] + weights["QQQ"]
    turnover = weights[["SPY", "QQQ", "BIL"]].diff().abs().sum(axis=1).fillna(0.0)
    return {
        "series": name,
        "avg_spy_weight_pct": float(weights["SPY"].mean() * 100.0),
        "avg_qqq_weight_pct": float(weights["QQQ"].mean() * 100.0),
        "avg_bil_weight_pct": float(weights["BIL"].mean() * 100.0),
        "avg_equity_weight_pct": float(equity_weight.mean() * 100.0),
        "time_full_equity_pct": float((equity_weight >= 0.999).mean() * 100.0),
        "time_full_risk_off_pct": float((weights["BIL"] >= 0.999).mean() * 100.0),
        "avg_daily_turnover_proxy_pct": float(turnover.mean() * 100.0),
    }


def _event_counts(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label, mask in {
        "weak_breadth__qqq_leading": panel["fragility_state"].eq("weak_breadth__qqq_leading"),
        "weak_breadth__qqq_lagging": panel["fragility_state"].eq("weak_breadth__qqq_lagging"),
        "high_corr": panel["corr_bucket"].eq("high_corr"),
        "low_corr": panel["corr_bucket"].eq("low_corr"),
    }.items():
        rows.append({"event": label, "bars": int(mask.sum()), "pct_of_panel": float(mask.mean() * 100.0)})
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


def _write_summary_md(path: Path, perf: pd.DataFrame, exposure: pd.DataFrame, events: pd.DataFrame, windows: pd.DataFrame, args: argparse.Namespace) -> None:
    lines = [
        "# Equity Alpha Rule Replay v1",
        "",
        "Research-only replay of breadth / leadership / correlation overlays on Equity Core SMA175 + BIL.",
        "",
        "## Inputs",
        "",
        "```text",
        f"Sectors: {args.sectors}",
        f"Optional assets: {args.optional_assets}",
        f"Equity core window: {args.equity_core_window}",
        f"Sector SMA window: {args.sector_sma_window}",
        f"Momentum lookback: {args.momentum_lookback}",
        f"Correlation lookback: {args.correlation_lookback}",
        f"Reduce scale: {args.reduce_scale}",
        "```",
        "",
        "## Performance Summary",
        "",
        _md_table(perf, max_rows=40),
        "",
        "## Exposure Summary",
        "",
        _md_table(exposure, max_rows=40),
        "",
        "## Rule Event Counts",
        "",
        _md_table(events, max_rows=20),
        "",
        "## Window Performance Summary",
        "",
        _md_table(windows, max_rows=80),
        "",
        "## Guardrail",
        "",
        "```text",
        "Research only. No paper trading, live allocation, broker/execution, runtime, dashboard, crypto allocator, or global allocator changes are approved.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not (0.0 <= args.reduce_scale <= 1.0):
        raise ValueError(f"reduce_scale must be between 0 and 1, got {args.reduce_scale}")

    sectors = _parse_csv_list(args.sectors)
    optional_assets = _parse_csv_list(args.optional_assets)
    loaded_sectors, skipped_sectors = _load_assets(sectors, Path(args.data_dir), args.min_bars, "sector")
    loaded_optional, skipped_optional = _load_assets(optional_assets, Path(args.data_dir), 20, "optional")
    skipped = pd.concat([skipped_sectors, skipped_optional], ignore_index=True) if not skipped_sectors.empty or not skipped_optional.empty else pd.DataFrame()
    if len(loaded_sectors) < 3:
        raise SystemExit(f"Need at least 3 sectors; loaded {len(loaded_sectors)}")

    spy = _load_close(Path(args.spy_data), "SPY")
    qqq = _load_close(Path(args.qqq_data), "QQQ")
    bil = _load_close(Path(args.bil_data), "BIL")
    prices = pd.concat([spy.rename("SPY"), qqq.rename("QQQ"), bil.rename("BIL")], axis=1).dropna()
    panel = _build_signal_panel(
        spy=spy,
        qqq=qqq,
        sectors=loaded_sectors,
        optional=loaded_optional,
        sector_sma_window=args.sector_sma_window,
        momentum_lookback=args.momentum_lookback,
        corr_window=args.correlation_lookback,
    ).reindex(prices.index)

    base = _base_weights(spy, qqq, bil, args.equity_core_window).reindex(prices.index).dropna()
    prices = prices.reindex(base.index).dropna()
    base = base.reindex(prices.index)
    rules = _apply_rules(base, panel.reindex(base.index), args.reduce_scale)

    curves: dict[str, pd.Series] = {}
    exposure_rows = []
    history_frames = []
    for name, weights in rules.items():
        curve, _ = _curve_from_weights(prices, weights, args.capital)
        curve.name = name
        curves[name] = curve
        exposure_rows.append(_exposure_summary(weights, name))
        h = weights.copy().reset_index(names="timestamp")
        h.insert(0, "series", name)
        history_frames.append(h)

    curves["PASSIVE_SPY_QQQ_50_50"] = _passive_curve(spy, qqq, args.capital).reindex(prices.index).dropna().rename("PASSIVE_SPY_QQQ_50_50")
    curves["SPY_HODL"] = _asset_curve(spy, args.capital, "SPY_HODL").reindex(prices.index).dropna().rename("SPY_HODL")
    curves["QQQ_HODL"] = _asset_curve(qqq, args.capital, "QQQ_HODL").reindex(prices.index).dropna().rename("QQQ_HODL")

    perf_rows = []
    for name, curve in curves.items():
        clean = curve.dropna()
        perf_rows.append({"series": name, "start": str(clean.index[0]), "end": str(clean.index[-1]), "bars": len(clean), **_perf(clean)})
    perf = pd.DataFrame(perf_rows).sort_values(["calmar", "sharpe", "cagr_pct"], ascending=[False, False, False])
    exposure = pd.DataFrame(exposure_rows).sort_values("series")
    events = _event_counts(panel.reindex(prices.index))
    history = pd.concat(history_frames, ignore_index=True) if history_frames else pd.DataFrame()
    curve_df = pd.concat(curves.values(), axis=1)

    window_rows = []
    for win_name, start, end in WINDOWS:
        for name, curve in curves.items():
            sub = _slice(curve, start, end)
            if len(sub) < 20:
                continue
            window_rows.append({"window": win_name, "series": name, "start": str(sub.index[0]), "end": str(sub.index[-1]), "bars": len(sub), **_perf(sub)})
    window_perf = pd.DataFrame(window_rows).sort_values(["window", "calmar", "sharpe"], ascending=[True, False, False]) if window_rows else pd.DataFrame()

    curve_df.to_csv(out_dir / "equity_curves.csv")
    perf.to_csv(out_dir / "performance_summary.csv", index=False)
    window_perf.to_csv(out_dir / "window_performance_summary.csv", index=False)
    exposure.to_csv(out_dir / "exposure_summary.csv", index=False)
    history.to_csv(out_dir / "rule_exposure_history.csv", index=False)
    events.to_csv(out_dir / "rule_event_counts.csv", index=False)
    skipped.to_csv(out_dir / "skipped_assets.csv", index=False)

    payload = {
        "research_status": "research_only_equity_alpha_rule_replay_v1",
        "inputs": {
            "spy_data": args.spy_data,
            "qqq_data": args.qqq_data,
            "bil_data": args.bil_data,
            "sectors": sectors,
            "loaded_sectors": list(loaded_sectors.keys()),
            "optional_assets": optional_assets,
            "loaded_optional_assets": list(loaded_optional.keys()),
            "equity_core_window": args.equity_core_window,
            "sector_sma_window": args.sector_sma_window,
            "momentum_lookback": args.momentum_lookback,
            "correlation_lookback": args.correlation_lookback,
            "reduce_scale": args.reduce_scale,
        },
        "artifacts": {
            "equity_curves": str(out_dir / "equity_curves.csv"),
            "performance_summary": str(out_dir / "performance_summary.csv"),
            "window_performance_summary": str(out_dir / "window_performance_summary.csv"),
            "exposure_summary": str(out_dir / "exposure_summary.csv"),
            "rule_exposure_history": str(out_dir / "rule_exposure_history.csv"),
            "rule_event_counts": str(out_dir / "rule_event_counts.csv"),
            "skipped_assets": str(out_dir / "skipped_assets.csv"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {"status": "diagnostic_replay_only", "not_approved": ["paper_trading", "live_allocation", "broker_change", "runtime_change", "dashboard_change", "global_allocator"]},
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", perf, exposure, events, window_perf, args)

    with pd.option_context("display.max_columns", None, "display.width", 420, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY ALPHA RULE REPLAY V1 ===")
        print(f"Loaded sectors: {', '.join(loaded_sectors.keys())}")
        print(f"Loaded optional assets: {', '.join(loaded_optional.keys()) if loaded_optional else 'none'}")
        if not skipped.empty:
            print("\nSkipped assets:")
            print(skipped.to_string(index=False))
        print("\nPerformance Summary:")
        print(perf.to_string(index=False))
        print("\nExposure Summary:")
        print(exposure.to_string(index=False))
        print("\nRule Event Counts:")
        print(events.to_string(index=False))
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
