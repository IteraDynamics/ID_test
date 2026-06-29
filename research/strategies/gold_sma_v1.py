"""Layer 2 — GoldSMAV1 — SMA200 trend following on GLD (daily bars).

Logic
-----
Long GLD when price is above its 200-day SMA; flat (cash) when below.
200-day SMA is the standard trend filter for gold and broadly replicated
in academic and practitioner literature.

Design notes
------------
- Daily bars only.
- No regime gate — the SMA cross IS the regime signal.
- 0.5% entry buffer above SMA prevents whipsawing at the boundary.
- Exposure fixed at 1.0 — whole sleeve capital is either fully in GLD or cash.
- Gold is structurally uncorrelated to both US equities and crypto over most
  regimes, providing genuine diversification as a fourth fund sleeve.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID  = "gold_sma_v1"
SMA_PERIOD   = 200
ENTRY_BUFFER = 0.005
EXPOSURE     = 1.0


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    if len(df) < SMA_PERIOD + 5:
        return _warmup_intent(ctx)

    close   = df["close"]
    sma     = close.rolling(SMA_PERIOD).mean()
    c       = float(close.iloc[-1])
    sma_val = float(sma.iloc[-1])

    if sma_val <= 0:
        return _warmup_intent(ctx)

    pct_vs_sma = (c - sma_val) / sma_val
    above_sma  = pct_vs_sma > 0
    entry_ok   = pct_vs_sma > ENTRY_BUFFER

    meta = {
        "sma200":     round(sma_val, 4),
        "close":      round(c, 4),
        "pct_vs_sma": round(pct_vs_sma, 5),
        "regime":     ctx.regime.value,
    }

    if ctx.current_exposure_frac > 0:
        if not above_sma:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.85,
                desired_exposure_frac=0.0,
                horizon_hours=24,
                reason=f"GLD {c:.2f} crossed below SMA200 {sma_val:.2f} — exit to cash",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.75,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=24,
            reason=f"GLD {pct_vs_sma:+.2%} above SMA200 — holding",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    if entry_ok:
        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=0.75,
            desired_exposure_frac=EXPOSURE,
            horizon_hours=24,
            reason=f"GLD {pct_vs_sma:+.2%} above SMA200 — enter long",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.70,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason=f"GLD {pct_vs_sma:+.2%} vs SMA200 — below entry buffer, flat",
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
