"""Layer 2 — EquitySMA175V3 — SMA175 with partial de-risk governor.

Extends equity_sma175 with a partial de-risk rule:

  When price is still above SMA175 (bullish primary signal) BUT SPY breaks
  below its 50-day SMA AND BTC is in hard parabolic territory (>100% above
  SMA365), reduce equity exposure to DERISKED_EXPOSURE (default 50%) until
  the risk condition clears — do NOT exit fully.

Rationale
---------
Full exit (equity_sma175_v2) was trigger-happy: it fired during normal 2021
corrections when BTC was parabolic, causing a whipsaw loss.  And it didn't
help 2025 because the tariff shock moved faster than any SMA50 signal.

Partial de-risk avoids both failure modes:
  - 2021: we reduce to 50% instead of exiting, so we participate in the
    recovery.  Net effect: less severe than a full exit → no whipsaw penalty.
  - 2025 tariff shock: if the signal fires before the worst damage, we halve
    the sleeve exposure and limit drawdown.  If it fires after (already too
    late), we take a smaller further hit vs holding 100%.

Recovery: once SPY climbs back above SMA50, we return to full exposure on
the next bar.  The primary SMA175 exit still governs trend-following exits
and operates completely unchanged.

Gate logic (layered, checked in order):
  1. Primary exit  (always):      price < SMA175 → EXIT 0%
  2. De-risk hold  (conditional): SPY < SMA50 AND btc_in_parabolic → HOLD 50%
  3. Full hold     (default):     price ≥ SMA175 → HOLD 100%
  4. Entry:                        price ≥ SMA175 + 0.5% buffer → ENTER 100%
     (de-risk does NOT apply on entry — only modifies an existing position)

Backward compatible: if btc_in_parabolic column is absent, behaviour is
identical to equity_sma175 (v1).
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "equity_sma175_v3"

SMA_PERIOD        = 175    # primary trend filter
FAST_SMA_PERIOD   = 50     # governs de-risk trigger
ENTRY_BUFFER      = 0.005  # price must be ≥0.5% above SMA175 to enter
FULL_EXPOSURE     = 1.0    # fully invested when long, risk-on
DERISKED_EXPOSURE = 0.50   # half-position during elevated risk
BTC_PARA_COL      = "btc_in_parabolic"


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate SMA175 equity intent with optional partial de-risk."""
    if len(df) < SMA_PERIOD + 5:
        return _warmup_intent(ctx)

    close   = df["close"]
    sma175  = close.rolling(SMA_PERIOD).mean()
    sma50   = close.rolling(FAST_SMA_PERIOD).mean()

    c          = float(close.iloc[-1])
    sma175_val = float(sma175.iloc[-1])
    sma50_val  = float(sma50.iloc[-1])

    if sma175_val <= 0:
        return _warmup_intent(ctx)

    pct_vs_sma175 = (c - sma175_val) / sma175_val
    above_sma175  = pct_vs_sma175 > 0
    entry_ok      = pct_vs_sma175 > ENTRY_BUFFER
    below_sma50   = c < sma50_val

    btc_parabolic = False
    if BTC_PARA_COL in df.columns:
        val = df[BTC_PARA_COL].iloc[-1]
        if pd.notna(val):
            btc_parabolic = bool(val)

    derisked = below_sma50 and btc_parabolic

    meta = {
        "sma175":           round(sma175_val, 4),
        "sma50":            round(sma50_val, 4),
        "close":            round(c, 4),
        "pct_vs_sma175":    round(pct_vs_sma175, 5),
        "below_sma50":      below_sma50,
        "btc_in_parabolic": btc_parabolic,
        "derisked":         derisked,
        "regime":           ctx.regime.value,
    }

    # ── When long ─────────────────────────────────────────────────────────
    if ctx.current_exposure_frac > 0:

        # 1. Primary exit: price below SMA175 — always overrides de-risk
        if not above_sma175:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.90,
                desired_exposure_frac=0.0,
                horizon_hours=24,
                reason=f"Price {c:.2f} < SMA175 {sma175_val:.2f} — exit to cash",
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # 2. De-risk: SPY below SMA50 while BTC parabolic — partial hold
        if derisked:
            return StrategyIntent(
                action=Action.HOLD,
                confidence=0.70,
                desired_exposure_frac=DERISKED_EXPOSURE,
                horizon_hours=24,
                reason=(
                    f"SPY < SMA50 {sma50_val:.2f} while BTC parabolic — "
                    f"partial de-risk to {DERISKED_EXPOSURE:.0%}"
                ),
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        # 3. Default hold
        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.75,
            desired_exposure_frac=FULL_EXPOSURE,
            horizon_hours=24,
            reason=f"Price {pct_vs_sma175:+.2%} above SMA175 — holding full",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── When flat: enter if above SMA175 with buffer ──────────────────────
    if entry_ok:
        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=0.75,
            desired_exposure_frac=FULL_EXPOSURE,
            horizon_hours=24,
            reason=f"Price {pct_vs_sma175:+.2%} above SMA175 — enter long",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    return StrategyIntent(
        action=Action.FLAT,
        confidence=0.70,
        desired_exposure_frac=0.0,
        horizon_hours=0,
        reason=f"Price {pct_vs_sma175:+.2%} vs SMA175 — below entry buffer, flat",
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
