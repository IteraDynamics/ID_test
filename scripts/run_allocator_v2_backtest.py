#!/usr/bin/env python
"""Itera Allocator v2 Backtest Runner (Defensive Overlay).

Dynamic allocation using a defensive overlay on top of a static baseline.

Outputs:
    artifacts/allocator_v2/
        allocator_v2_equity.csv
        allocator_v2_decisions.csv
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

from research.allocators.itera_allocator_v2 import decide_defensive_weights

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class Metrics:
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    sharpe: float
    calmar: float
    ann_vol_pct: float


def load_curve(path: str, col_candidates: list[str]) -> pd.Series:
    df = pd.read_csv(path)
    ts = df.columns[0]
    df[ts] = pd.to_datetime(df[ts])
    df = df.set_index(ts).sort_index()
    df.index = df.index.tz_localize(None) if getattr(df.index, "tz", None) is not None else df.index

    for c in col_candidates:
        if c in df.columns:
            return pd.to_numeric(df[c], errors="coerce").dropna().astype(float)

    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if not num_cols:
        raise ValueError(f"No numeric equity column found in {path}. Columns: {list(df.columns)}")
    return pd.to_numeric(df[num_cols[0]], errors="coerce").dropna().astype(float)


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
    return Metrics(total_return * 100, cagr * 100, max_dd * 100, sharpe, calmar, ann_vol * 100)


def run_static_blend(crypto_ret: pd.Series, equity_ret: pd.Series, capital: float, crypto_weight: float) -> pd.Series:
    nav = [capital]
    index = [crypto_ret.index[0]]
    equity_weight = 1.0 - crypto_weight
    for ts in crypto_ret.index[1:]:
        r = crypto_weight * crypto_ret.loc[ts] + equity_weight * equity_ret.loc[ts]
        nav.append(nav[-1] * (1.0 + r))
        index.append(ts)
    return pd.Series(nav, index=index, name=f"static_{int(crypto_weight*100)}_{int(equity_weight*100)}")


def run_allocator_v2(crypto: pd.Series, equity: pd.Series, capital: float):
    crypto_ret = crypto.pct_change().fillna(0.0)
    equity_ret = equity.pct_change().fillna(0.0)

    nav = [capital]
    index = [crypto.index[0]]
    rows = []

    defensive = False
    defensive_days = 0
    w_crypto = 0.70
    w_equity = 0.30

    rows.append({
        "timestamp": crypto.index[0],
        "nav": capital,
        "crypto_weight_applied": w_crypto,
        "equity_weight_applied": w_equity,
        "crypto_weight_next": w_crypto,
        "equity_weight_next": w_equity,
        "defensive_state": defensive,
        "defensive_days": defensive_days,
        "crypto_drawdown": 0.0,
        "crypto_trend_score": 0.0,
        "equity_trend_score": 0.0,
        "portfolio_return": 0.0,
        "crypto_return": 0.0,
        "equity_return": 0.0,
        "reason": "initial allocation",
    })

    for i in range(1, len(crypto.index)):
        ts = crypto.index[i]

        # Earn today's return with weights selected at yesterday's close.
        port_ret = w_crypto * crypto_ret.iloc[i] + w_equity * equity_ret.iloc[i]
        nav_new = nav[-1] * (1.0 + port_ret)
        nav.append(nav_new)
        index.append(ts)

        decision = decide_defensive_weights(
            crypto.iloc[: i + 1],
            equity.iloc[: i + 1],
            current_defensive_state=defensive,
            defensive_days=defensive_days,
        )

        next_defensive = decision.defensive_state
        next_defensive_days = defensive_days + 1 if next_defensive else 0

        rows.append({
            "timestamp": ts,
            "nav": nav_new,
            "crypto_weight_applied": w_crypto,
            "equity_weight_applied": w_equity,
            "crypto_weight_next": decision.crypto_weight,
            "equity_weight_next": decision.equity_weight,
            "defensive_state": next_defensive,
            "defensive_days": next_defensive_days,
            "crypto_drawdown": decision.crypto_drawdown,
            "crypto_trend_score": decision.crypto_trend_score,
            "equity_trend_score": decision.equity_trend_score,
            "portfolio_return": port_ret,
            "crypto_return": crypto_ret.iloc[i],
            "equity_return": equity_ret.iloc[i],
            "reason": decision.reason,
        })

        defensive = next_defensive
        defensive_days = next_defensive_days
        w_crypto = decision.crypto_weight
        w_equity = decision.equity_weight

    return pd.Series(nav, index=index, name="allocator_v2"), pd.DataFrame(rows).set_index("timestamp")


def print_metrics(label: str, m: Metrics) -> None:
    print(
        f"  {label:<18}"
        f" {m.total_return_pct:>9.2f}%"
        f" {m.cagr_pct:>9.2f}%"
        f" {m.max_drawdown_pct:>9.2f}%"
        f" {m.sharpe:>8.3f}"
        f" {m.calmar:>8.3f}"
        f" {m.ann_vol_pct:>9.2f}%"
    )


def main():
    p = argparse.ArgumentParser(description="Run Itera Allocator v2 defensive overlay backtest")
    p.add_argument("--crypto-equity", required=True)
    p.add_argument("--equity-equity", required=True)
    p.add_argument("--capital", type=float, default=100000)
    p.add_argument("--out-dir", default="artifacts/allocator_v2")
    args = p.parse_args()

    crypto_raw = load_curve(args.crypto_equity, ["portfolio", "equity", "portfolio_equity"]).resample("1D").last().dropna()
    equity_raw = load_curve(args.equity_equity, ["strategy_equity", "equity"]).resample("1D").last().dropna()

    idx = crypto_raw.index.intersection(equity_raw.index)
    if len(idx) < 30:
        raise SystemExit(f"Insufficient overlap: {len(idx)} daily bars")

    crypto = crypto_raw.loc[idx] / crypto_raw.loc[idx].iloc[0]
    equity = equity_raw.loc[idx] / equity_raw.loc[idx].iloc[0]

    allocator_nav, decisions = run_allocator_v2(crypto, equity, args.capital)

    crypto_ret = crypto.pct_change().fillna(0.0)
    equity_ret = equity.pct_change().fillna(0.0)
    static_70_30 = run_static_blend(crypto_ret, equity_ret, args.capital, 0.70)
    static_60_40 = run_static_blend(crypto_ret, equity_ret, args.capital, 0.60)
    static_50_50 = run_static_blend(crypto_ret, equity_ret, args.capital, 0.50)

    metrics = {
        "allocator_v2": compute_metrics(allocator_nav),
        "static_70_30": compute_metrics(static_70_30),
        "static_60_40": compute_metrics(static_60_40),
        "static_50_50": compute_metrics(static_50_50),
    }

    defensive_days_count = int(decisions["defensive_state"].sum())
    weight_switches = int((decisions["crypto_weight_next"].diff().abs() > 1e-9).sum())
    avg_crypto_weight = float(decisions["crypto_weight_applied"].mean())

    print("\n" + "=" * 98)
    print("  ITERA ALLOCATOR v2 — Defensive Overlay Backtest")
    print(f"  Period:  {str(idx[0])[:10]} → {str(idx[-1])[:10]}  ({len(idx)} daily bars)")
    print(f"  Capital: ${args.capital:,.0f}")
    print("=" * 98)

    print("\n  PERFORMANCE")
    print("  " + "-" * 86)
    print(f"  {'Series':<18} {'TotRet':>10} {'CAGR':>10} {'MaxDD':>10} {'Sharpe':>8} {'Calmar':>8} {'AnnVol':>10}")
    print("  " + "-" * 86)
    print_metrics("Allocator v2", metrics["allocator_v2"])
    print_metrics("Static 70/30", metrics["static_70_30"])
    print_metrics("Static 60/40", metrics["static_60_40"])
    print_metrics("Static 50/50", metrics["static_50_50"])

    base = metrics["static_70_30"]
    dyn = metrics["allocator_v2"]
    print("\n  DELTA vs STATIC 70/30")
    print("  " + "-" * 48)
    print(f"  CAGR   {dyn.cagr_pct - base.cagr_pct:+.2f}%")
    print(f"  MaxDD  {dyn.max_drawdown_pct - base.max_drawdown_pct:+.2f}%")
    print(f"  Sharpe {dyn.sharpe - base.sharpe:+.3f}")
    print(f"  Calmar {dyn.calmar - base.calmar:+.3f}")

    print("\n  DEFENSIVE ACTIVITY")
    print("  " + "-" * 48)
    print(f"  Avg crypto weight: {avg_crypto_weight:.1%}")
    print(f"  Defensive days:    {defensive_days_count} ({defensive_days_count / len(decisions):.1%})")
    print(f"  Weight switches:   {weight_switches}")
    print("  Weight distribution:")
    for weight, count in decisions["crypto_weight_applied"].round(2).value_counts().sort_index().items():
        print(f"    Crypto {weight:.0%}: {count} days")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    curves = pd.DataFrame({
        "allocator_v2": allocator_nav,
        "static_70_30": static_70_30,
        "static_60_40": static_60_40,
        "static_50_50": static_50_50,
    })
    curves.to_csv(out / "allocator_v2_equity.csv")
    decisions.to_csv(out / "allocator_v2_decisions.csv")

    summary = {
        "start": str(idx[0]),
        "end": str(idx[-1]),
        "daily_bars": len(idx),
        "capital": args.capital,
        "avg_crypto_weight": avg_crypto_weight,
        "defensive_days": defensive_days_count,
        "defensive_days_pct": defensive_days_count / len(decisions),
        "weight_switches": weight_switches,
        "metrics": {k: asdict(v) for k, v in metrics.items()},
        "delta_vs_static_70_30": {
            "cagr_pct": dyn.cagr_pct - base.cagr_pct,
            "max_drawdown_pct": dyn.max_drawdown_pct - base.max_drawdown_pct,
            "sharpe": dyn.sharpe - base.sharpe,
            "calmar": dyn.calmar - base.calmar,
        },
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("\n" + "=" * 98)
    print(f"  Artifacts saved to: {out}")
    print("    allocator_v2_equity.csv  allocator_v2_decisions.csv  summary.json")
    print("=" * 98)


if __name__ == "__main__":
    main()
