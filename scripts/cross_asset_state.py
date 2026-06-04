from __future__ import annotations

import numpy as np
import pandas as pd

BTC_STATE_COLUMNS = [
    "btc_above_sma175",
    "btc_extension_sma365",
    "btc_parabolic_soft",
    "btc_parabolic_hard",
    "btc_parabolic_tier",
]


def compute_btc_macro_state(btc_df: pd.DataFrame) -> pd.DataFrame:
    if btc_df.empty or "close" not in btc_df.columns:
        return pd.DataFrame(columns=BTC_STATE_COLUMNS)

    btc_daily = btc_df["close"].resample("D").last().dropna()
    sma175 = btc_daily.rolling(175, min_periods=175).mean()
    sma365 = btc_daily.rolling(365, min_periods=365).mean()

    extension = (btc_daily - sma365) / sma365.replace(0, np.nan)
    above_sma175 = btc_daily > sma175
    soft = extension > 0.60
    hard = extension > 1.00

    tier = pd.Series(0.0, index=btc_daily.index, name="btc_parabolic_tier")
    tier.loc[soft.fillna(False)] = 1.0
    tier.loc[hard.fillna(False)] = 2.0

    return pd.DataFrame(
        {
            "btc_above_sma175": above_sma175,
            "btc_extension_sma365": extension,
            "btc_parabolic_soft": soft,
            "btc_parabolic_hard": hard,
            "btc_parabolic_tier": tier,
        },
        index=btc_daily.index,
    )


def inject_btc_macro_state(df: pd.DataFrame, btc_state: pd.DataFrame | None) -> pd.DataFrame:
    if btc_state is None or btc_state.empty:
        return df
    out = df.copy()
    for col in BTC_STATE_COLUMNS:
        if col in btc_state.columns:
            out[col] = btc_state[col].reindex(out.index, method="ffill")
    return out
