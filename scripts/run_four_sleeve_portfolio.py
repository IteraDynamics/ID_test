#!/usr/bin/env python
"""Itera Dynamics — Four-Sleeve Portfolio Research Runner.

Combines:
    - Crypto Sleeve v1 equity curve
    - SPY defensive Equity Sleeve v1 equity curve
    - QQQ growth Equity Sleeve v1b equity curve
    - Short-vol carry sleeve equity curve

Supports optional one-time vol-sleeve shock testing.
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


def apply_vol_shock(vol_curve: pd.Series, shock_pct: float | None, shock_date: str | None = None) -> tuple[pd.Series, str | None]:
    """Apply a one-time permanent level shock to the vol sleeve curve.

    Example: shock_pct=-0.70 means vol sleeve loses 70% on the shock date and
    remains rebased from that lower level thereafter.
    """
    if shock_pct is None:
        return vol_curve, None
    if shock_pct >= 0 or shock_pct <= -1:
        raise ValueError("--shock-pct must be between -1 and 0, e.g. -0.5")

    shocked = vol_curve.copy().astype(float)
    if shock_date:
        ts = pd.Timestamp(shock_date)
        eligible = shocked.index[shocked.index >= ts]
        if len(eligible) == 0:
            raise ValueError(f"No vol data on/after shock date {shock_date}")
        shock_ts = eligible[0]
    else:
        shock_ts = shocked.index[len(shocked) // 2]

    shocked.loc[shock_ts:] = shocked.loc[shock_ts:] * (1.0 + shock_pct)
    return shocked, str(shock_ts)[:10]


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
    vol: pd.Series,
    capital: float,
    crypto_weight: float,
    spy_weight: float,
    qqq_weight: float,
    vol_weight: float,
) -> pd.DataFrame:
    total = crypto_weight + spy_weight + qqq_weight + vol_weight
    if total <= 0:
        raise ValueError("Weights must sum to > 0")

    cw = crypto_weight / total
    sw = spy_weight / total
    qw = qqq_weight / total
    vw = vol_weight / total

    curves = pd.DataFrame({
        "crypto_sleeve": normalize(crypto) * capital * cw,
        "spy_sleeve": normalize(spy) * capital * sw,
        "qqq_sleeve": normalize(qqq) * capital * qw,
        "vol_sleeve": normalize(vol) * capital * vw,
    })
    curves["itera_four_sleeve"] = curves.sum(axis=1)
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
    p = argparse.ArgumentParser(description="Run 4-sleeve Itera portfolio blend")
    p.add_argument("--crypto-equity", required=True)
    p.add_argument("--spy-equity", required=True)
    p.add_argument("--qqq-equity", required=True)
    p.add_argument("--vol-equity", required=True)
    p.add_argument("--capital", type=float, default=100000)
    p.add_argument("--crypto-weight", type=float, default=0.55)
    p.add_argument("--spy-weight", type=float, default=0.20)
    p.add_argument("--qqq-weight", type=float, default=0.15)
    p.add_argument("--vol-weight", type=float, default=0.10)
    p.add_argument("--shock-pct", type=float, default=None, help="Optional one-time vol sleeve shock, e.g. -0.5, -0.7, -0.9")
    p.add_argument("--shock-date", default=None, help="Optional shock date. Defaults to midpoint of common window.")
    p.add_argument("--sweep", action="store_true")
    p.add_argument("--out-dir", default="artifacts/four_sleeve_portfolio")
    args = p.parse_args()

    crypto = to_daily(load_curve(args.crypto_equity, ["portfolio", "equity", "portfolio_equity", "strategy_equity"]))
    spy = to_daily(load_curve(args.spy_equity, ["strategy_equity", "equity", "portfolio"]))
    qqq = to_daily(load_curve(args.qqq_equity, ["strategy_equity", "equity", "portfolio"]))
    vol = to_daily(load_curve(args.vol_equity, ["strategy_equity", "equity", "portfolio"]))

    common = crypto.index.intersection(spy.index).intersection(qqq.index).intersection(vol.index)
    if len(common) < 30:
        raise SystemExit(f"Insufficient overlap across sleeves: {len(common)} daily bars")

    crypto = crypto.loc[common]
    spy = spy.loc[common]
    qqq = qqq.loc[common]
    vol = vol.loc[common]
    vol, actual_shock_date = apply_vol_shock(vol, args.shock_pct, args.shock_date)

    curves = blend_curves(
        crypto,
        spy,
        qqq,
        vol,
        args.capital,
        args.crypto_weight,
        args.spy_weight,
        args.qqq_weight,
        args.vol_weight,
    )
    returns = curves.pct_change().dropna()

    metrics = {
        "crypto_sleeve": compute_metrics(curves["crypto_sleeve"]),
        "spy_sleeve": compute_metrics(curves["spy_sleeve"]),
        "qqq_sleeve": compute_metrics(curves["qqq_sleeve"]),
        "vol_sleeve": compute_metrics(curves["vol_sleeve"]),
        "itera_four_sleeve": compute_metrics(curves["itera_four_sleeve"]),
    }

    print("\n" + "=" * 112)
    title = "ITERA FOUR-SLEEVE PORTFOLIO — Static Research Blend"
    if args.shock_pct is not None:
        title += f" | VOL SHOCK {args.shock_pct:.0%} on {actual_shock_date}"
    print(f"  {title}")
    print(f"  Period:  {str(common[0])[:10]} → {str(common[-1])[:10]}  ({len(common)} daily bars)")
    print(
        f"  Capital: ${args.capital:,.0f}  |  "
        f"Crypto {args.crypto_weight:.0%} / SPY {args.spy_weight:.0%} / "
        f"QQQ {args.qqq_weight:.0%} / Vol {args.vol_weight:.0%}"
    )
    print("=" * 112)

    print("\n  PERFORMANCE")
    print("  " + "-" * 88)
    print(f"  {'Series':<20} {'TotRet':>10} {'CAGR':>10} {'MaxDD':>10} {'Sharpe':>8} {'Calmar':>8} {'AnnVol':>10}")
    print("  " + "-" * 88)
    print_metrics("Crypto Sleeve", metrics["crypto_sleeve"])
    print_metrics("SPY Sleeve", metrics["spy_sleeve"])
    print_metrics("QQQ Sleeve", metrics["qqq_sleeve"])
    print_metrics("Vol Sleeve", metrics["vol_sleeve"])
    print_metrics("Itera 4-Sleeve", metrics["itera_four_sleeve"])

    corr = pd.DataFrame({
        "crypto": normalize(crypto).pct_change(),
        "spy": normalize(spy).pct_change(),
        "qqq": normalize(qqq).pct_change(),
        "vol": normalize(vol).pct_change(),
    }).dropna().corr()

    print("\n  DAILY RETURN CORRELATION")
    print("  " + "-" * 64)
    print(corr.to_string(float_format=lambda x: f"{x: .3f}"))

    sweep_rows: list[dict] = []
    if args.sweep:
        print("\n  ALLOCATION SWEEP")
        print("  " + "-" * 128)
        print(f"  {'Crypto':>7} {'SPY':>7} {'QQQ':>7} {'Vol':>7} {'TotRet':>10} {'CAGR':>10} {'MaxDD':>10} {'Sharpe':>8} {'Calmar':>8} {'AnnVol':>10}")
        print("  " + "-" * 128)

        candidates = [
            (0.70, 0.30, 0.00, 0.00),
            (0.60, 0.20, 0.20, 0.00),
            (0.60, 0.20, 0.15, 0.05),
            (0.55, 0.20, 0.15, 0.10),
            (0.50, 0.25, 0.15, 0.10),
            (0.50, 0.20, 0.20, 0.10),
            (0.45, 0.25, 0.20, 0.10),
            (0.45, 0.20, 0.20, 0.15),
            (0.40, 0.30, 0.20, 0.10),
        ]
        for cw, sw, qw, vw in candidates:
            c = blend_curves(crypto, spy, qqq, vol, args.capital, cw, sw, qw, vw)
            m = compute_metrics(c["itera_four_sleeve"])
            row = {
                "crypto_weight": cw,
                "spy_weight": sw,
                "qqq_weight": qw,
                "vol_weight": vw,
                **asdict(m),
            }
            sweep_rows.append(row)
            print(
                f"  {cw:>6.0%} {sw:>6.0%} {qw:>6.0%} {vw:>6.0%}"
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
        "vol_weight": args.vol_weight,
        "shock_pct": args.shock_pct,
        "shock_date": actual_shock_date,
        "start": str(common[0]),
        "end": str(common[-1]),
        "daily_bars": len(common),
        "metrics": {k: asdict(v) for k, v in metrics.items()},
        "correlation": corr.to_dict(),
        "allocation_sweep": sweep_rows,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("\n" + "=" * 112)
    print(f"  Artifacts saved to: {out}")
    artifacts = "    equity_curves.csv  daily_returns.csv  summary.json"
    if sweep_rows:
        artifacts += "  allocation_sweep.csv"
    print(artifacts)
    print("=" * 112)


if __name__ == "__main__":
    main()
