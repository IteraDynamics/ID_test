#!/usr/bin/env python
"""Itera Allocator v1 Backtest Runner.

Runs a dynamic allocation backtest using:
    - Crypto Sleeve v1 equity curve
    - Equity Sleeve v1 equity curve
    - Itera Allocator v1

Important accounting rule:
    Portfolio NAV evolves from realized daily returns using yesterday's weights:

        nav[t] = nav[t-1] * (1 + w_crypto[t-1] * r_crypto[t]
                               + w_equity[t-1]  * r_equity[t])

    New weights are decided after the close using data through t and apply to the
    next day's returns. This avoids same-day lookahead and avoids revaluing the
    entire historical index at newly chosen weights.
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

from research.allocators.itera_allocator_v1 import decide_weights

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
    ts_col = df.columns[0]
    df[ts_col] = pd.to_datetime(df[ts_col])
    df = df.set_index(ts_col).sort_index()
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

    return pd.to_numeric(df[selected], errors="coerce").dropna().astype(float)


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


def run_static_blend(crypto_rets: pd.Series, equity_rets: pd.Series, capital: float, crypto_weight: float) -> pd.Series:
    equity_weight = 1.0 - crypto_weight
    nav = [capital]
    index = [crypto_rets.index[0]]

    for ts in crypto_rets.index[1:]:
        port_ret = crypto_weight * crypto_rets.loc[ts] + equity_weight * equity_rets.loc[ts]
        nav.append(nav[-1] * (1.0 + port_ret))
        index.append(ts)

    return pd.Series(nav, index=index, name=f"static_{int(crypto_weight * 100)}_{int(equity_weight * 100)}")


def run_allocator(crypto_curve: pd.Series, equity_curve: pd.Series, capital: float):
    crypto_rets = crypto_curve.pct_change().fillna(0.0)
    equity_rets = equity_curve.pct_change().fillna(0.0)

    nav = [capital]
    index = [crypto_curve.index[0]]
    rows = []

    current_crypto_w = 0.70
    current_equity_w = 0.30

    rows.append({
        "timestamp": crypto_curve.index[0],
        "nav": capital,
        "crypto_weight_applied": current_crypto_w,
        "equity_weight_applied": current_equity_w,
        "crypto_weight_next": current_crypto_w,
        "equity_weight_next": current_equity_w,
        "crypto_score": 0.0,
        "equity_score": 0.0,
        "reason": "initial allocation",
        "portfolio_return": 0.0,
        "crypto_return": 0.0,
        "equity_return": 0.0,
    })

    for i in range(1, len(crypto_curve)):
        ts = crypto_curve.index[i]

        # Today's return is earned with weights chosen at yesterday's close.
        port_ret = current_crypto_w * crypto_rets.iloc[i] + current_equity_w * equity_rets.iloc[i]
        new_nav = nav[-1] * (1.0 + port_ret)
        nav.append(new_nav)
        index.append(ts)

        # Decide next weights using information available through today's close.
        decision = decide_weights(
            crypto_curve.iloc[: i + 1],
            equity_curve.iloc[: i + 1],
            current_crypto_weight=current_crypto_w,
        )

        rows.append({
            "timestamp": ts,
            "nav": new_nav,
            "crypto_weight_applied": current_crypto_w,
            "equity_weight_applied": current_equity_w,
            "crypto_weight_next": decision.crypto_weight,
            "equity_weight_next": decision.equity_weight,
            "crypto_score": decision.crypto_score,
            "equity_score": decision.equity_score,
            "reason": decision.reason,
            "portfolio_return": port_ret,
            "crypto_return": crypto_rets.iloc[i],
            "equity_return": equity_rets.iloc[i],
        })

        current_crypto_w = decision.crypto_weight
        current_equity_w = decision.equity_weight

    return pd.Series(nav, index=index, name="allocator_v1"), pd.DataFrame(rows).set_index("timestamp")


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
    p = argparse.ArgumentParser(description="Run Itera Allocator v1 dynamic allocation backtest")
    p.add_argument("--crypto-equity", required=True)
    p.add_argument("--equity-equity", required=True)
    p.add_argument("--capital", type=float, default=100000)
    p.add_argument("--out-dir", default="artifacts/allocator_v1")
    args = p.parse_args()

    crypto = load_curve(args.crypto_equity, ["portfolio", "equity", "portfolio_equity"]).resample("1D").last().dropna()
    equity = load_curve(args.equity_equity, ["strategy_equity", "equity"]).resample("1D").last().dropna()

    idx = crypto.index.intersection(equity.index)
    if len(idx) < 30:
        raise SystemExit(f"Insufficient overlap: {len(idx)} daily bars")

    crypto = crypto.loc[idx]
    equity = equity.loc[idx]

    # Normalize each sleeve to index-level returns. NAV accounting happens below.
    crypto_idx = crypto / crypto.iloc[0]
    equity_idx = equity / equity.iloc[0]

    allocator_nav, decisions = run_allocator(crypto_idx, equity_idx, args.capital)

    crypto_rets = crypto_idx.pct_change().fillna(0.0)
    equity_rets = equity_idx.pct_change().fillna(0.0)
    static_70_30 = run_static_blend(crypto_rets, equity_rets, args.capital, 0.70)
    static_60_40 = run_static_blend(crypto_rets, equity_rets, args.capital, 0.60)
    static_50_50 = run_static_blend(crypto_rets, equity_rets, args.capital, 0.50)

    metrics = {
        "allocator_v1": compute_metrics(allocator_nav),
        "static_70_30": compute_metrics(static_70_30),
        "static_60_40": compute_metrics(static_60_40),
        "static_50_50": compute_metrics(static_50_50),
    }

    weight_switches = int((decisions["crypto_weight_next"].diff().abs() > 1e-9).sum())
    avg_crypto_weight = float(decisions["crypto_weight_applied"].mean())

    print("\n" + "=" * 98)
    print("  ITERA ALLOCATOR v1 — Dynamic Allocation Backtest")
    print(f"  Period:  {str(idx[0])[:10]} → {str(idx[-1])[:10]}  ({len(idx)} daily bars)")
    print(f"  Capital: ${args.capital:,.0f}")
    print("=" * 98)

    print("\n  PERFORMANCE")
    print("  " + "-" * 86)
    print(f"  {'Series':<18} {'TotRet':>10} {'CAGR':>10} {'MaxDD':>10} {'Sharpe':>8} {'Calmar':>8} {'AnnVol':>10}")
    print("  " + "-" * 86)
    print_metrics("Allocator v1", metrics["allocator_v1"])
    print_metrics("Static 70/30", metrics["static_70_30"])
    print_metrics("Static 60/40", metrics["static_60_40"])
    print_metrics("Static 50/50", metrics["static_50_50"])

    base = metrics["static_70_30"]
    dyn = metrics["allocator_v1"]
    print("\n  DELTA vs STATIC 70/30")
    print("  " + "-" * 48)
    print(f"  CAGR   {dyn.cagr_pct - base.cagr_pct:+.2f}%")
    print(f"  MaxDD  {dyn.max_drawdown_pct - base.max_drawdown_pct:+.2f}%")
    print(f"  Sharpe {dyn.sharpe - base.sharpe:+.3f}")
    print(f"  Calmar {dyn.calmar - base.calmar:+.3f}")

    print("\n  ALLOCATOR ACTIVITY")
    print("  " + "-" * 48)
    print(f"  Avg crypto weight: {avg_crypto_weight:.1%}")
    print(f"  Weight switches:    {weight_switches}")
    print("  Weight distribution:")
    for weight, count in decisions["crypto_weight_applied"].round(2).value_counts().sort_index().items():
        print(f"    Crypto {weight:.0%}: {count} days")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    curves = pd.DataFrame({
        "allocator_v1": allocator_nav,
        "static_70_30": static_70_30,
        "static_60_40": static_60_40,
        "static_50_50": static_50_50,
    })
    curves.to_csv(out / "allocator_v1_equity.csv")
    decisions.to_csv(out / "allocator_v1_decisions.csv")

    summary = {
        "start": str(idx[0]),
        "end": str(idx[-1]),
        "daily_bars": len(idx),
        "capital": args.capital,
        "avg_crypto_weight": avg_crypto_weight,
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
    print("    allocator_v1_equity.csv  allocator_v1_decisions.csv  summary.json")
    print("=" * 98)


if __name__ == "__main__":
    main()
