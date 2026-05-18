"""Unified Fund v1 — six-sleeve live runner.

Layer 3 Allocator Wrapper: runs six independent Orchestrators
(BTC_1H, BTC_4H, ETH_1H, ETH_4H crypto sub-sleeves + SPY + QQQ equity sub-sleeves)
and applies a ±5% drift buffer to maintain the 50/50 crypto/equity fund split.

Architecture:
  - BTC_1H sleeve:  trend_following (50%) + volatility_breakout (30%) + mean_reversion (20%) — hourly bars
  - BTC_4H sleeve:  same strategies — 4-hour resampled bars
  - ETH_1H sleeve:  same strategies — hourly bars
  - ETH_4H sleeve:  same strategies — 4-hour resampled bars
  - SPY sleeve:     equity_spy_qqq_sma_band_v1 (100%) — daily bars
  - QQQ sleeve:     equity_spy_qqq_sma_band_v1 (100%) — daily bars
  - Crypto NAV  = BTC_1H + BTC_4H + ETH_1H + ETH_4H
  - Equity NAV  = SPY + QQQ
  - Drift check compares (Crypto NAV) vs (Equity NAV) vs 50/50 target ±5%.
  - Master loop steps each orchestrator only when its timeframe produces a new bar.

Capital split (default $100k total):
  - Crypto 50% ($50k): BTC_1H=12.5%, BTC_4H=12.5%, ETH_1H=12.5%, ETH_4H=12.5%
  - Equity 50% ($50k): SPY=25%, QQQ=25%

4H crypto providers fetch 1H data from Coinbase and resample via
research.harness.resampler.resample_ohlcv — strictly backward-looking, no
lookahead bias.

Capital-flow semantics (cross-asset rebalance):
  - Crypto → Equity: drain 25% each from BTC_1H/BTC_4H/ETH_1H/ETH_4H;
    inject 50% each to SPY/QQQ.
  - Equity → Crypto: drain 50% each from SPY/QQQ;
    inject 25% each to BTC_1H/BTC_4H/ETH_1H/ETH_4H.

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
from research.harness.resampler import resample_ohlcv
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
TARGET_1H_BARS       = 900   # enough for 4H resampling headroom (≈225 4H bars)

BTC_ASSET = "BTC"
ETH_ASSET = "ETH"
SPY_ASSET = "SPY"
QQQ_ASSET = "QQQ"

TARGET_SPLIT = 0.50   # target crypto fraction of total fund NAV
DRIFT_BUFFER = 0.05   # ±5 pp: rebalance if crypto fraction leaves [45%, 55%]

# Within crypto sleeve (each 25% of crypto capital = 12.5% of total fund)
BTC_1H_WEIGHT = 0.25
BTC_4H_WEIGHT = 0.25
ETH_1H_WEIGHT = 0.25
ETH_4H_WEIGHT = 0.25

# Within equity sleeve
SPY_WEIGHT = 0.50
QQQ_WEIGHT = 0.50

BTC_1H_STATE_PATH        = "runtime/argus/state/BTC_1H_live_state.json"
BTC_4H_STATE_PATH        = "runtime/argus/state/BTC_4H_live_state.json"
ETH_1H_STATE_PATH        = "runtime/argus/state/ETH_1H_live_state.json"
ETH_4H_STATE_PATH        = "runtime/argus/state/ETH_4H_live_state.json"
SPY_STATE_PATH           = "runtime/argus/state/spy_state.json"
QQQ_STATE_PATH           = "runtime/argus/state/qqq_state.json"
CRYPTO_DETAIL_STATE_PATH = "runtime/argus/state/crypto_detail_state.json"
EQUITY_DETAIL_STATE_PATH = "runtime/argus/state/equity_detail_state.json"
FUND_STATE_PATH          = "runtime/argus/state/unified_fund_live_state.json"
REBALANCE_LOG_PATH       = "runtime/argus/state/unified_fund_rebalance_log.jsonl"
SIGNAL_LOG_PATH          = "runtime/argus/state/unified_fund_signals.jsonl"
FILLS_LOG_PATH           = "runtime/argus/state/unified_fund_fills.jsonl"


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
    """Restore DD governor HWM and halted flag from persisted RuntimeState."""
    state = RuntimeState.load(Path(state_path))
    orch.allocator.dd_gov.load_state({
        "high_water_mark": state.high_water_mark,
        "is_halted":       state.drawdown_governor_halted,
    })


def _build_crypto_orchestrator(asset: str, state_path: str, initial_cash: float) -> Orchestrator:
    """Shared factory for all crypto sub-sleeves (BTC_1H, BTC_4H, ETH_1H, ETH_4H)."""
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


def build_btc_1h_orchestrator(initial_cash: float) -> Orchestrator:
    return _build_crypto_orchestrator(BTC_ASSET, BTC_1H_STATE_PATH, initial_cash)


def build_btc_4h_orchestrator(initial_cash: float) -> Orchestrator:
    return _build_crypto_orchestrator(BTC_ASSET, BTC_4H_STATE_PATH, initial_cash)


def build_eth_1h_orchestrator(initial_cash: float) -> Orchestrator:
    return _build_crypto_orchestrator(ETH_ASSET, ETH_1H_STATE_PATH, initial_cash)


def build_eth_4h_orchestrator(initial_cash: float) -> Orchestrator:
    return _build_crypto_orchestrator(ETH_ASSET, ETH_4H_STATE_PATH, initial_cash)


def _build_equity_orchestrator(asset: str, state_path: str, initial_cash: float) -> Orchestrator:
    """Shared factory for SPY and QQQ equity sub-sleeves."""
    broker = PaperBroker(
        initial_cash=initial_cash,
        exec_config=_equity_exec_config(),
    )
    _rehydrate_broker(broker, state_path)
    strategies = [
        (equity_spy_qqq_sma_band_v1, 1.0),
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


def build_spy_orchestrator(initial_cash: float) -> Orchestrator:
    return _build_equity_orchestrator(SPY_ASSET, SPY_STATE_PATH, initial_cash)


def build_qqq_orchestrator(initial_cash: float) -> Orchestrator:
    return _build_equity_orchestrator(QQQ_ASSET, QQQ_STATE_PATH, initial_cash)


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
    """Paginate the Coinbase public candle API."""
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
    today = pd.Timestamp.now(tz="UTC").normalize().tz_localize(None)
    return df[df.index < today]


def _build_combined_equity_df(spy: pd.DataFrame, qqq: pd.DataFrame) -> pd.DataFrame:
    """Join raw SPY and QQQ frames into the wide format the SMA-band strategy expects."""
    s = spy.rename(columns={"close": "spy_close", "high": "spy_high",
                             "low": "spy_low", "open": "spy_open",
                             "volume": "spy_volume"})
    q = qqq.rename(columns={"close": "qqq_close", "high": "qqq_high",
                              "low": "qqq_low", "open": "qqq_open",
                              "volume": "qqq_volume"})
    return s.join(
        q[["qqq_close", "qqq_high", "qqq_low", "qqq_open", "qqq_volume"]],
        how="inner",
    )


# ── Data providers ─────────────────────────────────────────────────────────────

def build_live_btc_1h_provider() -> Callable[[], pd.DataFrame]:
    """Live BTC 1H provider: BTC-USD hourly bars via Coinbase public API."""
    def _provider() -> pd.DataFrame:
        df = _fetch_coinbase_paginated("BTC-USD", granularity=3600, n_candles=TARGET_1H_BARS)
        log.debug("BTC_1H provider: %d bars fetched (latest: %s)", len(df), df.index[-1])
        return df
    return _provider


def build_live_btc_4h_provider() -> Callable[[], pd.DataFrame]:
    """Live BTC 4H provider: fetches hourly bars and resamples to 4H."""
    def _provider() -> pd.DataFrame:
        raw = _fetch_coinbase_paginated("BTC-USD", granularity=3600, n_candles=TARGET_1H_BARS)
        df = resample_ohlcv(raw, "4h")
        log.debug("BTC_4H provider: %d bars (latest: %s)", len(df), df.index[-1])
        return df
    return _provider


def build_live_eth_1h_provider() -> Callable[[], pd.DataFrame]:
    """Live ETH 1H provider: ETH-USD hourly bars via Coinbase public API."""
    def _provider() -> pd.DataFrame:
        df = _fetch_coinbase_paginated("ETH-USD", granularity=3600, n_candles=TARGET_1H_BARS)
        log.debug("ETH_1H provider: %d bars fetched (latest: %s)", len(df), df.index[-1])
        return df
    return _provider


def build_live_eth_4h_provider() -> Callable[[], pd.DataFrame]:
    """Live ETH 4H provider: fetches hourly bars and resamples to 4H."""
    def _provider() -> pd.DataFrame:
        raw = _fetch_coinbase_paginated("ETH-USD", granularity=3600, n_candles=TARGET_1H_BARS)
        df = resample_ohlcv(raw, "4h")
        log.debug("ETH_4H provider: %d bars (latest: %s)", len(df), df.index[-1])
        return df
    return _provider


def build_live_spy_provider() -> Callable[[], pd.DataFrame]:
    """Live SPY provider: raw SPY daily bars with combined spy_close/qqq_close columns."""
    def _provider() -> pd.DataFrame:
        spy = _fetch_yahoo_daily("SPY")
        qqq = _fetch_yahoo_daily("QQQ")
        combined = _build_combined_equity_df(spy, qqq)
        combined["close"]  = combined["spy_close"]
        combined["high"]   = combined["spy_high"]
        combined["low"]    = combined["spy_low"]
        combined["open"]   = combined["spy_open"]
        combined["volume"] = combined["spy_volume"]
        log.debug("SPY provider: %d bars fetched (latest: %s)", len(combined), combined.index[-1])
        return combined
    return _provider


def build_live_qqq_provider() -> Callable[[], pd.DataFrame]:
    """Live QQQ provider: raw QQQ daily bars with combined spy_close/qqq_close columns."""
    def _provider() -> pd.DataFrame:
        spy = _fetch_yahoo_daily("SPY")
        qqq = _fetch_yahoo_daily("QQQ")
        combined = _build_combined_equity_df(spy, qqq)
        combined["close"]  = combined["qqq_close"]
        combined["high"]   = combined["qqq_high"]
        combined["low"]    = combined["qqq_low"]
        combined["open"]   = combined["qqq_open"]
        combined["volume"] = combined["qqq_volume"]
        log.debug("QQQ provider: %d bars fetched (latest: %s)", len(combined), combined.index[-1])
        return combined
    return _provider


# ── Mock providers (--mode mock; integration testing only) ────────────────────

def build_mock_crypto_provider(path: str, asset: str = "BTC", lookback: int = 500) -> Callable[[], pd.DataFrame]:
    """Mock 1H provider for a single crypto asset from CSV."""
    from research.harness.data_loader import load_ohlcv
    df = load_ohlcv(path)

    class _Provider:
        def __init__(self) -> None:
            self._idx = lookback

        def __call__(self) -> pd.DataFrame:
            if self._idx > len(df):
                raise StopIteration(f"End of {asset} 1H mock data.")
            window = df.iloc[: self._idx]
            self._idx += 1
            return window

    return _Provider()


def build_mock_crypto_4h_provider(path: str, asset: str = "BTC", lookback: int = 125) -> Callable[[], pd.DataFrame]:
    """Mock 4H provider: loads 1H CSV, resamples to 4H, uses rolling window.

    lookback default of 125 corresponds to ~500 hours of 1H data resampled to 4H.
    """
    from research.harness.data_loader import load_ohlcv
    df_1h = load_ohlcv(path)
    df_4h = resample_ohlcv(df_1h, "4h")

    class _Provider:
        def __init__(self) -> None:
            self._idx = lookback

        def __call__(self) -> pd.DataFrame:
            if self._idx > len(df_4h):
                raise StopIteration(f"End of {asset} 4H mock data.")
            window = df_4h.iloc[: self._idx]
            self._idx += 1
            return window

    return _Provider()


def _build_mock_equity_combined(spy_path: str, qqq_path: str) -> pd.DataFrame:
    """Load SPY and QQQ CSVs and join into the wide combined DataFrame."""
    from research.harness.data_loader import load_ohlcv
    spy = load_ohlcv(spy_path)
    qqq = load_ohlcv(qqq_path)
    return _build_combined_equity_df(spy, qqq)


def build_mock_spy_provider(spy_path: str, qqq_path: str, lookback: int = 500) -> Callable[[], pd.DataFrame]:
    """Mock SPY provider: rolling-window combined DataFrame with close=spy_close."""
    combined = _build_mock_equity_combined(spy_path, qqq_path)
    combined["close"]  = combined["spy_close"]
    combined["high"]   = combined["spy_high"]
    combined["low"]    = combined["spy_low"]
    combined["open"]   = combined["spy_open"]
    combined["volume"] = combined.get("spy_volume", 0.0)

    class _Provider:
        def __init__(self) -> None:
            self._idx = lookback

        def __call__(self) -> pd.DataFrame:
            if self._idx > len(combined):
                raise StopIteration("End of SPY mock data.")
            window = combined.iloc[: self._idx]
            self._idx += 1
            return window

    return _Provider()


def build_mock_qqq_provider(spy_path: str, qqq_path: str, lookback: int = 500) -> Callable[[], pd.DataFrame]:
    """Mock QQQ provider: rolling-window combined DataFrame with close=qqq_close."""
    combined = _build_mock_equity_combined(spy_path, qqq_path)
    combined["close"]  = combined["qqq_close"]
    combined["high"]   = combined["qqq_high"]
    combined["low"]    = combined["qqq_low"]
    combined["open"]   = combined["qqq_open"]
    combined["volume"] = combined.get("qqq_volume", 0.0)

    class _Provider:
        def __init__(self) -> None:
            self._idx = lookback

        def __call__(self) -> pd.DataFrame:
            if self._idx > len(combined):
                raise StopIteration("End of QQQ mock data.")
            window = combined.iloc[: self._idx]
            self._idx += 1
            return window

    return _Provider()


# ── NAV helpers ────────────────────────────────────────────────────────────────

def _sleeve_navs(
    btc1h_orch: Orchestrator,
    btc4h_orch: Orchestrator,
    eth1h_orch: Orchestrator,
    eth4h_orch: Orchestrator,
    spy_orch: Orchestrator,
    qqq_orch: Orchestrator,
    btc_price: float,
    eth_price: float,
    spy_price: float,
    qqq_price: float,
) -> tuple[float, float, float, float, float, float, float, float, float, float, float]:
    """Return (btc1h_nav, btc4h_nav, eth1h_nav, eth4h_nav, spy_nav, qqq_nav,
               btc_nav, eth_nav, crypto_nav, equity_nav, total_nav)."""
    btc1h_nav = btc1h_orch.broker.get_nav(BTC_ASSET, btc_price)
    btc4h_nav = btc4h_orch.broker.get_nav(BTC_ASSET, btc_price)
    eth1h_nav = eth1h_orch.broker.get_nav(ETH_ASSET, eth_price)
    eth4h_nav = eth4h_orch.broker.get_nav(ETH_ASSET, eth_price)
    spy_nav   = spy_orch.broker.get_nav(SPY_ASSET, spy_price)
    qqq_nav   = qqq_orch.broker.get_nav(QQQ_ASSET, qqq_price)
    btc_nav    = btc1h_nav + btc4h_nav
    eth_nav    = eth1h_nav + eth4h_nav
    crypto_nav = btc_nav + eth_nav
    equity_nav = spy_nav + qqq_nav
    return btc1h_nav, btc4h_nav, eth1h_nav, eth4h_nav, spy_nav, qqq_nav, btc_nav, eth_nav, crypto_nav, equity_nav, crypto_nav + equity_nav


# ── Drift buffer ───────────────────────────────────────────────────────────────

def check_drift(
    crypto_nav: float,
    equity_nav: float,
    total_nav: float,
) -> tuple[bool, float, float]:
    """Return (drift_triggered, crypto_frac, equity_frac)."""
    if total_nav <= 0:
        return False, TARGET_SPLIT, 1.0 - TARGET_SPLIT
    crypto_frac = crypto_nav / total_nav
    equity_frac = equity_nav / total_nav
    triggered = abs(crypto_frac - TARGET_SPLIT) > DRIFT_BUFFER
    return triggered, crypto_frac, equity_frac


def cross_asset_rebalance(
    btc1h_orch: Orchestrator,
    btc4h_orch: Orchestrator,
    eth1h_orch: Orchestrator,
    eth4h_orch: Orchestrator,
    spy_orch: Orchestrator,
    qqq_orch: Orchestrator,
    btc_price: float,
    eth_price: float,
    spy_price: float,
    qqq_price: float,
) -> dict:
    """Transfer capital between sub-sleeve paper brokers to restore 50/50 crypto/equity.

    Capital-flow logic:
      Crypto → Equity: drain 25% each from BTC_1H/BTC_4H/ETH_1H/ETH_4H;
        inject 50% each to SPY and QQQ.
      Equity → Crypto: drain 50% each from SPY/QQQ;
        inject 25% each to BTC_1H/BTC_4H/ETH_1H/ETH_4H.

    process_capital_flow() is called on both the broker and RuntimeState for every
    sleeve so that High-Water Marks scale proportionally and DD governors don't
    misinterpret the cash transfer as a drawdown breach.
    """
    (btc1h_nav, btc4h_nav, eth1h_nav, eth4h_nav,
     spy_nav, qqq_nav, btc_nav, eth_nav,
     crypto_nav, equity_nav, total_nav) = _sleeve_navs(
        btc1h_orch, btc4h_orch, eth1h_orch, eth4h_orch, spy_orch, qqq_orch,
        btc_price, eth_price, spy_price, qqq_price,
    )
    target_each = total_nav * TARGET_SPLIT
    crypto_excess = crypto_nav - target_each  # positive → crypto over-allocated

    if abs(crypto_excess) < 1.0:
        return {"type": "cross_asset_rebalance", "action": "skipped_below_1usd_threshold"}

    crypto_orchs = (btc1h_orch, btc4h_orch, eth1h_orch, eth4h_orch)
    crypto_weights = (BTC_1H_WEIGHT, BTC_4H_WEIGHT, ETH_1H_WEIGHT, ETH_4H_WEIGHT)

    if crypto_excess > 0:
        # Drain from crypto (25% each sub-sleeve) → inject into equity (50/50 SPY/QQQ)
        avail = [max(0.0, o.broker._cash) for o in crypto_orchs]
        drains = [min(crypto_excess * w, a) for w, a in zip(crypto_weights, avail)]
        transfer_usd = sum(drains)

        if transfer_usd < crypto_excess - 1.0:
            log.warning(
                "cross_asset_rebalance: needed to drain $%.2f from crypto but only "
                "$%.2f cash available. Crypto sleeves likely fully invested.",
                crypto_excess, transfer_usd,
            )

        inject_spy = transfer_usd * SPY_WEIGHT
        inject_qqq = transfer_usd * QQQ_WEIGHT

        for orch, drain in zip(crypto_orchs, drains):
            orch.broker.process_capital_flow(-drain)
            orch._state.process_capital_flow(-drain)

        spy_orch.broker.process_capital_flow(inject_spy)
        qqq_orch.broker.process_capital_flow(inject_qqq)
        spy_orch._state.process_capital_flow(inject_spy)
        qqq_orch._state.process_capital_flow(inject_qqq)

        direction = "crypto_to_equity"

    else:
        # Drain from equity (50/50 SPY/QQQ) → inject into crypto (25% each sub-sleeve)
        spy_avail = max(0.0, spy_orch.broker._cash)
        qqq_avail = max(0.0, qqq_orch.broker._cash)
        drain_spy = min(-crypto_excess * SPY_WEIGHT, spy_avail)
        drain_qqq = min(-crypto_excess * QQQ_WEIGHT, qqq_avail)
        transfer_usd = drain_spy + drain_qqq

        if transfer_usd < -crypto_excess - 1.0:
            log.warning(
                "cross_asset_rebalance: needed to drain $%.2f from equity but only "
                "$%.2f cash available (SPY=$%.2f QQQ=$%.2f). Equity sleeves likely "
                "fully invested.",
                -crypto_excess, transfer_usd, spy_avail, qqq_avail,
            )

        spy_orch.broker.process_capital_flow(-drain_spy)
        qqq_orch.broker.process_capital_flow(-drain_qqq)
        spy_orch._state.process_capital_flow(-drain_spy)
        qqq_orch._state.process_capital_flow(-drain_qqq)

        for orch, w in zip(crypto_orchs, crypto_weights):
            inject = transfer_usd * w
            orch.broker.process_capital_flow(inject)
            orch._state.process_capital_flow(inject)

        direction = "equity_to_crypto"

    # Sync in-memory DD governor HWMs for all six sleeves.
    for _orch in (*crypto_orchs, spy_orch, qqq_orch):
        _orch.allocator.dd_gov.load_state({
            "high_water_mark": _orch._state.high_water_mark,
            "is_halted":       _orch._state.drawdown_governor_halted,
        })

    # Persist updated sleeve states immediately.
    for _orch in (*crypto_orchs, spy_orch, qqq_orch):
        if _orch.state_path:
            _orch._state.save(_orch.state_path)

    (_, _, _, _, _, _,
     _, _, crypto_nav_after, equity_nav_after, total_after) = _sleeve_navs(
        btc1h_orch, btc4h_orch, eth1h_orch, eth4h_orch, spy_orch, qqq_orch,
        btc_price, eth_price, spy_price, qqq_price,
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
    btc1h_nav: float,
    btc4h_nav: float,
    eth1h_nav: float,
    eth4h_nav: float,
    spy_nav: float,
    qqq_nav: float,
    crypto_frac: float,
    equity_frac: float,
    high_water_mark: float,
) -> None:
    btc_nav    = btc1h_nav + btc4h_nav
    eth_nav    = eth1h_nav + eth4h_nav
    crypto_nav = btc_nav + eth_nav
    equity_nav = spy_nav + qqq_nav
    total_nav  = crypto_nav + equity_nav
    drawdown_frac = (total_nav / high_water_mark - 1.0) if high_water_mark > 0 else 0.0
    state = {
        "cycle":          cycle,
        "timestamp":      datetime.utcnow().isoformat(),
        "total_nav":      round(total_nav, 4),
        "crypto_nav":     round(crypto_nav, 4),
        "equity_nav":     round(equity_nav, 4),
        "btc_nav":        round(btc_nav, 4),
        "btc_1h_nav":     round(btc1h_nav, 4),
        "btc_4h_nav":     round(btc4h_nav, 4),
        "eth_nav":        round(eth_nav, 4),
        "eth_1h_nav":     round(eth1h_nav, 4),
        "eth_4h_nav":     round(eth4h_nav, 4),
        "spy_nav":        round(spy_nav, 4),
        "qqq_nav":        round(qqq_nav, 4),
        "crypto_frac":    round(crypto_frac, 6),
        "equity_frac":    round(equity_frac, 6),
        "high_water_mark": round(high_water_mark, 4),
        "drawdown_frac":  round(drawdown_frac, 6),
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
    """Write one entry to the fills log whenever a trade executes."""
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
    fill   = record["fill"]
    action = record["decision_action"]
    approved = record["decision_approved"]
    if fill is not None:
        return f"FILL_{fill['side']}"
    if not approved:
        return f"REJECTED_{action}"
    if action == "HOLD":
        return "HOLD"
    return f"NO_FILL_{action}"


def _sleeve_signal_entry(asset: str, record: dict, nav: float) -> dict:
    """Build the per-sleeve dict for the signal log."""
    fill = record["fill"]
    entry: dict = {
        "asset":         asset,
        "event":         _sleeve_event(record),
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
    btc1h_record: dict,
    btc4h_record: dict,
    eth1h_record: dict,
    eth4h_record: dict,
    spy_record: dict,
    qqq_record: dict,
    btc1h_nav: float,
    btc4h_nav: float,
    eth1h_nav: float,
    eth4h_nav: float,
    spy_nav: float,
    qqq_nav: float,
    total_nav: float,
    drawdown_frac: float,
) -> None:
    crypto_nav = btc1h_nav + btc4h_nav + eth1h_nav + eth4h_nav
    equity_nav = spy_nav + qqq_nav
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "cycle": cycle,
        "fund": {
            "total_nav":    round(total_nav, 4),
            "crypto_frac":  round(crypto_nav / total_nav, 6) if total_nav > 0 else 0.5,
            "equity_frac":  round(equity_nav / total_nav, 6) if total_nav > 0 else 0.5,
            "drawdown_frac": round(drawdown_frac, 6),
        },
        "sleeves": [
            _sleeve_signal_entry("BTC_1H", btc1h_record, btc1h_nav),
            _sleeve_signal_entry("BTC_4H", btc4h_record, btc4h_nav),
            _sleeve_signal_entry("ETH_1H", eth1h_record, eth1h_nav),
            _sleeve_signal_entry("ETH_4H", eth4h_record, eth4h_nav),
            _sleeve_signal_entry(SPY_ASSET, spy_record, spy_nav),
            _sleeve_signal_entry(QQQ_ASSET, qqq_record, qqq_nav),
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
    btc1h_record: dict,
    btc4h_record: dict,
    eth1h_record: dict,
    eth4h_record: dict,
) -> None:
    """Write per-asset breakdown for the crypto sleeve (all four sub-sleeves)."""
    detail = {
        "timestamp":      datetime.utcnow().isoformat(),
        "btc_regime":     btc1h_record.get("regime", ""),
        "eth_regime":     eth1h_record.get("regime", ""),
        "btc_close":      round(float(btc_df["close"].iloc[-1]), 2),
        "eth_close":      round(float(eth_df["close"].iloc[-1]), 2),
        "btc_1h_regime":  btc1h_record.get("regime", ""),
        "btc_4h_regime":  btc4h_record.get("regime", ""),
        "eth_1h_regime":  eth1h_record.get("regime", ""),
        "eth_4h_regime":  eth4h_record.get("regime", ""),
    }
    p = Path(CRYPTO_DETAIL_STATE_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(detail, indent=2), encoding="utf-8")


# ── Equity detail state ────────────────────────────────────────────────────────

def _save_equity_detail_state(
    equity_df: pd.DataFrame,
    spy_record: dict,
    qqq_record: dict,
) -> None:
    """Write per-asset breakdown + sniper overlay status for the equity sleeve.

    equity_df must be the combined wide DataFrame (spy_close + qqq_close columns).
    """
    sma = _sma_band_signal(equity_df)

    regime_str = qqq_record.get("regime", "UNKNOWN")
    try:
        regime = RegimeLabel(regime_str)
    except ValueError:
        regime = RegimeLabel.UNKNOWN

    qqq_exposure = float(qqq_record.get("exposure", 0.0))
    sniper_ctx = StrategyContext(
        regime=regime,
        current_exposure_frac=min(max(qqq_exposure, 0.0), 1.0),
        asset="QQQ",
        bar_index=len(equity_df) - 1,
    )

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
    elif qqq_exposure > 0.01 and sniper_intent.action == "HOLD":
        sniper_status = "ACTIVE"
    else:
        sniper_status = "POLLING"

    detail = {
        "timestamp":  datetime.utcnow().isoformat(),
        "spy_regime": spy_record.get("regime", ""),
        "qqq_regime": regime_str,
        "regime":     regime_str,
        "spy_close":  round(sma.spy_close, 4) if sma.spy_close is not None else None,
        "qqq_close":  round(sma.qqq_close, 4) if sma.qqq_close is not None else None,
        "spy_sma":    round(sma.spy_sma,   4) if sma.spy_sma   is not None else None,
        "qqq_sma":    round(sma.qqq_sma,   4) if sma.qqq_sma   is not None else None,
        "spy_active": sma.spy_active,
        "qqq_active": sma.qqq_active,
        "spy_weight": sma.target_weights.get("SPY", 0.0),
        "qqq_weight": sma.target_weights.get("QQQ", 0.0),
        "gross_exposure": sma.gross_exposure,
        "sma_warmup": sma.warmup,
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


def _step_if_new(orch: Orchestrator, df: pd.DataFrame) -> dict | None:
    """Call orch.step(df) only when the latest bar is new; return None otherwise.

    This prevents the orchestrator from re-processing the same bar, which would
    trigger duplicate strategy evaluations and potential duplicate fills.
    """
    if _bar_is_new(orch, df):
        return orch.step(df)
    return None


def run_fund(
    btc1h_orch: Orchestrator,
    btc4h_orch: Orchestrator,
    eth1h_orch: Orchestrator,
    eth4h_orch: Orchestrator,
    spy_orch: Orchestrator,
    qqq_orch: Orchestrator,
    btc1h_provider: Callable[[], pd.DataFrame],
    btc4h_provider: Callable[[], pd.DataFrame],
    eth1h_provider: Callable[[], pd.DataFrame],
    eth4h_provider: Callable[[], pd.DataFrame],
    spy_provider: Callable[[], pd.DataFrame],
    qqq_provider: Callable[[], pd.DataFrame],
    poll_interval_seconds: int = 3600,
    max_cycles: int | None = None,
) -> None:
    log.info(
        "Unified Fund v1 starting. 6 sleeves: BTC_1H + BTC_4H + ETH_1H + ETH_4H (crypto) "
        "+ SPY + QQQ (equity). Target split=50/50, drift_buffer=±%.0f%%.",
        DRIFT_BUFFER * 100,
    )

    cycle    = 0
    fund_hwm = 0.0
    total_nav = 0.0

    # Sentinel records used when a sleeve's bar hasn't changed this cycle.
    _NO_STEP: dict = {
        "timestamp": "", "regime": "", "price": 0.0, "nav": 0.0,
        "exposure": 0.0, "decision_action": "HOLD", "decision_approved": False,
        "decision_reason": "no_new_bar", "fill": None,
    }

    while True:
        try:
            btc1h_df = btc1h_provider()
            btc4h_df = btc4h_provider()
            eth1h_df = eth1h_provider()
            eth4h_df = eth4h_provider()
            spy_df   = spy_provider()
            qqq_df   = qqq_provider()

            any_new = any([
                _bar_is_new(btc1h_orch, btc1h_df),
                _bar_is_new(btc4h_orch, btc4h_df),
                _bar_is_new(eth1h_orch, eth1h_df),
                _bar_is_new(eth4h_orch, eth4h_df),
                _bar_is_new(spy_orch,   spy_df),
                _bar_is_new(qqq_orch,   qqq_df),
            ])
            if not any_new:
                log.info("Cycle %d | All bars already processed — skipping.", cycle)
                time.sleep(poll_interval_seconds)
                continue

            btc1h_record = _step_if_new(btc1h_orch, btc1h_df) or {**_NO_STEP, "price": float(btc1h_df["close"].iloc[-1])}
            btc4h_record = _step_if_new(btc4h_orch, btc4h_df) or {**_NO_STEP, "price": float(btc4h_df["close"].iloc[-1])}
            eth1h_record = _step_if_new(eth1h_orch, eth1h_df) or {**_NO_STEP, "price": float(eth1h_df["close"].iloc[-1])}
            eth4h_record = _step_if_new(eth4h_orch, eth4h_df) or {**_NO_STEP, "price": float(eth4h_df["close"].iloc[-1])}
            spy_record   = _step_if_new(spy_orch,   spy_df)   or {**_NO_STEP, "price": float(spy_df["close"].iloc[-1])}
            qqq_record   = _step_if_new(qqq_orch,   qqq_df)   or {**_NO_STEP, "price": float(qqq_df["close"].iloc[-1])}

            btc_price = float(btc1h_df["close"].iloc[-1])
            eth_price = float(eth1h_df["close"].iloc[-1])
            spy_price = float(spy_df["close"].iloc[-1])
            qqq_price = float(qqq_df["close"].iloc[-1])

            _append_fills_log(cycle, "BTC_1H", btc1h_orch, btc1h_record)
            _append_fills_log(cycle, "BTC_4H", btc4h_orch, btc4h_record)
            _append_fills_log(cycle, "ETH_1H", eth1h_orch, eth1h_record)
            _append_fills_log(cycle, "ETH_4H", eth4h_orch, eth4h_record)
            _append_fills_log(cycle, SPY_ASSET, spy_orch,   spy_record)
            _append_fills_log(cycle, QQQ_ASSET, qqq_orch,   qqq_record)

            _save_crypto_detail_state(btc1h_df, eth1h_df, btc1h_record, btc4h_record, eth1h_record, eth4h_record)
            # spy_df contains both spy_close and qqq_close — pass directly for SMA/sniper calc
            _save_equity_detail_state(spy_df, spy_record, qqq_record)

            (btc1h_nav, btc4h_nav, eth1h_nav, eth4h_nav,
             spy_nav, qqq_nav, btc_nav, eth_nav,
             crypto_nav, equity_nav, total_nav) = _sleeve_navs(
                btc1h_orch, btc4h_orch, eth1h_orch, eth4h_orch, spy_orch, qqq_orch,
                btc_price, eth_price, spy_price, qqq_price,
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
                    btc1h_orch, btc4h_orch, eth1h_orch, eth4h_orch, spy_orch, qqq_orch,
                    btc_price, eth_price, spy_price, qqq_price,
                )
                log.info("Rebalance executed: %s", json.dumps(cmd))
                _append_rebalance_log(cmd)

                # Re-read NAVs after cash transfer
                (btc1h_nav, btc4h_nav, eth1h_nav, eth4h_nav,
                 spy_nav, qqq_nav, btc_nav, eth_nav,
                 crypto_nav, equity_nav, total_nav) = _sleeve_navs(
                    btc1h_orch, btc4h_orch, eth1h_orch, eth4h_orch, spy_orch, qqq_orch,
                    btc_price, eth_price, spy_price, qqq_price,
                )
                crypto_frac = crypto_nav / total_nav if total_nav > 0 else TARGET_SPLIT
                equity_frac = equity_nav / total_nav if total_nav > 0 else 1.0 - TARGET_SPLIT

            dd_frac = (total_nav / fund_hwm - 1.0) if fund_hwm > 0 else 0.0
            _save_fund_state(
                cycle,
                btc1h_nav, btc4h_nav, eth1h_nav, eth4h_nav, spy_nav, qqq_nav,
                crypto_frac, equity_frac, fund_hwm,
            )
            _append_signal_log(
                cycle,
                btc1h_record, btc4h_record, eth1h_record, eth4h_record,
                spy_record, qqq_record,
                btc1h_nav, btc4h_nav, eth1h_nav, eth4h_nav, spy_nav, qqq_nav,
                total_nav, dd_frac,
            )

            log.info(
                "Cycle %d | NAV=$%.2f | Crypto=$%.2f (%.1f%%) "
                "[BTC=$%.2f (1H=$%.2f 4H=$%.2f) ETH=$%.2f (1H=$%.2f 4H=$%.2f)] "
                "| Equity=$%.2f (%.1f%%) [SPY=$%.2f QQQ=$%.2f] | DD=%.2f%%",
                cycle, total_nav,
                crypto_nav, crypto_frac * 100,
                btc_nav, btc1h_nav, btc4h_nav,
                eth_nav, eth1h_nav, eth4h_nav,
                equity_nav, equity_frac * 100,
                spy_nav, qqq_nav,
                dd_frac * 100,
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
        description="Unified Fund v1 — six-sleeve live runner (BTC_1H, BTC_4H, ETH_1H, ETH_4H, SPY, QQQ)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--capital", type=float, default=100_000.0,
        help="Total fund capital in USD (50%% crypto split into 4 equal sub-sleeves, 50%% equity split 50/50)",
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
            "live  = real-time data feeds; "
            "mock  = rolling-window CSV providers for integration testing"
        ),
    )
    parser.add_argument("--btc-data",  default=None, help="[mock] Path to BTC 1H OHLCV CSV")
    parser.add_argument("--eth-data",  default=None, help="[mock] Path to ETH 1H OHLCV CSV")
    parser.add_argument("--spy-data",  default=None, help="[mock] Path to SPY daily OHLCV CSV")
    parser.add_argument("--qqq-data",  default=None, help="[mock] Path to QQQ daily OHLCV CSV")
    args = parser.parse_args()

    # Capital allocation:
    #   Crypto 50%: BTC_1H=12.5%, BTC_4H=12.5%, ETH_1H=12.5%, ETH_4H=12.5%
    #   Equity 50%: SPY=25%, QQQ=25%
    crypto_sleeve   = args.capital * 0.50
    equity_sleeve   = args.capital * 0.50
    crypto_per_sub  = crypto_sleeve / 4.0   # 12.5% of total fund per crypto sub-sleeve
    equity_per_sub  = equity_sleeve * 0.50  # 25% of total fund per equity sub-sleeve

    log.info(
        "Building orchestrators: "
        "$%.2f crypto ($%.2f × 4 sub-sleeves: BTC_1H, BTC_4H, ETH_1H, ETH_4H), "
        "$%.2f equity ($%.2f × 2 sub-sleeves: SPY, QQQ)",
        crypto_sleeve, crypto_per_sub,
        equity_sleeve, equity_per_sub,
    )

    btc1h_orch = build_btc_1h_orchestrator(crypto_per_sub)
    btc4h_orch = build_btc_4h_orchestrator(crypto_per_sub)
    eth1h_orch = build_eth_1h_orchestrator(crypto_per_sub)
    eth4h_orch = build_eth_4h_orchestrator(crypto_per_sub)
    spy_orch   = build_spy_orchestrator(equity_per_sub)
    qqq_orch   = build_qqq_orchestrator(equity_per_sub)

    log.info(
        "RuntimeState files: %s | %s | %s | %s | %s | %s",
        BTC_1H_STATE_PATH, BTC_4H_STATE_PATH,
        ETH_1H_STATE_PATH, ETH_4H_STATE_PATH,
        SPY_STATE_PATH, QQQ_STATE_PATH,
    )

    if args.mode == "mock":
        missing = [n for n, v in [
            ("--btc-data", args.btc_data),
            ("--eth-data", args.eth_data),
            ("--spy-data", args.spy_data),
            ("--qqq-data", args.qqq_data),
        ] if not v]
        if missing:
            raise SystemExit(f"--mode mock requires: {', '.join(missing)}")
        btc1h_provider = build_mock_crypto_provider(args.btc_data, asset="BTC")
        btc4h_provider = build_mock_crypto_4h_provider(args.btc_data, asset="BTC")
        eth1h_provider = build_mock_crypto_provider(args.eth_data, asset="ETH")
        eth4h_provider = build_mock_crypto_4h_provider(args.eth_data, asset="ETH")
        spy_provider   = build_mock_spy_provider(args.spy_data, args.qqq_data)
        qqq_provider   = build_mock_qqq_provider(args.spy_data, args.qqq_data)
        log.info("Mock CSV providers loaded (4H providers derived from 1H data via resample_ohlcv).")
    else:
        btc1h_provider = build_live_btc_1h_provider()
        btc4h_provider = build_live_btc_4h_provider()
        eth1h_provider = build_live_eth_1h_provider()
        eth4h_provider = build_live_eth_4h_provider()
        spy_provider   = build_live_spy_provider()
        qqq_provider   = build_live_qqq_provider()

    run_fund(
        btc1h_orch=btc1h_orch,
        btc4h_orch=btc4h_orch,
        eth1h_orch=eth1h_orch,
        eth4h_orch=eth4h_orch,
        spy_orch=spy_orch,
        qqq_orch=qqq_orch,
        btc1h_provider=btc1h_provider,
        btc4h_provider=btc4h_provider,
        eth1h_provider=eth1h_provider,
        eth4h_provider=eth4h_provider,
        spy_provider=spy_provider,
        qqq_provider=qqq_provider,
        poll_interval_seconds=args.poll,
        max_cycles=args.max_cycles,
    )


if __name__ == "__main__":
    main()
