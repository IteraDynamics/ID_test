"""Layer 2 — TrendFollowingV8 (Regime-Graduated Entry + Slippage Control).

Analysis of v7 (-63% DD, +29% CAGR)
-------------------------------------
v7 removed the TREND_UP regime gate entirely, allowing entries whenever EMA
indicators were bullish regardless of volatility regime.  This increased CAGR
from 22% to 29% but blew the max drawdown to -63% — outside the institutional
target of -35% to -50%.  The Calmar ratio *worsened* slightly (0.46 vs 0.51).

Two compounding problems identified:
1. **Drawdown**: entries during HIGH_VOL regime (ATR > 4%) combined with 90%
   base exposure means a 20-30% BTC flash-crash wipes 18-27% of the portfolio
   in a single event.  Multiple such events compound into -63% DD.
2. **Slippage**: the execution model charges
   ``slippage_bps = base(5) + 10*(notional/nav) + 80*atr_pct``.
   At 90% NAV and 3.5% ATR the vol component adds 2.8 bps on top of 9 bps
   size cost; at a $400k NAV a single entry costs ~$600 in slippage.
   High-ATR entries also tend to whipsaw, forcing a quick exit and paying
   the full round-trip cost twice.

v8 design: regime-graduated entry + slippage gates
----------------------------------------------------
Tier 1 — HIGH_VOL, TREND_DOWN: **entry blocked**
  Regime characterises active dislocations or confirmed downtrends.
  No new positions entered.

Tier 2 — TREND_UP, VOL_COMPRESSION: **90% exposure, spread > 0.6%**
  Well-characterised, moderate-vol trend conditions.  Full allocation.
  Spread threshold raised 0.4% → 0.6% to require a more established trend
  and reduce marginal entries that quickly reverse.

Tier 3 — RANGE, VOL_EXPANSION: **70% exposure, spread > 1.0%**
  Trend exists but conditions are ambiguous or vol is expanding.
  Reduced allocation.  Higher spread threshold (1.0% vs 0.6%) requires a
  significantly more established trend signal.

Slippage gates (applied to all new entries and add-ons)
--------------------------------------------------------
- ENTRY_ATR_CAP (3.5%): blocks new entries when ATR is elevated but below
  the HIGH_VOL regime threshold (4.0%).  Regime check already handles ≥4%;
  this targets the 3.5-4.0% band where vol-slippage is high and entries are
  prone to whipsaw.  Existing long positions are NOT affected — the strategy
  holds through elevated vol once already invested.
- spread_momentum > 0 required for initial entry: the trend must be
  strengthening at the moment of entry, not weakening toward a reversal.
  Reduces "catch a falling knife" entries that reverse quickly, paying
  double round-trip slippage for a loss.

Additional changes from v7
---------------------------
- CRISIS_ATR_PCT: 5.5% → 5.0% — tighter crisis exit to reduce flash-crash
  losses; still above the 4% HIGH_VOL regime threshold for hysteresis.
- MIN_ENTRY_SPREAD: 0.4% → 0.6% (Tier 1).
- ELEVATED_ENTRY_SPREAD: 0.8% → 1.0% (Tier 3).
- ADD_SPREAD_THRESHOLD: 1.5% → 2.0% — add-on fires only on very strong
  trend confirmation; reduces add-on round trips.
- Add-on (90% → 100%): only fires in TREND_UP AND atr_pct ≤ ENTRY_ATR_CAP
  to avoid expensive adds in elevated-vol conditions.
"""

from __future__ import annotations

import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "trend_following_v8"

# ── EMAs ───────────────────────────────────────────────────────────────────────
FAST_EMA = 21
SLOW_EMA = 55
LONG_EMA = 200
MOMENTUM_LOOKBACK = 5
ATR_PERIOD = 24

# ── Tier 1 exposure (TREND_UP / VOL_COMPRESSION) ──────────────────────────────
BASE_EXPOSURE = 0.90
MIN_ENTRY_SPREAD = 0.006        # 0.6% — raised from 0.4% for signal quality

# ── Tier 2 exposure (RANGE / VOL_EXPANSION) ───────────────────────────────────
ELEVATED_EXPOSURE = 0.70
ELEVATED_ENTRY_SPREAD = 0.010   # 1.0% — raised from 0.8% for ambiguous regimes

# ── Slippage control: ATR cap for new entries ─────────────────────────────────
ENTRY_ATR_CAP = 0.035           # 3.5% — blocks new entries below HIGH_VOL (4%)

# ── Add-on ─────────────────────────────────────────────────────────────────────
ADD_EXPOSURE = 1.00
ADD_STATE_THRESHOLD = 0.95
ADD_SPREAD_THRESHOLD = 0.020    # 2.0% — raised from 1.5% to reduce add-on frequency
ADD_MOMENTUM_THRESHOLD = 0.001

# ── Exits ──────────────────────────────────────────────────────────────────────
CROSSOVER_EXIT_THRESHOLD = -0.020
PRICE_BREAK_THRESHOLD = -0.040
TREND_DOWN_SPREAD_THRESHOLD = -0.010
TREND_DOWN_CONFIRM_BARS = 3
CRISIS_ATR_PCT = 0.050          # tightened from 5.5% → 5.0%

FLAT_THRESHOLD = 0.05

# Regimes that block new entries
_BLOCKED_ENTRY_REGIMES = frozenset([RegimeLabel.HIGH_VOL, RegimeLabel.TREND_DOWN])
# Regimes that use tier-1 sizing (full allocation)
_TIER1_REGIMES = frozenset([RegimeLabel.TREND_UP, RegimeLabel.VOL_COMPRESSION])


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate a trend-following intent for the current closed bar."""
    min_bars = max(SLOW_EMA, LONG_EMA, ATR_PERIOD) + MOMENTUM_LOOKBACK + TREND_DOWN_CONFIRM_BARS + 5
    if len(df) < min_bars:
        return _warmup_intent(ctx)

    close = df["close"]
    high = df["high"]
    low = df["low"]

    ema_fast = close.ewm(span=FAST_EMA, adjust=False).mean()
    ema_slow = close.ewm(span=SLOW_EMA, adjust=False).mean()
    ema_long = close.ewm(span=LONG_EMA, adjust=False).mean()
    atr = _atr(high, low, close, ATR_PERIOD)

    c = float(close.iloc[-1])
    ef = float(ema_fast.iloc[-1])
    es = float(ema_slow.iloc[-1])
    el = float(ema_long.iloc[-1])
    atr_pct = float(atr.iloc[-1]) / c if c > 0 else 0.03

    ema_spread_series = (ema_fast - ema_slow) / close
    ema_spread = float(ema_spread_series.iloc[-1])
    spread_momentum = float(
        ema_spread_series.iloc[-1] - ema_spread_series.iloc[-MOMENTUM_LOOKBACK - 1]
    )
    price_vs_slow = (c - es) / es
    price_vs_long = (c - el) / el

    meta = {
        "ema_fast": round(ef, 4),
        "ema_slow": round(es, 4),
        "ema_long": round(el, 4),
        "ema_spread": round(ema_spread, 5),
        "spread_momentum": round(spread_momentum, 6),
        "price_vs_slow_ema": round(price_vs_slow, 5),
        "price_vs_long_ema": round(price_vs_long, 5),
        "atr_pct": round(atr_pct, 5),
        "regime": ctx.regime.value,
    }

    already_long = ctx.current_exposure_frac > FLAT_THRESHOLD
    at_base = already_long and ctx.current_exposure_frac < ADD_STATE_THRESHOLD

    # ── When long ─────────────────────────────────────────────────────────────
    if already_long:
        # Priority 1 — crisis exit (direct ATR, not regime label)
        if atr_pct > CRISIS_ATR_PCT:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.95,
                desired_exposure_frac=0.0,
                horizon_hours=1,
                reason=f"Crisis volatility: ATR {atr_pct:.3f} > {CRISIS_ATR_PCT}",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Priority 2 — sustained TREND_DOWN with confirmed bearish spread
        recent_spreads = ema_spread_series.iloc[-TREND_DOWN_CONFIRM_BARS:]
        sustained_bear = bool((recent_spreads < TREND_DOWN_SPREAD_THRESHOLD).all())
        if ctx.regime == RegimeLabel.TREND_DOWN and sustained_bear:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.85,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=(
                    f"TREND_DOWN + spread < {TREND_DOWN_SPREAD_THRESHOLD} "
                    f"for {TREND_DOWN_CONFIRM_BARS} bars"
                ),
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Priority 3 — deep EMA crossover
        if ema_spread < CROSSOVER_EXIT_THRESHOLD:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.80,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=f"Deep EMA crossover: spread {ema_spread:.3f} < {CROSSOVER_EXIT_THRESHOLD}",
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
                reason=f"Price {price_vs_slow:.3f} < {PRICE_BREAK_THRESHOLD} below slow EMA",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Add-on: TREND_UP only, ATR below entry cap to avoid expensive adds
        if at_base and ctx.regime == RegimeLabel.TREND_UP and atr_pct <= ENTRY_ATR_CAP:
            strong_trend = (
                ema_spread > ADD_SPREAD_THRESHOLD
                and spread_momentum > ADD_MOMENTUM_THRESHOLD
            )
            if strong_trend:
                return StrategyIntent(
                    action=Action.ENTER_LONG,
                    confidence=0.85,
                    desired_exposure_frac=ADD_EXPOSURE,
                    horizon_hours=72,
                    reason=f"Add-on (TREND_UP): spread={ema_spread:.3f} > {ADD_SPREAD_THRESHOLD}",
                    meta={**meta, "add_on": True},
                    strategy_id=STRATEGY_ID,
                )

        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.70,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=24,
            reason="In trend — holding",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── When flat: regime-graduated entry ────────────────────────────────────
    if ctx.regime in _BLOCKED_ENTRY_REGIMES or atr_pct > CRISIS_ATR_PCT:
        return StrategyIntent(
            action=Action.FLAT,
            confidence=0.60,
            desired_exposure_frac=0.0,
            horizon_hours=0,
            reason=f"Entry blocked: regime={ctx.regime.value} atr={atr_pct:.3f}",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # Slippage gate: don't initiate positions in elevated-vol conditions.
    # Regime check above handles ≥4% (HIGH_VOL); this covers 3.5-4.0% where
    # vol-slippage is still elevated and entries are prone to quick whipsaw.
    if atr_pct > ENTRY_ATR_CAP:
        return StrategyIntent(
            action=Action.FLAT,
            confidence=0.55,
            desired_exposure_frac=0.0,
            horizon_hours=0,
            reason=f"Entry ATR cap: atr={atr_pct:.3f} > {ENTRY_ATR_CAP} (high slippage)",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # Determine tier based on regime
    if ctx.regime in _TIER1_REGIMES:
        required_spread = MIN_ENTRY_SPREAD
        entry_exposure = BASE_EXPOSURE
        tier = "tier1"
    else:  # RANGE or VOL_EXPANSION
        required_spread = ELEVATED_ENTRY_SPREAD
        entry_exposure = ELEVATED_EXPOSURE
        tier = "tier2"

    # spread_momentum > 0: trend must be strengthening at entry — prevents
    # entering a weakening trend that reverses and forces a double round-trip.
    bullish_entry = (
        ema_spread > required_spread
        and spread_momentum > 0
        and price_vs_long > 0.0
        and price_vs_slow > 0.0
    )

    if bullish_entry:
        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=0.80,
            desired_exposure_frac=entry_exposure,
            horizon_hours=96,
            reason=(
                f"Trend entry ({tier}): regime={ctx.regime.value} "
                f"spread={ema_spread:.3f} mom={spread_momentum:.4f} "
                f"→ {entry_exposure:.0%} exposure"
            ),
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.60,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason=f"No signal: spread={ema_spread:.4f} required={required_spread} mom={spread_momentum:.4f} ({tier})",
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
