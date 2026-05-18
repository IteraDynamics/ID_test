#!/usr/bin/env python
"""Blend analysis — combine Fund v1 equity curve with a candidate sleeve.

Reads pre-computed equity curves from artifacts and computes blended
portfolio metrics at multiple weight splits without re-running backtests.

Usage
-----
# Blend Fund v1 with BTC post-capitulation sleeve:
python scripts/run_blend_analysis.py \
    --fund-equity   artifacts/fund_equal_4s_2019-03-08_2025-12-30/equity_curves.csv \
    --sleeve-equity artifacts/post_capitulation_long_v2_BTC_2019-01-01_2025-12-30/equity_curve.csv \
    --sleeve-label  "PostCap_BTC_v2"

PowerShell (no backtick continuation):
python scripts\run_blend_analysis.py --fund-equity artifacts\fund_equal_4s_2019-03-08_2025-12-30\equity_curves.csv --sleeve-equity artifacts\post_capitulation_long_v2_BTC_2019-01-01_2025-12-30\equity_curve.csv --sleeve-label PostCap_BTC_v2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd


# ── Metrics helpers ────────────────────────────────────────────────────────────

def _sharpe(daily_ret: pd.Series, periods_per_year: int = 252) -> float:
    mu = daily_ret.mean()
    sd = daily_ret.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return 0.0
    return float(mu / sd * np.sqrt(periods_per_year))


def _max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    return float(dd.min()) * 100


def _cagr(equity: pd.Series) -> float:
    days = (equity.index[-1] - equity.index[0]).days
    if days <= 0:
        return 0.0
    years = days / 365.25
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1) * 100


def _calmar(cagr_pct: float, max_dd_pct: float) -> float:
    if max_dd_pct == 0:
        return 0.0
    return cagr_pct / abs(max_dd_pct)


def _metrics_row(label: str, equity: pd.Series) -> dict:
    daily = equity.resample("1D").last().dropna()
    ret   = daily.pct_change().dropna()
    cagr  = _cagr(daily)
    mdd   = _max_drawdown(daily)
    sh    = _sharpe(ret)
    cal   = _calmar(cagr, mdd)
    tot   = (daily.iloc[-1] / daily.iloc[0] - 1) * 100
    return {
        "label":        label,
        "total_ret":    tot,
        "cagr":         cagr,
        "max_dd":       mdd,
        "sharpe":       sh,
        "calmar":       cal,
        "ann_vol":      float(ret.std(ddof=1) * np.sqrt(252) * 100),
        "corr_fund":    None,   # filled later
    }


def _print_row(d: dict) -> None:
    corr_str = f"{d['corr_fund']:>+.3f}" if d["corr_fund"] is not None else "  n/a "
    print(
        f"  {d['label']:<28}"
        f"  {d['total_ret']:>+8.2f}%"
        f"  {d['cagr']:>+7.2f}%"
        f"  {d['max_dd']:>8.2f}%"
        f"  {d['sharpe']:>7.3f}"
        f"  {d['calmar']:>7.3f}"
        f"  {d['ann_vol']:>7.2f}%"
        f"  {corr_str}"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Blend analysis — Fund v1 + candidate sleeve",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--fund-equity",   required=True,
                   help="Path to fund equity_curves.csv (must contain 'portfolio' column)")
    p.add_argument("--sleeve-equity", required=True,
                   help="Path to candidate sleeve equity_curve.csv")
    p.add_argument("--sleeve-label",  default="Candidate",
                   help="Display label for the candidate sleeve")
    p.add_argument("--weights",       default="90/10,85/15,80/20",
                   help="Comma-separated fund/sleeve split pairs, e.g. '90/10,85/15,80/20'")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # ── Load fund equity ───────────────────────────────────────────────────────
    fund_df = pd.read_csv(args.fund_equity, index_col=0, parse_dates=True)
    if "portfolio" in fund_df.columns:
        fund_eq = fund_df["portfolio"].dropna()
    else:
        # Fall back to first column
        fund_eq = fund_df.iloc[:, 0].dropna()
    fund_eq.name = "Fund_v1"

    # ── Load sleeve equity ─────────────────────────────────────────────────────
    slv_df = pd.read_csv(args.sleeve_equity, index_col=0, parse_dates=True)
    if "equity" in slv_df.columns:
        slv_eq = slv_df["equity"].dropna()
    else:
        slv_eq = slv_df.iloc[:, 0].dropna()
    slv_eq.name = args.sleeve_label

    # ── Align to daily, common period ─────────────────────────────────────────
    fund_daily = fund_eq.resample("1D").last().dropna()
    slv_daily  = slv_eq.resample("1D").last().dropna()

    common = fund_daily.index.intersection(slv_daily.index)
    if len(common) < 30:
        print(f"ERROR: Only {len(common)} common daily bars — check date ranges.")
        sys.exit(1)

    fund_d = fund_daily.loc[common]
    slv_d  = slv_daily.loc[common]

    # Normalise both to 100 at start of common period
    fund_norm = fund_d / fund_d.iloc[0] * 100
    slv_norm  = slv_d  / slv_d.iloc[0]  * 100

    # Daily returns
    fund_ret = fund_norm.pct_change().dropna()
    slv_ret  = slv_norm.pct_change().dropna()
    corr     = float(fund_ret.corr(slv_ret))

    # ── Parse blend weights ────────────────────────────────────────────────────
    blend_pairs: list[tuple[float, float]] = []
    for spec in args.weights.split(","):
        parts = spec.strip().split("/")
        fw, sw = float(parts[0]) / 100, float(parts[1]) / 100
        blend_pairs.append((fw, sw))

    # ── Compute metrics ────────────────────────────────────────────────────────
    rows = []

    m_fund = _metrics_row("Fund_v1 (baseline)", fund_norm)
    m_fund["corr_fund"] = 1.0
    rows.append(m_fund)

    m_slv = _metrics_row(args.sleeve_label, slv_norm)
    m_slv["corr_fund"] = corr
    rows.append(m_slv)

    for fw, sw in blend_pairs:
        blend = fw * fund_norm + sw * slv_norm
        label = f"Blend {fw:.0%}/{sw:.0%}"
        m = _metrics_row(label, blend)
        blend_ret = blend.pct_change().dropna()
        m["corr_fund"] = float(fund_ret.corr(blend_ret))
        rows.append(m)

    # ── Print ──────────────────────────────────────────────────────────────────
    period_str = f"{str(common[0])[:10]} → {str(common[-1])[:10]}"
    print("\n" + "=" * 105)
    print(f"  BLEND ANALYSIS — Fund v1  +  {args.sleeve_label}")
    print(f"  Common period: {period_str}  ({len(common)} daily bars)")
    print(f"  Daily return correlation (Fund v1 vs sleeve): {corr:+.4f}")
    print("=" * 105)
    print(
        f"  {'Strategy':<28}  {'TotRet':>9}  {'CAGR':>8}  {'MaxDD':>9}"
        f"  {'Sharpe':>8}  {'Calmar':>8}  {'AnnVol':>8}  {'CorrFund':>8}"
    )
    print("  " + "-" * 101)
    for row in rows:
        _print_row(row)
    print("=" * 105)

    # Delta vs baseline
    baseline = rows[0]
    print("\n  DELTA vs Fund v1 baseline")
    print("  " + "-" * 70)
    for row in rows[2:]:   # blend rows only
        dcagr  = row["cagr"]   - baseline["cagr"]
        dmdd   = row["max_dd"] - baseline["max_dd"]
        dsh    = row["sharpe"] - baseline["sharpe"]
        dcal   = row["calmar"] - baseline["calmar"]
        flag_sh  = "✓" if dsh  > 0 else "✗"
        flag_cal = "✓" if dcal > 0 else "✗"
        flag_dd  = "✓" if dmdd > 0 else "✗"   # less negative = better
        print(
            f"  {row['label']:<28}"
            f"  CAGR {dcagr:>+6.2f}%"
            f"  MaxDD {dmdd:>+6.2f}% {flag_dd}"
            f"  Sharpe {dsh:>+6.3f} {flag_sh}"
            f"  Calmar {dcal:>+6.3f} {flag_cal}"
        )
    print("=" * 105 + "\n")


if __name__ == "__main__":
    main()
