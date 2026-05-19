"""Layer 2 — Equity QQQ SMA Band v1.

Research-only single-asset equity sleeve for Itera Dynamics.

Purpose:
    Convert the salvageable QQQ portion of the SPY/QQQ composite book research
    into a directly tradeable, asset-local StrategyIntent.

Design:
    - asset target: QQQ or broad Nasdaq-100 proxy
    - timeframe: daily bars
    - signal family: long-only trend-to-cash
    - exposure: binary long / flat within the QQQ sleeve
    - no leverage
    - no shorting
    - deterministic and closed-bar only

Contract:
    generate_intent(df, ctx, closed_only=True) -> StrategyIntent
"""

from __future__ import annotations

import pandas as pd

from research.strategies.contracts import StrategyContext, StrategyIntent
from research.strategies.equity_sma_band_base import (
    DEFAULT_SMA_WINDOW,
    generate_single_asset_sma_intent,
)

STRATEGY_ID = "equity_qqq_sma_band_v1"
ASSET = "QQQ"


def generate_intent(
    df: pd.DataFrame,
    ctx: StrategyContext,
    closed_only: bool = True,
    sma_window: int = DEFAULT_SMA_WINDOW,
) -> StrategyIntent:
    """Generate a long/flat daily SMA intent for the QQQ sleeve."""
    return generate_single_asset_sma_intent(
        df=df,
        ctx=ctx,
        asset=ASSET,
        strategy_id=STRATEGY_ID,
        sma_window=sma_window,
    )
