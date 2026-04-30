#!/usr/bin/env python
"""Itera Allocator v1 Backtest Runner

Runs a dynamic allocation backtest using:
    - Crypto Sleeve v1 equity curve
    - Equity Sleeve v1 equity curve
    - Itera Allocator v1

This compares dynamic allocation vs static Itera Fund v0 baseline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from research.allocators.itera_allocator_v1 import decide_weights


def load_curve(path: str) -> pd.Series:
    df = pd.read_csv(path)
    ts_col = df.columns[0]
    df[ts_col] = pd.to_datetime(df[ts_col])
    df = df.set_index(ts_col)
    col = [c for c in df.columns if df[c].dtype != object][0]
    return df[col].astype(float)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--crypto-equity", required=True)
    p.add_argument("--equity-equity", required=True)
    p.add_argument("--capital", type=float, default=100000)
    p.add_argument("--out-dir", default="artifacts/allocator_v1")
    args = p.parse_args()

    crypto = load_curve(args.crypto_equity).resample("1D").last().dropna()
    equity = load_curve(args.equity_equity).resample("1D").last().dropna()

    idx = crypto.index.intersection(equity.index)
    crypto = crypto.loc[idx]
    equity = equity.loc[idx]

    crypto = crypto / crypto.iloc[0]
    equity = equity / equity.iloc[0]

    capital = args.capital
    weights = []
    portfolio = []

    current_w = 0.70

    for i in range(len(idx)):
        c_slice = crypto.iloc[: i + 1]
        e_slice = equity.iloc[: i + 1]

        decision = decide_weights(c_slice, e_slice, current_w)
        current_w = decision.crypto_weight

        weights.append(current_w)

        port_val = capital * (
            current_w * c_slice.iloc[-1]
            + (1 - current_w) * e_slice.iloc[-1]
        )
        portfolio.append(port_val)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame({
        "portfolio": portfolio,
        "crypto_weight": weights,
    }, index=idx)

    df.to_csv(out / "allocator_v1_equity.csv")

    print(f"Saved allocator v1 results to {out}")


if __name__ == "__main__":
    main()
