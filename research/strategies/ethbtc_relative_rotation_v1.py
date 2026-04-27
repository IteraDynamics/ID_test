"""ETH/BTC relative-rotation strategy v1.

Rotates crypto capital allocation between BTC and ETH based on the ETH/BTC
ratio trend.  Does NOT bet on absolute crypto direction — only on which asset
should own the risk budget at any given time.

THIS IS NOT A STANDARD StrategyIntent MODULE.
It does not implement generate_intent() and must not be added to REGISTRY.
Use scripts/run_ethbtc_rotation_backtest.py as the dedicated runner.

Signal logic
------------
- EMA(FAST_EMA) and EMA(SLOW_EMA) on ETHBTC close ratio (causal EWM)
- ETH favored  : fast > slow × (1 + MIN_REL_SPREAD) for CONFIRM_BARS
- BTC favored  : fast < slow × (1 − MIN_REL_SPREAD) for CONFIRM_BARS
- Neutral      : |spread| ≤ MIN_REL_SPREAD
- Signal locked for MIN_HOLD_BARS after each switch (churn prevention)

Target allocations (no leverage, long-only, both assets always held)
---------------------------------------------------------------------
  ETH favored  →  BTC 30% / ETH 70%
  BTC favored  →  BTC 70% / ETH 30%
  Neutral      →  BTC 50% / ETH 50%
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


# ── Constants ──────────────────────────────────────────────────────────────────

STRATEGY_ID = "ethbtc_relative_rotation_v1"

FAST_EMA = 48          # ~2 days at 1H
SLOW_EMA = 240         # ~10 days at 1H
CONFIRM_BARS = 8       # raw signal must persist this many bars before acting
MIN_HOLD_BARS = 48     # bars before rotation is allowed after the last switch
MIN_REL_SPREAD = 0.005 # EMA spread threshold (0.5% of slow EMA)

BTC_FRAC_ETH_FAVORED = 0.30
ETH_FRAC_ETH_FAVORED = 0.70
BTC_FRAC_BTC_FAVORED = 0.70
ETH_FRAC_BTC_FAVORED = 0.30
BTC_FRAC_NEUTRAL = 0.50
ETH_FRAC_NEUTRAL = 0.50

# Signal integer codes
ETH_FAVORED = 1
NEUTRAL = 0
BTC_FAVORED = -1


# ── Data types ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TargetAllocation:
    btc_frac: float
    eth_frac: float
    signal: int
    label: str


def signal_to_allocation(signal: int) -> TargetAllocation:
    """Map a signal integer to a target allocation dataclass."""
    if signal == ETH_FAVORED:
        return TargetAllocation(BTC_FRAC_ETH_FAVORED, ETH_FRAC_ETH_FAVORED, signal, "ETH_FAVORED")
    if signal == BTC_FAVORED:
        return TargetAllocation(BTC_FRAC_BTC_FAVORED, ETH_FRAC_BTC_FAVORED, signal, "BTC_FAVORED")
    return TargetAllocation(BTC_FRAC_NEUTRAL, ETH_FRAC_NEUTRAL, signal, "NEUTRAL")


# ── Signal computation ─────────────────────────────────────────────────────────

def compute_rotation_signal(
    ratio_df: pd.DataFrame,
    fast_ema: int = FAST_EMA,
    slow_ema: int = SLOW_EMA,
    confirm_bars: int = CONFIRM_BARS,
    min_hold_bars: int = MIN_HOLD_BARS,
    min_rel_spread: float = MIN_REL_SPREAD,
) -> pd.Series:
    """Compute the causal confirmed rotation signal for every bar.

    No lookahead: EWM is computed causally (adjust=False). The confirmation
    and min-hold logic is applied in a single forward pass.

    Parameters
    ----------
    ratio_df :
        ETHBTC synthetic ratio OHLCV (from ``build_ratio_df``).
    fast_ema, slow_ema :
        EMA span in bars.
    confirm_bars :
        Consecutive bars the raw signal must persist before activating.
    min_hold_bars :
        Minimum bars to hold a signal before a switch is allowed.
    min_rel_spread :
        Minimum |EMA spread / slow EMA| to produce a non-neutral raw signal.

    Returns
    -------
    pd.Series[int]
        ETH_FAVORED (+1), NEUTRAL (0), or BTC_FAVORED (-1) for every bar.
    """
    close = ratio_df["close"]

    fast = close.ewm(span=fast_ema, adjust=False).mean()
    slow = close.ewm(span=slow_ema, adjust=False).mean()
    spread = (fast - slow) / slow  # ratio always positive — no zero-division risk

    raw = np.zeros(len(close), dtype=np.int8)
    raw[spread.values > min_rel_spread] = ETH_FAVORED
    raw[spread.values < -min_rel_spread] = BTC_FAVORED

    confirmed = np.zeros(len(close), dtype=np.int8)
    current: int = NEUTRAL
    pending: int = NEUTRAL
    count: int = 0
    last_change: int = -9999

    for i in range(len(raw)):
        rv = int(raw[i])
        if rv == pending:
            count += 1
        else:
            pending = rv
            count = 1

        if (
            count >= confirm_bars
            and (i - last_change) >= min_hold_bars
            and pending != current
        ):
            current = pending
            last_change = i

        confirmed[i] = current

    return pd.Series(confirmed, index=close.index, name="rotation_signal")
