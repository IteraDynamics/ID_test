"""Layer 2 — MeanReversionStrategy (Counter-trend / Volatility Smoothing).

Logic summary:
    Captures short-term mean-reversion in ranging / compressed-vol environments.
    This sleeve is behaviorally anti-correlated with the trend-following sleeve,
    providing portfolio-level smoothing during consolidation periods.

Signal construction:
    1. RSI: classic 14-period RSI for overbought/oversold detection.
    2. Bollinger position: normalised price position within Bollinger bands.
    3. Regime gate: only active in RANGE or VOL_COMPRESSION regimes.
       Mean reversion in a strong trend is a value-destroying strategy.

Entry conditions (all must hold):
    - Regime is RANGE or VOL_COMPRESSION.
    - RSI < OVERSOLD_THRESHOLD (default 35).
    - Price in lower quartile of Bollinger band (bb_pos < 0.25).
    - No ongoing vol expansion (atr_pct not accelerating sharply).

Exit conditions (any triggers):
    - RSI > EXIT_RSI (default 55 — mean restored).
    - Price crosses above Bollinger midline.
    - Regime exits RANGE/VOL_COMPRESSION (trend or vol-spike overrides).

Sizing:
    - Conservative: 0.25–0.45 of NAV.
    - This is a volatility-smoothing sleeve; it's not the primary P&L driver.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "mean_reversion_v1"

# ── Parameters ─────────────────────────────────────────────────────────────────
RSI_PERIOD = 14
BB_PERIOD = 20
BB_STD = 2.0
OVERSOLD_THRESHOLD = 35.0
EXIT_RSI = 55.0
ATR_PERIOD = 14
MAX_ATR_PCT = 0.025       # don't enter if vol is expanding
MIN_EXPOSURE = 0.25
MAX_EXPOSURE = 0.45
HORIZON_HOURS = 12


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate a mean-reversion intent for the current closed bar."""
    min_bars = max(RSI_PERIOD, BB_PERIOD, ATR_PERIOD) + 10
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

    # Normalised position in band: 0 = at lower band, 1 = at upper band
    band_range = upper - lower
    bb_pos = ((c - lower) / band_range) if band_range > 1e-10 else 0.5

    meta = {
        "rsi": round(rsi, 2),
        "bb_pos": round(bb_pos, 4),
        "bb_mid": round(mid, 4),
        "atr_pct": round(atr_pct_now, 5),
        "regime": ctx.regime.value,
    }

    # ── Regime exit: trend or high vol overrides reversion ────────────
    regime_override = ctx.regime in (
        RegimeLabel.TREND_DOWN,
        RegimeLabel.HIGH_VOL,
        RegimeLabel.VOL_EXPANSION,
        RegimeLabel.TREND_UP,
    )
    if regime_override and ctx.current_exposure_frac > 0:
        return StrategyIntent(
            action=Action.EXIT_LONG,
            confidence=0.85,
            desired_exposure_frac=0.0,
            horizon_hours=2,
            reason=f"Regime {ctx.regime.value} not compatible with mean-reversion — exit",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── Exit: RSI normalised / price above midline ────────────────────
    if ctx.current_exposure_frac > 0:
        mean_restored = rsi >= EXIT_RSI or c >= mid
        if mean_restored:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.75,
                desired_exposure_frac=0.0,
                horizon_hours=2,
                reason=f"Mean restored: RSI={rsi:.1f}, price vs mid={c:.2f}/{mid:.2f}",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

    # ── Entry ─────────────────────────────────────────────────────────
    reversion_regime = ctx.regime in (RegimeLabel.RANGE, RegimeLabel.VOL_COMPRESSION)

    if (
        reversion_regime
        and rsi < OVERSOLD_THRESHOLD
        and bb_pos < 0.25
        and atr_pct_now < MAX_ATR_PCT
    ):
        # Deeper oversold = more confident / larger size
        oversold_depth = max(0.0, (OVERSOLD_THRESHOLD - rsi) / OVERSOLD_THRESHOLD)
        band_depth = max(0.0, 0.25 - bb_pos) * 4  # 0..1 as pos falls 0.25→0

        exposure = MIN_EXPOSURE + (oversold_depth * 0.5 + band_depth * 0.5) * (
            MAX_EXPOSURE - MIN_EXPOSURE
        )
        exposure = round(min(exposure, MAX_EXPOSURE), 4)
        confidence = round(0.50 + oversold_depth * 0.35, 4)

        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=confidence,
            desired_exposure_frac=exposure,
            horizon_hours=HORIZON_HOURS,
            reason=(
                f"Mean-reversion entry: RSI={rsi:.1f} oversold, "
                f"bb_pos={bb_pos:.3f}, regime={ctx.regime.value}"
            ),
            meta={
                **meta,
                "oversold_depth": round(oversold_depth, 4),
                "band_depth": round(band_depth, 4),
            },
            strategy_id=STRATEGY_ID,
        )

    # ── Hold ──────────────────────────────────────────────────────────
    if ctx.current_exposure_frac > 0:
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.55,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=HORIZON_HOURS,
            reason="Holding mean-reversion position — awaiting normalisation",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── Flat ──────────────────────────────────────────────────────────
    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.50,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason="No oversold condition in ranging regime — flat",
        meta=meta,
        strategy_id=STRATEGY_ID,
    )


# ── Indicators ─────────────────────────────────────────────────────────────────

def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _bollinger(close: pd.Series, period: int, std_mult: float) -> tuple[pd.Series, pd.Series, pd.Series]:
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
