#!/usr/bin/env python
"""Equity Alpha v1 — breadth / dispersion / leadership diagnostics.

Research-only diagnostic script. Builds ETF-based market-structure signals and
summarizes forward returns by regime buckets. This script intentionally does not
produce a trading strategy.

Signals:
    - sector breadth: count/pct above SMA200 and positive 126d momentum
    - leadership fragility: SPY/RSP, QQQ/SPY, XLK/SPY ratio trends
    - sector dispersion: cross-sectional return dispersion and sector correlation
    - forward returns for SPY, QQQ, SPY/QQQ 50/50, Equity Core cash, Equity Core BIL

No broker, runtime, paper-trading, execution, live-state, governor, dashboard,
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


DEFAULT_OUT = "artifacts/equity_alpha_breadth_dispersion_v1"
DEFAULT_SECTORS = "XLK,XLV,XLF,XLE,XLY,XLP,XLI,XLU,XLB,XLRE,XLC"
DEFAULT_OPTIONAL_ASSETS = "RSP,BIL,QQQE"
START_CAPITAL = 100_000.0
TRADING_DAYS = 252.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build Equity Alpha v1 breadth/dispersion/leadership diagnostics",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--sectors", default=DEFAULT_SECTORS)
    p.add_argument("--optional-assets", default=DEFAULT_OPTIONAL_ASSETS)
    p.add_argument("--sma-window", type=int, default=200)
    p.add_argument("--momentum-lookback", type=int, default=126)
    p.add_argument("--dispersion-lookbacks", default="63,126")
    p.add_argument("--correlation-lookback", type=int, default=63)
    p.add_argument("--forward-horizons", default="21,63,126")
    p.add_argument("--equity-core-window", type=int, default=175)
    p.add_argument("--capital", type=float, default=START_CAPITAL)
    p.add_argument("--min-bars", type=int, default=252)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    return p.parse_args()


def _parse_csv_list(raw: str, upper: bool = True) -> list[str]:
    values = []
    for part in str(raw).split(","):
        value = part.strip()
        if upper:
            value = value.upper()
        if value:
            values.append(value)
    return list(dict.fromkeys(values))


def _parse_ints(raw: str, label: str) -> list[int]:
    vals = []
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        val = int(part)
        if val <= 0:
            raise ValueError(f"{label} values must be positive; got {val}")
        vals.append(val)
    if not vals:
        raise ValueError(f"No {label} values supplied")
    return sorted(set(vals))


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


def _perf_from_returns(rets: pd.Series) -> dict[str, float]:
    rets = rets.dropna().astype(float)
    if len(rets) < 2:
        return {}
    eq = (1.0 + rets).cumprod()
    years = max(len(rets) / _bars_per_year(rets.index), 1e-9)
    total = float(eq.iloc[-1] - 1.0)
    cagr = float(eq.iloc[-1] ** (1.0 / years) - 1.0)
    dd = eq / eq.cummax() - 1.0
    max_dd = float(dd.min())
    std = float(rets.std(ddof=0))
    sharpe = float((rets.mean() / std) * math.sqrt(_bars_per_year(rets.index))) if std > 1e-12 else 0.0
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0
    return {
        "total_return_pct": total * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_dd * 100.0,
        "sharpe": sharpe,
        "calmar": calmar,
    }


def _forward_return(series: pd.Series, horizon: int) -> pd.Series:
    return series.shift(-horizon) / series - 1.0


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


def _above_below_bucket(s: pd.Series, threshold: float, above_label: str, below_label: str) -> pd.Series:
    out = pd.Series(index=s.index, dtype="object")
    out.loc[s >= threshold] = above_label
    out.loc[s < threshold] = below_label
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


def _equity_core_returns(spy: pd.Series, qqq: pd.Series, risk_off: pd.Series | None, sma_window: int) -> pd.Series:
    prices = pd.concat([spy.rename("SPY"), qqq.rename("QQQ")], axis=1).dropna()
    spy_sma = prices["SPY"].rolling(sma_window, min_periods=sma_window).mean()
    qqq_sma = prices["QQQ"].rolling(sma_window, min_periods=sma_window).mean()
    weights = pd.DataFrame(
        {
            "SPY": 0.5 * (prices["SPY"] > spy_sma).astype(float),
            "QQQ": 0.5 * (prices["QQQ"] > qqq_sma).astype(float),
        },
        index=prices.index,
    )
    weights["DEF"] = 1.0 - weights["SPY"] - weights["QQQ"]
    data = prices.copy()
    if risk_off is not None:
        data = pd.concat([data, risk_off.rename("DEF")], axis=1).dropna()
        weights = weights.reindex(data.index).fillna(0.0)
        def_rets = data["DEF"].pct_change(fill_method=None).fillna(0.0)
    else:
        weights = weights.reindex(data.index).fillna(0.0)
        def_rets = pd.Series(0.0, index=data.index)
    rets = data[["SPY", "QQQ"]].pct_change(fill_method=None).fillna(0.0)
    exec_w = weights.shift(1).fillna({"SPY": 0.0, "QQQ": 0.0, "DEF": 1.0})
    return (exec_w["SPY"] * rets["SPY"] + exec_w["QQQ"] * rets["QQQ"] + exec_w["DEF"] * def_rets).rename("EQUITY_CORE")


def _build_signal_panel(
    spy: pd.Series,
    qqq: pd.Series,
    sectors: dict[str, pd.Series],
    optional: dict[str, pd.Series],
    dispersion_lookbacks: list[int],
    sma_window: int,
    momentum_lookback: int,
    corr_window: int,
) -> pd.DataFrame:
    sector_prices = pd.concat(sectors.values(), axis=1).sort_index().ffill()
    panel = pd.DataFrame(index=sector_prices.index)
    spy_aligned = spy.reindex(panel.index).ffill()
    qqq_aligned = qqq.reindex(panel.index).ffill()
    panel["SPY"] = spy_aligned
    panel["QQQ"] = qqq_aligned

    sector_sma = sector_prices.rolling(sma_window, min_periods=sma_window).mean()
    sector_mom = sector_prices / sector_prices.shift(momentum_lookback) - 1.0
    above = sector_prices > sector_sma
    positive_mom = sector_mom > 0
    panel["sector_count_above_sma"] = above.sum(axis=1)
    panel["sector_pct_above_sma"] = above.mean(axis=1)
    panel["sector_count_positive_mom"] = positive_mom.sum(axis=1)
    panel["sector_pct_positive_mom"] = positive_mom.mean(axis=1)

    for lb in dispersion_lookbacks:
        ret = sector_prices / sector_prices.shift(lb) - 1.0
        panel[f"sector_return_dispersion_{lb}d"] = ret.std(axis=1, ddof=0)
        panel[f"sector_mom_spread_{lb}d"] = ret.max(axis=1) - ret.min(axis=1)
    daily_sector_rets = sector_prices.pct_change(fill_method=None)
    panel[f"sector_avg_pairwise_corr_{corr_window}d"] = _rolling_avg_pairwise_corr(daily_sector_rets, corr_window).reindex(panel.index)

    if "RSP" in optional:
        rsp = optional["RSP"].reindex(panel.index).ffill()
        panel["SPY_RSP_ratio"] = spy_aligned / rsp
        panel["SPY_RSP_ratio_63d_change"] = panel["SPY_RSP_ratio"] / panel["SPY_RSP_ratio"].shift(63) - 1.0
    if "QQQE" in optional:
        qqqe = optional["QQQE"].reindex(panel.index).ffill()
        panel["QQQ_QQQE_ratio"] = qqq_aligned / qqqe
        panel["QQQ_QQQE_ratio_63d_change"] = panel["QQQ_QQQE_ratio"] / panel["QQQ_QQQE_ratio"].shift(63) - 1.0
    panel["QQQ_SPY_ratio"] = qqq_aligned / spy_aligned
    panel["QQQ_SPY_ratio_63d_change"] = panel["QQQ_SPY_ratio"] / panel["QQQ_SPY_ratio"].shift(63) - 1.0
    if "XLK" in sectors:
        xlk = sectors["XLK"].reindex(panel.index).ffill()
        panel["XLK_SPY_ratio"] = xlk / spy_aligned
        panel["XLK_SPY_ratio_63d_change"] = panel["XLK_SPY_ratio"] / panel["XLK_SPY_ratio"].shift(63) - 1.0

    spy_sma = spy_aligned.rolling(175, min_periods=175).mean()
    panel["spy_above_sma175"] = spy_aligned > spy_sma
    panel["breadth_bucket"] = _quantile_bucket(panel["sector_pct_above_sma"])
    disp_col = f"sector_return_dispersion_{momentum_lookback}d"
    if disp_col in panel.columns:
        panel["dispersion_bucket"] = _quantile_bucket(panel[disp_col])
    panel["corr_bucket"] = _quantile_bucket(panel[f"sector_avg_pairwise_corr_{corr_window}d"], labels=("low_corr", "mid_corr", "high_corr"))
    panel["breadth_binary"] = _above_below_bucket(panel["sector_pct_above_sma"], 0.5, "healthy_breadth", "weak_breadth")
    panel["qqq_leadership_bucket"] = _quantile_bucket(panel["QQQ_SPY_ratio_63d_change"], labels=("qqq_lagging", "qqq_neutral", "qqq_leading"))
    panel["fragility_state"] = panel["breadth_binary"].fillna("unknown") + "__" + panel["qqq_leadership_bucket"].fillna("unknown")
    return panel


def _forward_tables(panel: pd.DataFrame, targets: dict[str, pd.Series], horizons: list[int]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    qrows = []
    count_rows = []
    regime_cols = [
        "breadth_bucket",
        "dispersion_bucket",
        "corr_bucket",
        "breadth_binary",
        "qqq_leadership_bucket",
        "fragility_state",
        "spy_above_sma175",
    ]
    signal_cols = [
        "sector_pct_above_sma",
        "sector_pct_positive_mom",
        "sector_return_dispersion_126d",
        "sector_mom_spread_126d",
        "sector_avg_pairwise_corr_63d",
        "QQQ_SPY_ratio_63d_change",
        "SPY_RSP_ratio_63d_change",
        "XLK_SPY_ratio_63d_change",
    ]
    available_signal_cols = [c for c in signal_cols if c in panel.columns]

    for target_name, series in targets.items():
        aligned = series.reindex(panel.index).ffill()
        for horizon in horizons:
            fwd = _forward_return(aligned, horizon)
            base = panel.copy()
            base["forward_return"] = fwd
            for regime_col in regime_cols:
                if regime_col not in base.columns:
                    continue
                grp = base.dropna(subset=[regime_col, "forward_return"]).groupby(regime_col)["forward_return"]
                for regime, vals in grp:
                    vals = vals.dropna()
                    if len(vals) < 20:
                        continue
                    rows.append(
                        {
                            "target": target_name,
                            "horizon_days": horizon,
                            "regime_family": regime_col,
                            "regime": str(regime),
                            "n": int(len(vals)),
                            "mean_forward_return_pct": float(vals.mean() * 100.0),
                            "median_forward_return_pct": float(vals.median() * 100.0),
                            "hit_rate_pct": float((vals > 0).mean() * 100.0),
                            "worst_forward_return_pct": float(vals.min() * 100.0),
                            "best_forward_return_pct": float(vals.max() * 100.0),
                        }
                    )
                    count_rows.append({"regime_family": regime_col, "regime": str(regime), "n": int(len(vals))})
            for col in available_signal_cols:
                bucket = _quantile_bucket(base[col])
                qbase = pd.DataFrame({"bucket": bucket, "forward_return": base["forward_return"]}).dropna()
                for bucket_name, vals in qbase.groupby("bucket")["forward_return"]:
                    vals = vals.dropna()
                    if len(vals) < 20:
                        continue
                    qrows.append(
                        {
                            "target": target_name,
                            "horizon_days": horizon,
                            "signal": col,
                            "bucket": str(bucket_name),
                            "n": int(len(vals)),
                            "mean_forward_return_pct": float(vals.mean() * 100.0),
                            "median_forward_return_pct": float(vals.median() * 100.0),
                            "hit_rate_pct": float((vals > 0).mean() * 100.0),
                            "worst_forward_return_pct": float(vals.min() * 100.0),
                            "best_forward_return_pct": float(vals.max() * 100.0),
                        }
                    )
    return pd.DataFrame(rows), pd.DataFrame(qrows), pd.DataFrame(count_rows)


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
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(_fmt_md_value(row[c]) for c in df.columns) + " |")
    return "\n".join(lines)


def _write_summary_md(path: Path, context: pd.DataFrame, regime: pd.DataFrame, quantile: pd.DataFrame, skipped: pd.DataFrame, args: argparse.Namespace) -> None:
    lines = [
        "# Equity Alpha v1 — Breadth / Dispersion Diagnostics",
        "",
        "Research-only diagnostics for ETF-based breadth, leadership fragility, and sector dispersion signals.",
        "",
        "## Inputs",
        "",
        "```text",
        f"Sectors: {args.sectors}",
        f"Optional assets: {args.optional_assets}",
        f"Forward horizons: {args.forward_horizons}",
        f"SMA window: {args.sma_window}",
        f"Momentum lookback: {args.momentum_lookback}",
        "```",
        "",
        "## Performance Context",
        "",
        _md_table(context, max_rows=20),
        "",
        "## Forward Return by Regime — First Rows",
        "",
        _md_table(regime, max_rows=40),
        "",
        "## Forward Return by Quantile — First Rows",
        "",
        _md_table(quantile, max_rows=40),
        "",
        "## Skipped Assets",
        "",
        _md_table(skipped),
        "",
        "## Guardrail",
        "",
        "```text",
        "Diagnostics only. No strategy, paper trading, live allocation, broker/execution, runtime, dashboard, crypto allocator, or global allocator changes are approved.",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sectors = _parse_csv_list(args.sectors)
    optional_assets = _parse_csv_list(args.optional_assets)
    horizons = _parse_ints(args.forward_horizons, "forward horizon")
    dispersion_lookbacks = _parse_ints(args.dispersion_lookbacks, "dispersion lookback")

    loaded_sectors, skipped_sectors = _load_assets(sectors, Path(args.data_dir), args.min_bars, "sector")
    loaded_optional, skipped_optional = _load_assets(optional_assets, Path(args.data_dir), 20, "optional")
    skipped = pd.concat([skipped_sectors, skipped_optional], ignore_index=True) if not skipped_sectors.empty or not skipped_optional.empty else pd.DataFrame()
    if len(loaded_sectors) < 3:
        raise SystemExit(f"Need at least 3 sectors for diagnostics; loaded {len(loaded_sectors)}")

    spy = _load_close(Path(args.spy_data), "SPY")
    qqq = _load_close(Path(args.qqq_data), "QQQ")
    panel = _build_signal_panel(
        spy=spy,
        qqq=qqq,
        sectors=loaded_sectors,
        optional=loaded_optional,
        dispersion_lookbacks=dispersion_lookbacks,
        sma_window=args.sma_window,
        momentum_lookback=args.momentum_lookback,
        corr_window=args.correlation_lookback,
    )

    spy_ret = spy.pct_change(fill_method=None).fillna(0.0).rename("SPY")
    qqq_ret = qqq.pct_change(fill_method=None).fillna(0.0).rename("QQQ")
    passive_price = (1.0 + (0.5 * spy_ret.reindex(panel.index).fillna(0.0) + 0.5 * qqq_ret.reindex(panel.index).fillna(0.0))).cumprod().rename("SPY_QQQ_50_50")
    core_cash_rets = _equity_core_returns(spy, qqq, None, args.equity_core_window)
    core_cash_price = (1.0 + core_cash_rets.reindex(panel.index).fillna(0.0)).cumprod().rename("EQUITY_CORE_CASH")
    targets = {
        "SPY": spy.reindex(panel.index).ffill(),
        "QQQ": qqq.reindex(panel.index).ffill(),
        "SPY_QQQ_50_50": passive_price,
        "EQUITY_CORE_CASH": core_cash_price,
    }
    if "BIL" in loaded_optional:
        core_bil_rets = _equity_core_returns(spy, qqq, loaded_optional["BIL"], args.equity_core_window)
        targets["EQUITY_CORE_BIL"] = (1.0 + core_bil_rets.reindex(panel.index).fillna(0.0)).cumprod().rename("EQUITY_CORE_BIL")

    regime_table, quantile_table, counts = _forward_tables(panel, targets, horizons)
    counts = counts.groupby(["regime_family", "regime"], as_index=False)["n"].max() if not counts.empty else counts

    context_rows = []
    for name, price in targets.items():
        returns = price.reindex(panel.index).ffill().pct_change(fill_method=None).dropna()
        context_rows.append({"target": name, **_perf_from_returns(returns)})
    context = pd.DataFrame(context_rows).sort_values(["calmar", "sharpe", "cagr_pct"], ascending=[False, False, False])

    panel.to_csv(out_dir / "daily_signal_panel.csv")
    regime_table.to_csv(out_dir / "forward_return_by_regime.csv", index=False)
    quantile_table.to_csv(out_dir / "forward_return_by_quantile.csv", index=False)
    counts.to_csv(out_dir / "regime_counts.csv", index=False)
    context.to_csv(out_dir / "performance_context_summary.csv", index=False)
    skipped.to_csv(out_dir / "skipped_assets.csv", index=False)

    payload = {
        "research_status": "research_only_equity_alpha_breadth_dispersion_v1",
        "inputs": {
            "sectors": sectors,
            "optional_assets": optional_assets,
            "loaded_sectors": list(loaded_sectors.keys()),
            "loaded_optional": list(loaded_optional.keys()),
            "sma_window": args.sma_window,
            "momentum_lookback": args.momentum_lookback,
            "dispersion_lookbacks": dispersion_lookbacks,
            "correlation_lookback": args.correlation_lookback,
            "forward_horizons": horizons,
        },
        "skipped_assets": skipped.to_dict(orient="records") if not skipped.empty else [],
        "artifacts": {
            "daily_signal_panel": str(out_dir / "daily_signal_panel.csv"),
            "forward_return_by_regime": str(out_dir / "forward_return_by_regime.csv"),
            "forward_return_by_quantile": str(out_dir / "forward_return_by_quantile.csv"),
            "regime_counts": str(out_dir / "regime_counts.csv"),
            "performance_context_summary": str(out_dir / "performance_context_summary.csv"),
            "skipped_assets": str(out_dir / "skipped_assets.csv"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {"status": "diagnostic_only", "not_approved": ["strategy", "paper_trading", "live_allocation", "broker_change", "runtime_change", "crypto_allocator_change", "global_allocator_change"]},
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", context, regime_table, quantile_table, skipped, args)

    interesting = regime_table.sort_values(["target", "horizon_days", "mean_forward_return_pct"], ascending=[True, True, False]) if not regime_table.empty else pd.DataFrame()
    with pd.option_context("display.max_columns", None, "display.width", 340, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY ALPHA V1 — BREADTH / DISPERSION DIAGNOSTICS ===")
        print(f"Loaded sectors: {', '.join(loaded_sectors.keys())}")
        print(f"Loaded optional assets: {', '.join(loaded_optional.keys()) if loaded_optional else 'none'}")
        if not skipped.empty:
            print("\nSkipped assets:")
            print(skipped.to_string(index=False))
        print("\nPerformance Context:")
        print(context.to_string(index=False))
        print("\nForward Return by Regime — Top rows:")
        print(interesting.head(40).to_string(index=False) if not interesting.empty else "No regime rows.")
        print("\nRegime Counts:")
        print(counts.to_string(index=False) if not counts.empty else "No count rows.")
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
