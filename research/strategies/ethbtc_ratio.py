"""Synthetic ETHBTC ratio OHLCV constructor.

High/low assumption:
  high = ETH_high / BTC_low   — ETH at intra-bar high, BTC at intra-bar low
  low  = ETH_low  / BTC_high  — ETH at intra-bar low,  BTC at intra-bar high

This conservatively over-states the intra-bar range. The true ratio high/low
always lies within [computed_low, computed_high] by construction — no true
intra-bar move is missed. It does NOT introduce lookahead; all values come
from the same closed bar.
"""

from __future__ import annotations

import pandas as pd


def build_ratio_df(btc_df: pd.DataFrame, eth_df: pd.DataFrame) -> pd.DataFrame:
    """Build a synthetic ETHBTC ratio OHLCV dataframe.

    Aligns on exact timestamp intersection — no forward-filling beyond strict
    alignment. Returns only the common period.

    Parameters
    ----------
    btc_df :
        BTC 1H OHLCV (columns: open, high, low, close, volume).
    eth_df :
        ETH 1H OHLCV (same schema and tz-naive DatetimeIndex as btc_df).

    Returns
    -------
    pd.DataFrame
        ETHBTC ratio with columns [open, high, low, close, volume].
        Index is the intersection of btc_df and eth_df timestamps.

    Raises
    ------
    ValueError
        If the two DataFrames share no common timestamps.
    """
    common_idx = btc_df.index.intersection(eth_df.index)
    if len(common_idx) == 0:
        raise ValueError("BTC and ETH DataFrames share no common timestamps.")

    btc = btc_df.loc[common_idx]
    eth = eth_df.loc[common_idx]

    ratio = pd.DataFrame(index=common_idx)
    ratio["open"] = eth["open"] / btc["open"]
    ratio["high"] = eth["high"] / btc["low"]   # conservative upper bound
    ratio["low"] = eth["low"] / btc["high"]    # conservative lower bound
    ratio["close"] = eth["close"] / btc["close"]
    ratio["volume"] = 0.0

    return ratio
