"""Layer 2 — EquitySMA175 (Daily equity trend following on SPY / QQQ).

Logic summary
-------------
SMA175 crossover on daily closes.  Long the ETF when price is above its
175-day simple moving average; flat (cash / SGOV proxy) when below.

This is the simplest defensible equity trend rule and has survived decades
of academic replication on large-cap US indices.  It avoids equity bear
markets (2000–02, 2008–09, 2022) by going to cash when price breaks below
the 175-day average, capturing most of the bull-market upside while sitting
out the worst drawdowns.

Design notes
------------
- Daily bars only.  Do NOT feed hourly bars to this strategy.
- No regime gate.  The SMA175 cross IS the regime signal; the baseline
  regime engine output is ignored.
- 0.5% entry buffer above SMA prevents whipsawing at the boundary.
- Exposure fixed at 1.0 — no dynamic sizing.  The whole sleeve capital
  is either fully invested in the ETF or fully in cash.
- HOLD returns exactly current_exposure_frac so the backtest engine never
  triggers a rebalance while the position is unchanged.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "equity_sma175_v1"

SMA_PERIOD   = 175
ENTRY_BUFFER = 0.005   # price must be ≥0.5% above SMA to enter (avoids whipsaw)
EXPOSURE     = 1.0     # fully invested when long


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate an SMA175 equity intent for the current closed daily bar."""
    if len(df) < SMA_PERIOD + 5:
        return _warmup_intent(ctx)

    close = df["close"]
    sma   = close.rolling(SMA_PERIOD).mean()

    c       = float(close.iloc[-1])
    sma_val = float(sma.iloc[-1])

    if sma_val <= 0:
        return _warmup_intent(ctx)

    pct_vs_sma = (c - sma_val) / sma_val
    above_sma  = pct_vs_sma > 0            # price > SMA175 (exit condition)
    entry_ok   = pct_vs_sma > ENTRY_BUFFER  # price ≥ 0.5% above SMA (entry condition)

    meta = {
        "sma175":      round(sma_val, 4),
        "close":       round(c, 4),
        "pct_vs_sma":  round(pct_vs_sma, 5),
        "regime":      ctx.regime.value,
    }

    # ── When long: hold or exit ────────────────────────────────────────
    if ctx.current_exposure_frac > 0:
        if not above_sma:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.85,
                desired_exposure_frac=0.0,
                horizon_hours=24,
                reason=f"Price {c:.2f} crossed below SMA175 {sma_val:.2f} — exit to cash",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.75,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=24,
            reason=f"Price {pct_vs_sma:+.2%} above SMA175 — holding",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── When flat: enter if above SMA with buffer ──────────────────────
    if entry_ok:
        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=0.75,
            desired_exposure_frac=EXPOSURE,
            horizon_hours=24,
            reason=f"Price {pct_vs_sma:+.2%} above SMA175 — enter long",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.70,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason=f"Price {pct_vs_sma:+.2%} vs SMA175 — below entry buffer, flat",
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
