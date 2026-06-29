"""Layer 2 — EquitySMA175V2 — SMA175 exit with parabolic BTC fast-exit.

Extends equity_sma175 with one additional exit condition:

  When BTC is in hard-cap parabolic territory (extension > 100% above its
  365-day SMA) AND SPY price breaks below its 50-day SMA, exit equity
  positions immediately — do not wait for the slow SMA175 signal.

Rationale
---------
The standard SMA175 exit is deliberately slow (~8.5-month average) to avoid
whipsawing on normal corrections.  But in 2025, the equity sleeve sat at
45% allocation fully exposed while the tariff shock drove SPY down -15%.
The SMA175 exit fired 6-8 weeks into the decline — long after the damage
was done.

The cross-asset context matters: when BTC is deeply parabolic (> 100% above
SMA365), macro risk is elevated globally.  In that regime, an equity SMA50
break is not a routine pullback — it's a genuine stress signal.  Exiting
faster in this regime avoids the worst of fast corrections without
meaningfully changing behaviour in normal years when BTC is not extended.

Gate logic:
  Normal exit  (always):      price < SMA175 → EXIT
  Fast exit    (conditional): price < SMA50 AND btc_in_parabolic → EXIT
  Entry buffer (unchanged):   price must be ≥ 0.5% above SMA175 to enter

Backward compatible: if df["btc_in_parabolic"] is absent (no BTC data),
behaviour is identical to equity_sma175.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent

STRATEGY_ID = "equity_sma175_v2"

SMA_PERIOD      = 175    # primary trend filter (unchanged)
FAST_SMA_PERIOD = 50     # fast exit trigger when BTC is parabolic
ENTRY_BUFFER    = 0.005  # price must be ≥0.5% above SMA175 to enter
EXPOSURE        = 1.0    # fully invested when long
BTC_PARA_COL    = "btc_in_parabolic"   # injected by fund runner


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
) -> StrategyIntent:
    """Generate an SMA175 equity intent with parabolic fast-exit for current bar."""
    if len(df) < SMA_PERIOD + 5:
        return _warmup_intent(ctx)

    close    = df["close"]
    sma175   = close.rolling(SMA_PERIOD).mean()
    sma50    = close.rolling(FAST_SMA_PERIOD).mean()

    c           = float(close.iloc[-1])
    sma175_val  = float(sma175.iloc[-1])
    sma50_val   = float(sma50.iloc[-1])

    if sma175_val <= 0:
        return _warmup_intent(ctx)

    pct_vs_sma175 = (c - sma175_val) / sma175_val
    above_sma175  = pct_vs_sma175 > 0
    entry_ok      = pct_vs_sma175 > ENTRY_BUFFER
    below_sma50   = c < sma50_val

    # Read BTC parabolic cross-asset flag
    btc_parabolic = False
    if BTC_PARA_COL in df.columns:
        val = df[BTC_PARA_COL].iloc[-1]
        if pd.notna(val):
            btc_parabolic = bool(val)

    meta = {
        "sma175":          round(sma175_val, 4),
        "sma50":           round(sma50_val, 4),
        "close":           round(c, 4),
        "pct_vs_sma175":   round(pct_vs_sma175, 5),
        "below_sma50":     below_sma50,
        "btc_in_parabolic": btc_parabolic,
        "regime":          ctx.regime.value,
    }

    # ── When long: check exit conditions ──────────────────────────────────
    if ctx.current_exposure_frac > 0:

        # Primary exit: price crossed below SMA175 (unchanged from v1)
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

        # Fast exit: price broke SMA50 AND BTC is in hard parabolic territory
        if below_sma50 and btc_parabolic:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.80,
                desired_exposure_frac=0.0,
                horizon_hours=24,
                reason=(
                    f"Price {c:.2f} < SMA50 {sma50_val:.2f} "
                    f"while BTC parabolic — early exit to cash"
                ),
                meta=meta,
                strategy_id=STRATEGY_ID,
            )

        return StrategyIntent(
            action=Action.HOLD,
            confidence=0.75,
            desired_exposure_frac=ctx.current_exposure_frac,
            horizon_hours=24,
            reason=f"Price {pct_vs_sma175:+.2%} above SMA175 — holding",
            meta=meta,
            strategy_id=STRATEGY_ID,
        )

    # ── When flat: enter only when above SMA175 with buffer ───────────────
    if entry_ok:
        return StrategyIntent(
            action=Action.ENTER_LONG,
            confidence=0.75,
            desired_exposure_frac=EXPOSURE,
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
