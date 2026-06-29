"""Layer 2 — TrendFollowingV9 — SPY macro gate + explicit BTC recovery override.

Extends trend_following_v8_ecap60_add80 with a two-signal cross-asset gate:

  1. SPY below SMA175 means macro bear context is active.
  2. BTC above SMA175 means crypto recovery is confirmed by the BTC regime anchor.

Canonical behavior
------------------
Runners should inject ``df["btc_above_sma175"]`` into every crypto trend
sleeve, including ETH. ETH still uses ETH price action for its local trend
signal, but the recovery override is BTC-anchored.

This prevents a subtle but material ambiguity: an ETH sleeve should not compute
"BTC recovery" from ETH's own dataframe. If the canonical BTC column is absent,
this module falls back to the local asset SMA175 for backward compatibility and
records ``btc_state_source = "asset_local_fallback"`` in metadata. Canonical
research runs should show ``btc_state_source = "explicit_btc"``.

The gate is one-directional:
  - Blocks new ENTER_LONG when SPY is bearish and BTC recovery is not confirmed.
  - Allows HOLD, EXIT, and FLAT unchanged.
  - Allows ENTER_LONG when SPY is bearish but BTC recovery is confirmed.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import trend_following_v8

STRATEGY_ID = "trend_following_v9"
ENTRY_CAP = 0.60
ADDON_CAP = 0.80
SPY_COL = "spy_above_sma175"
BTC_COL = "btc_above_sma175"
SMA_DAYS = 175


def _asset_local_above_sma175(df: pd.DataFrame) -> bool | None:
    """Backward-compatible fallback using the local asset's 175-day SMA."""
    close = df["close"]
    if len(close) < 2:
        return None
    bar_hours = max(1.0, (df.index[-1] - df.index[-2]).total_seconds() / 3600)
    sma_bars = round(SMA_DAYS * 24 / bar_hours)
    if len(close) < sma_bars:
        return None
    sma_val = close.rolling(sma_bars).mean().iloc[-1]
    if pd.isna(sma_val):
        return None
    return float(close.iloc[-1]) > float(sma_val)


def _read_spy_state(df: pd.DataFrame) -> bool | None:
    if SPY_COL not in df.columns:
        return None
    val = df[SPY_COL].iloc[-1]
    return bool(val) if pd.notna(val) else None


def _read_btc_recovery_state(df: pd.DataFrame) -> tuple[bool | None, str]:
    if BTC_COL in df.columns:
        val = df[BTC_COL].iloc[-1]
        if pd.notna(val):
            return bool(val), "explicit_btc"
    return _asset_local_above_sma175(df), "asset_local_fallback"


def _copy_intent(intent: StrategyIntent, meta_updates: dict, exposure: float | None = None) -> StrategyIntent:
    return StrategyIntent(
        action=intent.action,
        confidence=intent.confidence,
        desired_exposure_frac=intent.desired_exposure_frac if exposure is None else exposure,
        horizon_hours=intent.horizon_hours,
        reason=intent.reason,
        meta={**intent.meta, **meta_updates},
        strategy_id=STRATEGY_ID,
    )


def generate_intent(df: pd.DataFrame, ctx: StrategyContext, closed_only: bool = True) -> StrategyIntent:
    intent = trend_following_v8.generate_intent(df, ctx, closed_only)

    spy_state = _read_spy_state(df)
    btc_state, btc_source = _read_btc_recovery_state(df)
    base_meta = {
        "spy_above_sma175": spy_state,
        "btc_above_sma175": btc_state,
        "btc_state_source": btc_source,
    }

    if intent.action == Action.ENTER_LONG and spy_state is False:
        if btc_state is not True:
            return StrategyIntent(
                action=Action.FLAT,
                confidence=0.60,
                desired_exposure_frac=0.0,
                horizon_hours=0,
                reason=f"SPY macro bear and BTC recovery not confirmed ({btc_source})",
                meta={**intent.meta, **base_meta, "btc_override": False},
                strategy_id=STRATEGY_ID,
            )
        intent = _copy_intent(intent, {**base_meta, "btc_override": True})

    is_addon = intent.action == Action.ENTER_LONG and intent.meta.get("add_on", False)
    is_initial = intent.action == Action.ENTER_LONG and not is_addon

    if is_initial and intent.desired_exposure_frac > ENTRY_CAP:
        return _copy_intent(intent, {**base_meta, "entry_cap": ENTRY_CAP}, ENTRY_CAP)
    if is_addon and intent.desired_exposure_frac > ADDON_CAP:
        return _copy_intent(intent, {**base_meta, "addon_cap": ADDON_CAP}, ADDON_CAP)
    return _copy_intent(intent, base_meta)
