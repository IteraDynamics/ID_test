"""Run the sleeve contribution audit's hedge slot with a different strategy module.

`scripts/run_multi_strategy_fund.py` hardcodes HEDGE_STRATEGY = "crash_short_v6" --
there is no CLI flag to choose a different one. `trend_following_short_v2` is fully
built, registered in research/strategies/REGISTRY, and unused, sitting alongside
crash_short_v6 as the other candidate for Core v2's "structurally long-only"
deficiency: a broader bear-trend short rather than a confirmed-macro-crash-only
short.

This patches the HEDGE_STRATEGY module attribute before building sleeves --
identical in kind to the constant-patching scripts/run_core_v1_parameter_
sensitivity.py already uses and relies on, just swapping a strategy module
reference instead of a numeric constant. HEDGE_STRATEGY is read fresh from the
module namespace on every _build_sleeves() call (not captured as a function
default), so the patch is live for the whole run.

Defaults reproduce the same isolated, 100%-weight, standalone-read shape used for
the crash_short_v6 and mean_reversion probes earlier in this campaign, so the
result is directly comparable to those.

Writes artifacts to --out-dir like the audit script itself. Report-only: no
runtime, Core v1, or production behavior touched.
"""

from __future__ import annotations

import argparse
import importlib
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--btc-data", default="data/btcusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--eth-data", default="data/ethusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument(
        "--hedge-strategy-module",
        default="trend_following_short_v2",
        help="Key in research.strategies.REGISTRY to install as the hedge slot.",
    )
    p.add_argument("--out-dir", default="artifacts/core_v2_alt_hedge_probe")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    fund_module = importlib.import_module("scripts.run_multi_strategy_fund")
    original = fund_module.HEDGE_STRATEGY
    setattr(fund_module, "HEDGE_STRATEGY", args.hedge_strategy_module)
    print(f"Hedge slot: {original} -> {fund_module.HEDGE_STRATEGY}")

    import scripts.run_core_v1_sleeve_contribution_audit as audit

    audit_args = argparse.Namespace(
        btc_data=args.btc_data, eth_data=args.eth_data,
        spy_data=args.spy_data, qqq_data=None, bil_data=None, gld_data=None,
        capital=100_000.0,
        trend_weight=0.0, equity_weight=0.0, gold_weight=0.0,
        hedge_weight=1.0, mr_weight=0.0,
        data_start="2019-01-01", oos_start="2020-01-01", oos_end="2025-12-31",
        fee=0.0006, equity_fee=0.0001,
        base_slippage=3.0, slippage_vol_factor=50.0,
        cooldown=2, mr_cooldown=12, rebalance_threshold=0.02,
        out_dir=args.out_dir,
    )

    try:
        summary = audit.run_audit(audit_args)
        m = summary.get("fund_metrics", {})
        print(
            f"Reconstructed fund ({args.hedge_strategy_module}) -> "
            f"CAGR {m.get('cagr_pct', 0.0):.2f}% MaxDD {m.get('max_drawdown_pct', 0.0):.2f}% "
            f"Sharpe {m.get('sharpe', 0.0):.3f} Calmar {m.get('calmar', 0.0):.3f}"
        )
        print(f"Wrote artifacts to {args.out_dir}")
    except Exception:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "runner_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
