"""Layer 2 — TrendFollowingV2 (Binary, Freeze-on-Entry).

Design rationale
----------------
The v1 strategy generates continuous exposure changes (0.40–0.80) driven by
EMA spread strength on *every* bar.  This produces ~280x turnover because the
spread fluctuates constantly, causing the backtest engine to resize the
position on nearly every TREND_UP bar.

V2 eliminates all intra-trend resizing:

1. **Confidence-scaled exposure**: exposure ranges from 0.40 (low-confidence
   entry) to 0.80 (high-confidence entry), determined at entry time and then
   frozen until a structural exit fires.
2. **Freeze on entry**: once long, always return HOLD (delta = 0, no trade)
   unless a genuine structural exit fires.
3. **Tighter entry threshold**: spread must exceed 0.003 (vs 0.002 in v1)
   and price must be firmly above the slow EMA (> 0), reducing false starts.
4. **ATR entry guard**: entries are blocked when ATR% exceeds 2.5% (the
   regime engine's VOL_EXPANSION threshold), filtering high-risk entries.
5. **Disciplined exits**: exit conditions are graduated —
   - HIGH_VOL: immediate emergency exit (regime too dangerous).
   - TREND_DOWN + bearish crossover: requires *both* a regime flip AND EMA
     crossover to exit, preventing exits on brief regime dips that recover.
   - Adaptive trailing exit: price_vs_slow deterioration from its trailing
     peak triggers early exit before deeper structural breaks.
   - Material crossover: EMA spread < -0.5% (not just touching zero).
   - Hard structural break: close < slow EMA by more than -1.5% (vs -0.5%
     in v1), filtering out brief intraday dips below the EMA.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "trend_following_v2"

# ── Parameters ─────────────────────────────────────────────────────────────────
FAST_EMA = 21
SLOW_EMA = 55
MOMENTUM_LOOKBACK = 5

MIN_ENTRY_EXPOSURE = 0.40
MAX_ENTRY_EXPOSURE = 0.80
MIN_ENTRY_SPREAD = 0.003        # fast EMA must be 0.3% above slow (vs 0.2% in v1)

# Exit thresholds — raised vs v1 to suppress whipsaws
CROSSOVER_EXIT_THRESHOLD = -0.005   # spread must cross -0.5% (not just zero)
PRICE_BREAK_THRESHOLD = -0.015      # close < slow_ema * (1 - 0.015)

# Adaptive trailing exit: exit when price_vs_slow drops by this fraction of
# its trailing peak (e.g. peak was 5%, drop to 2% = 60% deterioration).
TRAILING_EXIT_DRAWDOWN_FRAC = 0.60
TRAILING_EXIT_MIN_PEAK = 0.02      # peak must have been at least 2% to arm

# Trailing window: number of bars to look back for the price_vs_slow peak.
TRAILING_PEAK_WINDOW = 72

# ATR entry guard threshold (matches regime engine's mid_vol_threshold)
ATR_ENTRY_BLOCK_THRESHOLD = 0.025

# Exposure threshold below which we consider ourselves "flat"
FLAT_THRESHOLD = 0.05


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _compute_atr_pct(df: pd.DataFrame, period: int = 14) -> float:
    """Compute ATR% at the last bar.  Causal, no lookahead."""
    close = df["close"]
    high = df["high"]
    low = df["low"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()
    return float((atr / close).fillna(0.0).iloc[-1])


def _entry_confidence(
    ema_spread: float,
    spread_momentum: float,
    price_vs_slow: float,
    atr_pct: float,
) -> float:
    """Map trend-strength features to a bounded entry confidence in [0, 1].

    Scores are normalised around the same structural thresholds used by entry
    logic so confidence remains interpretable and stable across market regimes.
    """
    spread_score = _clip01((ema_spread - MIN_ENTRY_SPREAD) / 0.006)
    momentum_score = _clip01((spread_momentum + 0.0015) / 0.003)
    structure_score = _clip01(price_vs_slow / 0.015)
    # Vol penalty: lower confidence when ATR is elevated (but below hard block)
    vol_penalty = _clip01((atr_pct - 0.010) / 0.015)  # 0 at 1%, 1 at 2.5%

    score = (
        0.40 * spread_score
        + 0.25 * momentum_score
        + 0.20 * structure_score
        - 0.15 * vol_penalty
    )
    score = max(0.0, score)
    confidence = 0.25 + 0.65 * score
    return _clip01(confidence)


def _trailing_peak_price_vs_slow(df: pd.DataFrame, window: int) -> float:
    """Compute the peak price_vs_slow over the trailing window.  Causal."""
    close = df["close"]
    ema_slow = close.ewm(span=SLOW_EMA, adjust=False).mean()
    pvs = (close - ema_slow) / ema_slow
    lookback = pvs.iloc[-window:] if len(pvs) >= window else pvs
    return float(lookback.max())


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate a trade intent for the current closed bar.

    Parameters
    ----------
    df :
        OHLCV DataFrame up to and including the current closed bar.
    ctx :
        StrategyContext with regime, current exposure, and asset info.
    closed_only :
        Contract guarantee flag — must be True in production.

    Returns
    -------
    StrategyIntent
    """
    if len(df) < SLOW_EMA + MOMENTUM_LOOKBACK + 5:
        return _warmup_intent(ctx)

    close = df["close"]
    ema_fast = close.ewm(span=FAST_EMA, adjust=False).mean()
    ema_slow = close.ewm(span=SLOW_EMA, adjust=False).mean()

    c = float(close.iloc[-1])
    ef = float(ema_fast.iloc[-1])
    es = float(ema_slow.iloc[-1])

    ema_spread = (ef - es) / c

    ema_spread_series = (ema_fast - ema_slow) / close
    spread_momentum = float(
        ema_spread_series.iloc[-1] - ema_spread_series.iloc[-MOMENTUM_LOOKBACK - 1]
    )

    price_vs_slow = (c - es) / es

    meta = {
        "ema_fast": round(ef, 4),
        "ema_slow": round(es, 4),
        "ema_spread": round(ema_spread, 5),
        "spread_momentum": round(spread_momentum, 6),
        "price_vs_slow_ema": round(price_vs_slow, 5),
        "regime": ctx.regime.value,
    }

    already_long = ctx.current_exposure_frac > FLAT_THRESHOLD

    # ── When long: HOLD or structural exit only ───────────────────────────────
    if already_long:
        # Priority 1 — emergency exit: regime too dangerous
        if ctx.regime == RegimeLabel.HIGH_VOL:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.95,
                desired_exposure_frac=0.0,
                horizon_hours=1,
                reason="HIGH_VOL regime — emergency exit",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Priority 2 — regime flip WITH crossover confirmation
        if ctx.regime == RegimeLabel.TREND_DOWN and ema_spread < 0:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.85,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason="TREND_DOWN confirmed by bearish EMA crossover",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Priority 3 — adaptive trailing exit
        trailing_peak = _trailing_peak_price_vs_slow(df, TRAILING_PEAK_WINDOW)
        meta["trailing_peak_pvs"] = round(trailing_peak, 5)
        if (
            trailing_peak >= TRAILING_EXIT_MIN_PEAK
            and price_vs_slow < trailing_peak * (1.0 - TRAILING_EXIT_DRAWDOWN_FRAC)
        ):
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.82,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=(
                    f"Trailing exit: price_vs_slow {price_vs_slow:.4f} "
                    f"dropped >{TRAILING_EXIT_DRAWDOWN_FRAC:.0%} from peak {trailing_peak:.4f}"
                ),
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Priority 4 — material EMA crossover (spread clearly negative)
        if ema_spread < CROSSOVER_EXIT_THRESHOLD:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.80,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason="Material EMA crossover — fast EMA >0.5% below slow",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Priority 5 — hard structural price break
        if price_vs_slow < PRICE_BREAK_THRESHOLD:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.75,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason="Price >1.5% below slow EMA — structural break",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # No exit condition — freeze exposure, no resize
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.70,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=24,
            reason="In trend — holding, no resize",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── When flat: entry logic only ───────────────────────────────────────────
    atr_pct = _compute_atr_pct(df)
    meta["atr_pct"] = round(atr_pct, 6)

    bullish_entry = (
        ctx.regime == RegimeLabel.TREND_UP
        and ema_spread > MIN_ENTRY_SPREAD
        and price_vs_slow > 0.0
        and spread_momentum >= 0
        and atr_pct <= ATR_ENTRY_BLOCK_THRESHOLD
    )

    if bullish_entry:
        entry_confidence = _entry_confidence(ema_spread, spread_momentum, price_vs_slow, atr_pct)
        desired_exposure = MIN_ENTRY_EXPOSURE + (MAX_ENTRY_EXPOSURE - MIN_ENTRY_EXPOSURE) * entry_confidence
        desired_exposure = _clip01(desired_exposure)

        meta["entry_confidence_raw"] = round(entry_confidence, 6)
        meta["entry_confidence_components"] = {
            "spread_score": round(_clip01((ema_spread - MIN_ENTRY_SPREAD) / 0.006), 6),
            "momentum_score": round(_clip01((spread_momentum + 0.0015) / 0.003), 6),
            "structure_score": round(_clip01(price_vs_slow / 0.015), 6),
            "vol_penalty": round(_clip01((atr_pct - 0.010) / 0.015), 6),
        }
        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=entry_confidence,
            desired_exposure_frac=desired_exposure,
            horizon_hours=72,
            reason="Trend entry: TREND_UP + EMA spread + price structure",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.60,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason="No bullish structure — flat",
        meta=meta,
        strategy_id=STRATEGY_ID,
    )


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
