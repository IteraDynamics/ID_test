"""Layer 2 — TrendFollowingShortV2 (Durational Filter + Slippage Control).

Analysis of short_v1 (2022: -14.4% return, -31.6% DD, 168 trades, $28k costs)
-------------------------------------------------------------------------------
v1 entered shorts on any TREND_DOWN bar with bearish EMA alignment.  In 2022's
bear market, BTC had repeated 30-50% relief rallies that caused the regime
engine to flip TREND_DOWN → TREND_UP → TREND_DOWN in quick succession.  Each
cycle triggered a cover and re-entry, paying ~50 bps round-trip per cycle.
$28k in costs on $100k capital wiped any raw signal edge.

Two root causes:
1. No durational gate: a single TREND_DOWN bar was sufficient to enter.
   Brief dips into TREND_DOWN during relief rallies triggered fresh shorts
   that were then squeezed and covered at a loss.
2. No slippage gate: entries fired during elevated-ATR bars (> 3.5%) where
   slippage is highest and whipsaw risk is greatest.

v2 design: durational confirmation + ATR gate
----------------------------------------------
Entry requirements (ALL must hold):
  - Regime is TREND_DOWN on current bar.
  - EMA spread has been < -0.6% for the last CONFIRM_BARS (3) bars.
    This filters single-bar dips: the bearish structure must persist.
  - spread_momentum < 0: trend still strengthening bearishly at entry.
    Avoids "catch a dead-cat bounce" entries where spread is already narrowing.
  - price < slow EMA (structural confirmation).
  - price < 200-bar EMA (macro downtrend, not just a local dip).
  - ATR% ≤ ENTRY_ATR_CAP (3.5%): skips high-slippage, high-whipsaw moments.

Exit (cover) requirements:
  - Crisis ATR (> 5.0%): cover immediately — spike vol often precedes
    short-squeeze rallies; removing the risk is more important than holding.
  - Sustained TREND_UP: regime TREND_UP AND EMA spread > +1.0% for
    CONFIRM_BARS bars — requires the reversal to prove itself before covering.
  - Deep EMA crossover bullish: spread > +2.0% (strong structural reversal).
  - Hard price break: close > slow EMA by > 4% (structural breach).
"""

from __future__ import annotations

import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "trend_following_short_v2"

# ── EMAs / indicators ──────────────────────────────────────────────────────────
FAST_EMA = 21
SLOW_EMA = 55
LONG_EMA = 200
MOMENTUM_LOOKBACK = 5
ATR_PERIOD = 24

# ── Entry ──────────────────────────────────────────────────────────────────────
ENTRY_EXPOSURE = 0.60
MIN_ENTRY_SPREAD = 0.006        # EMA spread must be < -0.6% for CONFIRM_BARS
ENTRY_ATR_CAP = 0.035           # 3.5% — blocks entries when slippage is elevated
CONFIRM_BARS = 3                # consecutive bars of bearish structure required

# ── Exits ──────────────────────────────────────────────────────────────────────
CRISIS_ATR_PCT = 0.050          # 5.0% — cover immediately (short-squeeze risk)
CROSSOVER_EXIT_SPREAD = 0.020   # +2.0% spread signals strong structural reversal
PRICE_BREAK_THRESHOLD = 0.040   # price > slow EMA by 4% forces cover
TREND_UP_SPREAD_THRESHOLD = 0.010  # spread threshold for sustained TREND_UP exit

FLAT_THRESHOLD = 0.05


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate a short trade intent for the current closed bar."""
    min_bars = max(SLOW_EMA, LONG_EMA, ATR_PERIOD) + MOMENTUM_LOOKBACK + CONFIRM_BARS + 5
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

    signed_exposure = ctx.meta.get("signed_exposure", 0.0)
    currently_short = signed_exposure < -FLAT_THRESHOLD

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
        "signed_exposure": round(signed_exposure, 4),
    }

    # ── When short: cover / hold ──────────────────────────────────────────────
    if currently_short:
        # Priority 1 — crisis vol: cover immediately, short-squeeze risk
        if atr_pct > CRISIS_ATR_PCT:
            return StrategyIntent(
                action=Action.EXIT_SHORT,
                confidence=0.95,
                desired_exposure_frac=0.0,
                horizon_hours=1,
                reason=f"Crisis ATR {atr_pct:.3f} > {CRISIS_ATR_PCT} — covering short",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Priority 2 — sustained TREND_UP with confirmed bullish EMA spread
        recent_spreads = ema_spread_series.iloc[-CONFIRM_BARS:]
        sustained_bull = bool((recent_spreads > TREND_UP_SPREAD_THRESHOLD).all())
        if ctx.regime == RegimeLabel.TREND_UP and sustained_bull:
            return StrategyIntent(
                action=Action.EXIT_SHORT,
                confidence=0.85,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=(
                    f"TREND_UP + spread > {TREND_UP_SPREAD_THRESHOLD} "
                    f"for {CONFIRM_BARS} bars — covering short"
                ),
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Priority 3 — deep EMA crossover bullish
        if ema_spread > CROSSOVER_EXIT_SPREAD:
            return StrategyIntent(
                action=Action.EXIT_SHORT,
                confidence=0.80,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=f"Deep bullish crossover: spread {ema_spread:.3f} > {CROSSOVER_EXIT_SPREAD}",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # Priority 4 — hard price break above slow EMA
        if price_vs_slow > PRICE_BREAK_THRESHOLD:
            return StrategyIntent(
                action=Action.EXIT_SHORT,
                confidence=0.75,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=f"Price {price_vs_slow:.3f} > {PRICE_BREAK_THRESHOLD} above slow EMA",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.70,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=24,
            reason="In downtrend — holding short",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── When flat: entry ──────────────────────────────────────────────────────

    # Regime gate: only enter in TREND_DOWN
    if ctx.regime != RegimeLabel.TREND_DOWN or atr_pct > CRISIS_ATR_PCT:
        return StrategyIntent(
            action=Action.FLAT,
            confidence=0.60,
            desired_exposure_frac=0.0,
            horizon_hours=0,
            reason=f"Entry blocked: regime={ctx.regime.value} atr={atr_pct:.3f}",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # Slippage gate
    if atr_pct > ENTRY_ATR_CAP:
        return StrategyIntent(
            action=Action.FLAT,
            confidence=0.55,
            desired_exposure_frac=0.0,
            horizon_hours=0,
            reason=f"ATR gate: {atr_pct:.3f} > {ENTRY_ATR_CAP} — high slippage risk",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # Durational filter: EMA spread must be consistently bearish for N bars
    recent_spreads = ema_spread_series.iloc[-CONFIRM_BARS:]
    sustained_down = bool((recent_spreads < -MIN_ENTRY_SPREAD).all())

    bearish_entry = (
        sustained_down          # bearish structure confirmed over N bars
        and spread_momentum < 0 # trend still strengthening, not reversing
        and price_vs_slow < 0   # price below slow EMA
        and price_vs_long < 0   # below macro 200-bar EMA (not just local dip)
    )

    if bearish_entry:
        return StrategyIntent(
            action=Action.ENTER_SHORT,
            confidence=0.80,
            desired_exposure_frac=ENTRY_EXPOSURE,
            horizon_hours=96,
            reason=(
                f"Short entry: TREND_DOWN confirmed {CONFIRM_BARS}bars "
                f"spread={ema_spread:.3f} mom={spread_momentum:.4f} "
                f"atr={atr_pct:.3f} → {ENTRY_EXPOSURE:.0%}"
            ),
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.60,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason=(
            f"No entry: sustained={sustained_down} spread={ema_spread:.4f} "
            f"mom={spread_momentum:.4f} pvs={price_vs_slow:.4f} pvl={price_vs_long:.4f}"
        ),
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
