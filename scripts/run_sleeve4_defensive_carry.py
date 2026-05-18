#!/usr/bin/env python
"""Itera Dynamics — Sleeve 4 Defensive Carry Research Runner.

Research-only utility. Compares the current three-sleeve core
(Crypto / SPY / QQQ) against simple Sleeve 4 defensive-carry variants.

Sleeve 4 can be either:
    - synthetic cash / fixed annual carry; or
    - an external equity curve proxy such as SGOV/BIL/SHV.

No runtime, allocator, governor, paper-trading, or execution paths are changed.
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
    worst_90d_return_pct: float
    worst_180d_return_pct: float


@dataclass(frozen=True)
class AllocationCandidate:
    name: str
    crypto_weight: float
    spy_weight: float
    qqq_weight: float
    carry_weight: float


DEFAULT_ALLOCATIONS = [
    AllocationCandidate("core_60_20_20", 0.60, 0.20, 0.20, 0.00),
    AllocationCandidate("carry_55_20_15_10", 0.55, 0.20, 0.15, 0.10),
    AllocationCandidate("carry_50_20_20_10", 0.50, 0.20, 0.20, 0.10),
    AllocationCandidate("carry_50_25_15_10", 0.50, 0.25, 0.15, 0.10),
    AllocationCandidate("carry_45_25_20_10", 0.45, 0.25, 0.20, 0.10),
    AllocationCandidate("carry_55_225_175_5", 0.55, 0.225, 0.175, 0.05),
]


def load_curve(path: str, preferred_columns: list[str]) -> pd.Series:
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Empty curve file: {path}")

    ts = df.columns[0]
    df[ts] = pd.to_datetime(df[ts], errors="coerce")
    df = df.dropna(subset=[ts]).set_index(ts).sort_index()
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
    curve = curve.dropna().astype(float)
    if curve.empty:
        raise ValueError("Cannot normalize empty curve")
    if curve.iloc[0] <= 0:
        raise ValueError("Cannot normalize curve starting <= 0")
    return curve / curve.iloc[0]


def synthetic_carry_curve(index: pd.DatetimeIndex, annual_carry: float) -> pd.Series:
    """Create a smooth daily carry curve with no mark-to-market volatility."""
    if len(index) == 0:
        raise ValueError("Cannot build synthetic carry curve on empty index")
    daily_rate = (1.0 + annual_carry) ** (1.0 / TRADING_DAYS_PER_YEAR) - 1.0
    values = [(1.0 + daily_rate) ** i for i in range(len(index))]
    return pd.Series(values, index=index, name="defensive_carry")


def compute_metrics(equity: pd.Series) -> Metrics:
    equity = equity.dropna().astype(float)
    returns = equity.pct_change().dropna()
    if len(equity) < 2:
        return Metrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

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
    worst_90 = float(equity.pct_change(90).dropna().min()) if len(equity) > 90 else 0.0
    worst_180 = float(equity.pct_change(180).dropna().min()) if len(equity) > 180 else 0.0

    return Metrics(
        total_return * 100.0,
        cagr * 100.0,
        max_dd * 100.0,
        sharpe,
        calmar,
        ann_vol * 100.0,
        worst_90 * 100.0,
        worst_180 * 100.0,
    )


def blend_curves(
    crypto: pd.Series,
    spy: pd.Series,
    qqq: pd.Series,
    carry: pd.Series,
    allocation: AllocationCandidate,
    capital: float,
) -> pd.DataFrame:
    total = allocation.crypto_weight + allocation.spy_weight + allocation.qqq_weight + allocation.carry_weight
    if total <= 0:
        raise ValueError("Allocation weights must sum to > 0")

    cw = allocation.crypto_weight / total
    sw = allocation.spy_weight / total
    qw = allocation.qqq_weight / total
    dw = allocation.carry_weight / total

    curves = pd.DataFrame(
        {
            "crypto_sleeve": normalize(crypto) * capital * cw,
            "spy_sleeve": normalize(spy) * capital * sw,
            "qqq_sleeve": normalize(qqq) * capital * qw,
            "carry_sleeve": normalize(carry) * capital * dw,
        }
    )
    curves["itera_sleeve4_portfolio"] = curves.sum(axis=1)
    return curves


def yearly_returns(equity: pd.Series) -> pd.Series:
    annual = equity.resample("YE").last().pct_change().dropna()
    annual.index = annual.index.year
    return annual


def portfolio_drawdown_periods(equity: pd.Series, top_n: int = 5) -> pd.DataFrame:
    dd = equity / equity.cummax() - 1.0
    rows = []
    in_dd = False
    start = None
    trough = None
    trough_dd = 0.0

    for ts, value in dd.items():
        if value < 0 and not in_dd:
            in_dd = True
            start = ts
            trough = ts
            trough_dd = float(value)
        elif value < 0 and in_dd:
            if value < trough_dd:
                trough = ts
                trough_dd = float(value)
        elif value >= 0 and in_dd:
            rows.append(
                {
                    "start": start,
                    "trough": trough,
                    "recovery": ts,
                    "max_drawdown_pct": trough_dd * 100.0,
                    "days_to_trough": int((trough - start).days) if start is not None and trough is not None else 0,
                    "days_to_recovery": int((ts - start).days) if start is not None else 0,
                }
            )
            in_dd = False
            start = None
            trough = None
            trough_dd = 0.0

    if in_dd:
        rows.append(
            {
                "start": start,
                "trough": trough,
                "recovery": None,
                "max_drawdown_pct": trough_dd * 100.0,
                "days_to_trough": int((trough - start).days) if start is not None and trough is not None else 0,
                "days_to_recovery": None,
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("max_drawdown_pct").head(top_n)


def print_metric_row(label: str, m: Metrics) -> None:
    print(
        f"  {label:<28}"
        f" {m.total_return_pct:>9.2f}%"
        f" {m.cagr_pct:>9.2f}%"
        f" {m.max_drawdown_pct:>9.2f}%"
        f" {m.sharpe:>8.3f}"
        f" {m.calmar:>8.3f}"
        f" {m.ann_vol_pct:>9.2f}%"
        f" {m.worst_90d_return_pct:>10.2f}%"
        f" {m.worst_180d_return_pct:>10.2f}%"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Run Sleeve 4 defensive-carry static allocation research")
    p.add_argument("--crypto-equity", required=True)
    p.add_argument("--spy-equity", required=True)
    p.add_argument("--qqq-equity", required=True)
    p.add_argument("--carry-equity", default=None, help="Optional external defensive-carry/T-bill equity curve")
    p.add_argument("--carry-annual-rate", type=float, default=0.00, help="Synthetic annual carry if --carry-equity is omitted. Example: 0.04")
    p.add_argument("--capital", type=float, default=100000)
    p.add_argument("--out-dir", default="artifacts/sleeve4_defensive_carry_v1")
    args = p.parse_args()

    crypto = to_daily(load_curve(args.crypto_equity, ["portfolio", "equity", "portfolio_equity", "strategy_equity"]))
    spy = to_daily(load_curve(args.spy_equity, ["strategy_equity", "equity", "portfolio"]))
    qqq = to_daily(load_curve(args.qqq_equity, ["strategy_equity", "equity", "portfolio"]))

    common = crypto.index.intersection(spy.index).intersection(qqq.index)
    if len(common) < 252:
        raise SystemExit(f"Insufficient overlap across core sleeves: {len(common)} daily bars")

    crypto = crypto.loc[common]
    spy = spy.loc[common]
    qqq = qqq.loc[common]

    if args.carry_equity:
        carry = to_daily(load_curve(args.carry_equity, ["strategy_equity", "equity", "portfolio", "close", "Close"]))
        common = common.intersection(carry.index)
        if len(common) < 252:
            raise SystemExit(f"Insufficient overlap after adding carry curve: {len(common)} daily bars")
        crypto = crypto.loc[common]
        spy = spy.loc[common]
        qqq = qqq.loc[common]
        carry = carry.loc[common]
        carry_source = args.carry_equity
    else:
        carry = synthetic_carry_curve(common, args.carry_annual_rate)
        carry_source = f"synthetic_cash_carry_{args.carry_annual_rate:.2%}"

    candidate_curves: dict[str, pd.DataFrame] = {}
    summary_rows: list[dict] = []

    for allocation in DEFAULT_ALLOCATIONS:
        curves = blend_curves(crypto, spy, qqq, carry, allocation, args.capital)
        candidate_curves[allocation.name] = curves
        m = compute_metrics(curves["itera_sleeve4_portfolio"])
        summary_rows.append(
            {
                "candidate": allocation.name,
                "crypto_weight": allocation.crypto_weight,
                "spy_weight": allocation.spy_weight,
                "qqq_weight": allocation.qqq_weight,
                "carry_weight": allocation.carry_weight,
                **asdict(m),
            }
        )

    summary = pd.DataFrame(summary_rows)
    benchmark = summary[summary["candidate"] == "core_60_20_20"].iloc[0]
    for col in ["total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar", "ann_vol_pct", "worst_90d_return_pct", "worst_180d_return_pct"]:
        summary[f"delta_{col}"] = summary[col] - float(benchmark[col])

    portfolio_equity = pd.DataFrame(
        {
            name: curves["itera_sleeve4_portfolio"]
            for name, curves in candidate_curves.items()
        }
    )
    daily_returns = portfolio_equity.pct_change().dropna()
    yearly = pd.DataFrame({name: yearly_returns(curve) for name, curve in portfolio_equity.items()})
    corr = pd.DataFrame(
        {
            "crypto": normalize(crypto).pct_change(),
            "spy": normalize(spy).pct_change(),
            "qqq": normalize(qqq).pct_change(),
            "carry": normalize(carry).pct_change(),
        }
    ).dropna().corr()

    drawdowns = []
    for name, curve in portfolio_equity.items():
        dd = portfolio_drawdown_periods(curve)
        if not dd.empty:
            dd.insert(0, "candidate", name)
            drawdowns.append(dd)
    drawdown_summary = pd.concat(drawdowns, ignore_index=True) if drawdowns else pd.DataFrame()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out / "allocation_summary.csv", index=False)
    portfolio_equity.to_csv(out / "portfolio_equity_curves.csv")
    daily_returns.to_csv(out / "portfolio_daily_returns.csv")
    yearly.to_csv(out / "yearly_returns.csv")
    corr.to_csv(out / "sleeve_correlation.csv")
    drawdown_summary.to_csv(out / "top_drawdowns.csv", index=False)

    payload = {
        "research_status": "research_only",
        "inputs": {
            "crypto_equity": args.crypto_equity,
            "spy_equity": args.spy_equity,
            "qqq_equity": args.qqq_equity,
            "carry_source": carry_source,
            "carry_annual_rate": args.carry_annual_rate,
            "capital": args.capital,
        },
        "period": {
            "start": str(common[0]),
            "end": str(common[-1]),
            "daily_bars": int(len(common)),
        },
        "benchmark": "core_60_20_20",
        "artifacts": {
            "allocation_summary": str(out / "allocation_summary.csv"),
            "portfolio_equity_curves": str(out / "portfolio_equity_curves.csv"),
            "portfolio_daily_returns": str(out / "portfolio_daily_returns.csv"),
            "yearly_returns": str(out / "yearly_returns.csv"),
            "sleeve_correlation": str(out / "sleeve_correlation.csv"),
            "top_drawdowns": str(out / "top_drawdowns.csv"),
            "summary_json": str(out / "summary.json"),
        },
        "decision": {
            "status": "research_only_first_pass",
            "next_step": "review whether defensive carry improves core portfolio shape enough to warrant external T-bill proxy testing",
            "not_approved": [
                "fund_v1_runtime_change",
                "paper_trading_change",
                "production_allocation_change",
                "execution_change",
            ],
        },
    }
    (out / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print("\n" + "=" * 132)
    print("  SLEEVE 4 DEFENSIVE CARRY — Static Allocation Research")
    print(f"  Period: {str(common[0])[:10]} → {str(common[-1])[:10]} ({len(common)} daily bars)")
    print(f"  Carry source: {carry_source}")
    print("=" * 132)
    print("\n  ALLOCATION SUMMARY")
    print("  " + "-" * 128)
    print(
        f"  {'Candidate':<28} {'TotRet':>10} {'CAGR':>10} {'MaxDD':>10} {'Sharpe':>8} {'Calmar':>8} "
        f"{'AnnVol':>10} {'Worst90D':>11} {'Worst180D':>11}"
    )
    print("  " + "-" * 128)
    for _, row in summary.iterrows():
        print_metric_row(
            str(row["candidate"]),
            Metrics(
                float(row["total_return_pct"]),
                float(row["cagr_pct"]),
                float(row["max_drawdown_pct"]),
                float(row["sharpe"]),
                float(row["calmar"]),
                float(row["ann_vol_pct"]),
                float(row["worst_90d_return_pct"]),
                float(row["worst_180d_return_pct"]),
            ),
        )

    ranked = summary.sort_values(["calmar", "sharpe", "max_drawdown_pct"], ascending=[False, False, False])
    print("\n  RANKING BY CALMAR / SHARPE")
    print("  " + "-" * 128)
    with pd.option_context("display.max_columns", None, "display.width", 220, "display.float_format", "{:.4f}".format):
        print(ranked[["candidate", "cagr_pct", "max_drawdown_pct", "sharpe", "calmar", "ann_vol_pct", "delta_cagr_pct", "delta_max_drawdown_pct", "delta_sharpe", "delta_calmar"]].to_string(index=False))

    print("\n  SLEEVE DAILY RETURN CORRELATION")
    print("  " + "-" * 64)
    print(corr.to_string(float_format=lambda x: f"{x: .3f}"))

    print("\n" + "=" * 132)
    print(f"  Artifacts saved to: {out}")
    print("=" * 132)


if __name__ == "__main__":
    main()
