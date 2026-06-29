"""Diagnostic: count which gates block crash_short_v4 entries in 2022."""
from __future__ import annotations

import argparse
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from research.strategies.crash_short_v4 import (
    MACRO_EMA, DRAWDOWN_LOOKBACK, DRAWDOWN_THRESHOLD,
    FAST_EMA, SLOW_EMA, MOMENTUM_LOOKBACK,
    EMA_SPREAD_THRESHOLD, CONFIRM_BARS,
    ATR_PERIOD, MIN_ATR_PCT,
    _atr,
)
from research.regimes.contracts import RegimeLabel

def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.set_index("timestamp").sort_index()
    df.columns = [c.lower() for c in df.columns]
    return df

def run_gate_audit(df_full: pd.DataFrame, regime_col: str = "regime") -> None:
    """Count gate failures for flat bars in 2022."""
    # We need regime labels — proxy with a simple rule if not available
    close = df_full["close"]
    high  = df_full["high"]
    low   = df_full["low"]

    ema_fast  = close.ewm(span=FAST_EMA,  adjust=False).mean()
    ema_slow  = close.ewm(span=SLOW_EMA,  adjust=False).mean()
    ema_macro = close.ewm(span=MACRO_EMA, adjust=False).mean()
    atr       = _atr(high, low, close, ATR_PERIOD)

    atr_pct_series = atr / close.clip(lower=1.0)
    ema_spread_series = (ema_fast - ema_slow) / close
    rolling_high = close.rolling(DRAWDOWN_LOOKBACK).max()
    drawdown_series = (rolling_high - close) / rolling_high.clip(lower=1e-9)
    price_vs_macro = (close - ema_macro) / ema_macro
    spread_momentum_series = ema_spread_series - ema_spread_series.shift(MOMENTUM_LOOKBACK + 1)

    # Slice to 2022 only (after warmup)
    start = "2022-01-01"
    end   = "2022-12-31"
    idx = df_full.loc[start:end].index

    counters = {
        "total_bars": 0,
        "g1_not_trend_down": 0,   # regime != TREND_DOWN (we proxy: price > macro EMA as non-bearish)
        "g2_atr_floor": 0,         # ATR < 2.5%
        "g3_macro_ema": 0,         # price >= macro EMA
        "g4_drawdown": 0,          # drawdown < 20%
        "g5_spread": 0,            # EMA spread not sustained for 6 bars
        "g6_momentum": 0,          # spread_momentum >= 0
        "would_enter": 0,
        "atr_over_7pct": 0,        # would have been blocked by v3 ATR cap
        "v3_blocked_atr": 0,       # bars v3 blocks at ATR gates but v4 passes all other gates
    }

    min_bars = DRAWDOWN_LOOKBACK + max(SLOW_EMA, MACRO_EMA, ATR_PERIOD) + CONFIRM_BARS + MOMENTUM_LOOKBACK + 10

    for ts in idx:
        iloc = df_full.index.get_loc(ts)
        if iloc < min_bars:
            continue

        counters["total_bars"] += 1

        atr_v = float(atr_pct_series.iloc[iloc])
        dd_v  = float(drawdown_series.iloc[iloc])
        pvm_v = float(price_vs_macro.iloc[iloc])
        es_v  = float(ema_spread_series.iloc[iloc])
        sm_v  = float(spread_momentum_series.iloc[iloc])

        recent_spreads = ema_spread_series.iloc[max(0, iloc - CONFIRM_BARS + 1): iloc + 1]
        spread_ok = bool((recent_spreads < EMA_SPREAD_THRESHOLD).all())

        # Proxy regime: TREND_DOWN if price_vs_macro < -0.02 and drawdown > 10%
        # (rough approximation since we don't have the real regime labels)
        regime_ok = (pvm_v < -0.02) and (dd_v > 0.10)

        if not regime_ok:
            counters["g1_not_trend_down"] += 1
            continue

        if atr_v < MIN_ATR_PCT:
            counters["g2_atr_floor"] += 1
            continue

        if pvm_v >= 0:
            counters["g3_macro_ema"] += 1
            continue

        if dd_v < DRAWDOWN_THRESHOLD:
            counters["g4_drawdown"] += 1
            continue

        if not spread_ok:
            counters["g5_spread"] += 1
            continue

        if sm_v >= 0:
            counters["g6_momentum"] += 1
            continue

        # All v4 gates passed
        counters["would_enter"] += 1
        if atr_v > 0.07:
            counters["atr_over_7pct"] += 1
            counters["v3_blocked_atr"] += 1

    print("\n=== Gate Audit 2022 ===")
    total = counters["total_bars"]
    for k, v in counters.items():
        pct = f" ({v/total*100:.1f}%)" if total > 0 and k != "total_bars" else ""
        print(f"  {k:<30} {v:>6}{pct}")
    print()
    print("Interpretation:")
    print(f"  v4 would enter on {counters['would_enter']} bars in 2022")
    print(f"  Of those, {counters['atr_over_7pct']} had ATR > 7% (would be blocked by v3 ATR cap)")
    print(f"  → v3 ATR cap adds 0 new entries if 'v3_blocked_atr' is small relative to 'would_enter'")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--btc-data", required=True)
    args = parser.parse_args()

    print(f"Loading {args.btc_data} ...")
    df = load_csv(args.btc_data)
    print(f"  {len(df)} bars  {df.index[0]} → {df.index[-1]}")
    run_gate_audit(df)


if __name__ == "__main__":
    main()
