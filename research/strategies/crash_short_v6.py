"""Layer 2 — CrashShortV6 (Crash-Only / Macro-Bear Hedge Sleeve — v6).

Philosophy
----------
Targeted fix to crash_short_v5: add a cross-asset regime gate so the hedge
only fires during macro bear markets, not crypto-specific corrections.

What v5 taught us
-----------------
Gate audit confirmed the ATR floor (1.0%) fires too loosely in bull markets:
    2021 Q2: BTC -54%, SPY +15% → all crypto gates pass, but SPY is fine
             This is a crypto-specific correction.  Do NOT short.
    2022:    BTC -64%, SPY -19% → all crypto gates pass AND equity is also down
             This is a macro bear market.  DO short.

A rule-based regime classifier on single-asset OHLCV cannot distinguish these
two cases.  The cross-asset signal (is SPY also in a downtrend?) can.

Changes vs v5
-------------
1. Gate 7 added: SPY must be below its 175-day SMA.
   If SPY is above SMA175 (equity bull market), the BTC crash is likely a
   crypto-specific correction — entry is blocked.
   If SPY is below SMA175 (equity bear or neutral), the crash may be macro —
   entry is allowed.

   The gate reads from df["spy_above_sma175"] injected by the fund runner.
   If the column is absent (BTC-only runs), the gate is skipped (backward
   compatible).

   SMA175 = 175 trading days ≈ 8.5 months — same threshold as equity_sma175
   strategy, ensuring regime language is consistent across sleeves.

Entry gate — ALL must hold:
    1. Regime == TREND_DOWN.
    2. ATR% >= 1.0% (bear trend live; no upper cap).
    3. Price < 720-bar EMA (≈ 30-day structural trend is bearish).
    4. Price ≥ 20% below 90-day rolling high (macro crash confirmed).
    5. EMA spread < -0.8% for 6 consecutive bars.
    6. spread_momentum < 0 (trend still accelerating bearishly).
    7. SPY below 175-day SMA (equity also bearish — macro bear, not correction).

Exit / cover — any single condition triggers:
    1. Regime in (VOL_COMPRESSION, RANGE) AND ATR% < 0.8%: trend dead.
    2. Regime TREND_UP sustained for 3 bars with spread > +1.0%.
    3. ATR% < 0.5% regardless of regime: market completely frozen.
    4. EMA spread > +1.5%: structural bullish reversal underway.
    5. Close > slow EMA by 3.5%: price reclaimed structural level.
"""

from __future__ import annotations

import pandas as pd

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "crash_short_v6"

# ── Macro structural filters ───────────────────────────────────────────────────
MACRO_EMA = 720
DRAWDOWN_LOOKBACK = 2160
DRAWDOWN_THRESHOLD = 0.20

# ── EMA structure ──────────────────────────────────────────────────────────────
FAST_EMA = 21
SLOW_EMA = 55
MOMENTUM_LOOKBACK = 5
EMA_SPREAD_THRESHOLD = -0.008

# ── Persistence ────────────────────────────────────────────────────────────────
CONFIRM_BARS = 6

# ── Volatility ─────────────────────────────────────────────────────────────────
ATR_PERIOD = 24
MIN_ATR_PCT = 0.010          # 1.0% floor — captures slow grind, not just spikes
VOL_COMPRESS_ATR = 0.008     # must be < entry floor to avoid whipsaw
VOL_COLLAPSE_ATR = 0.005     # complete market freeze

# ── Exposure ───────────────────────────────────────────────────────────────────
ENTRY_EXPOSURE = 0.50

# ── Exit thresholds ────────────────────────────────────────────────────────────
TREND_UP_CONFIRM_BARS = 3
TREND_UP_SPREAD_THRESHOLD = 0.010
CROSSOVER_EXIT_SPREAD = 0.015
PRICE_BREAK_THRESHOLD = 0.035

FLAT_THRESHOLD = 0.05

# ── Cross-asset ────────────────────────────────────────────────────────────────
SPY_SMA_COL = "spy_above_sma175"   # boolean column injected by fund runner


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
    atr_pct  = float(atr.iloc[-1]) / c if c > 0 else 0.01

    ema_spread_series = (ema_fast - ema_slow) / close
    ema_spread        = float(ema_spread_series.iloc[-1])
    spread_momentum   = float(
        ema_spread_series.iloc[-1] - ema_spread_series.iloc[-MOMENTUM_LOOKBACK - 1]
    )
    price_vs_slow  = (c - es) / es
    price_vs_macro = (c - em) / em

    rolling_high       = float(close.rolling(DRAWDOWN_LOOKBACK).max().iloc[-1])
    drawdown_from_high = (rolling_high - c) / rolling_high if rolling_high > 0 else 0.0

    # Cross-asset: SPY above SMA175 (None if column not present)
    spy_bullish: bool | None = None
    if SPY_SMA_COL in df.columns:
        val = df[SPY_SMA_COL].iloc[-1]
        if pd.notna(val):
            spy_bullish = bool(val)

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
        "spy_above_sma175":    spy_bullish,
    }

    # ── When short: cover conditions ──────────────────────────────────────────
    if currently_short:
        # 1. Market completely frozen
        if atr_pct < VOL_COLLAPSE_ATR:
            return StrategyIntent(
                action=Action.EXIT_SHORT,
                confidence=0.85,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=f"Vol frozen: ATR {atr_pct:.3f} < {VOL_COLLAPSE_ATR}",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # 2. Ranging/compression with very low ATR
        if ctx.regime in (RegimeLabel.VOL_COMPRESSION, RegimeLabel.RANGE) and atr_pct < VOL_COMPRESS_ATR:
            return StrategyIntent(
                action=Action.EXIT_SHORT,
                confidence=0.85,
                desired_exposure_frac=0.0,
                horizon_hours=4,
                reason=f"Bear trend ended: {ctx.regime.value} ATR {atr_pct:.3f} < {VOL_COMPRESS_ATR}",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # 3. Sustained TREND_UP with confirmed bullish spread
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

        # 4. Deep bullish EMA crossover
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

        # 5. Price reclaimed slow EMA
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
            reason="Bear regime active — holding short",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── When flat: entry gate ─────────────────────────────────────────────────

    # Gate 1: regime
    if ctx.regime != RegimeLabel.TREND_DOWN:
        return _flat(f"regime={ctx.regime.value} — entry blocked", meta)

    # Gate 2: ATR floor — bear trend must be live
    if atr_pct < MIN_ATR_PCT:
        return _flat(f"ATR {atr_pct:.3f} < {MIN_ATR_PCT} — bear trend not live", meta)

    # Gate 3: macro structural trend
    if price_vs_macro >= 0:
        return _flat(f"price above 720-bar macro EMA ({price_vs_macro:.3f}) — not structural bear", meta)

    # Gate 4: macro drawdown from 90-day high
    if drawdown_from_high < DRAWDOWN_THRESHOLD:
        return _flat(
            f"drawdown {drawdown_from_high:.2%} < {DRAWDOWN_THRESHOLD:.0%} from 90d high — correction not crash",
            meta,
        )

    # Gate 5: persistent EMA spread
    recent_spreads = ema_spread_series.iloc[-CONFIRM_BARS:]
    sustained_down = bool((recent_spreads < EMA_SPREAD_THRESHOLD).all())
    if not sustained_down:
        return _flat(
            f"spread not sustained < {EMA_SPREAD_THRESHOLD} for {CONFIRM_BARS} bars",
            meta,
        )

    # Gate 6: trend still accelerating bearishly
    if spread_momentum >= 0:
        return _flat(f"spread_momentum {spread_momentum:.5f} >= 0 — trend weakening", meta)

    # Gate 7: cross-asset macro confirmation — SPY must not be in equity bull
    if spy_bullish is True:
        return _flat(
            "SPY above SMA175 — equity bull trend, crypto-specific correction not macro bear",
            meta,
        )

    return StrategyIntent(
        action=Action.ENTER_SHORT,
        confidence=0.80,
        desired_exposure_frac=ENTRY_EXPOSURE,
        horizon_hours=120,
        reason=(
            f"Macro bear short: TREND_DOWN dd={drawdown_from_high:.1%} "
            f"spread={ema_spread:.3f} atr={atr_pct:.3f} "
            f"SPY_bull={spy_bullish} → {ENTRY_EXPOSURE:.0%}"
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
