"""Layer 2 — CrashShortV1 (Crash-Only / Macro-Bear Hedge Sleeve).

Philosophy
----------
NOT a generic short strategy.  NOT a symmetric mirror of the long sleeve.
Designed as portfolio insurance: flat 90–95% of the time.

trend_following_short_v2 still activates during -15% to -30% corrections
inside bull markets because its 200-bar macro filter (≈ 8 days) cannot
distinguish a correction from a structural bear.  This sleeve requires
seven conditions to hold simultaneously before any entry is allowed.
The combinatorial AND logic is what keeps it mostly dormant.

Entry gate — ALL must hold:
    1. Regime == TREND_DOWN (current bar confirms bearish hourly regime).
    2. Price < 720-bar EMA (≈ 30-day structural trend is bearish).
    3. Price ≥ 20% below 90-day rolling high (macro drawdown confirmed,
       not a -10% to -15% pullback inside a bull market).
    4. EMA spread < -0.8% for 6 consecutive bars (persistent bear structure,
       not a one-bar regime flip).
    5. ATR% ≥ 2.5% (volatility is actively expanding — crash is live).
    6. ATR% ≤ 6.0% (not so extreme that fills would be catastrophic).
    7. spread_momentum < 0 (trend still accelerating bearishly at entry).

Exit / cover — any single condition triggers:
    1. Regime in (VOL_COMPRESSION, RANGE) AND ATR% < 2.0%: crash over.
    2. Regime TREND_UP sustained for CONFIRM_BARS with spread > +1.0%.
    3. ATR% < 1.5% regardless of regime: volatility collapsed.
    4. EMA spread > +1.5%: structural bullish reversal underway.
    5. Close > slow EMA by 3.5%: price reclaimed structural level.
    6. ATR% > 8.0%: extreme spike — cover to avoid short-squeeze.
"""

from __future__ import annotations

import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "crash_short_v1"

# ── Macro structural filters ───────────────────────────────────────────────────
MACRO_EMA = 720              # ≈ 30 days on 1-hour bars
DRAWDOWN_LOOKBACK = 2160     # 90-day rolling high window (bars)
DRAWDOWN_THRESHOLD = 0.20    # price must be ≥ 20% below 90-day rolling high

# ── EMA structure ──────────────────────────────────────────────────────────────
FAST_EMA = 21
SLOW_EMA = 55
MOMENTUM_LOOKBACK = 5
EMA_SPREAD_THRESHOLD = -0.008   # spread < -0.8% required for CONFIRM_BARS

# ── Persistence ────────────────────────────────────────────────────────────────
CONFIRM_BARS = 6                # consecutive bars of confirmed bearish structure

# ── Volatility ─────────────────────────────────────────────────────────────────
ATR_PERIOD = 24
MIN_ATR_PCT = 0.025             # 2.5% floor — crash must be live and expanding
ENTRY_ATR_CAP = 0.060           # 6.0% ceiling — cap for acceptable fill quality
CRISIS_ATR_PCT = 0.080          # 8.0% — extreme spike triggers immediate cover
VOL_COMPRESS_ATR = 0.020        # 2.0% — crash over when ATR drops here

# ── Exposure ───────────────────────────────────────────────────────────────────
ENTRY_EXPOSURE = 0.50           # conservative: insurance, not a profit centre

# ── Exit thresholds ────────────────────────────────────────────────────────────
TREND_UP_CONFIRM_BARS = 3
TREND_UP_SPREAD_THRESHOLD = 0.010
CROSSOVER_EXIT_SPREAD = 0.015   # spread > +1.5% → structural reversal
PRICE_BREAK_THRESHOLD = 0.035   # close > slow EMA by 3.5%
VOL_COLLAPSE_ATR = 0.015        # 1.5% — vol collapsed unconditionally

FLAT_THRESHOLD = 0.05


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate a crash-hedge intent for the current closed bar."""
    min_bars = DRAWDOWN_LOOKBACK + max(SLOW_EMA, MACRO_EMA, ATR_PERIOD) + CONFIRM_BARS + MOMENTUM_LOOKBACK + 10
    if len(df) < min_bars:
        return _warmup_intent(ctx)

    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    ema_fast  = close.ewm(span=FAST_EMA,  adjust=False).mean()
    ema_slow  = close.ewm(span=SLOW_EMA,  adjust=False).mean()
    ema_macro = close.ewm(span=MACRO_EMA, adjust=False).mean()
    atr       = _atr(high, low, close, ATR_PERIOD)

    c        = float(close.iloc[-1])
    es       = float(ema_slow.iloc[-1])
    em       = float(ema_macro.iloc[-1])
    atr_pct  = float(atr.iloc[-1]) / c if c > 0 else 0.03

    ema_spread_series = (ema_fast - ema_slow) / close
    ema_spread        = float(ema_spread_series.iloc[-1])
    spread_momentum   = float(
        ema_spread_series.iloc[-1] - ema_spread_series.iloc[-MOMENTUM_LOOKBACK - 1]
    )
    price_vs_slow  = (c - es) / es
    price_vs_macro = (c - em) / em

    # 90-day drawdown from rolling high
    rolling_high    = float(close.rolling(DRAWDOWN_LOOKBACK).max().iloc[-1])
    drawdown_from_high = (rolling_high - c) / rolling_high if rolling_high > 0 else 0.0

    signed_exposure = ctx.meta.get("signed_exposure", 0.0)
    currently_short = signed_exposure < -FLAT_THRESHOLD

    meta = {
        "ema_spread":          round(ema_spread, 5),
        "spread_momentum":     round(spread_momentum, 6),
        "price_vs_slow_ema":   round(price_vs_slow, 5),
        "price_vs_macro_ema":  round(price_vs_macro, 5),
        "drawdown_from_high":  round(drawdown_from_high, 4),
        "atr_pct":             round(atr_pct, 5),
        "regime":              ctx.regime.value,
        "signed_exposure":     round(signed_exposure, 4),
    }

    # ── When short: cover conditions ──────────────────────────────────────────
    if currently_short:
        # 1. Extreme ATR spike — short-squeeze risk
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

        # 2. Vol collapsed — crash regime over
        if atr_pct < VOL_COLLAPSE_ATR:
            return StrategyIntent(
                action=Action.EXIT_SHORT,
                confidence=0.85,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=f"Vol collapsed: ATR {atr_pct:.3f} < {VOL_COLLAPSE_ATR} — crash over",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # 3. Ranging/compression regime with low ATR — crash regime ended
        if ctx.regime in (RegimeLabel.VOL_COMPRESSION, RegimeLabel.RANGE) and atr_pct < VOL_COMPRESS_ATR:
            return StrategyIntent(
                action=Action.EXIT_SHORT,
                confidence=0.85,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=f"Crash regime ended: {ctx.regime.value} ATR {atr_pct:.3f} < {VOL_COMPRESS_ATR}",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # 4. Sustained TREND_UP with confirmed bullish EMA spread
        recent_spreads = ema_spread_series.iloc[-TREND_UP_CONFIRM_BARS:]
        sustained_bull = bool((recent_spreads > TREND_UP_SPREAD_THRESHOLD).all())
        if ctx.regime == RegimeLabel.TREND_UP and sustained_bull:
            return StrategyIntent(
                action=Action.EXIT_SHORT,
                confidence=0.85,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=(
                    f"TREND_UP + spread > {TREND_UP_SPREAD_THRESHOLD} "
                    f"for {TREND_UP_CONFIRM_BARS} bars — covering short"
                ),
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # 5. Deep bullish EMA crossover
        if ema_spread > CROSSOVER_EXIT_SPREAD:
            return StrategyIntent(
                action=Action.EXIT_SHORT,
                confidence=0.80,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=f"Bullish crossover: spread {ema_spread:.3f} > {CROSSOVER_EXIT_SPREAD}",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # 6. Price reclaimed slow EMA structurally
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
            reason="Crash regime active — holding short",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── When flat: entry gate (ALL seven conditions must hold) ────────────────

    # Gate 1: regime
    if ctx.regime != RegimeLabel.TREND_DOWN:
        return _flat(f"regime={ctx.regime.value} — entry blocked", meta)

    # Gate 2 + 3: vol gates (check before expensive EMA spread scan)
    if atr_pct > CRISIS_ATR_PCT:
        return _flat(f"crisis ATR {atr_pct:.3f} > {CRISIS_ATR_PCT}", meta)

    if atr_pct < MIN_ATR_PCT:
        return _flat(f"ATR {atr_pct:.3f} < {MIN_ATR_PCT} — crash not live", meta)

    if atr_pct > ENTRY_ATR_CAP:
        return _flat(f"ATR {atr_pct:.3f} > {ENTRY_ATR_CAP} — fill quality too poor", meta)

    # Gate 4: macro structural trend
    if price_vs_macro >= 0:
        return _flat(f"price above 720-bar macro EMA ({price_vs_macro:.3f}) — not structural bear", meta)

    # Gate 5: macro drawdown from 90-day high
    if drawdown_from_high < DRAWDOWN_THRESHOLD:
        return _flat(
            f"drawdown {drawdown_from_high:.2%} < {DRAWDOWN_THRESHOLD:.0%} from 90d high — correction not crash",
            meta,
        )

    # Gate 6: persistent EMA spread (CONFIRM_BARS consecutive bars)
    recent_spreads = ema_spread_series.iloc[-CONFIRM_BARS:]
    sustained_down = bool((recent_spreads < EMA_SPREAD_THRESHOLD).all())
    if not sustained_down:
        return _flat(
            f"spread not sustained < {EMA_SPREAD_THRESHOLD} for {CONFIRM_BARS} bars",
            meta,
        )

    # Gate 7: trend still accelerating bearishly
    if spread_momentum >= 0:
        return _flat(f"spread_momentum {spread_momentum:.5f} >= 0 — trend weakening", meta)

    # All gates passed
    return StrategyIntent(
        action=Action.ENTER_SHORT,
        confidence=0.80,
        desired_exposure_frac=ENTRY_EXPOSURE,
        horizon_hours=120,
        reason=(
            f"Crash short entry: TREND_DOWN regime={ctx.regime.value} "
            f"dd={drawdown_from_high:.1%} spread={ema_spread:.3f} "
            f"atr={atr_pct:.3f} → {ENTRY_EXPOSURE:.0%}"
        ),
        meta=meta,
        strategy_id=STRATEGY_ID,
    )


def _flat(reason: str, meta: dict) -> StrategyIntent:
    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.60,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason=reason,
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
