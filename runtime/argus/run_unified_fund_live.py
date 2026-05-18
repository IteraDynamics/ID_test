"""Unified Fund v1 — dual-sleeve live runner.

Layer 3 Allocator Wrapper: runs three independent Orchestrators
(BTC + ETH crypto sub-sleeves, plus equity) and applies a ±5% drift
buffer to maintain the 50/50 crypto/equity fund split.

Architecture:
  - BTC sleeve:            trend_following (50%) + volatility_breakout (30%) + mean_reversion (20%)
  - ETH sleeve:            trend_following (50%) + volatility_breakout (30%) + mean_reversion (20%)
  - EQUITY_COMPOSITE sleeve: equity_spy_qqq_sma_band_v1 (100%)
  - Crypto sleeve NAV = BTC NAV + ETH NAV; drift check uses combined crypto vs equity.
  - Master loop steps all three orchestrators per bar, then checks allocation drift.

Constraints enforced:
  - Orchestrator is NOT modified; this wrapper calls it as-is.
  - portfolio_allocator.py is NOT modified.
  - No lookahead bias; no datetime.now() in strategy logic.
  - No historical CSV data loaded in live mode.

Usage:
  # Live mode (real-time Coinbase + Yahoo feeds):
  python runtime/argus/run_unified_fund_live.py --mode live --capital 100000

  # Mock mode (CSV data, for integration testing):
  python runtime/argus/run_unified_fund_live.py --mode mock \\
      --btc-data data/BTC_1H.csv --eth-data data/ETH_1H.csv \\
      --spy-data data/SPY_1D.csv --qqq-data data/QQQ_1D.csv
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv()

from research.harness.execution_model import ExecutionConfig
from research.regimes.baseline_engine import BaselineRegimeEngine
from research.regimes.contracts import RegimeLabel
from research.strategies import (
    equity_qqq_trend_v1,
    equity_spy_qqq_sma_band_v1,
    mean_reversion,
    trend_following,
    volatility_breakout,
)
from research.strategies.contracts import StrategyContext
from research.strategies.equity_spy_qqq_sma_band_v1 import compute_signal as _sma_band_signal
from runtime.argus.apex_core.orchestrator import Orchestrator
from runtime.argus.brokers.base import Fill
from runtime.argus.brokers.paper_broker import PaperBroker
from runtime.argus.governors.drawdown_governor import DrawdownGovernor
from runtime.argus.governors.exposure_governor import ExposureGovernor
from runtime.argus.state.runtime_state import RuntimeState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("argus.unified_fund")

# ── Constants ──────────────────────────────────────────────────────────────────

COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{product}/candles"
YAHOO_CHART_URL      = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
TARGET_1H_BARS       = 900   # enough for 4H resampling headroom if ever needed

BTC_ASSET    = "BTC"
ETH_ASSET    = "ETH"
EQUITY_ASSET = "EQUITY_COMPOSITE"

TARGET_SPLIT = 0.50   # target crypto fraction of total fund NAV
DRIFT_BUFFER = 0.05   # ±5 pp: rebalance if crypto fraction leaves [45%, 55%]

BTC_WEIGHT = 0.50     # fraction of crypto sleeve capital allocated to BTC
ETH_WEIGHT = 0.50     # fraction of crypto sleeve capital allocated to ETH

BTC_STATE_PATH           = "runtime/argus/state/BTC_live_state.json"
ETH_STATE_PATH           = "runtime/argus/state/ETH_live_state.json"
EQUITY_STATE_PATH        = "runtime/argus/state/EQUITY_COMPOSITE_live_state.json"
CRYPTO_DETAIL_STATE_PATH = "runtime/argus/state/crypto_detail_state.json"
EQUITY_DETAIL_STATE_PATH = "runtime/argus/state/equity_detail_state.json"
FUND_STATE_PATH         = "runtime/argus/state/unified_fund_live_state.json"
REBALANCE_LOG_PATH      = "runtime/argus/state/unified_fund_rebalance_log.jsonl"
SIGNAL_LOG_PATH         = "runtime/argus/state/unified_fund_signals.jsonl"
FILLS_LOG_PATH          = "runtime/argus/state/unified_fund_fills.jsonl"


# ── Execution configs ──────────────────────────────────────────────────────────

def _crypto_exec_config() -> ExecutionConfig:
    """9 bps all-in: 6 bps taker fee + 3 bps base slippage."""
    return ExecutionConfig(
        taker_fee_rate=0.0006,
        base_slippage_bps=3.0,
        min_slippage_bps=1.0,
        max_slippage_bps=50.0,
        slippage_size_factor=10.0,
        slippage_vol_factor=50.0,
    )


def _equity_exec_config() -> ExecutionConfig:
    """9.5 bps all-in: 7.5 bps slippage + 2 bps commission proxy."""
    return ExecutionConfig(
        taker_fee_rate=0.0002,
        base_slippage_bps=7.5,
        min_slippage_bps=1.0,
        max_slippage_bps=30.0,
        slippage_size_factor=5.0,
        slippage_vol_factor=20.0,
    )


# ── Broker state re-hydration ──────────────────────────────────────────────────

def _rehydrate_broker(broker: PaperBroker, state_path: str) -> None:
    """Overwrite broker in-memory state from the persisted RuntimeState JSON.

    No-ops when the state file is missing or records a zero NAV (fresh start).
    """
    state = RuntimeState.load(Path(state_path))
    if not state.nav:
        return
    broker._cash = state.cash
    broker._positions = {state.asset: state.position_units}
    broker._initial_cash = state.cash + (state.position_units * state.average_entry_price)

    # Restore fill history so get_average_entry_price() returns the correct cost
    # basis after a restart. Without this, _fill_history is empty and the method
    # returns 0.0, which then gets persisted back to state and the dashboard shows
    # the sleeve as FLAT even though a position is held.
    if state.position_units > 1e-10 and state.average_entry_price > 0:
        broker._fill_history = [Fill(
            order_id="__rehydrated__",
            asset=state.asset,
            side="BUY",
            qty=state.position_units,
            fill_price=state.average_entry_price,
            fee=0.0,
        )]

    log.info(
        "Re-hydrated broker from state: Cash=$%.2f, Positions=%s, AvgEntry=%.4f",
        state.cash,
        broker._positions,
        state.average_entry_price,
    )


# ── Orchestrator factories ─────────────────────────────────────────────────────

def _rehydrate_dd_governor(orch: Orchestrator, state_path: str) -> None:
    """Restore DD governor HWM and halted flag from persisted RuntimeState.

    Without this, every restart resets the governor to HWM=None, which clears
    any active drawdown halt and resets the high-water mark to the current NAV.
    """
    state = RuntimeState.load(Path(state_path))
    orch.allocator.dd_gov.load_state({
        "high_water_mark": state.high_water_mark,
        "is_halted":       state.drawdown_governor_halted,
    })


def _build_crypto_orchestrator(asset: str, state_path: str, initial_cash: float) -> Orchestrator:
    """Shared factory for BTC and ETH crypto sub-sleeves."""
    broker = PaperBroker(
        initial_cash=initial_cash,
        exec_config=_crypto_exec_config(),
    )
    _rehydrate_broker(broker, state_path)
    strategies = [
        (trend_following,     0.50),
        (volatility_breakout, 0.30),
        (mean_reversion,      0.20),
    ]
    orch = Orchestrator(
        broker=broker,
        strategies=strategies,
        regime_engine=BaselineRegimeEngine(),
        drawdown_governor=DrawdownGovernor(),
        exposure_governor=ExposureGovernor(),
        asset=asset,
        state_path=state_path,
    )
    _rehydrate_dd_governor(orch, state_path)
    return orch


def build_btc_orchestrator(initial_cash: float) -> Orchestrator:
    return _build_crypto_orchestrator(BTC_ASSET, BTC_STATE_PATH, initial_cash)


def build_eth_orchestrator(initial_cash: float) -> Orchestrator:
    return _build_crypto_orchestrator(ETH_ASSET, ETH_STATE_PATH, initial_cash)


def build_equity_orchestrator(initial_cash: float) -> Orchestrator:
    """Equity sleeve: SPY/QQQ SMA-band strategy.

    The equity data provider must supply a DataFrame that includes both
    standard OHLCV columns (open/high/low/close for ATR + price tracking)
    and per-asset close columns (spy_close, qqq_close) consumed by the strategy.
    """
    broker = PaperBroker(
        initial_cash=initial_cash,
        exec_config=_equity_exec_config(),
    )
    _rehydrate_broker(broker, EQUITY_STATE_PATH)
    strategies = [
        (equity_spy_qqq_sma_band_v1, 1.0),
    ]
    orch = Orchestrator(
        broker=broker,
        strategies=strategies,
        regime_engine=BaselineRegimeEngine(),
        drawdown_governor=DrawdownGovernor(),
        exposure_governor=ExposureGovernor(),
        asset=EQUITY_ASSET,
        state_path=EQUITY_STATE_PATH,
    )
    _rehydrate_dd_governor(orch, EQUITY_STATE_PATH)
    return orch


# ── Live data helpers ──────────────────────────────────────────────────────────

def _parse_coinbase_candles(raw: list) -> pd.DataFrame:
    df = pd.DataFrame(raw, columns=["time", "low", "high", "open", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_localize(None)
    df = df.set_index("time").rename_axis("timestamp")
    df = df[["open", "high", "low", "close", "volume"]].astype(float).sort_index()
    return df[~df.index.duplicated(keep="last")]


def _fetch_coinbase_paginated(
    product_id: str,
    granularity: int = 3600,
    n_candles: int = TARGET_1H_BARS,
) -> pd.DataFrame:
    """Paginate the Coinbase public candle API — mirrors run_fund_v1_live.py logic."""
    all_frames: list[pd.DataFrame] = []
    end_time: datetime | None = None
    remaining = n_candles

    while remaining > 0:
        url = f"{COINBASE_CANDLES_URL.format(product=product_id)}?granularity={granularity}"
        if end_time is not None:
            start_dt = end_time - timedelta(seconds=300 * granularity)
            url += (
                f"&start={start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                f"&end={end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )
        req = urllib.request.Request(url, headers={"User-Agent": "IteraDynamics/unified-fund-v1"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            if all_frames:
                log.warning("Coinbase pagination stopped early: %s", exc)
                break
            raise RuntimeError(f"Coinbase fetch failed for {product_id}: {exc}") from exc
        if not raw:
            break
        page_df = _parse_coinbase_candles(raw)
        all_frames.append(page_df)
        remaining -= len(page_df)
        if len(page_df) < 300:
            break
        oldest = page_df.index[0]
        end_time = oldest.to_pydatetime() - timedelta(seconds=granularity)
        time.sleep(0.25)

    if not all_frames:
        raise RuntimeError(f"No candles returned for {product_id}")
    combined = pd.concat(all_frames)
    return combined[~combined.index.duplicated(keep="last")].sort_index()


def _fetch_yahoo_daily(ticker: str) -> pd.DataFrame:
    """Fetch 2 years of daily OHLCV from Yahoo Finance (no API key required)."""
    url = f"{YAHOO_CHART_URL.format(ticker=ticker)}?interval=1d&range=2y&includePrePost=false"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())

    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    q = result["indicators"]["quote"][0]

    idx = pd.to_datetime(timestamps, unit="s", utc=True).tz_localize(None).normalize()
    df = pd.DataFrame(
        {"open": q["open"], "high": q["high"], "low": q["low"],
         "close": q["close"], "volume": q.get("volume")},
        index=idx,
    )
    df = df.dropna(subset=["close"]).sort_index()
    df = df[~df.index.duplicated(keep="last")]

    # Drop today's incomplete bar — only closed daily bars feed the strategy.
    # Use UTC midnight so bar-index dates (which Yahoo normalises to UTC midnight)
    # compare consistently regardless of the server's local timezone.
    today = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
    return df[df.index < today]


# ── Data providers ─────────────────────────────────────────────────────────────

def build_live_btc_provider() -> Callable[[], pd.DataFrame]:
    """Live BTC provider: BTC-USD hourly bars via Coinbase public API."""
    def _provider() -> pd.DataFrame:
        df = _fetch_coinbase_paginated("BTC-USD", granularity=3600, n_candles=TARGET_1H_BARS)
        log.debug("BTC provider: %d bars fetched (latest: %s)", len(df), df.index[-1])
        return df
    return _provider


def build_live_eth_provider() -> Callable[[], pd.DataFrame]:
    """Live ETH provider: ETH-USD hourly bars via Coinbase public API."""
    def _provider() -> pd.DataFrame:
        df = _fetch_coinbase_paginated("ETH-USD", granularity=3600, n_candles=TARGET_1H_BARS)
        log.debug("ETH provider: %d bars fetched (latest: %s)", len(df), df.index[-1])
        return df
    return _provider


def build_live_equity_provider() -> Callable[[], pd.DataFrame]:
    """Live equity provider: SPY + QQQ daily bars via Yahoo Finance.

    Returns a wide DataFrame with:
        close / high / low / open  — equal-weight SPY+QQQ composite price
        spy_close / qqq_close      — individual closes for equity_spy_qqq_sma_band_v1
    """
    def _provider() -> pd.DataFrame:
        spy = _fetch_yahoo_daily("SPY")
        qqq = _fetch_yahoo_daily("QQQ")

        s = spy.rename(columns={"close": "spy_close", "high": "spy_high",
                                 "low": "spy_low", "open": "spy_open"})
        q = qqq.rename(columns={"close": "qqq_close", "high": "qqq_high",
                                  "low": "qqq_low", "open": "qqq_open"})
        combined = s.join(q[["qqq_close", "qqq_high", "qqq_low", "qqq_open"]], how="inner")
        combined["close"] = 0.5 * combined["spy_close"] + 0.5 * combined["qqq_close"]
        combined["high"]  = 0.5 * combined["spy_high"]  + 0.5 * combined["qqq_high"]
        combined["low"]   = 0.5 * combined["spy_low"]   + 0.5 * combined["qqq_low"]
        combined["open"]  = 0.5 * combined["spy_open"]  + 0.5 * combined["qqq_open"]
        log.debug("Equity provider: %d bars fetched (latest: %s)", len(combined), combined.index[-1])
        return combined
    return _provider


# ── Mock providers (--mode mock; integration testing only) ────────────────────

def build_mock_crypto_provider(path: str, asset: str = "BTC", lookback: int = 500) -> Callable[[], pd.DataFrame]:
    """Mock provider for a single crypto asset (BTC or ETH) from CSV."""
    from research.harness.data_loader import load_ohlcv
    df = load_ohlcv(path)

    class _Provider:
        def __init__(self) -> None:
            self._idx = lookback

        def __call__(self) -> pd.DataFrame:
            if self._idx > len(df):
                raise StopIteration(f"End of {asset} mock data.")
            window = df.iloc[: self._idx]
            self._idx += 1
            return window

    return _Provider()


def build_mock_equity_provider(
    spy_path: str, qqq_path: str, lookback: int = 500
) -> Callable[[], pd.DataFrame]:
    """Combines SPY + QQQ CSV data into the wide DataFrame the equity strategy expects."""
    from research.harness.data_loader import load_ohlcv
    spy = load_ohlcv(spy_path)
    qqq = load_ohlcv(qqq_path)

    spy_renamed = spy.rename(columns={
        "close": "spy_close", "high": "spy_high",
        "low": "spy_low", "open": "spy_open",
    })
    qqq_renamed = qqq.rename(columns={
        "close": "qqq_close", "high": "qqq_high",
        "low": "qqq_low", "open": "qqq_open",
    })

    combined = spy_renamed.join(qqq_renamed, how="inner")
    combined["close"]  = 0.5 * combined["spy_close"]  + 0.5 * combined["qqq_close"]
    combined["high"]   = 0.5 * combined["spy_high"]   + 0.5 * combined["qqq_high"]
    combined["low"]    = 0.5 * combined["spy_low"]    + 0.5 * combined["qqq_low"]
    combined["open"]   = 0.5 * combined["spy_open"]   + 0.5 * combined["qqq_open"]

    class _Provider:
        def __init__(self) -> None:
            self._idx = lookback

        def __call__(self) -> pd.DataFrame:
            if self._idx > len(combined):
                raise StopIteration("End of equity mock data.")
            window = combined.iloc[: self._idx]
            self._idx += 1
            return window

    return _Provider()


# ── NAV helpers ────────────────────────────────────────────────────────────────

def _sleeve_navs(
    btc_orch: Orchestrator,
    eth_orch: Orchestrator,
    equity_orch: Orchestrator,
    btc_price: float,
    eth_price: float,
    equity_price: float,
) -> tuple[float, float, float, float, float]:
    """Return (btc_nav, eth_nav, crypto_nav, equity_nav, total_nav)."""
    btc_nav    = btc_orch.broker.get_nav(BTC_ASSET, btc_price)
    eth_nav    = eth_orch.broker.get_nav(ETH_ASSET, eth_price)
    equity_nav = equity_orch.broker.get_nav(EQUITY_ASSET, equity_price)
    crypto_nav = btc_nav + eth_nav
    return btc_nav, eth_nav, crypto_nav, equity_nav, crypto_nav + equity_nav


# ── Drift buffer ───────────────────────────────────────────────────────────────

def check_drift(
    crypto_nav: float,
    equity_nav: float,
    total_nav: float,
) -> tuple[bool, float, float]:
    """Return (drift_triggered, crypto_frac, equity_frac).

    Drift is triggered when the crypto sleeve fraction moves outside
    [TARGET_SPLIT - DRIFT_BUFFER, TARGET_SPLIT + DRIFT_BUFFER].
    Fractions are computed from real-time NAVs, not from initial capital.
    """
    if total_nav <= 0:
        return False, TARGET_SPLIT, 1.0 - TARGET_SPLIT
    crypto_frac = crypto_nav / total_nav
    equity_frac = equity_nav / total_nav
    triggered = abs(crypto_frac - TARGET_SPLIT) > DRIFT_BUFFER
    return triggered, crypto_frac, equity_frac


def cross_asset_rebalance(
    btc_orch: Orchestrator,
    eth_orch: Orchestrator,
    equity_orch: Orchestrator,
    btc_price: float,
    eth_price: float,
    equity_price: float,
) -> dict:
    """Transfer capital between sleeve paper brokers to restore the 50/50 split.

    Paper-mode implementation: adjusts broker._cash directly to simulate a
    fund-level capital transfer. Positions are not force-liquidated; the
    orchestrators rebalance their exposure naturally over subsequent cycles
    given the new per-sleeve cash balance.

    When capital flows into the crypto sleeve it is split equally between BTC
    and ETH (BTC_WEIGHT / ETH_WEIGHT).  When capital flows out it is drawn from
    whichever crypto sub-broker has more available cash first.

    In live mode, replace the cash-adjustment block with actual exchange
    orders or prime-brokerage transfer instructions.
    """
    btc_nav, eth_nav, crypto_nav, equity_nav, total_nav = _sleeve_navs(
        btc_orch, eth_orch, equity_orch, btc_price, eth_price, equity_price
    )
    target_each = total_nav * TARGET_SPLIT
    crypto_excess = crypto_nav - target_each  # positive → crypto over-allocated

    if abs(crypto_excess) < 1.0:
        return {"type": "cross_asset_rebalance", "action": "skipped_below_1usd_threshold"}

    if crypto_excess > 0:
        # Drain from crypto: take available cash from BTC first, then ETH
        btc_avail = max(0.0, btc_orch.broker._cash)
        eth_avail = max(0.0, eth_orch.broker._cash)
        drain_btc = min(crypto_excess * BTC_WEIGHT, btc_avail)
        drain_eth = min(crypto_excess * ETH_WEIGHT, eth_avail)
        transfer_usd = drain_btc + drain_eth
        if transfer_usd < crypto_excess - 1.0:
            log.warning(
                "cross_asset_rebalance: needed to drain $%.2f but only $%.2f cash "
                "available (BTC=$%.2f ETH=$%.2f). Crypto sleeves are likely fully "
                "invested. Allocation drift will persist until positions are liquidated.",
                crypto_excess, transfer_usd, btc_avail, eth_avail,
            )

        btc_orch.broker.process_capital_flow(-drain_btc)
        eth_orch.broker.process_capital_flow(-drain_eth)
        equity_orch.broker.process_capital_flow(transfer_usd)

        btc_orch._state.process_capital_flow(-drain_btc)
        eth_orch._state.process_capital_flow(-drain_eth)
        equity_orch._state.process_capital_flow(transfer_usd)

        # Sync in-memory DD governor HWMs so the cash withdrawal does not
        # register as a drawdown breach on the very next cycle.
        for _orch in (btc_orch, eth_orch, equity_orch):
            _orch.allocator.dd_gov.load_state({
                "high_water_mark": _orch._state.high_water_mark,
                "is_halted":       _orch._state.drawdown_governor_halted,
            })

        direction = "crypto_to_equity"
    else:
        # Add to crypto: split the inflow by BTC_WEIGHT / ETH_WEIGHT
        avail_from_equity = max(0.0, equity_orch.broker._cash)
        transfer_usd = min(-crypto_excess, avail_from_equity)

        equity_orch.broker.process_capital_flow(-transfer_usd)
        btc_orch.broker.process_capital_flow(transfer_usd * BTC_WEIGHT)
        eth_orch.broker.process_capital_flow(transfer_usd * ETH_WEIGHT)

        equity_orch._state.process_capital_flow(-transfer_usd)
        btc_orch._state.process_capital_flow(transfer_usd * BTC_WEIGHT)
        eth_orch._state.process_capital_flow(transfer_usd * ETH_WEIGHT)

        # Sync in-memory DD governor HWMs so the cash withdrawal does not
        # register as a drawdown breach on the very next cycle.
        for _orch in (btc_orch, eth_orch, equity_orch):
            _orch.allocator.dd_gov.load_state({
                "high_water_mark": _orch._state.high_water_mark,
                "is_halted":       _orch._state.drawdown_governor_halted,
            })

        direction = "equity_to_crypto"

    # Persist updated sleeve states immediately so the adjusted HWMs are durable
    # in case the runner stops before the next orchestrator cycle writes state.
    for _orch in (btc_orch, eth_orch, equity_orch):
        if _orch.state_path:
            _orch._state.save(_orch.state_path)

    _, _, crypto_nav_after, equity_nav_after, total_after = _sleeve_navs(
        btc_orch, eth_orch, equity_orch, btc_price, eth_price, equity_price
    )
    return {
        "type": "cross_asset_rebalance",
        "timestamp": datetime.utcnow().isoformat(),
        "direction": direction,
        "transfer_usd": round(transfer_usd, 4),
        "crypto_nav_before":   round(crypto_nav, 4),
        "equity_nav_before":   round(equity_nav, 4),
        "total_nav_before":    round(total_nav, 4),
        "crypto_split_before": round(crypto_nav / total_nav, 6),
        "equity_split_before": round(equity_nav / total_nav, 6),
        "crypto_nav_after":    round(crypto_nav_after, 4),
        "equity_nav_after":    round(equity_nav_after, 4),
        "crypto_split_after":  round(crypto_nav_after / total_after, 6) if total_after > 0 else 0.5,
        "equity_split_after":  round(equity_nav_after / total_after, 6) if total_after > 0 else 0.5,
    }


# ── Fund state persistence ─────────────────────────────────────────────────────

def _save_fund_state(
    cycle: int,
    crypto_nav: float,
    equity_nav: float,
    crypto_frac: float,
    equity_frac: float,
    high_water_mark: float,
) -> None:
    total_nav = crypto_nav + equity_nav
    drawdown_frac = (total_nav / high_water_mark - 1.0) if high_water_mark > 0 else 0.0
    state = {
        "cycle": cycle,
        "timestamp": datetime.utcnow().isoformat(),
        "total_nav": round(total_nav, 4),
        "crypto_nav": round(crypto_nav, 4),
        "equity_nav": round(equity_nav, 4),
        "crypto_frac": round(crypto_frac, 6),
        "equity_frac": round(equity_frac, 6),
        "high_water_mark": round(high_water_mark, 4),
        "drawdown_frac": round(drawdown_frac, 6),
    }
    p = Path(FUND_STATE_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _append_rebalance_log(record: dict) -> None:
    p = Path(REBALANCE_LOG_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _append_fills_log(
    cycle: int,
    sleeve: str,
    orch: Orchestrator,
    record: dict,
    extra_fields: dict | None = None,
) -> None:
    """Write one entry to the fills log whenever a trade executes.

    Pulls the full Fill object off broker.fill_history for slippage/cost detail
    that the abbreviated step() return dict omits.
    Pass extra_fields to attach sleeve-specific data (e.g. spy_close_at_fill /
    qqq_close_at_fill for equity fills so the dashboard can compute exact per-asset
    cost basis going forward).
    """
    if not record["fill"] or not orch.broker.fill_history:
        return
    fill = orch.broker.fill_history[-1]
    entry = {
        "timestamp":    datetime.utcnow().isoformat(),
        "cycle":        cycle,
        "sleeve":       sleeve,
        "bar_timestamp": record["timestamp"],
        "side":         fill.side,
        "qty":          round(fill.qty, 8),
        "fill_price":   round(fill.fill_price, 6),
        "mid_price":    round(fill.mid_price, 6),
        "slippage_usd": round(fill.slippage_usd, 4),
        "spread_usd":   round(fill.spread_usd, 4),
        "fee":          round(fill.fee, 4),
        "cost_bps":     round(fill.cost_bps, 4),
        "nav_after":    round(record["nav"], 4),
        "exposure_after": round(record["exposure"], 6),
        "regime":       record["regime"],
        "reason":       record["decision_reason"],
    }
    if extra_fields:
        entry.update(extra_fields)
    p = Path(FILLS_LOG_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _sleeve_event(record: dict) -> str:
    """Classify a sleeve step() record into a single readable event label."""
    fill = record["fill"]
    action = record["decision_action"]
    approved = record["decision_approved"]
    if fill is not None:
        return f"FILL_{fill['side']}"          # FILL_BUY or FILL_SELL
    if not approved:
        return f"REJECTED_{action}"            # REJECTED_SELL, REJECTED_BUY, REJECTED_HOLD
    if action == "HOLD":
        return "HOLD"
    return f"NO_FILL_{action}"                 # approved but qty too small / min-notional


def _sleeve_signal_entry(asset: str, record: dict, nav: float) -> dict:
    """Build the per-sleeve dict for the signal log, with a top-level event label."""
    fill = record["fill"]
    entry: dict = {
        "asset":         asset,
        "event":         _sleeve_event(record),   # <-- top-level, easy to grep/filter
        "bar_timestamp": record["timestamp"],
        "regime":        record["regime"],
        "price":         record["price"],
        "nav":           round(nav, 4),
        "exposure":      round(record["exposure"], 6),
        "action":        record["decision_action"],
        "approved":      record["decision_approved"],
        "reason":        record["decision_reason"],
    }
    if fill is not None:
        entry["fill"] = {
            "side":  fill["side"],
            "qty":   fill["qty"],
            "price": fill["price"],
            "fee":   fill["fee"],
        }
    else:
        entry["fill"] = None
    return entry


def _append_signal_log(
    cycle: int,
    btc_record: dict,
    eth_record: dict,
    equity_record: dict,
    btc_nav: float,
    eth_nav: float,
    equity_nav: float,
    total_nav: float,
    drawdown_frac: float,
) -> None:
    crypto_nav = btc_nav + eth_nav
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "cycle": cycle,
        "fund": {
            "total_nav": round(total_nav, 4),
            "crypto_frac": round(crypto_nav / total_nav, 6) if total_nav > 0 else 0.5,
            "equity_frac": round(equity_nav / total_nav, 6) if total_nav > 0 else 0.5,
            "drawdown_frac": round(drawdown_frac, 6),
        },
        "sleeves": [
            _sleeve_signal_entry(BTC_ASSET, btc_record, btc_nav),
            _sleeve_signal_entry(ETH_ASSET, eth_record, eth_nav),
            _sleeve_signal_entry(EQUITY_ASSET, equity_record, equity_nav),
        ],
    }
    p = Path(SIGNAL_LOG_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Crypto detail state ───────────────────────────────────────────────────────

def _save_crypto_detail_state(
    btc_df: pd.DataFrame,
    eth_df: pd.DataFrame,
    btc_record: dict,
    eth_record: dict,
) -> None:
    """Write per-asset breakdown for the crypto sleeve (BTC + ETH)."""
    detail = {
        "timestamp":  datetime.utcnow().isoformat(),
        "btc_regime": btc_record.get("regime", ""),
        "eth_regime": eth_record.get("regime", ""),
        "btc_close":  round(float(btc_df["close"].iloc[-1]), 2),
        "eth_close":  round(float(eth_df["close"].iloc[-1]), 2),
    }
    p = Path(CRYPTO_DETAIL_STATE_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(detail, indent=2), encoding="utf-8")


# ── Equity detail state ────────────────────────────────────────────────────────

def _save_equity_detail_state(
    equity_df: pd.DataFrame,
    equity_record: dict,
    current_exposure: float,
) -> None:
    """Write per-asset breakdown + sniper overlay status for the equity sleeve.

    Runs both strategies as pure read-only calls — no trades, no side effects.
    Output is consumed by the dashboard Position Health strip.
    """
    # Core beta: full SMA-band signal with per-asset detail
    sma = _sma_band_signal(equity_df)

    # Sniper: QQQ trend strategy in monitoring mode.
    # Pass the real sleeve exposure so ACTIVE (sniper conditions met and we're in)
    # is distinguishable from ARMED (conditions met but flat).
    regime_str = equity_record.get("regime", "UNKNOWN")
    try:
        regime = RegimeLabel(regime_str)
    except ValueError:
        regime = RegimeLabel.UNKNOWN

    sniper_ctx = StrategyContext(
        regime=regime,
        current_exposure_frac=min(max(current_exposure, 0.0), 1.0),
        asset="QQQ",
        bar_index=len(equity_df) - 1,
    )

    # Build a QQQ-only close series for the sniper (it only needs "close")
    if "qqq_close" in equity_df.columns:
        qqq_df = equity_df.assign(close=equity_df["qqq_close"])
    else:
        qqq_df = equity_df

    sniper_intent = equity_qqq_trend_v1.generate_intent(qqq_df, sniper_ctx)
    sm = sniper_intent.meta

    if sm.get("warmup"):
        sniper_status = "WARMUP"
    elif sniper_intent.action == "ENTER_LONG":
        sniper_status = "ARMED"
    elif current_exposure > 0.01 and sniper_intent.action == "HOLD":
        sniper_status = "ACTIVE"
    else:
        sniper_status = "POLLING"

    detail = {
        "timestamp":    datetime.utcnow().isoformat(),
        "regime":       regime_str,
        # Core beta
        "spy_close":    round(sma.spy_close, 4) if sma.spy_close is not None else None,
        "qqq_close":    round(sma.qqq_close, 4) if sma.qqq_close is not None else None,
        "spy_sma":      round(sma.spy_sma,   4) if sma.spy_sma   is not None else None,
        "qqq_sma":      round(sma.qqq_sma,   4) if sma.qqq_sma   is not None else None,
        "spy_active":   sma.spy_active,
        "qqq_active":   sma.qqq_active,
        "spy_weight":   sma.target_weights.get("SPY", 0.0),
        "qqq_weight":   sma.target_weights.get("QQQ", 0.0),
        "gross_exposure": sma.gross_exposure,
        "sma_warmup":   sma.warmup,
        # Sniper overlay
        "sniper_status":          sniper_status,
        "sniper_entry_confirmed": bool(sm.get("entry_confirmed", False)),
        "sniper_exit_confirmed":  bool(sm.get("exit_confirmed", False)),
        "sniper_long_momentum":   round(float(sm["long_momentum"]), 6) if sm.get("long_momentum") is not None else None,
        "sniper_ema_fast":        round(float(sm["ema_fast"]), 4) if sm.get("ema_fast") is not None else None,
        "sniper_ema_slow":        round(float(sm["ema_slow"]), 4) if sm.get("ema_slow") is not None else None,
        "sniper_reason":          sniper_intent.reason,
    }
    p = Path(EQUITY_DETAIL_STATE_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(detail, indent=2), encoding="utf-8")


# ── Master loop ────────────────────────────────────────────────────────────────

def _bar_is_new(orch: Orchestrator, df: pd.DataFrame) -> bool:
    """Return True if the latest bar in df hasn't been processed by this orchestrator yet."""
    return str(df.index[-1]) != orch._state.last_bar_timestamp


def run_fund(
    btc_orch: Orchestrator,
    eth_orch: Orchestrator,
    equity_orch: Orchestrator,
    btc_provider: Callable[[], pd.DataFrame],
    eth_provider: Callable[[], pd.DataFrame],
    equity_provider: Callable[[], pd.DataFrame],
    poll_interval_seconds: int = 3600,
    max_cycles: int | None = None,
) -> None:
    log.info(
        "Unified Fund v1 starting. Target split=50/50, drift_buffer=±%.0f%%, "
        "crypto sub-sleeves: BTC(%.0f%%) + ETH(%.0f%%)",
        DRIFT_BUFFER * 100, BTC_WEIGHT * 100, ETH_WEIGHT * 100,
    )

    cycle = 0
    fund_hwm = 0.0
    total_nav = 0.0

    while True:
        try:
            btc_df    = btc_provider()
            eth_df    = eth_provider()
            equity_df = equity_provider()

            if not (_bar_is_new(btc_orch, btc_df)
                    or _bar_is_new(eth_orch, eth_df)
                    or _bar_is_new(equity_orch, equity_df)):
                log.info(
                    "Cycle %d | All bars already processed — skipping (restart dedup).",
                    cycle,
                )
                time.sleep(poll_interval_seconds)
                continue

            btc_record    = btc_orch.step(btc_df)
            eth_record    = eth_orch.step(eth_df)
            equity_record = equity_orch.step(equity_df)

            btc_price    = float(btc_record["price"])
            eth_price    = float(eth_record["price"])
            equity_price = float(equity_record["price"])

            _append_fills_log(cycle, BTC_ASSET, btc_orch, btc_record)
            _append_fills_log(cycle, ETH_ASSET, eth_orch, eth_record)
            _eq_fill_extra: dict = {}
            if "spy_close" in equity_df.columns:
                _eq_fill_extra["spy_close_at_fill"] = round(float(equity_df["spy_close"].iloc[-1]), 4)
            if "qqq_close" in equity_df.columns:
                _eq_fill_extra["qqq_close_at_fill"] = round(float(equity_df["qqq_close"].iloc[-1]), 4)
            _append_fills_log(cycle, EQUITY_ASSET, equity_orch, equity_record,
                              extra_fields=_eq_fill_extra or None)
            _save_crypto_detail_state(btc_df, eth_df, btc_record, eth_record)
            _save_equity_detail_state(equity_df, equity_record, equity_record["exposure"])

            btc_nav, eth_nav, crypto_nav, equity_nav, total_nav = _sleeve_navs(
                btc_orch, eth_orch, equity_orch, btc_price, eth_price, equity_price
            )

            if total_nav > fund_hwm:
                fund_hwm = total_nav

            drift_triggered, crypto_frac, equity_frac = check_drift(
                crypto_nav, equity_nav, total_nav
            )

            if drift_triggered:
                log.warning(
                    "Cycle %d | Drift breached: crypto=%.1f%% equity=%.1f%% "
                    "(target 50/50, buffer ±5%%) — executing cross-asset rebalance.",
                    cycle, crypto_frac * 100, equity_frac * 100,
                )
                cmd = cross_asset_rebalance(
                    btc_orch, eth_orch, equity_orch,
                    btc_price, eth_price, equity_price,
                )
                log.info("Rebalance executed: %s", json.dumps(cmd))
                _append_rebalance_log(cmd)

                # Re-read NAVs after cash transfer
                btc_nav, eth_nav, crypto_nav, equity_nav, total_nav = _sleeve_navs(
                    btc_orch, eth_orch, equity_orch, btc_price, eth_price, equity_price
                )
                crypto_frac = crypto_nav / total_nav if total_nav > 0 else TARGET_SPLIT
                equity_frac = equity_nav / total_nav if total_nav > 0 else 1.0 - TARGET_SPLIT

            dd_frac = (total_nav / fund_hwm - 1.0) if fund_hwm > 0 else 0.0
            _save_fund_state(cycle, crypto_nav, equity_nav, crypto_frac, equity_frac, fund_hwm)
            _append_signal_log(
                cycle, btc_record, eth_record, equity_record,
                btc_nav, eth_nav, equity_nav, total_nav, dd_frac,
            )

            dd_pct = dd_frac * 100
            log.info(
                "Cycle %d | NAV=$%.2f | Crypto=$%.2f (%.1f%%) "
                "[BTC=$%.2f ETH=$%.2f] | Equity=$%.2f (%.1f%%) | DD=%.2f%%",
                cycle, total_nav,
                crypto_nav, crypto_frac * 100,
                btc_nav, eth_nav,
                equity_nav, equity_frac * 100,
                dd_pct,
            )

            cycle += 1
            if max_cycles is not None and cycle >= max_cycles:
                log.info("Reached max_cycles=%d — stopping.", max_cycles)
                break

            time.sleep(poll_interval_seconds)

        except KeyboardInterrupt:
            log.info("Unified Fund stopped by user. Final NAV=$%.2f", total_nav)
            break
        except StopIteration as exc:
            log.info("Data exhausted: %s", exc)
            break
        except Exception as exc:
            log.exception("Master loop error at cycle %d: %s", cycle, exc)
            time.sleep(min(poll_interval_seconds, 60))


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified Fund v1 — dual-sleeve live runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--capital", type=float, default=100_000.0,
        help="Total fund capital in USD (split 50/50 between sleeves)",
    )
    parser.add_argument(
        "--poll", type=int, default=3600,
        help="Seconds between bar cycles",
    )
    parser.add_argument(
        "--max-cycles", type=int, default=None,
        help="Stop after N cycles (omit for continuous)",
    )
    parser.add_argument(
        "--mode", choices=["live", "mock"], default="live",
        help=(
            "live  = real-time data feeds (wire providers before running); "
            "mock  = rolling-window CSV providers for integration testing"
        ),
    )
    # Mock-mode paths
    parser.add_argument("--btc-data",  default=None, help="[mock] Path to BTC OHLCV CSV")
    parser.add_argument("--eth-data",  default=None, help="[mock] Path to ETH OHLCV CSV")
    parser.add_argument("--spy-data",  default=None, help="[mock] Path to SPY OHLCV CSV")
    parser.add_argument("--qqq-data",  default=None, help="[mock] Path to QQQ OHLCV CSV")
    args = parser.parse_args()

    sleeve_capital = args.capital / 2.0
    crypto_per_asset = sleeve_capital * BTC_WEIGHT  # BTC_WEIGHT == ETH_WEIGHT == 0.5
    log.info(
        "Building orchestrators: $%.2f crypto sleeve ($%.2f BTC + $%.2f ETH), $%.2f equity",
        sleeve_capital, crypto_per_asset, sleeve_capital - crypto_per_asset, sleeve_capital,
    )

    btc_orch    = build_btc_orchestrator(crypto_per_asset)
    eth_orch    = build_eth_orchestrator(sleeve_capital - crypto_per_asset)
    equity_orch = build_equity_orchestrator(sleeve_capital)

    if args.mode == "mock":
        missing = [n for n, v in [
            ("--btc-data",  args.btc_data),
            ("--eth-data",  args.eth_data),
            ("--spy-data",  args.spy_data),
            ("--qqq-data",  args.qqq_data),
        ] if not v]
        if missing:
            raise SystemExit(f"--mode mock requires: {', '.join(missing)}")
        btc_provider    = build_mock_crypto_provider(args.btc_data, asset="BTC")
        eth_provider    = build_mock_crypto_provider(args.eth_data, asset="ETH")
        equity_provider = build_mock_equity_provider(args.spy_data, args.qqq_data)
        log.info("Mock CSV providers loaded.")
    else:
        btc_provider    = build_live_btc_provider()
        eth_provider    = build_live_eth_provider()
        equity_provider = build_live_equity_provider()

    run_fund(
        btc_orch=btc_orch,
        eth_orch=eth_orch,
        equity_orch=equity_orch,
        btc_provider=btc_provider,
        eth_provider=eth_provider,
        equity_provider=equity_provider,
        poll_interval_seconds=args.poll,
        max_cycles=args.max_cycles,
    )


if __name__ == "__main__":
    main()
