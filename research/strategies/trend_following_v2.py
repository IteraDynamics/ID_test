"""Layer 2 — TrendFollowingV2 (Binary, Freeze-on-Entry).

Design rationale
----------------
The v1 strategy generates continuous exposure changes (0.40–0.80) driven by
EMA spread strength on *every* bar.  This produces ~280x turnover because the
spread fluctuates constantly, causing the backtest engine to resize the
position on nearly every TREND_UP bar.

V2 eliminates all intra-trend resizing:

1. **Binary exposure**: flat (0.0) or long (0.75) — two states only.
2. **Freeze on entry**: once long, always return HOLD (delta = 0, no trade)
   unless a genuine structural exit fires.
3. **Tighter entry threshold**: spread must exceed 0.003 (vs 0.002 in v1)
   and price must be firmly above the slow EMA (> 0), reducing false starts.
4. **Disciplined exits**: exit conditions are graduated —
   - HIGH_VOL: immediate emergency exit (regime too dangerous).
   - TREND_DOWN + bearish crossover: requires *both* a regime flip AND EMA
     crossover to exit, preventing exits on brief regime dips that recover.
   - Material crossover: EMA spread < -0.5% (not just touching zero).
   - Hard structural break: close < slow EMA by more than -1.5% (vs -0.5%
     in v1), filtering out brief intraday dips below the EMA.

Expected impact
---------------
- Trades: ~50–120 (from ~560–690)
- Turnover: ~20–60x (from ~280x)
- Net CAGR: similar or better (fewer entry/exit round-trips vs v1 whipsaws)
"""

from __future__ import annotations

import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "trend_following_v2"

# ── Parameters ─────────────────────────────────────────────────────────────────
FAST_EMA = 21
SLOW_EMA = 55
MOMENTUM_LOOKBACK = 5

ENTRY_EXPOSURE = 0.75           # fixed — no continuous sizing
MIN_ENTRY_SPREAD = 0.003        # fast EMA must be 0.3% above slow (vs 0.2% in v1)

# Exit thresholds — raised vs v1 to suppress whipsaws
CROSSOVER_EXIT_THRESHOLD = -0.005   # spread must cross -0.5% (not just zero)
PRICE_BREAK_THRESHOLD = -0.015      # close < slow_ema * (1 - 0.015)

# Exposure threshold below which we consider ourselves "flat"
FLAT_THRESHOLD = 0.05


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

        # Priority 3 — material EMA crossover (spread clearly negative)
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

        # Priority 4 — hard structural price break
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
    bullish_entry = (
        ctx.regime == RegimeLabel.TREND_UP
        and ema_spread > MIN_ENTRY_SPREAD
        and price_vs_slow > 0.0          # price firmly above slow EMA
        and spread_momentum >= 0         # trend not decelerating
    )

    if bullish_entry:
        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=0.75,
            desired_exposure_frac=ENTRY_EXPOSURE,
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
