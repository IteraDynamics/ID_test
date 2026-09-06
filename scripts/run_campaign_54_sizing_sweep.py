"""Campaign #54 Closure — crash_short_v6 sizing sweep in a Core v2 blended composition.

Authorized by the 2026-08-19 board transition (docs/ITERA_CAMPAIGN_BOARD.md): Section 3/4 of
docs/research/CAMPAIGN_54_CRASH_SHORT_PLANNING_CHARTER.md are frozen, this sweep is the Closure
work that freeze unlocked. No new data or code beyond this driver; it calls the existing
sleeve-contribution audit harness once per hedge weight.

Trend weight is reduced as hedge weight rises (trend + hedge = 0.50 throughout), matching the
already-run no-hedge-vs-10%-hedge comparison recorded in the campaign document's own §2. Equity
and gold weights are held fixed at 0.35 / 0.15 for every point on the grid, so the sweep isolates
one variable: how much of the trend sleeve's risk budget crash_short_v6 should receive.
"""

from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import json
import sys
from pathlib import Path


from scripts.run_core_v1_sleeve_contribution_audit import run_audit


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Campaign #54 Closure: crash_short_v6 hedge-weight sizing sweep.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", default=None)
    p.add_argument("--spy-data", default=None)
    p.add_argument("--qqq-data", default=None)
    p.add_argument("--bil-data", default=None)
    p.add_argument("--gld-data", default=None)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--equity-weight", type=float, default=0.35)
    p.add_argument("--gold-weight", type=float, default=0.15)
    p.add_argument(
        "--hedge-weights",
        default="0.00,0.05,0.10,0.15,0.20,0.25",
        help="Comma-separated hedge weights to sweep. Trend weight is set to 0.50 minus each value.",
    )
    p.add_argument("--data-start", default="2019-01-01")
    p.add_argument("--oos-start", default="2020-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--fee", type=float, default=0.0006)
    p.add_argument("--equity-fee", type=float, default=0.0001)
    p.add_argument("--base-slippage", type=float, default=3.0)
    p.add_argument("--slippage-vol-factor", type=float, default=50.0)
    p.add_argument("--cooldown", type=int, default=2)
    p.add_argument("--mr-cooldown", type=int, default=12)
    p.add_argument("--rebalance-threshold", type=float, default=0.02)
    p.add_argument(
        "--out-dir",
        default="artifacts/campaign_54_sizing_sweep",
        help="Parent directory; one subdirectory per hedge weight is created underneath.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    hedge_weights = [float(w.strip()) for w in args.hedge_weights.split(",") if w.strip()]

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    rows = []
    for hedge_weight in hedge_weights:
        trend_weight = round(0.50 - hedge_weight, 10)
        if trend_weight < 0:
            raise ValueError(f"hedge weight {hedge_weight} exceeds the 0.50 trend+hedge budget")

        run_ns = argparse.Namespace(
            btc_data=args.btc_data,
            eth_data=args.eth_data,
            spy_data=args.spy_data,
            qqq_data=args.qqq_data,
            bil_data=args.bil_data,
            gld_data=args.gld_data,
            capital=args.capital,
            trend_weight=trend_weight,
            equity_weight=args.equity_weight,
            gold_weight=args.gold_weight,
            hedge_weight=hedge_weight,
            mr_weight=0.0,
            data_start=args.data_start,
            oos_start=args.oos_start,
            oos_end=args.oos_end,
            fee=args.fee,
            equity_fee=args.equity_fee,
            base_slippage=args.base_slippage,
            slippage_vol_factor=args.slippage_vol_factor,
            cooldown=args.cooldown,
            mr_cooldown=args.mr_cooldown,
            rebalance_threshold=args.rebalance_threshold,
            out_dir=str(out_root / f"hedge_{hedge_weight:.2f}".replace(".", "")),
        )

        print(f"--- hedge_weight={hedge_weight:.2f} trend_weight={trend_weight:.2f} ---", flush=True)
        summary = run_audit(run_ns)
        m = summary.get("fund_metrics", {})
        row = {
            "hedge_weight": hedge_weight,
            "trend_weight": trend_weight,
            "cagr_pct": m.get("cagr_pct"),
            "max_drawdown_pct": m.get("max_drawdown_pct"),
            "sharpe": m.get("sharpe"),
            "calmar": m.get("calmar"),
        }
        rows.append(row)
        print(
            f"  CAGR {row['cagr_pct']:.2f}%  MaxDD {row['max_drawdown_pct']:.2f}%  "
            f"Sharpe {row['sharpe']:.3f}  Calmar {row['calmar']:.3f}",
            flush=True,
        )

    (out_root / "sizing_sweep_summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")

    print("\n=== Campaign #54 sizing sweep — summary ===")
    print(f"{'hedge_wt':>9} {'trend_wt':>9} {'CAGR%':>8} {'MaxDD%':>8} {'Sharpe':>8} {'Calmar':>8}")
    for row in rows:
        print(
            f"{row['hedge_weight']:>9.2f} {row['trend_weight']:>9.2f} "
            f"{row['cagr_pct']:>8.2f} {row['max_drawdown_pct']:>8.2f} "
            f"{row['sharpe']:>8.3f} {row['calmar']:>8.3f}"
        )
    print(f"\nWrote {out_root / 'sizing_sweep_summary.json'}")


if __name__ == "__main__":
    main()
