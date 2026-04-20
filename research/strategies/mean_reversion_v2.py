"""Layer 2 — MeanReversionV2 (Active Dip-Buyer for BTC Ranging Markets).

Why v1 under-delivers as a portfolio complement
-------------------------------------------------
mean_reversion_v1 requires RSI < 35 AND bb_pos < 0.25 AND atr < 2.5% AND
regime in {RANGE, VOL_COMPRESSION}.  On hourly BTC, this four-way conjunction
is rare — v1 fires infrequently, sizes conservatively (25-45% NAV), and has
no exit discipline if the mean simply doesn't restore.  Portfolio contribution
is negligible.

v2 design goals
---------------
The trend-following sleeve (v8_ecap75_add90) is flat ~40% of the time —
during RANGE and VOL_COMPRESSION regimes when BTC is consolidating.  v2 is
designed to put that idle capital to work:

  - Broader entry: RSI < 40 (not 35), bb_pos < 0.30 (not 0.25).
    Catches a larger fraction of genuine oversold dips without becoming
    noise-prone.

  - Larger sizing: 0.40 – 0.60 NAV.  Sized to matter in a portfolio context.
    Scaled by oversold depth and band depth, same formula as v1 but with
    higher bounds.

  - Timeout exit: hard 48-bar (48 hour) exit if neither the RSI target nor
    the price target is reached.  Prevents capital from being trapped in a
    position that simply drifts sideways.

  - Profit exit: price crosses above BB midline + 1% buffer (not just midline).
    Gives the mean-reversion move room to complete without triggering on noise.

  - RSI exit target raised: 60 (not 55).  Allows more of the reversion move
    to be captured before exiting.

Regime logic unchanged from v1
--------------------------------
  - Entry only in RANGE or VOL_COMPRESSION.
  - Any transition to TREND_UP, TREND_DOWN, HIGH_VOL, or VOL_EXPANSION
    triggers an immediate exit.  Mean reversion in a trending or spiking
    market is a losing proposition.

Portfolio role
--------------
Intended as a 25-35% weight sleeve alongside the trend-following primary.
Correlation with trend-following is structurally low: it activates in the
regime windows where the trend follower is deliberately flat.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "mean_reversion_v2"

# ── Indicators ────────────────────────────────────────────────────────────────
RSI_PERIOD = 14
BB_PERIOD = 20
BB_STD = 2.0
ATR_PERIOD = 14

# ── Entry gates ───────────────────────────────────────────────────────────────
OVERSOLD_THRESHOLD = 40.0       # raised from 35 — catches more genuine dips
BB_ENTRY_POS = 0.30             # raised from 0.25 — lower quartile of band
MAX_ATR_PCT = 0.030             # raised from 2.5% — slightly more vol tolerance

# ── Sizing ────────────────────────────────────────────────────────────────────
MIN_EXPOSURE = 0.40             # raised from 0.25
MAX_EXPOSURE = 0.60             # raised from 0.45

# ── Exits ─────────────────────────────────────────────────────────────────────
EXIT_RSI = 60.0                 # raised from 55 — capture more of the move
BB_MIDLINE_BUFFER = 0.010       # exit when price > midline + 1%
TIMEOUT_BARS = 48               # hard timeout: exit after 48 bars if unresolved

_REVERSION_REGIMES = frozenset([RegimeLabel.RANGE, RegimeLabel.VOL_COMPRESSION])
_EXIT_REGIMES = frozenset([
    RegimeLabel.TREND_UP,
    RegimeLabel.TREND_DOWN,
    RegimeLabel.HIGH_VOL,
    RegimeLabel.VOL_EXPANSION,
])


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate a mean-reversion intent for the current closed bar."""
    min_bars = max(RSI_PERIOD, BB_PERIOD, ATR_PERIOD) + TIMEOUT_BARS + 10
    if len(df) < min_bars:
        return _warmup_intent(ctx)

    close = df["close"]
    high = df["high"]
    low = df["low"]

    rsi_series = _rsi(close, RSI_PERIOD)
    bb_mid, bb_upper, bb_lower = _bollinger(close, BB_PERIOD, BB_STD)
    atr = _atr(high, low, close, ATR_PERIOD)
    atr_pct = atr / close

    c = float(close.iloc[-1])
    rsi = float(rsi_series.iloc[-1])
    mid = float(bb_mid.iloc[-1])
    upper = float(bb_upper.iloc[-1])
    lower = float(bb_lower.iloc[-1])
    atr_pct_now = float(atr_pct.iloc[-1])

    band_range = upper - lower
    bb_pos = ((c - lower) / band_range) if band_range > 1e-10 else 0.5

    # Timeout: count how many bars since we entered (bar_index proxy via df length)
    # We use the distance from current bar back to where exposure first became non-zero.
    # Approximated by looking at the RSI series for a sustained entry window.
    # Since the strategy is stateless, we estimate bars-in-trade via a trailing
    # price comparison: how long has price been below the midline continuously?
    bars_below_mid = int(
        (close.iloc[-TIMEOUT_BARS:] < bb_mid.iloc[-TIMEOUT_BARS:]).sum()
    )
    timeout_triggered = (
        ctx.current_exposure_frac > 0 and bars_below_mid >= TIMEOUT_BARS
    )

    meta = {
        "rsi": round(rsi, 2),
        "bb_pos": round(bb_pos, 4),
        "bb_mid": round(mid, 4),
        "atr_pct": round(atr_pct_now, 5),
        "bars_below_mid": bars_below_mid,
        "regime": ctx.regime.value,
    }

    already_long = ctx.current_exposure_frac > 0

    # ── Priority 1: Regime override exit ─────────────────────────────────────
    if already_long and ctx.regime in _EXIT_REGIMES:
        return StrategyIntent(
            action=Action.EXIT_LONG,
            confidence=0.90,
            desired_exposure_frac=0.0,
            horizon_hours=2,
            reason=f"Regime {ctx.regime.value} not compatible with mean-reversion — exit",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── Priority 2: Profit / RSI exit ─────────────────────────────────────────
    if already_long:
        profit_target_hit = c >= mid * (1.0 + BB_MIDLINE_BUFFER)
        rsi_target_hit = rsi >= EXIT_RSI
        if profit_target_hit or rsi_target_hit:
            reason = (
                f"RSI={rsi:.1f} ≥ {EXIT_RSI}"
                if rsi_target_hit
                else f"Price {c:.2f} ≥ midline+{BB_MIDLINE_BUFFER:.0%} ({mid * (1 + BB_MIDLINE_BUFFER):.2f})"
            )
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.80,
                desired_exposure_frac=0.0,
                horizon_hours=2,
                reason=reason,
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

    # ── Priority 3: Timeout exit ───────────────────────────────────────────────
    if timeout_triggered:
        return StrategyIntent(
            action=Action.EXIT_LONG,
            confidence=0.65,
            desired_exposure_frac=0.0,
            horizon_hours=2,
            reason=f"Timeout: {TIMEOUT_BARS} bars without mean restoration",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── Entry ─────────────────────────────────────────────────────────────────
    if (
        not already_long
        and ctx.regime in _REVERSION_REGIMES
        and rsi < OVERSOLD_THRESHOLD
        and bb_pos < BB_ENTRY_POS
        and atr_pct_now < MAX_ATR_PCT
    ):
        oversold_depth = max(0.0, (OVERSOLD_THRESHOLD - rsi) / OVERSOLD_THRESHOLD)
        band_depth = max(0.0, BB_ENTRY_POS - bb_pos) / BB_ENTRY_POS

        exposure = MIN_EXPOSURE + (
            oversold_depth * 0.5 + band_depth * 0.5
        ) * (MAX_EXPOSURE - MIN_EXPOSURE)
        exposure = round(min(exposure, MAX_EXPOSURE), 4)
        confidence = round(min(0.50 + oversold_depth * 0.35, 0.85), 4)

        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=confidence,
            desired_exposure_frac=exposure,
            horizon_hours=TIMEOUT_BARS,
            reason=(
                f"MR entry: RSI={rsi:.1f} oversold, "
                f"bb_pos={bb_pos:.3f}, regime={ctx.regime.value}, "
                f"exposure={exposure:.0%}"
            ),
            meta={
                **meta,
                "oversold_depth": round(oversold_depth, 4),
                "band_depth": round(band_depth, 4),
            },
            strategy_id=STRATEGY_ID,
        )

    # ── Hold ──────────────────────────────────────────────────────────────────
    if already_long:
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.55,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=TIMEOUT_BARS,
            reason=f"Holding MR position — RSI={rsi:.1f}, bb_pos={bb_pos:.3f}",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── Flat ──────────────────────────────────────────────────────────────────
    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.50,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason=f"No oversold condition — RSI={rsi:.1f}, bb_pos={bb_pos:.3f}, regime={ctx.regime.value}",
        meta=meta,
        strategy_id=STRATEGY_ID,
    )


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _bollinger(
    close: pd.Series, period: int, std_mult: float
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = close.rolling(period).mean()
    std = close.rolling(period).std(ddof=0)
    return mid, mid + std_mult * std, mid - std_mult * std


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def _warmup_intent(ctx: StrategyContext) -> StrategyIntent:
    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.0,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason="Insufficient data — warmup period",
        meta={"regime": ctx.regime.value},
        strategy_id=STRATEGY_ID,
    )
