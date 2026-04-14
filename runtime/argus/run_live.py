"""Entry point for paper / live trading.

Usage:
    python runtime/argus/run_live.py --asset BTC --mode paper --data data/btc_1h.csv

This script wires together:
- A data provider (CSV-based for paper, exchange-based for live).
- The broker (PaperBroker or StubLiveBroker).
- The Orchestrator.

For real exchange integration, replace the CSV data provider with a live
feed and configure StubLiveBroker with real API credentials.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd

# ── Ensure project root is on sys.path ────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from dotenv import load_dotenv

load_dotenv()

from research.regimes.baseline_engine import BaselineRegimeEngine
from research.strategies import trend_following, volatility_breakout, mean_reversion
from runtime.argus.brokers.paper_broker import PaperBroker
from runtime.argus.brokers.stub_live_broker import StubLiveBroker
from runtime.argus.governors.drawdown_governor import DrawdownGovernor
from runtime.argus.governors.exposure_governor import ExposureGovernor
from runtime.argus.apex_core.orchestrator import Orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("argus.run_live")


def build_csv_provider(path: str, lookback_bars: int = 500):
    """Build a data provider that returns a rolling window from a CSV."""
    from research.harness.data_loader import load_ohlcv
    df_full = load_ohlcv(path)

    class CSVProvider:
        def __init__(self):
            self._idx = lookback_bars

        def __call__(self) -> pd.DataFrame:
            if self._idx > len(df_full):
                raise StopIteration("End of CSV data.")
            window = df_full.iloc[: self._idx]
            self._idx += 1
            return window

    return CSVProvider()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IteraDynamics paper/live trading runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--asset", default="BTC", help="Asset identifier")
    parser.add_argument(
        "--mode", choices=["paper", "live"], default="paper", help="Trading mode"
    )
    parser.add_argument("--data", required=True, help="Path to OHLCV CSV (paper mode)")
    parser.add_argument(
        "--capital", type=float, default=100_000.0, help="Initial capital (paper mode)"
    )
    parser.add_argument(
        "--poll", type=int, default=3600, help="Poll interval in seconds (live mode)"
    )
    parser.add_argument(
        "--max-cycles", type=int, default=None, help="Stop after N cycles (for testing)"
    )
    parser.add_argument(
        "--state-path", default=None, help="Path to persist runtime state JSON"
    )
    args = parser.parse_args()

    # ── Broker ────────────────────────────────────────────────────────
    if args.mode == "paper":
        broker = PaperBroker(initial_cash=args.capital)
        log.info("Paper broker initialised with $%.2f", args.capital)
    else:
        broker = StubLiveBroker(dry_run=False)
        log.info("Live broker (stub) initialised.")

    # ── Strategies (default: all three sleeves, equal weight) ─────────
    strategies = [
        (trend_following, 0.50),
        (volatility_breakout, 0.30),
        (mean_reversion, 0.20),
    ]

    # ── Data provider ─────────────────────────────────────────────────
    if args.mode == "paper":
        data_provider = build_csv_provider(args.data)
    else:
        raise NotImplementedError(
            "Live data provider not implemented. "
            "Wire to your exchange feed and replace CSVProvider."
        )

    # ── Orchestrator ──────────────────────────────────────────────────
    orchestrator = Orchestrator(
        broker=broker,
        strategies=strategies,
        regime_engine=BaselineRegimeEngine(),
        drawdown_governor=DrawdownGovernor(),
        exposure_governor=ExposureGovernor(),
        asset=args.asset,
        state_path=args.state_path,
    )

    # ── Run ───────────────────────────────────────────────────────────
    try:
        orchestrator.run_loop(
            df_provider=data_provider,
            poll_interval_seconds=args.poll,
            max_cycles=args.max_cycles,
        )
    except StopIteration:
        log.info("Data exhausted. Final NAV: %.2f", broker.get_nav(args.asset, 0.0))
    except KeyboardInterrupt:
        log.info("Stopped.")


if __name__ == "__main__":
    main()
