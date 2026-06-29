"""Layer 2 — TrendFollowingV11 — explicit BTC parabolic exposure trimmer.

Extends trend_following_v9 with a parabolic-risk cap. The cap is BTC-anchored:
runners should inject ``df["btc_extension_sma365"]`` into all crypto trend
sleeves, including ETH. ETH still trades its own local trend, but BTC defines
crypto-wide parabolic risk.

Canonical behavior
------------------
When ``btc_extension_sma365`` is present, metadata records
``btc_parabolic_state_source = "explicit_btc"``. If absent, the module falls
back to local-asset extension for backward compatibility and records
``btc_parabolic_state_source = "asset_local_fallback"``. Canonical research
runs should show only ``explicit_btc`` for trend sleeves.

The cap only affects new ENTER_LONG intents. Existing positions are not
force-reduced; normal exit conditions still apply.
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import Action, StrategyContext, StrategyIntent
from research.strategies import trend_following_v9

STRATEGY_ID = "trend_following_v11"

PARA_SMA_DAYS = 365
SOFT_THRESHOLD = 0.60
HARD_THRESHOLD = 1.00
SOFT_ENTRY_CAP = 0.40
SOFT_ADDON_CAP = 0.60
HARD_ENTRY_CAP = 0.25
HARD_ADDON_CAP = 0.40
EXT_COL = "btc_extension_sma365"


def _asset_local_extension(df: pd.DataFrame) -> float | None:
    """Backward-compatible fallback using the local asset's SMA365 extension."""
    close = df["close"]
    if len(close) < 2:
        return None
    bar_hours = max(1.0, (df.index[-1] - df.index[-2]).total_seconds() / 3600)
    sma_bars = round(PARA_SMA_DAYS * 24 / bar_hours)
    if len(close) < sma_bars:
        return None
    sma_val = float(close.rolling(sma_bars).mean().iloc[-1])
    if pd.isna(sma_val) or sma_val <= 0:
        return None
    return (float(close.iloc[-1]) - sma_val) / sma_val


def _read_btc_extension(df: pd.DataFrame) -> tuple[float | None, str]:
    if EXT_COL in df.columns:
        val = df[EXT_COL].iloc[-1]
        if pd.notna(val):
            return float(val), "explicit_btc"
    return _asset_local_extension(df), "asset_local_fallback"


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
    intent = trend_following_v9.generate_intent(df, ctx, closed_only)
    extension, source = _read_btc_extension(df)
    meta = {
        "btc_extension_sma365": round(extension, 3) if extension is not None else None,
        "btc_parabolic_state_source": source,
    }

    if intent.action != Action.ENTER_LONG:
        return _copy_intent(intent, meta)

    is_addon = intent.meta.get("add_on", False)
    if extension is not None and extension > HARD_THRESHOLD:
        cap = HARD_ADDON_CAP if is_addon else HARD_ENTRY_CAP
        tier = "parabolic"
    elif extension is not None and extension > SOFT_THRESHOLD:
        cap = SOFT_ADDON_CAP if is_addon else SOFT_ENTRY_CAP
        tier = "extended"
    else:
        return _copy_intent(intent, meta)

    return _copy_intent(
        intent,
        {
            **meta,
            "parabolic_tier": tier,
            "parabolic_cap": cap,
            "pre_cap_exposure": round(intent.desired_exposure_frac, 3),
        },
        min(intent.desired_exposure_frac, cap),
    )
