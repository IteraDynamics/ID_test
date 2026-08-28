"""Is the equity sleeve's partial de-risk branch reachable? — REPORT ONLY.

The Core v1 parameter sensitivity pass returned metrics identical to baseline
to four significant figures for all four perturbations of `FAST_SMA_PERIOD`
(50 -> 40, 60) and `DERISKED_EXPOSURE` (0.50 -> 0.40, 0.60). Identical output
under a changed input is not robustness; it means the input did not reach the
model. This measures which.

In `research/strategies/equity_sma175_v3.py` both constants feed exactly one
decision:

    derisked = below_sma50 and btc_parabolic        # below_sma50 uses FAST_SMA_PERIOD

and `derisked` is consulted only in the "when long" branch, after the primary
SMA175 exit has been checked. `sma50_val` otherwise appears only in `meta` and
in a reason string, neither of which affects NAV. So if `derisked` never
becomes true while the sleeve is long and above SMA175, both constants are
inert by construction.

This computes the *necessary* condition:

    above_sma175 AND below_sma50 AND btc_parabolic_hard

which is an upper bound on how often the branch can fire -- the sleeve must
additionally already hold a position. If the count is zero, the branch is
provably unreachable and no position-state modelling is needed to say so.

Signals are constructed the same way the audit harness constructs them:
`btc_parabolic_hard` from `research.harness.cross_asset_state`, resampled
daily and forward-filled onto the SPY index.

Strictly read-only. Reads price CSVs, writes nothing, changes no runtime,
strategy, or portfolio behaviour. This is a measurement of Core v1, not a
modification of it -- the One Rule applies and nothing here proposes a change.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from research.harness.cross_asset_state import compute_btc_macro_state  # noqa: E402
from research.strategies.equity_sma175_v3 import (  # noqa: E402
    ENTRY_BUFFER,
    FAST_SMA_PERIOD,
    SMA_PERIOD,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Measure reachability of the equity partial de-risk branch.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--spy-data", default="data/SPY_1D.csv")
    p.add_argument("--qqq-data", default="data/QQQ_1D.csv")
    p.add_argument("--btc-data", default="data/btcusd_3600s.csv")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default=None)
    p.add_argument(
        "--fast-sma",
        type=int,
        action="append",
        default=None,
        help="FAST_SMA_PERIOD values to test (repeatable). Default: the canonical "
             "value plus the two perturbations used by the sensitivity pass.",
    )
    return p.parse_args(argv)


def load_close(path: str, start: str, end: str | None) -> pd.Series:
    frame = pd.read_csv(path)
    stamp = next(c for c in frame.columns if c.lower() in {"timestamp", "date", "time", "datetime"})
    frame[stamp] = pd.to_datetime(frame[stamp], utc=True, format="mixed").dt.tz_localize(None)
    close = frame.set_index(stamp)["close"].sort_index()
    close = close.loc[start:] if end is None else close.loc[start:end]
    return close[~close.index.duplicated(keep="last")]


def report(label: str, close: pd.Series, parabolic: pd.Series, fast_periods: list[int]) -> None:
    sma_slow = close.rolling(SMA_PERIOD).mean()
    pct_vs_slow = (close - sma_slow) / sma_slow
    above = pct_vs_slow > 0
    entry_ok = pct_vs_slow > ENTRY_BUFFER
    para = parabolic.reindex(close.index, method="ffill").fillna(False).astype(bool)

    print(f"\n=== {label} ===")
    print(f"sessions: {len(close)}  ({close.index[0].date()} .. {close.index[-1].date()})")
    print(f"above SMA{SMA_PERIOD}: {int(above.sum())}   "
          f"entry-eligible (> {ENTRY_BUFFER:.2%}): {int(entry_ok.sum())}")
    print(f"BTC parabolic (hard, extension > 100% over SMA365): {int(para.sum())} sessions")

    both = above & para
    print(f"above SMA{SMA_PERIOD} AND BTC parabolic: {int(both.sum())} sessions")

    for period in fast_periods:
        below_fast = close < close.rolling(period).mean()
        reachable = both & below_fast
        count = int(reachable.sum())
        marker = "  <-- UNREACHABLE" if count == 0 else ""
        print(f"  FAST_SMA_PERIOD={period:>3}: de-risk necessary condition true "
              f"on {count} sessions{marker}")
        if count:
            firsts = reachable[reachable].index[:5]
            print(f"      first occurrences: {', '.join(str(d.date()) for d in firsts)}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    fast_periods = args.fast_sma or sorted({FAST_SMA_PERIOD, 40, 60})

    btc = pd.read_csv(args.btc_data)
    stamp = next(c for c in btc.columns if c.lower() in {"timestamp", "date", "time", "datetime"})
    btc[stamp] = pd.to_datetime(btc[stamp], utc=True, format="mixed").dt.tz_localize(None)
    btc = btc.set_index(stamp).sort_index()

    state = compute_btc_macro_state(btc)
    if state.empty:
        raise SystemExit("BTC macro state empty; check --btc-data coverage.")
    parabolic = state["btc_parabolic_hard"].fillna(False).astype(bool)

    print("Equity partial de-risk reachability — REPORT ONLY")
    print(f"BTC state: {len(state)} daily rows, "
          f"{int(parabolic.sum())} parabolic-hard sessions "
          f"({state.index[0].date()} .. {state.index[-1].date()})")

    for label, path in (("SPY", args.spy_data), ("QQQ", args.qqq_data)):
        if not Path(path).exists():
            print(f"\n=== {label} ===\n  source missing: {path}")
            continue
        report(label, load_close(path, args.start, args.end), parabolic, fast_periods)

    print(
        "\nA zero count is an upper bound reaching zero: the branch cannot fire, so "
        "FAST_SMA_PERIOD and DERISKED_EXPOSURE cannot affect any Core v1 output, and "
        "their sensitivity rows are evidence about nothing.\n"
        "A non-zero count means the branch is reachable in principle and the identical "
        "sensitivity rows need a different explanation — position state, cooldown, or "
        "the rebalance threshold absorbing the exposure change."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
