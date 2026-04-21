#!/usr/bin/env python
"""IteraDynamics — Live paper trading runner.

Polls Coinbase public API every hour, steps two independent orchestrators:
  - BTC-USD  60% allocation  PaperBroker($60k)  trend_following_v8_ecap60_add80
  - ETH-USD  40% allocation  PaperBroker($40k)  trend_following_v8_ecap60_add80

Calibrators are loaded automatically from artifacts/ml_models/ if present.

Usage:
    python scripts/run_paper_live.py
    python scripts/run_paper_live.py --capital 100000 --max-cycles 24
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("run_paper_live")

from research.strategies import trend_following_v8_ecap60_add80
from runtime.argus.brokers.paper_broker import PaperBroker
from runtime.argus.governors.drawdown_governor import DrawdownGovernor
from runtime.argus.governors.exposure_governor import ExposureGovernor
from runtime.argus.apex_core.orchestrator import Orchestrator
from research.regimes.baseline_engine import BaselineRegimeEngine

COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{product}/candles"
MIN_BARS = 250   # trend_following_v8 needs ~213; 250 gives headroom


def fetch_candles(product_id: str, granularity: int = 3600, n_candles: int = 300) -> pd.DataFrame:
    """Fetch recent hourly candles from Coinbase public API.

    Returns DataFrame with columns [open, high, low, close, volume] and a
    UTC tz-naive DatetimeIndex, sorted ascending.

    Coinbase response format per row: [time_unix_sec, low, high, open, close, volume]
    """
    url = f"{COINBASE_CANDLES_URL.format(product=product_id)}?granularity={granularity}"
    req = urllib.request.Request(url, headers={"User-Agent": "IteraDynamics/paper-trader"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = json.loads(resp.read().decode())
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Coinbase fetch failed for {product_id}: {exc}") from exc

    if not raw:
        raise RuntimeError(f"Empty candle response for {product_id}")

    df = pd.DataFrame(raw, columns=["time", "low", "high", "open", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_localize(None)
    df = df.set_index("time")
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df.index.name = "timestamp"
    return df


class CoinbaseLiveProvider:
    """Callable that returns a fresh OHLCV DataFrame on each call."""

    def __init__(self, product_id: str, granularity: int = 3600) -> None:
        self.product_id = product_id
        self.granularity = granularity
        self._cache: pd.DataFrame | None = None

    def __call__(self) -> pd.DataFrame:
        df = fetch_candles(self.product_id, self.granularity)
        if len(df) < MIN_BARS:
            raise RuntimeError(
                f"{self.product_id}: only {len(df)} bars fetched, need {MIN_BARS}"
            )
        # Drop the last (potentially still-open) bar — only use closed bars
        df = df.iloc[:-1]
        self._cache = df
        log.info(
            "%s: %d bars fetched  %s → %s",
            self.product_id, len(df), df.index[0], df.index[-1],
        )
        return df


def build_orchestrator(
    asset: str,
    initial_cash: float,
    state_path: str,
    calibrators_dir: str | None = None,
) -> tuple[Orchestrator, PaperBroker]:
    broker = PaperBroker(initial_cash=initial_cash)
    orchestrator = Orchestrator(
        broker=broker,
        strategies=[(trend_following_v8_ecap60_add80, 1.0)],
        regime_engine=BaselineRegimeEngine(),
        drawdown_governor=DrawdownGovernor(),
        exposure_governor=ExposureGovernor(),
        asset=asset,
        state_path=state_path,
        calibrators_dir=calibrators_dir,
    )
    return orchestrator, broker


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="IteraDynamics live paper trading — BTC(60%) + ETH(40%)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--capital", type=float, default=100_000.0, help="Total portfolio capital")
    p.add_argument("--poll", type=int, default=3600, help="Poll interval in seconds")
    p.add_argument("--max-cycles", type=int, default=None, help="Stop after N cycles")
    p.add_argument(
        "--state-dir",
        default="runtime/argus/state",
        help="Directory for per-asset state JSON files",
    )
    p.add_argument(
        "--calibrators-dir",
        default=None,
        help="Directory with calibrator JSON files (default: artifacts/ml_models/)",
    )
    return p.parse_args()


def print_summary(label: str, broker: PaperBroker, asset: str, price: float) -> None:
    nav = broker.get_nav(asset, price)
    cash = broker.get_balance().get("USD", 0.0)
    pos = broker.get_position(asset)
    n_fills = len(broker.fill_history)
    log.info(
        "%s | NAV=%.2f  cash=%.2f  pos=%.6f %s  fills=%d",
        label, nav, cash, pos, asset, n_fills,
    )


def main() -> None:
    args = parse_args()

    state_dir = Path(args.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)

    btc_capital = args.capital * 0.60
    eth_capital = args.capital * 0.40

    btc_state_path = str(state_dir / "paper_btc_state.json")
    eth_state_path = str(state_dir / "paper_eth_state.json")

    log.info("Building BTC orchestrator  capital=%.0f  state=%s", btc_capital, btc_state_path)
    btc_orch, btc_broker = build_orchestrator(
        asset="BTC",
        initial_cash=btc_capital,
        state_path=btc_state_path,
        calibrators_dir=args.calibrators_dir,
    )

    log.info("Building ETH orchestrator  capital=%.0f  state=%s", eth_capital, eth_state_path)
    eth_orch, eth_broker = build_orchestrator(
        asset="ETH",
        initial_cash=eth_capital,
        state_path=eth_state_path,
        calibrators_dir=args.calibrators_dir,
    )

    btc_provider = CoinbaseLiveProvider("BTC-USD")
    eth_provider = CoinbaseLiveProvider("ETH-USD")

    log.info(
        "Starting live paper trader  strategy=trend_following_v8_ecap60_add80  "
        "BTC=$%.0f  ETH=$%.0f  poll=%ds",
        btc_capital, eth_capital, args.poll,
    )

    cycle = 0
    while True:
        cycle_start = time.monotonic()
        cycle += 1
        log.info("── Cycle %d  %s ──", cycle, datetime.now(timezone.utc).isoformat())

        # BTC
        try:
            btc_df = btc_provider()
            btc_record = btc_orch.step(btc_df)
            btc_price = float(btc_df["close"].iloc[-1])
            print_summary("BTC", btc_broker, "BTC", btc_price)
        except Exception as exc:
            log.exception("BTC cycle %d failed: %s", cycle, exc)

        # ETH
        try:
            eth_df = eth_provider()
            eth_record = eth_orch.step(eth_df)
            eth_price = float(eth_df["close"].iloc[-1])
            print_summary("ETH", eth_broker, "ETH", eth_price)
        except Exception as exc:
            log.exception("ETH cycle %d failed: %s", cycle, exc)

        # Portfolio NAV
        try:
            total_nav = btc_broker.get_nav("BTC", btc_price) + eth_broker.get_nav("ETH", eth_price)
            log.info("Portfolio NAV=%.2f  (BTC+ETH combined)", total_nav)
        except Exception:
            pass

        if args.max_cycles and cycle >= args.max_cycles:
            log.info("Reached max_cycles=%d — stopping.", args.max_cycles)
            break

        elapsed = time.monotonic() - cycle_start
        sleep_sec = max(0, args.poll - elapsed)
        log.info("Sleeping %.0fs until next cycle.", sleep_sec)
        time.sleep(sleep_sec)


if __name__ == "__main__":
    main()
