"""Every historical episode where crash_short_v6's entry gate would fire.

Campaign #54's open question (docs/research/CAMPAIGN_54_CRASH_SHORT_
PLANNING_CHARTER.md, section 3c): the campaign's entire power case rests on
one historical crisis, 2022. Whether the 2020 COVID crash counts as a second,
weaker observation was named as unchecked. This answers that directly, and
more completely -- rather than checking one date range, it finds every
distinct episode across the full reachable history where all seven of
crash_short_v6's entry gates align simultaneously, using the same regime
engine (BaselineRegimeEngine) and the same formulas as the strategy module
and the production backtest engine, not an approximation.

This does not replay a full backtest (no position sizing, no exits, no P&L).
It answers a narrower, prior question: how many independent times has this
exact rule combination triggered, historically? That number is the direct
input to whether Campaign #54's power problem is genuinely n=1 or something
better than that.

Read-only. Report only. No runtime, Core v1, or production behavior touched.
"""

from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
from pathlib import Path

import pandas as pd

import sys
REPO_ROOT = Path(__file__).resolve().parent.parent

from research.harness.data_loader import load_ohlcv  # noqa: E402
from research.regimes.baseline_engine import BaselineRegimeEngine  # noqa: E402
from research.regimes.contracts import RegimeLabel  # noqa: E402

# Constants copied from research/strategies/crash_short_v6.py -- not imported,
# because the strategy module only exposes per-bar generate_intent(), not a
# vectorised form. Kept here as literal values so a diff against that file is
# a direct, visible check that this replica hasn't drifted.
MACRO_EMA = 720
DRAWDOWN_LOOKBACK = 2160
DRAWDOWN_THRESHOLD = 0.20
FAST_EMA = 21
SLOW_EMA = 55
MOMENTUM_LOOKBACK = 5
EMA_SPREAD_THRESHOLD = -0.008
CONFIRM_BARS = 6
ATR_PERIOD = 24
MIN_ATR_PCT = 0.010


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--btc-data", default="data/btcusd_3600s_2018-01-01_to_2025-12-31.csv")
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    return p.parse_args(argv)


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    btc = load_ohlcv(args.btc_data, start=args.start, end=args.end, asset="BTC")
    print(f"BTC: {len(btc)} bars {btc.index[0]} -> {btc.index[-1]}")

    spy = load_ohlcv(args.spy_data, start=args.start, end=args.end, asset="SPY")
    spy_sma175 = spy["close"].rolling(175).mean()
    spy_bullish_daily = (spy["close"] > spy_sma175).rename("spy_bullish")
    spy_bullish = spy_bullish_daily.reindex(btc.index, method="ffill")
    print(f"SPY: {len(spy)} bars {spy.index[0]} -> {spy.index[-1]}")

    print("\nClassifying regimes with the production BaselineRegimeEngine "
          "(same engine research/harness/backtest_engine.py uses)...")
    engine = BaselineRegimeEngine()
    signals = engine.classify_dataframe(btc)
    regime = pd.Series([s.label for s in signals], index=btc.index, name="regime")

    close, high, low = btc["close"], btc["high"], btc["low"]
    ema_fast = close.ewm(span=FAST_EMA, adjust=False).mean()
    ema_slow = close.ewm(span=SLOW_EMA, adjust=False).mean()
    ema_macro = close.ewm(span=MACRO_EMA, adjust=False).mean()
    atr_pct = _atr(high, low, close, ATR_PERIOD) / close

    ema_spread = (ema_fast - ema_slow) / close
    spread_momentum = ema_spread - ema_spread.shift(MOMENTUM_LOOKBACK)
    price_vs_macro = (close - ema_macro) / ema_macro
    rolling_high = close.rolling(DRAWDOWN_LOOKBACK).max()
    drawdown_from_high = (rolling_high - close) / rolling_high

    sustained_down = (ema_spread < EMA_SPREAD_THRESHOLD).rolling(CONFIRM_BARS).sum() >= CONFIRM_BARS

    gates = pd.DataFrame({
        "g1_trend_down": regime.values == RegimeLabel.TREND_DOWN,
        "g2_atr_floor": atr_pct >= MIN_ATR_PCT,
        "g3_below_macro_ema": price_vs_macro < 0,
        "g4_drawdown_20pct": drawdown_from_high >= DRAWDOWN_THRESHOLD,
        "g5_sustained_spread": sustained_down,
        "g6_momentum_down": spread_momentum < 0,
        "g7_spy_not_bullish": spy_bullish.reindex(btc.index).fillna(False).values != True,  # noqa: E712
    }, index=btc.index)

    all_seven = gates.all(axis=1)
    six_without_spy = gates.drop(columns=["g7_spy_not_bullish"]).all(axis=1)

    def episodes(mask: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
        if not mask.any():
            return []
        grp = (mask != mask.shift(fill_value=False)).cumsum()
        out = []
        for _, block in mask[mask].groupby(grp[mask]):
            out.append((block.index[0], block.index[-1]))
        return out

    all_episodes = episodes(all_seven)
    print(f"\nEntry-eligible episodes (all 7 gates, incl. SPY confirmation): {len(all_episodes)}")
    for start, end in all_episodes:
        duration_h = (end - start).total_seconds() / 3600 + 1
        p0, p1 = float(close.loc[start]), float(close.loc[end])
        print(
            f"  {start} -> {end}  ({duration_h:.0f}h)  "
            f"BTC {p0:,.0f} -> {p1:,.0f} ({(p1/p0-1)*100:+.1f}%)"
        )

    without_spy_episodes = episodes(six_without_spy)
    print(f"\nEntry-eligible on the other 6 gates alone (SPY confirmation removed): "
          f"{len(without_spy_episodes)}")
    for start, end in without_spy_episodes:
        duration_h = (end - start).total_seconds() / 3600 + 1
        confirmed = all_seven.loc[start:end].any()
        print(
            f"  {start} -> {end}  ({duration_h:.0f}h)  "
            f"{'SPY confirmed part of this window' if confirmed else 'SPY NEVER confirmed -- blocked entirely'}"
        )

    print("\n--- 2020 COVID crash, specifically ---")
    covid_window = gates.loc["2020-02-15":"2020-04-15"]
    if covid_window.empty:
        print("No BTC data in this window.")
    else:
        for col in gates.columns:
            hit_rate = covid_window[col].mean()
            print(f"  {col}: true on {covid_window[col].sum()} of {len(covid_window)} bars "
                  f"({hit_rate:.0%})")
        covid_all = covid_window.all(axis=1)
        if covid_all.any():
            print(f"  -> ALL 7 GATES ALIGNED during this window: "
                  f"{covid_all[covid_all].index[0]} to {covid_all[covid_all].index[-1]}")
        else:
            blocking = [c for c in gates.columns if not covid_window[c].any()]
            print(f"  -> Never all-7 aligned. Gate(s) never satisfied in this window: {blocking}")

    print(
        "\nThis counts entry-ELIGIBLE windows, not realized trades -- no exit logic, no "
        "cooldown, no position sizing. It answers 'how many independent times did this exact "
        "rule combination trigger', which bounds Campaign #54's power problem; it does not "
        "replace the full audit harness for P&L."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
