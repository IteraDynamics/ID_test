"""Relative-value pairs trading, distance method (Gatev/Goetzmann/Rouwenhorst 2006), from
first principles, end to end: pair selection, walk-forward backtest, and a Monte Carlo /
negative-control battery run in the same pass -- not staged as separate asks.

Mechanism, stated plainly: this is not directional (no view on where any single name goes),
not event-driven, not carry. It bets on the RELATIONSHIP between two price series reverting
after it stretches, nothing else. Two tickers are a "pair" if their normalized price paths
tracked each other closely over a formation period; when they diverge beyond their own
historical relationship during the following trading period, go long the laggard / short the
leader, and close on reversion (or force-close on a stop or at window end if it never comes
back). Every trading window is scored using ONLY pair selections and thresholds computed on
the strictly prior formation window -- there is no separate "OOS confirmation" step bolted on
afterward, because the walk-forward design is out-of-sample by construction: nothing about
window N's trading period informs window N's own pair selection.

THE CANARY, not optional, run automatically as part of this script rather than offered as a
follow-up: broad equity dispersion alone can produce a positive-looking long-short spread with
almost any random pairing, because shorting-the-winner/buying-the-loser has a generic
mean-reversion tailwind in many regimes independent of any real cointegration between the two
specific names. So this also runs the IDENTICAL simulation with RANDOMLY selected pairs
(same count, same windows, same thresholds, same costs) as a null. If distance-selected pairs
don't clear the random-pair null by a wide, unambiguous margin, this has not found a real,
pair-specific relative-value effect -- it has found generic equity dispersion wearing a pairs-
trading costume, and should be read as a fail, not a marginal pass.

Two more Monte Carlo layers, run here rather than promised for later:
  1. A bootstrap resample of the REAL strategy's own window-level returns, to get a Sharpe
     confidence interval and an explicit P(Sharpe <= 0) rather than a single point estimate.
  2. The permutation p-value itself: the fraction of random-pair null repeats whose Sharpe
     matches or beats the real, distance-selected result.

Deliberate simplifications, named rather than hidden:
  - Spread P&L uses normalized-price DIFFERENCE (not log-return spread) -- a close
    approximation for small-to-moderate moves, not exact. Good enough to judge whether this is
    worth refining further; not offered as a precise P&L model.
  - Position sizing is unit notional ($1 long, $1 short) per open trade. This deliberately does
    NOT attempt capital/concurrency sizing at this stage -- that is a separate, later question
    (how many pairs can actually be open at once at a given book size) that only matters once
    the RAW mechanism has cleared its own null. Answering a sizing question for a mechanism
    that hasn't passed its own negative control would be premature.
  - Costs are a single all-in round-trip bps knob per leg (entry+exit, both legs) -- no separate
    commission/slippage decomposition, no borrow cost modeled for the short leg. Any real
    result here is a pre-borrow-cost estimate; borrow cost only cuts it down, never up.
  - No sector/fundamental matching constrains pair selection -- pairs are chosen purely on
    normalized-price-path distance, which can and does select statistically-close but
    fundamentally-unrelated names. That's the original Gatev/Goetzmann/Rouwenhorst design
    choice, not an oversight; a sector-constrained variant is a natural follow-up if this
    passes its own null.

Uses the same {TICKER}_1D.csv local price files already used elsewhere in this repo --
requires no new data acquisition. Stdlib + numpy/pandas/scipy only, deterministic given
--seed, per this repo's replay-verification convention.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

RNG_SEED = 20260901  # fixed for replay determinism, not tuned
MIN_FORMATION_STD = 1e-6  # guards a near-degenerate (effectively identical) pair's spread std


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--formation-months", type=int, default=12)
    parser.add_argument("--trading-months", type=int, default=6)
    parser.add_argument("--top-n-pairs", type=int, default=20, help="Pairs selected per window, by lowest formation-period distance.")
    parser.add_argument("--entry-z", type=float, default=2.0)
    parser.add_argument("--exit-z", type=float, default=0.0)
    parser.add_argument("--stop-z", type=float, default=4.0, help="Force-close if the spread diverges this far -- treat as a breakdown, not a bigger opportunity.")
    parser.add_argument("--cost-bps", type=float, default=5.0, help="Per-leg, per-transaction, all-in bps (commission+slippage combined).")
    parser.add_argument("--min-price", type=float, default=5.0, help="Excludes tickers ever below this price within a window -- avoids penny-stock pct-return artifacts.")
    parser.add_argument("--n-permutation-nulls", type=int, default=100)
    parser.add_argument("--n-bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=RNG_SEED)
    parser.add_argument("--output-dir", default="artifacts/pairs_distance_method")
    return parser.parse_args()


def load_price_panel(data_dir: Path) -> pd.DataFrame:
    """Local {TICKER}_1D.csv files aren't guaranteed to agree on tz-awareness -- some were
    pulled tz-naive, some tz-aware, depending on when/how each was downloaded (the same
    inconsistency this repo already hit once in the earnings-drift stage 2 script). Normalizing
    every series to tz-naive UTC before combining avoids pandas refusing to union a tz-naive
    index with a tz-aware one when building the panel."""
    frames = {}
    for path in sorted(data_dir.glob("*_1D.csv")):
        ticker = path.stem[: -len("_1D")]
        frame = pd.read_csv(path, parse_dates=["timestamp"])
        frame = frame.sort_values("timestamp").drop_duplicates(subset="timestamp").set_index("timestamp")
        if frame.index.tz is not None:
            frame.index = frame.index.tz_convert("UTC").tz_localize(None)
        frames[ticker] = frame["close"]
    if not frames:
        raise FileNotFoundError(f"No {{TICKER}}_1D.csv files found in {data_dir}. Nothing to pair.")
    panel = pd.DataFrame(frames)
    print(f"Loaded {panel.shape[1]} tickers, {panel.shape[0]} raw dates, {panel.index.min().date()} to {panel.index.max().date()}.")
    return panel


def generate_windows(panel_index: pd.DatetimeIndex, formation_months: int, trading_months: int) -> list[tuple]:
    windows = []
    trading_start = panel_index.min() + pd.DateOffset(months=formation_months)
    data_end = panel_index.max()
    while True:
        formation_start = trading_start - pd.DateOffset(months=formation_months)
        trading_end = trading_start + pd.DateOffset(months=trading_months)
        if trading_end > data_end:
            break
        windows.append((formation_start, trading_start, trading_end))
        trading_start = trading_start + pd.DateOffset(months=trading_months)
    return windows


def eligible_slice(panel: pd.DataFrame, formation_start: pd.Timestamp, trading_end: pd.Timestamp, min_price: float) -> pd.DataFrame:
    window = panel.loc[(panel.index >= formation_start) & (panel.index < trading_end)]
    valid_cols = [c for c in window.columns if window[c].notna().all() and (window[c] >= min_price).all()]
    return window[valid_cols]


def select_pairs_by_distance(formation_prices: pd.DataFrame, top_n: int) -> list[tuple[str, str]]:
    normalized = formation_prices / formation_prices.iloc[0]
    tickers = normalized.columns.tolist()
    n = len(tickers)
    if n < 2:
        return []
    arr = normalized.to_numpy()
    sq_sum = (arr ** 2).sum(axis=0)
    ssd = sq_sum[:, None] + sq_sum[None, :] - 2.0 * (arr.T @ arr)
    iu = np.triu_indices(n, k=1)
    pair_ssd = ssd[iu]
    order = np.argsort(pair_ssd)[: min(top_n, len(pair_ssd))]
    return [(tickers[iu[0][idx]], tickers[iu[1][idx]]) for idx in order]


def select_pairs_random(tickers: list[str], top_n: int, rng: np.random.Generator) -> list[tuple[str, str]]:
    n = len(tickers)
    if n < 2:
        return []
    max_pairs = n * (n - 1) // 2
    chosen: set[tuple[str, str]] = set()
    attempts = 0
    while len(chosen) < min(top_n, max_pairs) and attempts < top_n * 20:
        a, b = rng.choice(tickers, size=2, replace=False)
        key = (a, b) if a < b else (b, a)
        chosen.add(key)
        attempts += 1
    return list(chosen)


def formation_spread_stats(formation_normalized: pd.DataFrame, ticker_a: str, ticker_b: str) -> tuple[float, float]:
    spread = formation_normalized[ticker_a] - formation_normalized[ticker_b]
    return float(spread.mean()), float(spread.std(ddof=1))


def simulate_pair_trades(
    dates: list, spread_values: np.ndarray, formation_mean: float, formation_std: float,
    entry_z: float, exit_z: float, stop_z: float, cost_bps: float, pair_label: str,
) -> list[dict]:
    trades = []
    position = 0
    entry_idx = None
    entry_spread = None

    for i, s in enumerate(spread_values):
        z = (s - formation_mean) / formation_std
        if position == 0:
            if z >= entry_z:
                position, entry_idx, entry_spread = -1, i, s
            elif z <= -entry_z:
                position, entry_idx, entry_spread = 1, i, s
        else:
            crossed_exit = (position == 1 and z >= exit_z) or (position == -1 and z <= exit_z)
            stopped_out = abs(z) >= stop_z
            window_ending = i == len(spread_values) - 1
            if crossed_exit or stopped_out or window_ending:
                gross_return = position * (s - entry_spread)
                cost = 4.0 * (cost_bps / 10_000.0)  # 2 legs x (entry + exit)
                reason = "stop" if stopped_out else ("window_end" if window_ending and not crossed_exit else "reverted")
                trades.append({
                    "pair": pair_label,
                    "entry_date": dates[entry_idx],
                    "exit_date": dates[i],
                    "direction": "long_spread" if position == 1 else "short_spread",
                    "gross_return": float(gross_return),
                    "net_return": float(gross_return - cost),
                    "exit_reason": reason,
                })
                position, entry_idx, entry_spread = 0, None, None
    return trades


def run_walk_forward(
    panel: pd.DataFrame, windows: list[tuple], top_n: int, entry_z: float, exit_z: float,
    stop_z: float, cost_bps: float, min_price: float, rng: np.random.Generator | None,
) -> tuple[list[dict], list[float], list[dict]]:
    """rng=None means real distance-based selection; rng given means random-pair null.

    Always collects per-window diagnostics (eligible-ticker and pair counts) -- cheap to
    compute, and the only way to tell "this window had a thin universe" apart from "this
    window had a full universe that just never crossed the entry threshold." Both look
    identical from the trade count alone."""
    all_trades: list[dict] = []
    window_returns: list[float] = []
    diagnostics: list[dict] = []

    for formation_start, trading_start, trading_end in windows:
        window_prices = eligible_slice(panel, formation_start, trading_end, min_price)
        diag = {
            "formation_start": formation_start,
            "trading_start": trading_start,
            "trading_end": trading_end,
            "n_eligible_tickers": int(window_prices.shape[1]),
            "n_pairs_selected": 0,
            "n_pairs_valid": 0,
            "n_trades": 0,
            "skip_reason": None,
        }
        if window_prices.shape[1] < 2:
            diag["skip_reason"] = "fewer than 2 eligible tickers"
            diagnostics.append(diag)
            continue

        formation_prices = window_prices.loc[window_prices.index < trading_start]
        if len(formation_prices) < 20:
            diag["skip_reason"] = "fewer than 20 formation-period observations"
            diagnostics.append(diag)
            continue
        base_row = formation_prices.iloc[0]
        formation_normalized = formation_prices / base_row

        if rng is None:
            pairs = select_pairs_by_distance(formation_prices, top_n)
        else:
            pairs = select_pairs_random(window_prices.columns.tolist(), top_n, rng)
        diag["n_pairs_selected"] = len(pairs)

        trading_prices = window_prices.loc[window_prices.index >= trading_start]
        if trading_prices.empty:
            diag["skip_reason"] = "no trading-period data"
            diagnostics.append(diag)
            continue
        trading_normalized = trading_prices / base_row

        window_trades: list[dict] = []
        n_pairs_valid = 0
        for ticker_a, ticker_b in pairs:
            formation_mean, formation_std = formation_spread_stats(formation_normalized, ticker_a, ticker_b)
            if formation_std < MIN_FORMATION_STD or np.isnan(formation_std):
                continue
            n_pairs_valid += 1
            spread_series = (trading_normalized[ticker_a] - trading_normalized[ticker_b]).to_numpy()
            trades = simulate_pair_trades(
                trading_normalized.index.to_list(), spread_series, formation_mean, formation_std,
                entry_z, exit_z, stop_z, cost_bps, f"{ticker_a}/{ticker_b}",
            )
            window_trades.extend(trades)
        diag["n_pairs_valid"] = n_pairs_valid
        diag["n_trades"] = len(window_trades)
        if not pairs:
            diag["skip_reason"] = "fewer than 2 eligible tickers to form a pair"
        elif n_pairs_valid == 0:
            diag["skip_reason"] = "every selected pair had a degenerate (near-zero) formation spread std"
        elif not window_trades:
            diag["skip_reason"] = "valid pairs formed but none crossed the entry threshold"
        diagnostics.append(diag)

        all_trades.extend(window_trades)
        if window_trades:
            window_returns.append(float(np.mean([t["net_return"] for t in window_trades])))

    return all_trades, window_returns, diagnostics


def annualized_sharpe(window_returns: np.ndarray, windows_per_year: float) -> float:
    if len(window_returns) < 2 or window_returns.std(ddof=1) == 0:
        return 0.0
    return float(window_returns.mean() / window_returns.std(ddof=1) * np.sqrt(windows_per_year))


def bootstrap_sharpe_distribution(window_returns: np.ndarray, windows_per_year: float, n_bootstrap: int, rng: np.random.Generator) -> dict:
    n = len(window_returns)
    sharpes = np.empty(n_bootstrap)
    for b in range(n_bootstrap):
        resample = window_returns[rng.integers(0, n, n)]
        sharpes[b] = annualized_sharpe(resample, windows_per_year)
    return {
        "p5": float(np.percentile(sharpes, 5)),
        "p50": float(np.percentile(sharpes, 50)),
        "p95": float(np.percentile(sharpes, 95)),
        "prob_sharpe_le_zero": float((sharpes <= 0).mean()),
    }


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    panel = load_price_panel(data_dir)
    windows = generate_windows(panel.index, args.formation_months, args.trading_months)
    if not windows:
        raise RuntimeError(
            f"No complete {args.formation_months}mo formation + {args.trading_months}mo trading window fits "
            "in the available data. Need more price history."
        )
    windows_per_year = 12.0 / args.trading_months
    print(f"{len(windows)} walk-forward windows, {args.formation_months}mo formation / {args.trading_months}mo trading each.\n")

    print("=== Real strategy: distance-method pair selection ===")
    real_trades, real_window_returns, real_diagnostics = run_walk_forward(
        panel, windows, args.top_n_pairs, args.entry_z, args.exit_z, args.stop_z,
        args.cost_bps, args.min_price, rng=None,
    )
    real_window_returns_arr = np.array(real_window_returns)
    real_sharpe = annualized_sharpe(real_window_returns_arr, windows_per_year)
    n_trades = len(real_trades)
    net_returns = np.array([t["net_return"] for t in real_trades]) if real_trades else np.array([])

    print(f"{n_trades} trades across {len(real_window_returns)} windows with at least one trade.")
    if n_trades:
        win_rate = float((net_returns > 0).mean())
        print(f"Mean net return/trade: {net_returns.mean():+.3%}  Win rate: {win_rate:.1%}")
    print(f"Annualized Sharpe (window-level, equal-weight across pairs each window): {real_sharpe:+.2f}\n")

    n_skipped = sum(1 for d in real_diagnostics if d["n_trades"] == 0)
    print(f"=== Window diagnostic: why {n_skipped}/{len(real_diagnostics)} windows produced zero trades ===")
    reason_counts: dict[str, int] = {}
    for d in real_diagnostics:
        if d["n_trades"] == 0:
            reason_counts[d["skip_reason"]] = reason_counts.get(d["skip_reason"], 0) + 1
    for reason, count in sorted(reason_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {count:>2} window(s): {reason}")
    print(f"{'trading_start':>13} | {'eligible':>8} | {'pairs_sel':>9} | {'pairs_valid':>11} | {'trades':>6} | reason")
    for d in real_diagnostics:
        reason = d["skip_reason"] or ""
        print(
            f"  {pd.Timestamp(d['trading_start']).date()} | {d['n_eligible_tickers']:>8} | "
            f"{d['n_pairs_selected']:>9} | {d['n_pairs_valid']:>11} | {d['n_trades']:>6} | {reason}"
        )
    print()

    print(f"=== Negative control: {args.n_permutation_nulls} random-pair null repeats ===")
    null_sharpes = []
    for i in range(args.n_permutation_nulls):
        _, null_window_returns, _ = run_walk_forward(
            panel, windows, args.top_n_pairs, args.entry_z, args.exit_z, args.stop_z,
            args.cost_bps, args.min_price, rng=rng,
        )
        null_sharpes.append(annualized_sharpe(np.array(null_window_returns), windows_per_year))
    null_sharpes_arr = np.array(null_sharpes)
    beat_or_tied = int((null_sharpes_arr >= real_sharpe).sum())
    permutation_p_value = (1 + beat_or_tied) / (1 + args.n_permutation_nulls)

    print(f"Random-pair null Sharpe: mean={null_sharpes_arr.mean():+.2f} p95={np.percentile(null_sharpes_arr, 95):+.2f}")
    print(f"Real (distance-selected) Sharpe: {real_sharpe:+.2f}")
    print(f"Permutation p-value (fraction of random-pair nulls >= real): {permutation_p_value:.4f}")
    print(
        "  -- this is the canary. If real doesn't clear the random-pair null by a wide margin, "
        "the apparent edge is generic equity dispersion, not pair-specific relative value.\n"
    )

    print(f"=== Monte Carlo: bootstrap of real strategy's own window returns, {args.n_bootstrap} resamples ===")
    if len(real_window_returns_arr) >= 2:
        bootstrap = bootstrap_sharpe_distribution(real_window_returns_arr, windows_per_year, args.n_bootstrap, rng)
        print(
            f"Sharpe 90% CI: [{bootstrap['p5']:+.2f}, {bootstrap['p95']:+.2f}]  "
            f"median={bootstrap['p50']:+.2f}  P(Sharpe<=0)={bootstrap['prob_sharpe_le_zero']:.3f}"
        )
    else:
        bootstrap = {"insufficient_windows": True}
        print("Fewer than 2 windows produced trades -- cannot bootstrap.")

    verdict = "FAIL"
    if n_trades > 0 and permutation_p_value <= 0.05 and real_sharpe > 0 and bootstrap.get("prob_sharpe_le_zero", 1.0) < 0.25:
        verdict = "CLEARS OWN NEGATIVE CONTROL -- worth a closer look, not yet a green light"
    print(f"\nVerdict: {verdict}")
    print(
        "This verdict is mechanical (p<=0.05 vs. the random-pair null, positive real Sharpe, "
        "P(Sharpe<=0)<25% under bootstrap) -- read it as a gate, not a recommendation. Clearing "
        "it means the mechanism itself is real and pair-specific, not that it's sized, costed for "
        "borrow, or tradeable at any particular capital scale -- those are separate, later questions."
    )

    summary = {
        "n_windows": len(windows),
        "n_trades": n_trades,
        "real_sharpe": real_sharpe,
        "real_window_returns": real_window_returns,
        "real_window_diagnostics": real_diagnostics,
        "null_sharpes": null_sharpes,
        "permutation_p_value": permutation_p_value,
        "bootstrap": bootstrap,
        "verdict": verdict,
        "args": vars(args),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    if real_trades:
        pd.DataFrame(real_trades).to_csv(output_dir / "trades.csv", index=False)
    print(f"\nWrote results to {output_dir}/")


if __name__ == "__main__":
    main()
