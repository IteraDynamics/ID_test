#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from research.harness.resampler import resample_ohlcv
from research.strategies.contracts import StrategyContext
from research.regimes.contracts import RegimeLabel
from research.strategies import trend_following_v9_explicit_btc, trend_following_v11_explicit_btc
from scripts.cross_asset_state import compute_btc_macro_state, inject_btc_macro_state
from scripts.run_multi_strategy_fund import _load_asset


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Diagnose explicit BTC macro-state injection")
    p.add_argument("--btc-data", required=True)
    p.add_argument("--eth-data", required=True)
    p.add_argument("--data-start", default="2019-01-01")
    p.add_argument("--sample-timestamp", default=None)
    return p.parse_args()


def _ctx(asset: str) -> StrategyContext:
    return StrategyContext(
        regime=RegimeLabel.TREND_UP,
        current_exposure_frac=0.0,
        asset=asset,
        bar_index=0,
        meta={},
    )


def main() -> None:
    args = parse_args()
    btc = _load_asset(args.btc_data, "BTC", args.data_start, None)
    eth = _load_asset(args.eth_data, "ETH", args.data_start, None)
    btc_state = compute_btc_macro_state(btc)

    eth_4h = resample_ohlcv(eth, "4h")
    eth_with_btc = inject_btc_macro_state(eth_4h, btc_state)

    if args.sample_timestamp:
        ts = pd.Timestamp(args.sample_timestamp)
        eth_slice = eth_with_btc.loc[:ts]
    else:
        available = eth_with_btc.dropna(subset=["btc_above_sma175", "btc_extension_sma365"])
        if available.empty:
            raise SystemExit("No rows with full BTC macro state available")
        ts = available.index[len(available) // 2]
        eth_slice = eth_with_btc.loc[:ts]

    intent9 = trend_following_v9_explicit_btc.generate_intent(eth_slice, _ctx("ETH"), closed_only=True)
    intent11 = trend_following_v11_explicit_btc.generate_intent(eth_slice, _ctx("ETH"), closed_only=True)

    print("timestamp", eth_slice.index[-1])
    print("eth_close", float(eth_slice["close"].iloc[-1]))
    print("btc_above_sma175_col", eth_slice["btc_above_sma175"].iloc[-1])
    print("btc_extension_sma365_col", eth_slice["btc_extension_sma365"].iloc[-1])
    print("v9_action", intent9.action.name)
    print("v9_btc_state_source", intent9.meta.get("btc_state_source"))
    print("v9_btc_above_sma175", intent9.meta.get("btc_above_sma175"))
    print("v11_action", intent11.action.name)
    print("v11_btc_parabolic_state_source", intent11.meta.get("btc_parabolic_state_source"))
    print("v11_btc_extension_sma365", intent11.meta.get("btc_extension_sma365"))

    if intent9.meta.get("btc_state_source") != "explicit_btc":
        raise SystemExit("FAIL: v9 did not use explicit BTC state")
    if intent11.meta.get("btc_parabolic_state_source") != "explicit_btc":
        raise SystemExit("FAIL: v11 did not use explicit BTC parabolic state")
    print("PASS explicit BTC state consumed by ETH trend strategies")


if __name__ == "__main__":
    main()
