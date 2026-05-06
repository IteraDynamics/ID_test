#!/usr/bin/env python
"""Equity Enhancements v1 — defensive carry / risk-off substitute sweep.

Research-only script. Keeps the SPY/QQQ SMA equity signal fixed and varies only
what inactive sleeves hold: cash, SGOV, BIL, SHV, IEF, TLT, GLD, or any supplied
ETF ticker with a local daily CSV.

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


DEFAULT_OUT = "artifacts/equity_enhancements_v1_defensive_sweep"
DEFAULT_DEFENSIVE_ASSETS = "cash,SGOV,BIL,SHV,IEF,TLT,GLD"
DEFAULT_SMA_WINDOW = 175
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
        description="Sweep Equity Core v1 risk-off substitutes while keeping SPY/QQQ SMA signal fixed",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--data-dir", default="data", help="Directory containing <TICKER>_1D.csv files.")
    p.add_argument("--defensive-assets", default=DEFAULT_DEFENSIVE_ASSETS)
    p.add_argument("--sma-window", type=int, default=DEFAULT_SMA_WINDOW)
    p.add_argument("--capital", type=float, default=START_CAPITAL)
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    return p.parse_args()


def _parse_assets(raw: str) -> list[str]:
    assets = []
    for part in str(raw).split(","):
        asset = part.strip().upper()
        if asset:
            assets.append(asset)
    if "CASH" not in assets:
        assets.insert(0, "CASH")
    # Preserve order while removing duplicates.
    return list(dict.fromkeys(assets))


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


def _load_defensive_assets(assets: Iterable[str], data_dir: Path) -> tuple[dict[str, pd.Series | None], pd.DataFrame]:
    loaded: dict[str, pd.Series | None] = {}
    skipped = []
    for asset in assets:
        if asset == "CASH":
            loaded[asset] = None
            continue
        path = data_dir / f"{asset}_1D.csv"
        if not path.exists():
            skipped.append({"asset": asset, "path": str(path), "reason": "missing_file"})
            continue
        try:
            loaded[asset] = _load_close(path, asset)
        except Exception as exc:  # pragma: no cover - defensive research utility path
            skipped.append({"asset": asset, "path": str(path), "reason": f"load_error: {exc}"})
    return loaded, pd.DataFrame(skipped)


def _common_spy_qqq(spy_path: Path, qqq_path: Path) -> pd.DataFrame:
    spy = _load_close(spy_path, "SPY")
    qqq = _load_close(qqq_path, "QQQ")
    prices = pd.concat([spy.rename("SPY"), qqq.rename("QQQ")], axis=1).dropna().sort_index()
    if len(prices) < DEFAULT_SMA_WINDOW:
        raise ValueError(f"Insufficient common SPY/QQQ history: {len(prices)} rows")
    return prices


def _signal_weights(prices: pd.DataFrame, sma_window: int) -> pd.DataFrame:
    if sma_window <= 1:
        raise ValueError(f"sma_window must be > 1, got {sma_window}")
    spy_sma = prices["SPY"].rolling(sma_window, min_periods=sma_window).mean()
    qqq_sma = prices["QQQ"].rolling(sma_window, min_periods=sma_window).mean()
    spy_active = (prices["SPY"] > spy_sma).astype(float)
    qqq_active = (prices["QQQ"] > qqq_sma).astype(float)
    return pd.DataFrame(
        {
            "target_spy_weight": 0.50 * spy_active,
            "target_qqq_weight": 0.50 * qqq_active,
            "risk_off_weight": 1.0 - 0.50 * spy_active - 0.50 * qqq_active,
            "spy_active": spy_active.astype(bool),
            "qqq_active": qqq_active.astype(bool),
            "spy_sma": spy_sma,
            "qqq_sma": qqq_sma,
        },
        index=prices.index,
    )


def _build_curve(
    prices: pd.DataFrame,
    signal: pd.DataFrame,
    defensive_close: pd.Series | None,
    capital: float,
) -> tuple[pd.Series, pd.DataFrame]:
    data = pd.concat([prices, signal], axis=1).dropna(subset=["SPY", "QQQ"])
    if defensive_close is not None:
        data = pd.concat([data, defensive_close.rename("DEF")], axis=1).dropna(subset=["DEF"])
    returns = data[["SPY", "QQQ"]].pct_change().fillna(0.0)
    if defensive_close is not None:
        def_returns = data["DEF"].pct_change().fillna(0.0)
    else:
        def_returns = pd.Series(0.0, index=data.index)
    exec_spy = data["target_spy_weight"].shift(1).fillna(0.0)
    exec_qqq = data["target_qqq_weight"].shift(1).fillna(0.0)
    exec_def = data["risk_off_weight"].shift(1).fillna(1.0)
    strat_returns = exec_spy * returns["SPY"] + exec_qqq * returns["QQQ"] + exec_def * def_returns
    passive_returns = 0.50 * returns["SPY"] + 0.50 * returns["QQQ"]
    curve = float(capital) * (1.0 + strat_returns).cumprod()
    details = pd.DataFrame(
        {
            "exec_spy_weight": exec_spy,
            "exec_qqq_weight": exec_qqq,
            "exec_defensive_weight": exec_def,
            "strategy_return": strat_returns,
            "passive_5050_return": passive_returns,
        },
        index=data.index,
    )
    return curve, details


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
    rets = eq.dropna().astype(float).pct_change().dropna()
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
    rets = eq.pct_change().dropna()
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
    worst_90 = float(eq.pct_change(90).dropna().min()) if len(eq) > 90 else 0.0
    worst_180 = float(eq.pct_change(180).dropna().min()) if len(eq) > 180 else 0.0
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


def _write_summary_md(path: Path, perf: pd.DataFrame, comparisons: pd.DataFrame, skipped: pd.DataFrame, args: argparse.Namespace) -> None:
    lines = [
        "# Equity Enhancements v1 — Defensive Substitute Sweep",
        "",
        "Research-only sweep keeping the SPY/QQQ SMA175 signal fixed while varying inactive-sleeve risk-off assets.",
        "",
        "## Inputs",
        "",
        "```text",
        f"SPY data: {args.spy_data}",
        f"QQQ data: {args.qqq_data}",
        f"Data dir: {args.data_dir}",
        f"SMA window: {args.sma_window}",
        f"Defensive assets: {args.defensive_assets}",
        "```",
        "",
        "## Performance Summary",
        "",
        _md_table(perf, max_rows=40),
        "",
        "## Pairwise vs Cash",
        "",
        _md_table(comparisons, max_rows=40),
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
    defensive_assets = _parse_assets(args.defensive_assets)
    prices = _common_spy_qqq(Path(args.spy_data), Path(args.qqq_data))
    signal = _signal_weights(prices, args.sma_window)
    loaded, skipped = _load_defensive_assets(defensive_assets, Path(args.data_dir))

    curves: dict[str, pd.Series] = {}
    allocation_rows = []
    perf_rows = []
    window_rows = []
    detail_frames = []

    passive_curve, passive_details = _build_curve(prices, signal.assign(target_spy_weight=0.5, target_qqq_weight=0.5, risk_off_weight=0.0), None, args.capital)
    passive_curve.name = "PASSIVE_SPY_QQQ_50_50"
    curves[passive_curve.name] = passive_curve
    perf_rows.append({"series": passive_curve.name, "defensive_asset": "NONE", "start": str(passive_curve.index[0]), "end": str(passive_curve.index[-1]), "bars": len(passive_curve), **_perf(passive_curve)})

    for asset, close in loaded.items():
        series_name = f"SPY_QQQ_SMA{args.sma_window}_RISK_OFF_{asset}"
        curve, details = _build_curve(prices, signal, close, args.capital)
        curve.name = series_name
        curves[series_name] = curve
        detail = details.copy()
        detail.insert(0, "series", series_name)
        detail_frames.append(detail.reset_index(names="timestamp"))
        perf_rows.append({"series": series_name, "defensive_asset": asset, "start": str(curve.index[0]), "end": str(curve.index[-1]), "bars": len(curve), **_perf(curve)})
        allocation_rows.append(
            {
                "series": series_name,
                "defensive_asset": asset,
                "avg_spy_weight_pct": float(details["exec_spy_weight"].mean() * 100.0),
                "avg_qqq_weight_pct": float(details["exec_qqq_weight"].mean() * 100.0),
                "avg_defensive_weight_pct": float(details["exec_defensive_weight"].mean() * 100.0),
                "time_any_equity_pct": float(((details["exec_spy_weight"] + details["exec_qqq_weight"]) > 1e-12).mean() * 100.0),
                "time_full_defensive_pct": float((details["exec_defensive_weight"] >= 0.999).mean() * 100.0),
            }
        )
        for win_name, start, end in WINDOWS:
            sub = _slice(curve, start, end)
            if len(sub) < 20:
                continue
            window_rows.append({"window": win_name, "series": series_name, "defensive_asset": asset, "start": str(sub.index[0]), "end": str(sub.index[-1]), "bars": len(sub), **_perf(sub)})

    perf = pd.DataFrame(perf_rows).sort_values(["calmar", "sharpe", "cagr_pct"], ascending=[False, False, False])
    allocation = pd.DataFrame(allocation_rows)
    window_perf = pd.DataFrame(window_rows).sort_values(["window", "calmar", "sharpe"], ascending=[True, False, False]) if window_rows else pd.DataFrame()
    curve_df = pd.concat(curves.values(), axis=1)
    details_df = pd.concat(detail_frames, ignore_index=True) if detail_frames else pd.DataFrame()

    cash_name = f"SPY_QQQ_SMA{args.sma_window}_RISK_OFF_CASH"
    comparisons = []
    for row in perf_rows:
        name = row["series"]
        if name in {cash_name, "PASSIVE_SPY_QQQ_50_50"}:
            continue
        if cash_name not in curves:
            continue
        common = curves[name].dropna().index.intersection(curves[cash_name].dropna().index)
        if len(common) < 20:
            continue
        candidate_perf = _perf(curves[name].loc[common])
        cash_perf = _perf(curves[cash_name].loc[common])
        comparisons.append(
            {
                "series": name,
                "defensive_asset": row["defensive_asset"],
                "overlap_start": str(common[0]),
                "overlap_end": str(common[-1]),
                "bars": len(common),
                "delta_cagr_pct_vs_cash": candidate_perf.get("cagr_pct", 0.0) - cash_perf.get("cagr_pct", 0.0),
                "delta_max_drawdown_pct_vs_cash": candidate_perf.get("max_drawdown_pct", 0.0) - cash_perf.get("max_drawdown_pct", 0.0),
                "delta_sharpe_vs_cash": candidate_perf.get("sharpe", 0.0) - cash_perf.get("sharpe", 0.0),
                "delta_sortino_vs_cash": candidate_perf.get("sortino", 0.0) - cash_perf.get("sortino", 0.0),
                "delta_calmar_vs_cash": candidate_perf.get("calmar", 0.0) - cash_perf.get("calmar", 0.0),
            }
        )
    comparison_df = pd.DataFrame(comparisons).sort_values(["delta_calmar_vs_cash", "delta_sharpe_vs_cash", "delta_cagr_pct_vs_cash"], ascending=[False, False, False]) if comparisons else pd.DataFrame()

    curve_df.to_csv(out_dir / "equity_curves.csv")
    details_df.to_csv(out_dir / "weight_and_return_history.csv", index=False)
    perf.to_csv(out_dir / "performance_summary.csv", index=False)
    comparison_df.to_csv(out_dir / "pairwise_cash_comparison.csv", index=False)
    window_perf.to_csv(out_dir / "window_performance_summary.csv", index=False)
    allocation.to_csv(out_dir / "allocation_summary.csv", index=False)
    skipped.to_csv(out_dir / "skipped_assets.csv", index=False)

    payload = {
        "research_status": "research_only_equity_enhancements_v1_defensive_substitute_sweep",
        "inputs": {
            "spy_data": args.spy_data,
            "qqq_data": args.qqq_data,
            "data_dir": args.data_dir,
            "defensive_assets": defensive_assets,
            "sma_window": args.sma_window,
            "capital": args.capital,
        },
        "loaded_assets": list(loaded.keys()),
        "skipped_assets": skipped.to_dict(orient="records") if not skipped.empty else [],
        "artifacts": {
            "equity_curves": str(out_dir / "equity_curves.csv"),
            "weight_and_return_history": str(out_dir / "weight_and_return_history.csv"),
            "performance_summary": str(out_dir / "performance_summary.csv"),
            "pairwise_cash_comparison": str(out_dir / "pairwise_cash_comparison.csv"),
            "window_performance_summary": str(out_dir / "window_performance_summary.csv"),
            "allocation_summary": str(out_dir / "allocation_summary.csv"),
            "skipped_assets": str(out_dir / "skipped_assets.csv"),
            "summary_json": str(out_dir / "summary.json"),
            "summary_md": str(out_dir / "summary.md"),
        },
        "decision": {"status": "diagnostic_only", "not_approved": ["paper_trading", "live_allocation", "broker_change", "runtime_change", "crypto_allocator_change", "global_allocator_change"]},
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_summary_md(out_dir / "summary.md", perf, comparison_df, skipped, args)

    with pd.option_context("display.max_columns", None, "display.width", 300, "display.float_format", "{:.4f}".format):
        print("\n=== EQUITY ENHANCEMENTS V1 — DEFENSIVE SUBSTITUTE SWEEP ===")
        print(f"SPY/QQQ overlap: {prices.index[0]} → {prices.index[-1]} ({len(prices)} bars)")
        print(f"SMA window: {args.sma_window}")
        print(f"Loaded defensive assets: {', '.join(loaded.keys())}")
        if not skipped.empty:
            print("\nSkipped assets:")
            print(skipped.to_string(index=False))
        print("\nPerformance Summary:")
        print(perf.to_string(index=False))
        print("\nPairwise vs Cash:")
        print(comparison_df.to_string(index=False) if not comparison_df.empty else "No non-cash candidates available.")
    print(f"\nArtifacts saved to: {out_dir}")


if __name__ == "__main__":
    main()
