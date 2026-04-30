#!/usr/bin/env python
"""Itera Allocator v2 Backtest Runner (Defensive Overlay).

Dynamic allocation using a defensive overlay on top of a static baseline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from research.allocators.itera_allocator_v2 import decide_defensive_weights


def load_curve(path: str, col_candidates: list[str]) -> pd.Series:
    df = pd.read_csv(path)
    ts = df.columns[0]
    df[ts] = pd.to_datetime(df[ts])
    df = df.set_index(ts)

    for c in col_candidates:
        if c in df.columns:
            return df[c].astype(float)

    num_cols = [c for c in df.columns if df[c].dtype != object]
    return df[num_cols[0]].astype(float)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--crypto-equity", required=True)
    p.add_argument("--equity-equity", required=True)
    p.add_argument("--capital", type=float, default=100000)
    args = p.parse_args()

    crypto = load_curve(args.crypto_equity, ["portfolio", "equity"]).resample("1D").last().dropna()
    equity = load_curve(args.equity_equity, ["strategy_equity", "equity"]).resample("1D").last().dropna()

    idx = crypto.index.intersection(equity.index)
    crypto = crypto.loc[idx] / crypto.iloc[0]
    equity = equity.loc[idx] / equity.iloc[0]

    crypto_ret = crypto.pct_change().fillna(0)
    equity_ret = equity.pct_change().fillna(0)

    nav = [args.capital]
    weights = []
    defensive = False
    defensive_days = 0

    w_crypto = 0.70

    for i in range(1, len(idx)):
        r = w_crypto * crypto_ret.iloc[i] + (1 - w_crypto) * equity_ret.iloc[i]
        nav.append(nav[-1] * (1 + r))

        decision = decide_defensive_weights(
            crypto.iloc[: i + 1],
            equity.iloc[: i + 1],
            current_defensive_state=defensive,
            defensive_days=defensive_days,
        )

        defensive = decision.defensive_state
        if defensive:
            defensive_days += 1
        else:
            defensive_days = 0

        w_crypto = decision.crypto_weight
        weights.append(w_crypto)

    print("Allocator v2 run complete")


if __name__ == "__main__":
    main()
