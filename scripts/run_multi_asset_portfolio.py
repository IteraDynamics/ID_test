#!/usr/bin/env python
"""
Itera Dynamics — Multi-Asset Portfolio Research Runner

Purpose:
    Combine an existing Crypto Sleeve equity curve with an existing Equity Sleeve
    equity curve into a single research portfolio.

Classification:
    Research-only. This script does not run live execution, does not mutate runtime
    state, and does not affect Crypto Sleeve v1 / v2 paper trading.

Inputs:
    - Crypto Sleeve equity curve from run_fund_portfolio.py
      Expected column: portfolio, equity, or first numeric column

    - Equity Sleeve equity curve from run_equity_spy_backtest.py
      Expected column: strategy_equity or first numeric column

Design:
    This is a portfolio-construction test, not strategy research. Each sleeve is
    assumed to have already been independently backtested. The script aligns both
    curves to daily frequency, normalizes each to its allocated capital, and then
    sums them into a combined Itera research portfolio.

Outputs:
    artifacts/multi_asset_portfolio/
        - equity_curves.csv
        - daily_returns.csv
        - summary.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class Metrics:
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    sharpe: float
    calmar: float
    ann_vol_pct: float


def _load_equity_curve(path: str | Path, preferred_columns: list[str]) -> pd.Series:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Equity curve not found: {path}")

    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Equity curve file is empty: {path}")

    timestamp_col = None
    for candidate in ("timestamp", "date", "datetime", "Unnamed: 0"):
        if candidate in df.columns:
            timestamp_col = candidate
            break

    if timestamp_col is None:
        timestamp_col = df.columns[0]

    df[timestamp_col] = pd.to_datetime(df[timestamp_col])
    df = df.set_index(timestamp_col).sort_index()
    df.index = df.index.tz_localize(None) if getattr(df.index, "tz", None) is not None else df.index

    selected = None
    for col in preferred_columns:
        if col in df.columns:
            selected = col
            break

    if selected is None:
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if not numeric_cols:
            raise ValueError(f"No numeric equity column found in {path}. Columns: {list(df.columns)}")
        selected = numeric_cols[0]

    s = pd.to_numeric(df[selected], errors="coerce").dropna()
    if s.empty:
        raise ValueError(f"Selected equity column {selected!r} has no numeric data in {path}")
    s.name = selected
    return s


def _to_daily_equity(curve: pd.Series) -> pd.Series:
    daily = curve.resample("1D").last().dropna()
    daily = daily[~daily.index.duplicated(keep="last")]
    return daily


def _normalize_to_capital(curve: pd.Series, target_capital: float, name: str) -> pd.Series:
    if curve.iloc[0] <= 0:
        raise ValueError(f"Cannot normalize {name}: first equity value <= 0")
    out = curve / curve.iloc[0] * target_capital
    out.name = name
    return out


def compute_metrics(equity: pd.Series) -> Metrics:
    equity = equity.dropna().astype(float)
    returns = equity.pct_change().dropna()

    if len(equity) < 2:
        return Metrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0

    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    max_dd = float(drawdown.min())

    if len(returns) and returns.std(ddof=0) > 0:
        ann_vol = float(returns.std(ddof=0) * math.sqrt(TRADING_DAYS_PER_YEAR))
        sharpe = float((returns.mean() / returns.std(ddof=0)) * math.sqrt(TRADING_DAYS_PER_YEAR))
    else:
        ann_vol = 0.0
        sharpe = 0.0

    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0

    return Metrics(
        total_return_pct=total_return * 100.0,
        cagr_pct=cagr * 100.0,
        max_drawdown_pct=max_dd * 100.0,
        sharpe=sharpe,
        calmar=calmar,
        ann_vol_pct=ann_vol * 100.0,
    )


def print_metrics(label: str, m: Metrics, corr: float | None = None) -> None:
    corr_txt = "   —" if corr is None else f" {corr:>7.3f}"
    print(
        f"  {label:<20}"
        f" {m.total_return_pct:>9.2f}%"
        f" {m.cagr_pct:>9.2f}%"
        f" {m.max_drawdown_pct:>9.2f}%"
        f" {m.sharpe:>8.3f}"
        f" {m.calmar:>8.3f}"
        f" {m.ann_vol_pct:>9.2f}%"
        f"{corr_txt}"
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Blend Crypto Sleeve and Equity Sleeve equity curves into a multi-asset research portfolio",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--crypto-equity", required=True, help="Path to Crypto Sleeve equity curve CSV")
    p.add_argument("--equity-equity", required=True, help="Path to Equity Sleeve equity curve CSV")
    p.add_argument("--capital", type=float, default=100000.0, help="Total research portfolio capital")
    p.add_argument("--crypto-weight", type=float, default=0.70, help="Capital weight assigned to Crypto Sleeve")
    p.add_argument("--equity-weight", type=float, default=0.30, help="Capital weight assigned to Equity Sleeve")
    p.add_argument("--out-dir", default="artifacts/multi_asset_portfolio")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    total_weight = args.crypto_weight + args.equity_weight
    if total_weight <= 0:
        raise SystemExit("Weights must sum to a positive number")

    crypto_weight = args.crypto_weight / total_weight
    equity_weight = args.equity_weight / total_weight

    crypto_raw = _load_equity_curve(args.crypto_equity, ["portfolio", "equity", "portfolio_equity"])
    equity_raw = _load_equity_curve(args.equity_equity, ["strategy_equity", "equity"])

    crypto_daily = _to_daily_equity(crypto_raw)
    equity_daily = _to_daily_equity(equity_raw)

    common_index = crypto_daily.index.intersection(equity_daily.index)
    if len(common_index) < 30:
        raise SystemExit(
            f"Insufficient overlap between curves: {len(common_index)} daily bars. "
            "Check date ranges and input files."
        )

    crypto_daily = crypto_daily.loc[common_index]
    equity_daily = equity_daily.loc[common_index]

    crypto_alloc = args.capital * crypto_weight
    equity_alloc = args.capital * equity_weight

    crypto_scaled = _normalize_to_capital(crypto_daily, crypto_alloc, "crypto_sleeve")
    equity_scaled = _normalize_to_capital(equity_daily, equity_alloc, "equity_sleeve")
    combined = crypto_scaled + equity_scaled
    combined.name = "itera_multi_asset"

    curves = pd.DataFrame({
        "crypto_sleeve": crypto_scaled,
        "equity_sleeve": equity_scaled,
        "itera_multi_asset": combined,
    })

    daily_returns = curves.pct_change().dropna()
    corr_crypto_equity = float(daily_returns["crypto_sleeve"].corr(daily_returns["equity_sleeve"]))
    corr_combined_crypto = float(daily_returns["itera_multi_asset"].corr(daily_returns["crypto_sleeve"]))
    corr_combined_equity = float(daily_returns["itera_multi_asset"].corr(daily_returns["equity_sleeve"]))

    metrics = {
        "crypto_sleeve": compute_metrics(curves["crypto_sleeve"]),
        "equity_sleeve": compute_metrics(curves["equity_sleeve"]),
        "itera_multi_asset": compute_metrics(curves["itera_multi_asset"]),
    }

    print("\n" + "=" * 108)
    print("  ITERA MULTI-ASSET PORTFOLIO — Research Blend")
    print(f"  Period:  {str(common_index[0])[:10]} → {str(common_index[-1])[:10]}  ({len(common_index)} daily bars)")
    print(f"  Capital: ${args.capital:,.0f}  |  Crypto {crypto_weight:.0%} / Equity {equity_weight:.0%}")
    print("=" * 108)

    print("\n  PERFORMANCE")
    print("  " + "-" * 98)
    print(f"  {'Series':<20} {'TotRet':>10} {'CAGR':>10} {'MaxDD':>10} {'Sharpe':>8} {'Calmar':>8} {'AnnVol':>10} {'Corr':>7}")
    print("  " + "-" * 98)
    print_metrics("Crypto Sleeve", metrics["crypto_sleeve"], corr_combined_crypto)
    print_metrics("Equity Sleeve", metrics["equity_sleeve"], corr_combined_equity)
    print_metrics("Itera Multi-Asset", metrics["itera_multi_asset"], None)

    print("\n  DIVERSIFICATION")
    print("  " + "-" * 60)
    print(f"  Daily return corr — Crypto vs Equity: {corr_crypto_equity:+.4f}")

    print("\n  DELTA vs CRYPTO SLEEVE")
    print("  " + "-" * 60)
    c = metrics["crypto_sleeve"]
    p = metrics["itera_multi_asset"]
    print(f"  CAGR   {p.cagr_pct - c.cagr_pct:+.2f}%")
    print(f"  MaxDD  {p.max_drawdown_pct - c.max_drawdown_pct:+.2f}%")
    print(f"  Sharpe {p.sharpe - c.sharpe:+.3f}")
    print(f"  Calmar {p.calmar - c.calmar:+.3f}")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    curves.to_csv(out / "equity_curves.csv")
    daily_returns.to_csv(out / "daily_returns.csv")

    summary = {
        "capital": args.capital,
        "crypto_weight": crypto_weight,
        "equity_weight": equity_weight,
        "start": str(common_index[0]),
        "end": str(common_index[-1]),
        "daily_bars": len(common_index),
        "correlation_crypto_equity": corr_crypto_equity,
        "correlation_combined_crypto": corr_combined_crypto,
        "correlation_combined_equity": corr_combined_equity,
        "metrics": {k: asdict(v) for k, v in metrics.items()},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("\n" + "=" * 108)
    print(f"  Artifacts saved to: {out}")
    print("    equity_curves.csv  daily_returns.csv  summary.json")
    print("=" * 108)


if __name__ == "__main__":
    main()
