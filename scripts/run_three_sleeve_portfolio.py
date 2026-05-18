#!/usr/bin/env python
"""Itera Dynamics — Three-Sleeve Portfolio Research Runner.

Combines:
    - Crypto Sleeve v1 equity curve
    - SPY defensive Equity Sleeve v1 equity curve
    - QQQ growth Equity Sleeve v1/b equity curve

Purpose:
    Test whether QQQ adds useful portfolio-level diversification or growth when
    added as a third sleeve to the existing Itera Fund v0 static baseline.

Outputs:
    artifacts/three_sleeve_portfolio/
        equity_curves.csv
        daily_returns.csv
        allocation_sweep.csv
        summary.json
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


def load_curve(path: str, preferred_columns: list[str]) -> pd.Series:
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty curve file: {path}")

    ts = df.columns[0]
    df[ts] = pd.to_datetime(df[ts])
    df = df.set_index(ts).sort_index()
    df.index = df.index.tz_localize(None) if getattr(df.index, "tz", None) is not None else df.index

    for col in preferred_columns:
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce").dropna().astype(float)

    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if not numeric:
        raise ValueError(f"No numeric columns found in {path}. Columns={list(df.columns)}")
    return pd.to_numeric(df[numeric[0]], errors="coerce").dropna().astype(float)


def to_daily(curve: pd.Series) -> pd.Series:
    return curve.resample("1D").last().dropna()


def normalize(curve: pd.Series) -> pd.Series:
    if curve.iloc[0] <= 0:
        raise ValueError("Cannot normalize curve starting <= 0")
    return curve / curve.iloc[0]


def compute_metrics(equity: pd.Series) -> Metrics:
    equity = equity.dropna().astype(float)
    returns = equity.pct_change().dropna()
    if len(equity) < 2:
        return Metrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0
    dd = equity / equity.cummax() - 1.0
    max_dd = float(dd.min())

    if len(returns) and returns.std(ddof=0) > 0:
        ann_vol = float(returns.std(ddof=0) * math.sqrt(TRADING_DAYS_PER_YEAR))
        sharpe = float((returns.mean() / returns.std(ddof=0)) * math.sqrt(TRADING_DAYS_PER_YEAR))
    else:
        ann_vol = 0.0
        sharpe = 0.0

    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0
    return Metrics(total_return * 100, cagr * 100, max_dd * 100, sharpe, calmar, ann_vol * 100)


def blend_curves(
    crypto: pd.Series,
    spy: pd.Series,
    qqq: pd.Series,
    capital: float,
    crypto_weight: float,
    spy_weight: float,
    qqq_weight: float,
) -> pd.DataFrame:
    total = crypto_weight + spy_weight + qqq_weight
    if total <= 0:
        raise ValueError("Weights must sum to > 0")

    cw = crypto_weight / total
    sw = spy_weight / total
    qw = qqq_weight / total

    curves = pd.DataFrame({
        "crypto_sleeve": normalize(crypto) * capital * cw,
        "spy_sleeve": normalize(spy) * capital * sw,
        "qqq_sleeve": normalize(qqq) * capital * qw,
    })
    curves["itera_three_sleeve"] = curves.sum(axis=1)
    return curves


def print_metrics(label: str, m: Metrics) -> None:
    print(
        f"  {label:<20}"
        f" {m.total_return_pct:>9.2f}%"
        f" {m.cagr_pct:>9.2f}%"
        f" {m.max_drawdown_pct:>9.2f}%"
        f" {m.sharpe:>8.3f}"
        f" {m.calmar:>8.3f}"
        f" {m.ann_vol_pct:>9.2f}%"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Run 3-sleeve Itera portfolio blend")
    p.add_argument("--crypto-equity", required=True)
    p.add_argument("--spy-equity", required=True)
    p.add_argument("--qqq-equity", required=True)
    p.add_argument("--capital", type=float, default=100000)
    p.add_argument("--crypto-weight", type=float, default=0.60)
    p.add_argument("--spy-weight", type=float, default=0.25)
    p.add_argument("--qqq-weight", type=float, default=0.15)
    p.add_argument("--sweep", action="store_true")
    p.add_argument("--out-dir", default="artifacts/three_sleeve_portfolio")
    args = p.parse_args()

    crypto = to_daily(load_curve(args.crypto_equity, ["portfolio", "equity", "portfolio_equity", "strategy_equity"]))
    spy = to_daily(load_curve(args.spy_equity, ["strategy_equity", "equity", "portfolio"]))
    qqq = to_daily(load_curve(args.qqq_equity, ["strategy_equity", "equity", "portfolio"]))

    common = crypto.index.intersection(spy.index).intersection(qqq.index)
    if len(common) < 30:
        raise SystemExit(f"Insufficient overlap across sleeves: {len(common)} daily bars")

    crypto = crypto.loc[common]
    spy = spy.loc[common]
    qqq = qqq.loc[common]

    curves = blend_curves(
        crypto,
        spy,
        qqq,
        args.capital,
        args.crypto_weight,
        args.spy_weight,
        args.qqq_weight,
    )
    returns = curves.pct_change().dropna()

    metrics = {
        "crypto_sleeve": compute_metrics(curves["crypto_sleeve"]),
        "spy_sleeve": compute_metrics(curves["spy_sleeve"]),
        "qqq_sleeve": compute_metrics(curves["qqq_sleeve"]),
        "itera_three_sleeve": compute_metrics(curves["itera_three_sleeve"]),
    }

    print("\n" + "=" * 108)
    print("  ITERA THREE-SLEEVE PORTFOLIO — Static Research Blend")
    print(f"  Period:  {str(common[0])[:10]} → {str(common[-1])[:10]}  ({len(common)} daily bars)")
    print(
        f"  Capital: ${args.capital:,.0f}  |  "
        f"Crypto {args.crypto_weight:.0%} / SPY {args.spy_weight:.0%} / QQQ {args.qqq_weight:.0%}"
    )
    print("=" * 108)

    print("\n  PERFORMANCE")
    print("  " + "-" * 88)
    print(f"  {'Series':<20} {'TotRet':>10} {'CAGR':>10} {'MaxDD':>10} {'Sharpe':>8} {'Calmar':>8} {'AnnVol':>10}")
    print("  " + "-" * 88)
    print_metrics("Crypto Sleeve", metrics["crypto_sleeve"])
    print_metrics("SPY Sleeve", metrics["spy_sleeve"])
    print_metrics("QQQ Sleeve", metrics["qqq_sleeve"])
    print_metrics("Itera 3-Sleeve", metrics["itera_three_sleeve"])

    corr = pd.DataFrame({
        "crypto": normalize(crypto).pct_change(),
        "spy": normalize(spy).pct_change(),
        "qqq": normalize(qqq).pct_change(),
    }).dropna().corr()

    print("\n  DAILY RETURN CORRELATION")
    print("  " + "-" * 52)
    print(corr.to_string(float_format=lambda x: f"{x: .3f}"))

    sweep_rows: list[dict] = []
    if args.sweep:
        print("\n  ALLOCATION SWEEP")
        print("  " + "-" * 118)
        print(f"  {'Crypto':>7} {'SPY':>7} {'QQQ':>7} {'TotRet':>10} {'CAGR':>10} {'MaxDD':>10} {'Sharpe':>8} {'Calmar':>8} {'AnnVol':>10}")
        print("  " + "-" * 118)

        candidates = [
            (0.70, 0.30, 0.00),
            (0.65, 0.25, 0.10),
            (0.60, 0.25, 0.15),
            (0.60, 0.20, 0.20),
            (0.55, 0.25, 0.20),
            (0.50, 0.30, 0.20),
            (0.50, 0.25, 0.25),
            (0.50, 0.20, 0.30),
            (0.40, 0.40, 0.20),
        ]
        for cw, sw, qw in candidates:
            c = blend_curves(crypto, spy, qqq, args.capital, cw, sw, qw)
            m = compute_metrics(c["itera_three_sleeve"])
            row = {
                "crypto_weight": cw,
                "spy_weight": sw,
                "qqq_weight": qw,
                **asdict(m),
            }
            sweep_rows.append(row)
            print(
                f"  {cw:>6.0%} {sw:>6.0%} {qw:>6.0%}"
                f" {m.total_return_pct:>9.2f}%"
                f" {m.cagr_pct:>9.2f}%"
                f" {m.max_drawdown_pct:>9.2f}%"
                f" {m.sharpe:>8.3f}"
                f" {m.calmar:>8.3f}"
                f" {m.ann_vol_pct:>9.2f}%"
            )

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    curves.to_csv(out / "equity_curves.csv")
    returns.to_csv(out / "daily_returns.csv")
    if sweep_rows:
        pd.DataFrame(sweep_rows).to_csv(out / "allocation_sweep.csv", index=False)

    summary = {
        "capital": args.capital,
        "crypto_weight": args.crypto_weight,
        "spy_weight": args.spy_weight,
        "qqq_weight": args.qqq_weight,
        "start": str(common[0]),
        "end": str(common[-1]),
        "daily_bars": len(common),
        "metrics": {k: asdict(v) for k, v in metrics.items()},
        "correlation": corr.to_dict(),
        "allocation_sweep": sweep_rows,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("\n" + "=" * 108)
    print(f"  Artifacts saved to: {out}")
    artifacts = "    equity_curves.csv  daily_returns.csv  summary.json"
    if sweep_rows:
        artifacts += "  allocation_sweep.csv"
    print(artifacts)
    print("=" * 108)


if __name__ == "__main__":
    main()
