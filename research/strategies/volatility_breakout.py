"""Layer 2 — VolatilityBreakoutStrategy (Orthogonal Alpha Sleeve).

Logic summary:
    Detects vol-compression consolidation followed by directional breakout.
    This strategy is orthogonal to the trend-following sleeve — it fires
    when volatility transitions from contracted to expanded, capturing the
    initial impulse.

Signal construction:
    1. Vol contraction: rolling ATR-pct below compression threshold for N bars.
    2. Breakout: close moves beyond Bollinger-band equivalent (ATR-based band).
    3. Direction: upward breakout only (long-only strategy).
    4. Regime gate: active in VOL_COMPRESSION → VOL_EXPANSION transition,
       and in RANGE regime.  Disabled in HIGH_VOL (too late, risk is on).

Entry conditions (all must hold):
    - Prior N bars in contracted-vol state.
    - Current close > upper band (contraction midpoint + mult * ATR).
    - Regime is VOL_COMPRESSION, RANGE, or VOL_EXPANSION (entry at start).
    - Volume surge: volume > vol_lookback average × vol_surge_mult.

Exit conditions:
    - Price falls back below the breakout level (midpoint of consolidation range).
    - Regime transitions to HIGH_VOL (volatility overshoot, risk-off).
    - Fixed time-stop: horizon_hours exceeded (evaluated by harness/runtime).

Sizing:
    - 0.50 base, scaled by volume surge strength and consolidation duration.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "vol_breakout_v1"

# ── Parameters ─────────────────────────────────────────────────────────────────
ATR_PERIOD = 14
CONSOLIDATION_BARS = 12          # bars vol must be compressed before breakout
COMPRESSION_ATR_PCT = 0.018      # ATR/close threshold for "compressed"
BREAKOUT_MULT = 1.5              # band = midpoint ± mult * ATR
VOL_SURGE_MULT = 1.4             # volume must be X× its lookback average
VOL_LOOKBACK = 20                # volume average lookback
MIN_EXPOSURE = 0.35
MAX_EXPOSURE = 0.60
HORIZON_HOURS = 24


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate a breakout intent for the current closed bar."""
    min_bars = ATR_PERIOD + CONSOLIDATION_BARS + VOL_LOOKBACK + 5
    if len(df) < min_bars:
        return _warmup_intent(ctx)

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    atr = _atr(high, low, close, ATR_PERIOD)
    atr_pct = atr / close

    # Rolling mean of ATR-pct for consolidation check
    # A bar is "compressed" if atr_pct <= COMPRESSION_ATR_PCT
    compressed = (atr_pct <= COMPRESSION_ATR_PCT).astype(float)
    n_compressed = compressed.rolling(CONSOLIDATION_BARS).sum()

    c = float(close.iloc[-1])
    atr_now = float(atr.iloc[-1])
    compressed_count = float(n_compressed.iloc[-1])

    # Midpoint of last CONSOLIDATION_BARS range
    recent_high = float(high.iloc[-CONSOLIDATION_BARS:].max())
    recent_low = float(low.iloc[-CONSOLIDATION_BARS:].min())
    consolidation_mid = (recent_high + recent_low) / 2.0

    # Breakout band
    upper_band = consolidation_mid + BREAKOUT_MULT * atr_now

    # Volume surge
    avg_vol = float(volume.rolling(VOL_LOOKBACK).mean().iloc[-1])
    cur_vol = float(volume.iloc[-1])
    vol_ratio = cur_vol / avg_vol if avg_vol > 0 else 0.0

    meta = {
        "atr_pct": round(float(atr_pct.iloc[-1]), 5),
        "compressed_count": compressed_count,
        "consolidation_mid": round(consolidation_mid, 4),
        "upper_band": round(upper_band, 4),
        "vol_ratio": round(vol_ratio, 3),
        "regime": ctx.regime.value,
    }

    # ── Regime-based exit ─────────────────────────────────────────────
    if ctx.regime == RegimeLabel.HIGH_VOL and ctx.current_exposure_frac > 0:
        return StrategyIntent(
            action=Action.EXIT_LONG,
            confidence=0.85,
            desired_exposure_frac=0.0,
            horizon_hours=2,
            reason="HIGH_VOL regime: vol breakout strategy exits to protect capital",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── Price-based exit: close fell back below midpoint ──────────────
    if ctx.current_exposure_frac > 0 and c < consolidation_mid:
        return StrategyIntent(
            action=Action.EXIT_LONG,
            confidence=0.75,
            desired_exposure_frac=0.0,
            horizon_hours=2,
            reason="Price retreated below consolidation midpoint — breakout failed",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── Entry: breakout above upper band ─────────────────────────────
    entry_regime_ok = ctx.regime in (
        RegimeLabel.VOL_COMPRESSION,
        RegimeLabel.RANGE,
        RegimeLabel.VOL_EXPANSION,
        RegimeLabel.TREND_UP,
    )

    if (
        entry_regime_ok
        and compressed_count >= CONSOLIDATION_BARS * 0.75
        and c > upper_band
        and vol_ratio >= VOL_SURGE_MULT
    ):
        # Scale by how many compressed bars (more consolidation → stronger breakout)
        consolidation_strength = min(compressed_count / CONSOLIDATION_BARS, 1.0)
        vol_strength = min((vol_ratio - 1.0) / 2.0, 1.0)
        exposure = MIN_EXPOSURE + consolidation_strength * vol_strength * (MAX_EXPOSURE - MIN_EXPOSURE)
        exposure = round(min(exposure, MAX_EXPOSURE), 4)
        confidence = round(0.55 + consolidation_strength * 0.3, 4)

        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=confidence,
            desired_exposure_frac=exposure,
            horizon_hours=HORIZON_HOURS,
            reason=(
                f"Vol breakout: {int(compressed_count)} compressed bars, "
                f"close {c:.2f} above band {upper_band:.2f}, vol×{vol_ratio:.2f}"
            ),
            meta={
                **meta,
                "consolidation_strength": round(consolidation_strength, 4),
                "vol_strength": round(vol_strength, 4),
            },
            strategy_id=STRATEGY_ID,
        )

    # ── Hold ──────────────────────────────────────────────────────────
    if ctx.current_exposure_frac > 0:
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.60,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=HORIZON_HOURS,
            reason="Holding breakout position",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── Flat ──────────────────────────────────────────────────────────
    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.50,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason="No breakout signal — waiting for consolidation + breakout",
        meta=meta,
        strategy_id=STRATEGY_ID,
    )


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
