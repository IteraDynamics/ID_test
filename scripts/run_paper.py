#!/usr/bin/env python
"""IteraDynamics — Paper Trading CLI.

Simulates a live paper-trading session by stepping through a CSV bar by bar,
running the full Argus orchestrator pipeline on each closed bar.

Usage:
    python scripts/run_paper.py --data data/btc_1h.csv
    python scripts/run_paper.py --data data/btc_1h.csv --capital 50000 --cycles 200

PowerShell:
    python scripts\\run_paper.py --data data\\btc_1h.csv --cycles 100
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("run_paper")

from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.regimes.baseline_engine import BaselineRegimeEngine
from research.strategies import trend_following, volatility_breakout, mean_reversion
from runtime.argus.brokers.paper_broker import PaperBroker
from runtime.argus.governors.drawdown_governor import DrawdownGovernor
from runtime.argus.governors.exposure_governor import ExposureGovernor
from runtime.argus.apex_core.orchestrator import Orchestrator


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="IteraDynamics paper trading runner (CSV-driven)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--data", required=True, help="Path to OHLCV CSV")
    p.add_argument("--asset", default="BTC")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument(
        "--weights",
        default="0.5,0.3,0.2",
        help="Comma-separated sleeve weights: trend,volbreak,meanrev",
    )
    p.add_argument(
        "--cycles", type=int, default=None,
        help="Max cycles to run (default: all bars after warmup)"
    )
    p.add_argument(
        "--warmup", type=int, default=100,
        help="Number of warmup bars before first cycle"
    )
    p.add_argument("--state-path", default=None, help="Path to persist state JSON")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # ── Load data ─────────────────────────────────────────────────────
    log.info("Loading data: %s", args.data)
    df_full = load_ohlcv(args.data, asset=args.asset)
    warnings = validate_ohlcv(df_full)
    for w in warnings:
        log.warning("Data warning: %s", w)

    total_bars = len(df_full)
    log.info("Loaded %d bars  %s → %s", total_bars, df_full.index[0], df_full.index[-1])

    # ── Parse weights ─────────────────────────────────────────────────
    try:
        w_trend, w_vol, w_rev = [float(x.strip()) for x in args.weights.split(",")]
    except Exception:
        log.error("--weights must be 3 comma-separated floats")
        sys.exit(1)

    # ── Components ────────────────────────────────────────────────────
    broker = PaperBroker(initial_cash=args.capital)
    strategies = [
        (trend_following, w_trend),
        (volatility_breakout, w_vol),
        (mean_reversion, w_rev),
    ]
    orchestrator = Orchestrator(
        broker=broker,
        strategies=strategies,
        regime_engine=BaselineRegimeEngine(),
        drawdown_governor=DrawdownGovernor(),
        exposure_governor=ExposureGovernor(),
        asset=args.asset,
        state_path=args.state_path,
    )

    # ── Step through bars ─────────────────────────────────────────────
    cycle_log: list[dict] = []
    start_bar = args.warmup
    end_bar = total_bars

    max_cycles = args.cycles
    n_cycles = 0

    for bar_end in range(start_bar, end_bar):
        df_slice = df_full.iloc[: bar_end + 1]
        record = orchestrator.step(df_slice)
        cycle_log.append(record)
        n_cycles += 1

        if max_cycles and n_cycles >= max_cycles:
            log.info("Reached max_cycles=%d — stopping.", max_cycles)
            break

    # ── Final summary ─────────────────────────────────────────────────
    final_price = float(df_full["close"].iloc[bar_end])
    final_nav = broker.get_nav(args.asset, final_price)
    total_ret = (final_nav / args.capital - 1) * 100
    n_fills = len(broker.fill_history)

    print("\n" + "=" * 60)
    print(f"  PAPER RUN COMPLETE — {args.asset}")
    print("=" * 60)
    print(f"  Cycles run:   {n_cycles}")
    print(f"  Initial:      ${args.capital:>12,.2f}")
    print(f"  Final NAV:    ${final_nav:>12,.2f}")
    print(f"  Return:       {total_ret:>+.2f}%")
    print(f"  Fills:        {len(broker.fill_history)}")
    bal = broker.get_balance()
    print(f"  Cash:         ${bal.get('USD', 0):>12,.2f}")
    pos = broker.get_position(args.asset)
    print(f"  Position:     {pos:.6f} {args.asset}")
    print("=" * 60)

    # Optionally write cycle log
    if args.state_path:
        log_path = Path(args.state_path).parent / "paper_cycle_log.json"
        with open(log_path, "w") as f:
            json.dump(cycle_log[-50:], f, indent=2, default=str)  # last 50 cycles
        log.info("Cycle log (last 50): %s", log_path)


if __name__ == "__main__":
    main()
