#!/usr/bin/env python
"""Equity Sector Rotation v1 — sector momentum / trend-filter sweep.

Research-only script. Tests a simple sector rotation sleeve:
    - rank sector ETFs by trailing momentum
    - hold top N sectors above their own SMA trend filter
    - optional broad SPY SMA filter
    - equal-weight selected sectors
    - risk-off to cash or a defensive asset such as BIL
    - closed-bar signal, executed next bar

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


DEFAULT_OUT = "artifacts/equity_sector_rotation_v1_sweep"
DEFAULT_SECTORS = "XLK,XLV,XLF,XLE,XLY,XLP,XLI,XLU,XLB,XLRE,XLC"
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
        description="Sweep Equity Sector Rotation v1 variants",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--data-dir", default="data", help="Directory containing <TICKER>_1D.csv files.")
    p.add_argument("--sectors", default=DEFAULT_SECTORS)
    p.add_argument("--risk-off-assets", default="cash,BIL")
    p.add_argument("--momentum-lookback", type=int, default=126)
    p.add_argument("--sector-sma-window", type=int, default=200)
    p.add_argument("--spy-filter-window", type=int, default=175)
    p.add_argument("--top-n", type=int, default=3)
    p.add_argument("--capital", type=float, default=START_CAPITAL)
    p.add_argument("--min-bars", type=int, default=252, help="Minimum bars required to include a sector asset.")
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
        except Exception as exc:  # pragma: no cover - defensive research utility path
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


def _max_time_underwater_days(eq: pd.Series) -> float:
    eq = eq.dropna().astype(float)
    if eq.empty:
        return 0.0
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
    std = float(rets.std(ddof=0)) if len(rets) else 0.0
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


def _build_equity_core_curve(spy: pd.Series, qqq: pd.Series, risk_off: pd.Series | None, sma_window: int, capital: float) -> pd.Series:
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
    port_rets = exec_w["SPY"] * rets["SPY"] + exec_w["QQQ"] * rets["QQQ"] + exec_w["DEF"] * def_rets
    out = float(capital) * (1.0 + port_rets).cumprod()
    return out.rename("EQUITY_CORE")


def _passive_curve(spy: pd.Series, qqq: pd.Series, capital: float) -> pd.Series:
    prices = pd.concat([spy.rename("SPY"), qqq.rename("QQQ")], axis=1).dropna()
    rets = prices.pct_change(fill_method=None).fillna(0.0)
    port_rets = 0.5 * rets["SPY"] + 0.5 * rets["QQQ"]
    return (float(capital) * (1.0 + port_rets).cumprod()).rename("PASSIVE_SPY_QQQ_50_50")


def _asset_curve(asset: pd.Series, capital: float, name: str) -> pd.Series:
    rets = asset.dropna().pct_change(fill_method=None).fillna(0.0)
    return (float(capital) * (1.0 + rets).cumprod()).rename(name)


def _sector_weights_for_variant(
    sector_prices: pd.DataFrame,
    spy: pd.Series,
    momentum_lookback: int,
    sector_sma_window: int,
    spy_filter_window: int,
    top_n: int,
    use_spy_filter: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    momentum = sector_prices / sector_prices.shift(momentum_lookback) - 1.0
    sma = sector_prices.rolling(sector_sma_window, min_periods=sector_sma_window).mean()
    trend_ok = sector_prices > sma
    spy_aligned = spy.reindex(sector_prices.index).ffill()
    spy_sma = spy_aligned.rolling(spy_filter_window, min_periods=spy_filter_window).mean()
    broad_ok = (spy_aligned > spy_sma) if use_spy_filter else pd.Series(True, index=sector_prices.index)

    weights = pd.DataFrame(0.0, index=sector_prices.index, columns=sector_prices.columns)
    holdings_rows = []
    for ts in sector_prices.index:
        if not bool(broad_ok.loc[ts]):
            holdings_rows.append({"timestamp": ts, "selected_count": 0, "selected_assets": "", "broad_filter_ok": False})
            continue
        mom_row = momentum.loc[ts].dropna()
        if mom_row.empty:
            holdings_rows.append({"timestamp": ts, "selected_count": 0, "selected_assets": "", "broad_filter_ok": True})
            continue
        eligible = [asset for asset in mom_row.sort_values(ascending=False).index if bool(trend_ok.loc[ts, asset])]
        selected = eligible[:top_n]
        if selected:
            weight = 1.0 / float(len(selected))
            for asset in selected:
                weights.loc[ts, asset] = weight
        holdings_rows.append(
            {
                "timestamp": ts,
                "selected_count": len(selected),
                "selected_assets": ",".join(selected),
                "broad_filter_ok": bool(broad_ok.loc[ts]),
            }
        )
    holdings = pd.DataFrame(holdings_rows).set_index("timestamp")
    return weights, holdings


def _build_rotation_curve(
    sector_prices: pd.DataFrame,
    weights: pd.DataFrame,
    risk_off: pd.Series | None,
    capital: float,
) -> tuple[pd.Series, pd.DataFrame]:
    data = sector_prices.copy()
    if risk_off is not None:
        data = pd.concat([data, risk_off.rename("DEF")], axis=1).dropna()
    weights = weights.reindex(data.index).fillna(0.0)
    sector_rets = data[sector_prices.columns].pct_change(fill_method=None).fillna(0.0)
    exec_w = weights.shift(1).fillna(0.0)
    risk_off_weight = 1.0 - exec_w.sum(axis=1)
    if risk_off is not None:
        def_rets = data["DEF"].pct_change(fill_method=None).fillna(0.0)
    else:
        def_rets = pd.Series(0.0, index=data.index)
    port_rets = (exec_w * sector_rets).sum(axis=1) + risk_off_weight * def_rets
    curve = float(capital) * (1.0 + port_rets).cumprod()
    details = exec_w.copy()
    details["risk_off_weight"] = risk_off_weight
    details["strategy_return"] = port_rets
    return curve, details


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


def _write_summary_md(path: Path, perf: pd.DataFrame, skipped: pd.DataFrame, args: argparse.Namespace) -> None:
    lines = [
        "# Equity Sector Rotation v1 — Sweep Summary",
        "",
        "Research-only sweep of simple top-N sector momentum / trend-filter variants.",
        "",
        "## Inputs",
        "",
        "```text",
        f"Sectors: {args.sectors}",
        f"Risk-off assets: {args.risk_off_assets}",
        f"Momentum lookback: {args.momentum_lookback}",
        f"Sector SMA window: {args.sector_sma_window}",
        f"SPY filter window: {args.spy_filter_window}",
        f"Top N: {args.top_n}",
        "```",
        "",
        "## Performance Summary",
        "",
        _md_table(perf, max_rows=60),
        "",
        "## Skipped Assets",
        "",
        _md_table(skipped),
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

    sectors = _parse_csv_list(args.sectors)
    risk_off_assets = _parse_csv_list(args.risk_off_assets)
    if "CASH" not in risk_off_assets:
        risk_off_assets.insert(0, "CASH")

    loaded_sectors, skipped_sectors = _load_assets(sectors, Path(args.data_dir), args.min_bars, "sector")
    if len(loaded_sectors) < max(2, args.top_n):
        raise SystemExit(f"Need at least {max(2, args.top_n)} sector assets; loaded {len(loaded_sectors)}")

    defensive_assets = [asset for asset in risk_off_assets if asset != "CASH"]
    loaded_defensive, skipped_defensive = _load_assets(defensive_assets, Path(args.data_dir), 20, "risk_off")
    skipped = pd.concat([skipped_sectors, skipped_defensive], ignore_index=True) if not skipped_sectors.empty or not skipped_defensive.empty else pd.DataFrame()

    spy = _load_close(Path(args.spy_data), "SPY")
    qqq = _load_close(Path(args.qqq_data), "QQQ")
    sector_prices = pd.concat(loaded_sectors.values(), axis=1).sort_index()
    sector_prices = sector_prices.dropna(how="all")
    sector_prices = sector_prices.ffill().dropna(how="all")

    curves: dict[str, pd.Series] = {}
    perf_rows = []
    window_rows = []
    allocation_rows = []
    holdings_frames = []

    passive = _passive_curve(spy, qqq, args.capital)
    curves[passive.name] = passive
    core_cash = _build_equity_core_curve(spy, qqq, None, args.spy_filter_window, args.capital).rename("EQUITY_CORE_SMA175_CASH")
    curves[core_cash.name] = core_cash
    curves["SPY_HODL"] = _asset_curve(spy, args.capital, "SPY_HODL")
    curves["QQQ_HODL"] = _asset_curve(qqq, args.capital, "QQQ_HODL")
    if "BIL" in loaded_defensive:
        core_bil = _build_equity_core_curve(spy, qqq, loaded_defensive["BIL"], args.spy_filter_window, args.capital).rename("EQUITY_CORE_SMA175_BIL")
        curves[core_bil.name] = core_bil

    variants = []
    for use_spy_filter in [False, True]:
        for risk_asset in risk_off_assets:
            if risk_asset != "CASH" and risk_asset not in loaded_defensive:
                continue
            suffix = "SPYFILTER" if use_spy_filter else "NO_SPYFILTER"
            name = f"SECTOR_TOP{args.top_n}_MOM{args.momentum_lookback}_SMA{args.sector_sma_window}_{suffix}_{risk_asset}"
            variants.append((name, use_spy_filter, risk_asset))

    for name, use_spy_filter, risk_asset in variants:
        weights, holdings = _sector_weights_for_variant(
            sector_prices=sector_prices,
            spy=spy,
            momentum_lookback=args.momentum_lookback,
            sector_sma_window=args.sector_sma_window,
            spy_filter_window=args.spy_filter_window,
            top_n=args.top_n,
            use_spy_filter=use_spy_filter,
        )
        risk_off = None if risk_asset == "CASH" else loaded_defensive[risk_asset]
        curve, details = _build_rotation_curve(sector_prices, weights, risk_off, args.capital)
        curve.name = name
        curves[name] = curve
        h = holdings.copy().reset_index()
        h.insert(0, "series", name)
        h.insert(1, "risk_off_asset", risk_asset)
        h.insert(2, "spy_filter", bool(use_spy_filter))
        holdings_frames.append(h)
        allocation_rows.append(
            {
                "series": name,
                "risk_off_asset": risk_asset,
                "spy_filter": bool(use_spy_filter),
                "avg_risk_off_weight_pct": float(details["risk_off_weight"].mean() * 100.0),
                "time_any_sector_pct": float((details.drop(columns=["risk_off_weight", "strategy_return"]).sum(axis=1) > 1e-12).mean() * 100.0),
                "time_full_risk_off_pct": float((details["risk_off_weight"] >= 0.999).mean() * 100.0),
                "avg_selected_count": float(holdings["selected_count"].mean()),
            }
        )

    for name, curve in curves.items():
        perf_rows.append({"series": name, "start": str(curve.dropna().index[0]), "end": str(curve.dropna().index[-1]), "bars": int(curve.dropna().shape[0]), **_perf(curve)})
        for win_name, start, end in WINDOWS:
            sub = _slice(curve, start, end)
            if len(sub) < 20:
                continue
            window_rows.append({"window": win_name, "series": name, "start": str(sub.index[0]), "end": str(sub.index[-1]), "bars": int(len(sub)), **_perf(sub)})

    perf = pd.DataFrame(perf_rows).sort_values(["calmar", "sharpe", "cagr_pct"], ascending=[False, False, False])
    window_perf = pd.DataFrame(window_rows).sort_values(["window", "calmar", "sharpe"], ascending=[True, False, False]) if window_rows else pd.DataFrame()
    allocation = pd.DataFrame(allocation_rows).sort_values(["series"]) if allocation_rows else pd.DataFrame()
    curve_df = pd.concat(curves.values(), axis=1)
    holdings_history = pd.concat(holdings_frames, ignore_index=True) if holdings_frames else pd.DataFrame()

    curve_df.to_csv(out_dir / "equity_curves.csv")
    perf.to_csv(out_dir / "performance_summary.csv", index=False)
    window_perf.to_csv(out_dir / "window_performance_summary.csv", index=False)
    allocation.to_csv(out_dir / "allocation_summary.csv", index=False)
    holdings_history.to_csv(out_dir / "holdings_history.csv", index=False)
    skipped.to_csv(out_dir / "skipped_assets.csv", index=False)

    payload = {
        "research_status": "research_only_equity_sector_rotation_v1_sweep",
        "inputs": {
            "sectors": sectors,
            "risk_off_assets": risk_off_assets,
            "momentum_lookback": args.momentum_lookback,
            "sector_sma_window": args.sector_sma_window,
            "spy_filter_window": args.spy_filter_window,
            "top_n": args.top_n,
            "capital": args.capital,
        },
        "loaded_sectors": list(loaded_sectors.keys()),
        "loaded_risk_off_assets": ["CASH"] + list(loaded_defensive.keys()),
        "skipped_assets": skipped.to_dict(orient="records") if not skipped.empty else [],
        "artifacts": {
            "equity_curves": str(out_dir / "equity_curves.csv"),
            "performance_summary": str(out_dir / "performance_summary.csv"),
            "window_performance_summary": str(out_dir / "window_performance_summary.csv"),
            "allocation_summary": str(out_dir / "allocation_summary.csv"),
            "holdings_history": str(out_dir / "holdings_history.csv"),
            "skipped_assets": str(out_dir / "skipped_assets.csv"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {"status": "diagnostic_only", "not_approved": ["paper_trading", "live_allocation", "broker_change", "runtime_change", "crypto_allocator_change", "global_allocator_change"]},
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", perf, skipped, args)

    with pd.option_context("display.max_columns", None, "display.width", 320, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY SECTOR ROTATION V1 — SWEEP ===")
        print(f"Loaded sectors: {', '.join(loaded_sectors.keys())}")
        print(f"Loaded risk-off assets: {', '.join(['CASH'] + list(loaded_defensive.keys()))}")
        if not skipped.empty:
            print("\nSkipped assets:")
            print(skipped.to_string(index=False))
        print("\nPerformance Summary:")
        print(perf.to_string(index=False))
        print("\nAllocation Summary:")
        print(allocation.to_string(index=False) if not allocation.empty else "No allocation rows.")
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
