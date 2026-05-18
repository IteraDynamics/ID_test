"""Execution model — deterministic fill cost computation.

Canonical source of truth for execution costs.  Used identically by:
- research/harness/backtest_engine.py  (offline research)
- runtime/argus/brokers/paper_broker.py  (live paper trading)

No randomness.  No external data.  No lookahead.

Slippage model
--------------
slippage_bps = base_slippage_bps
             + slippage_size_factor  * (notional / nav)
             + slippage_vol_factor   * atr_pct
             + [nonlinear penalty if notional > large_trade_threshold * nav]

Clamped to [min_slippage_bps, max_slippage_bps].

Spread model
------------
half_spread_bps = max(min_spread_bps, spread_k * atr_pct * 10_000 / 2)

Applied per side (entry and exit both pay half-spread).

Fee model
---------
fee_usd = notional * fee_rate   (taker by default; maker optional)

Cash accounting
---------------
The total fill adjustment (slippage + spread) is embedded in effective_price,
not deducted as a separate cash flow.  Only fee_usd is a direct cash deduction.
slippage_usd and spread_usd are accounting figures that quantify the implicit
NAV cost from worse fill prices.

cost_bps = (fee_usd + slippage_usd + spread_usd) / notional * 10_000
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pandas as pd


# ── Environment-backed defaults ────────────────────────────────────────────────

def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key, "")
    if val.lower() in ("1", "true", "yes"):
        return True
    if val.lower() in ("0", "false", "no"):
        return False
    return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass
class ExecutionConfig:
    """All parameters controlling fill cost simulation.

    Parameters
    ----------
    taker_fee_rate : float
        Taker fee as a fraction of notional (default 0.0006 = 6 bps).
    maker_fee_rate : float
        Maker fee as a fraction of notional (default 0.0002 = 2 bps).
    use_maker_fees : bool
        If True, use maker_fee_rate; otherwise taker_fee_rate.
    base_slippage_bps : float
        Floor slippage regardless of trade size or volatility (bps).
    slippage_size_factor : float
        Additional slippage per unit of NAV turned over (bps at 100% turnover).
    slippage_vol_factor : float
        Additional slippage per unit of ATR% (bps at 100% ATR).
    min_slippage_bps : float
        Hard floor on slippage component (bps).
    max_slippage_bps : float
        Hard ceiling on slippage component (bps).
    spread_k : float
        Spread coefficient: half_spread_bps = k * atr_pct * 10_000 / 2.
    min_spread_bps : float
        Minimum half-spread per side (bps).
    large_trade_threshold : float
        Notional fraction of NAV above which nonlinear slippage applies.
    cooldown_bars : int
        Minimum bars between consecutive trades (backtest engine only).
    """

    taker_fee_rate: float = 0.0006
    maker_fee_rate: float = 0.0002
    use_maker_fees: bool = False

    base_slippage_bps: float = 3.0
    slippage_size_factor: float = 10.0
    slippage_vol_factor: float = 50.0
    min_slippage_bps: float = 1.0
    max_slippage_bps: float = 50.0

    spread_k: float = 0.5
    min_spread_bps: float = 1.0

    large_trade_threshold: float = 0.25

    cooldown_bars: int = 0

    @classmethod
    def from_env(cls) -> "ExecutionConfig":
        """Construct config from environment variables, falling back to defaults."""
        return cls(
            taker_fee_rate=_env_float("FEE_RATE", 0.0006),
            maker_fee_rate=_env_float("MAKER_FEE_RATE", 0.0002),
            use_maker_fees=_env_bool("USE_MAKER_FEES", False),
            base_slippage_bps=_env_float("BASE_SLIPPAGE_BPS", 3.0),
            slippage_size_factor=_env_float("SLIPPAGE_SIZE_FACTOR", 10.0),
            slippage_vol_factor=_env_float("SLIPPAGE_VOL_FACTOR", 50.0),
            min_slippage_bps=_env_float("MIN_SLIPPAGE_BPS", 1.0),
            max_slippage_bps=_env_float("MAX_SLIPPAGE_BPS", 50.0),
            spread_k=_env_float("SPREAD_K", 0.5),
            min_spread_bps=_env_float("MIN_SPREAD_BPS", 1.0),
            large_trade_threshold=_env_float("LARGE_TRADE_THRESHOLD", 0.25),
            cooldown_bars=_env_int("COOLDOWN_BARS", 0),
        )


@dataclass
class FillResult:
    """Outcome of a single simulated fill.

    Attributes
    ----------
    mid_price : float
        The bar close price before any adjustment.
    effective_price : float
        Actual fill price after slippage + spread adjustment.
    fee_usd : float
        Exchange fee (explicit cash deduction).
    slippage_usd : float
        Implicit NAV cost from worse fill price (accounting only).
    spread_usd : float
        Implicit NAV cost from bid/ask spread (accounting only).
    total_cost_usd : float
        fee_usd + slippage_usd + spread_usd.
    cost_bps : float
        total_cost_usd / notional * 10_000.
    slippage_bps_applied : float
        Slippage component actually applied (after clamping).
    fee_rate_applied : float
        The fee rate used (taker or maker).
    """

    mid_price: float
    effective_price: float
    fee_usd: float
    slippage_usd: float
    spread_usd: float
    total_cost_usd: float
    cost_bps: float
    slippage_bps_applied: float
    fee_rate_applied: float


def compute_fill(
    mid_price: float,
    notional: float,
    nav: float,
    atr_pct: float,
    direction: str,
    config: ExecutionConfig,
) -> FillResult:
    """Compute a deterministic fill result for one trade.

    Parameters
    ----------
    mid_price :
        Bar close price (the execution reference price).
    notional :
        Target trade size in USD at mid-price.
    nav :
        Current portfolio NAV in USD (used for size-relative slippage).
    atr_pct :
        ATR as fraction of price at current bar (e.g. 0.02 = 2%).
    direction :
        "BUY" or "SELL".
    config :
        ExecutionConfig controlling all cost parameters.

    Returns
    -------
    FillResult
    """
    # ── Fee ───────────────────────────────────────────────────────────────────
    fee_rate = config.maker_fee_rate if config.use_maker_fees else config.taker_fee_rate
    fee_usd = notional * fee_rate

    # ── Slippage ──────────────────────────────────────────────────────────────
    size_frac = notional / nav if nav > 1e-9 else 0.0

    slippage_bps = (
        config.base_slippage_bps
        + config.slippage_size_factor * size_frac
        + config.slippage_vol_factor * atr_pct
    )

    # Nonlinear penalty: marginal cost doubles above large_trade_threshold
    if size_frac > config.large_trade_threshold:
        excess = size_frac - config.large_trade_threshold
        slippage_bps += config.slippage_size_factor * excess

    slippage_bps = float(
        np.clip(slippage_bps, config.min_slippage_bps, config.max_slippage_bps)
    )

    # ── Spread (half-spread per side) ─────────────────────────────────────────
    half_spread_bps = max(
        config.min_spread_bps,
        config.spread_k * atr_pct * 10_000.0 / 2.0,
    )

    # ── Effective fill price ──────────────────────────────────────────────────
    total_adj_bps = slippage_bps + half_spread_bps
    adj_frac = total_adj_bps / 10_000.0

    if direction == "BUY":
        effective_price = mid_price * (1.0 + adj_frac)
    else:
        effective_price = mid_price * (1.0 - adj_frac)

    # ── Cost accounting ───────────────────────────────────────────────────────
    slippage_usd = notional * (slippage_bps / 10_000.0)
    spread_usd = notional * (half_spread_bps / 10_000.0)
    total_cost_usd = fee_usd + slippage_usd + spread_usd
    cost_bps = (total_cost_usd / notional * 10_000.0) if notional > 0 else 0.0

    return FillResult(
        mid_price=mid_price,
        effective_price=effective_price,
        fee_usd=fee_usd,
        slippage_usd=slippage_usd,
        spread_usd=spread_usd,
        total_cost_usd=total_cost_usd,
        cost_bps=cost_bps,
        slippage_bps_applied=slippage_bps,
        fee_rate_applied=fee_rate,
    )


def compute_atr_pct_series(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute ATR as a fraction of close for every bar in *df*.

    Uses Wilder's EWM formulation (adjust=False) — causal, no lookahead.
    Returns a Series aligned to df.index.  First ~period bars will be small
    but non-zero due to EWM warm-up.
    """
    close = df["close"]
    high = df["high"]
    low = df["low"]

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = tr.ewm(span=period, adjust=False).mean()
    atr_pct = (atr / close).fillna(0.0)
    return atr_pct


def compute_atr_pct_scalar(df: pd.DataFrame, period: int = 14) -> float:
    """Return ATR% at the last bar of *df*.  Convenience wrapper."""
    series = compute_atr_pct_series(df, period=period)
    if len(series) == 0:
        return 0.0
    return float(series.iloc[-1])
