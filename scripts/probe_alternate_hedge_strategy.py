"""Run the sleeve contribution audit's hedge slot with a different strategy module.

`trend_following_short_v2` is fully built, registered in research.strategies.
REGISTRY, and unused -- the other candidate for Core v2's "structurally
long-only" deficiency alongside crash_short_v6, trading sustained bear trends
broadly rather than confirmed-macro-crash-only conditions.

IMPORTANT, found the hard way: scripts/run_core_v1_sleeve_contribution_audit.py
carries its OWN HEDGE_STRATEGY constant, independent of scripts/run_multi_
strategy_fund.py's same-named one. Its strategy_for(spec) dispatches by
spec.family using this local constant for hedge/mr/equity/gold, and hardcodes
trend_following_v11 directly for trend -- spec.strategy (what _build_sleeves
sets from the fund module's constant) is never consulted for any family
_build_sleeves actually produces. A first version of this script patched only
the fund module's constant: it printed a successful-looking swap and silently
ran crash_short_v6 anyway. That was caught because the result was byte-
identical to the crash_short_v6 probe, three decimals on four metrics --
essentially impossible by coincidence for two strategies with different EMA
periods and gates -- not because anything in the script itself detected the
failure. This patches scripts.run_core_v1_sleeve_contribution_audit.
HEDGE_STRATEGY specifically, the constant strategy_for() actually reads, and
verifies the swap by calling strategy_for() directly against a real hedge-
family spec before running anything, so a silent no-op patch fails loudly
here instead of downstream in a six-hour result.

Writes artifacts to --out-dir like the audit script itself. Report-only: no
runtime, Core v1, or production behavior touched.
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
import importlib
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


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

    import scripts.run_core_v1_sleeve_contribution_audit as audit
    from scripts.run_multi_strategy_fund import SleeveSpec

    original = audit.HEDGE_STRATEGY
    setattr(audit, "HEDGE_STRATEGY", args.hedge_strategy_module)
    print(f"Hedge slot: {original} -> {audit.HEDGE_STRATEGY}")

    # Verify against the actual dispatch function, not the SleeveSpec.strategy
    # field the earlier broken version trusted -- that field is dead code for
    # this audit's hedge/mr/equity/gold families.
    probe_spec = SleeveSpec(label="_verify", family="hedge", asset="BTC",
                             timeframe="1H", strategy="_unused", capital=1.0)
    resolved = audit.strategy_for(probe_spec)
    resolved_id = getattr(resolved, "STRATEGY_ID", getattr(resolved, "__name__", "?"))
    expected_id = args.hedge_strategy_module
    if expected_id not in str(resolved_id) and expected_id.replace("_", "") not in str(resolved_id).replace("_", ""):
        raise RuntimeError(
            f"Patch verification failed: strategy_for() resolved to {resolved_id!r}, "
            f"expected something matching {expected_id!r}. Refusing to run six years "
            f"of backtest against the wrong strategy."
        )
    print(f"Verified: strategy_for(hedge spec) -> {resolved_id}")

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
