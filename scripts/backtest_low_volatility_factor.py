"""Cross-sectional low-volatility anomaly, walk-forward with a built-in negative control and
Monte Carlo -- same discipline as the pairs-trading script, same universe, same infrastructure.

Mechanism: rank the eligible universe by trailing realized volatility each formation window, go
long the lowest-volatility quintile / short the highest-volatility quintile, hold for the
following trading window, walk forward. Distinct in kind from everything already tested this
session -- not relative-value (pairs), not event-driven (earnings surprise), not trend, not
funding-rate carry. A cross-sectional risk-based sort.

Structural rationale, stated at the same level of scrutiny as every other candidate considered
this session: the documented explanation (Ang/Hodrick/Xing/Zhang 2006 for the volatility-sort
version; Frazzini/Pedersen 2014 "Betting Against Beta" for the beta-neutral version) is that
leverage-constrained investors who cannot lever up a low-risk portfolio to their target return
instead overpay for high-risk/high-beta names to get there directly, structurally depressing
high-vol expected returns and elevating low-vol ones. That is a constraint-driven premium, not
pure informational mispricing -- which is the argument for why it persists.

Honest caveat, stated before any result rather than after: this is also one of the most widely
known, heavily traded factors in finance -- there are billion-dollar low-volatility ETFs built
directly on it (USMV, SPLV, etc). It is not undiscovered. The case for it surviving is that the
underlying constraint (leverage-averse capital) does not disappear just because the factor is
known, not that nobody has found it. Whether that argument actually holds is exactly what the
negative control below is for -- it is not assumed here.

Deliberate simplifications, named rather than hidden:
  - Sorts on trailing REALIZED VOLATILITY (annualized std of daily returns), not a regression
    beta against a market benchmark. Closely related in the literature but not identical to the
    classic beta-neutral Frazzini/Pedersen construction -- simpler and more robust (no benchmark
    regression, no beta-estimation noise per name) at the cost of not being the textbook exact
    implementation.
  - Equal-weight within each leg, not beta-scaled to make each leg's portfolio beta exactly 1
    (the "betting against beta" leverage-neutralization step). A real simplification: this
    version is a volatility-sorted long-short spread, not a beta-neutral one.
  - Unit notional per leg, no capital/concurrency sizing (same reasoning as the pairs script --
    sizing is a later question, only relevant once the raw mechanism clears its own null).
  - Single all-in cost-bps knob per leg per window (entry+exit), no short-borrow cost modeled.
  - No sector-neutrality constraint on the long/short legs -- a real risk sector concentration
    could exist in either leg and isn't controlled for here.

Reuses the exact loading/eligibility/window infrastructure from
scripts/backtest_pairs_distance_method.py (ticker-pattern filter restricting to a single
coherent market, the tz/DST-safe timestamp parsing, the walk-forward window generator) rather
than re-deriving it and re-risking the same bugs that script already found and fixed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from backtest_pairs_distance_method import (  # noqa: E402
    US_EQUITY_TICKER_PATTERN,
    eligible_slice,
    generate_windows,
    load_price_panel,
)

RNG_SEED = 20260901  # fixed for replay determinism, not tuned
N_QUINTILES = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--ticker-pattern", default=US_EQUITY_TICKER_PATTERN.pattern)
    parser.add_argument("--formation-months", type=int, default=12, help="Trailing window trailing volatility is computed over.")
    parser.add_argument("--trading-months", type=int, default=3, help="Holding period before the next rebalance.")
    parser.add_argument("--min-price", type=float, default=5.0)
    parser.add_argument("--cost-bps", type=float, default=5.0, help="Per-leg, per-window, all-in bps (commission+slippage combined, entry+exit).")
    parser.add_argument("--n-permutation-nulls", type=int, default=100)
    parser.add_argument("--n-bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=RNG_SEED)
    parser.add_argument("--output-dir", default="artifacts/low_volatility_factor")
    return parser.parse_args()


def trailing_volatility(formation_prices: pd.DataFrame) -> pd.Series:
    daily_returns = formation_prices.pct_change().dropna(how="all")
    return daily_returns.std(ddof=1) * np.sqrt(252)


def form_quintile_legs(vol: pd.Series, n_quintiles: int) -> tuple[list[str], list[str]]:
    quintile = pd.qcut(vol, n_quintiles, labels=False, duplicates="drop")
    n_actual = quintile.nunique()
    if n_actual < 2:
        return [], []
    long_leg = quintile[quintile == quintile.min()].index.tolist()   # lowest vol
    short_leg = quintile[quintile == quintile.max()].index.tolist()  # highest vol
    return long_leg, short_leg


def leg_trading_return(trading_prices: pd.DataFrame, tickers: list[str]) -> float:
    if not tickers:
        return 0.0
    period_returns = trading_prices[tickers].iloc[-1] / trading_prices[tickers].iloc[0] - 1.0
    return float(period_returns.mean())


def run_walk_forward(
    panel: pd.DataFrame, windows: list[tuple], min_price: float, cost_bps: float,
    n_quintiles: int, rng: np.random.Generator | None,
) -> tuple[list[float], list[dict]]:
    """rng=None means real volatility-sorted legs; rng given means a random long/short split of
    the same universe and leg sizes, as the negative control."""
    window_returns: list[float] = []
    diagnostics: list[dict] = []

    for formation_start, trading_start, trading_end in windows:
        window_prices = eligible_slice(panel, formation_start, trading_end, min_price)
        diag = {
            "trading_start": trading_start, "n_eligible": int(window_prices.shape[1]),
            "n_long": 0, "n_short": 0, "skip_reason": None,
        }
        if window_prices.shape[1] < n_quintiles * 2:
            diag["skip_reason"] = f"fewer than {n_quintiles * 2} eligible tickers to form quintiles both ways"
            diagnostics.append(diag)
            continue

        formation_prices = window_prices.loc[window_prices.index < trading_start]
        trading_prices = window_prices.loc[window_prices.index >= trading_start]
        if len(formation_prices) < 20 or trading_prices.empty:
            diag["skip_reason"] = "insufficient formation or trading observations"
            diagnostics.append(diag)
            continue

        if rng is None:
            vol = trailing_volatility(formation_prices)
            long_leg, short_leg = form_quintile_legs(vol, n_quintiles)
        else:
            tickers = window_prices.columns.tolist()
            shuffled = rng.permutation(tickers)
            leg_size = len(tickers) // n_quintiles
            long_leg, short_leg = list(shuffled[:leg_size]), list(shuffled[-leg_size:])

        diag["n_long"], diag["n_short"] = len(long_leg), len(short_leg)
        if not long_leg or not short_leg:
            diag["skip_reason"] = "quintile split degenerate (too few distinct volatility values)"
            diagnostics.append(diag)
            continue

        long_return = leg_trading_return(trading_prices, long_leg)
        short_return = leg_trading_return(trading_prices, short_leg)
        cost = 2.0 * (cost_bps / 10_000.0)  # entry + exit, one leg's own notional
        window_return = (long_return - short_return) - cost
        window_returns.append(window_return)
        diagnostics.append(diag)

    return window_returns, diagnostics


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
        "p5": float(np.percentile(sharpes, 5)), "p50": float(np.percentile(sharpes, 50)),
        "p95": float(np.percentile(sharpes, 95)), "prob_sharpe_le_zero": float((sharpes <= 0).mean()),
    }


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    panel = load_price_panel(data_dir, args.ticker_pattern)
    windows = generate_windows(panel.index, args.formation_months, args.trading_months)
    if not windows:
        raise RuntimeError("No complete formation+trading window fits in the available data.")
    windows_per_year = 12.0 / args.trading_months
    print(f"{len(windows)} walk-forward windows, {args.formation_months}mo formation / {args.trading_months}mo trading each.\n")

    print("=== Real strategy: low-volatility long / high-volatility short ===")
    real_returns, real_diagnostics = run_walk_forward(
        panel, windows, args.min_price, args.cost_bps, N_QUINTILES, rng=None,
    )
    real_returns_arr = np.array(real_returns)
    real_sharpe = annualized_sharpe(real_returns_arr, windows_per_year)
    print(f"{len(real_returns)}/{len(windows)} windows produced a return.")
    if len(real_returns):
        win_rate = float((real_returns_arr > 0).mean())
        print(f"Mean window return: {real_returns_arr.mean():+.3%}  Win rate: {win_rate:.1%}")
    print(f"Annualized Sharpe: {real_sharpe:+.2f}\n")

    n_skipped = sum(1 for d in real_diagnostics if d["skip_reason"] is not None)
    print(f"=== Window diagnostic: why {n_skipped}/{len(real_diagnostics)} windows were skipped ===")
    for d in real_diagnostics:
        if d["skip_reason"]:
            print(f"  {pd.Timestamp(d['trading_start']).date()} | eligible={d['n_eligible']:>4} | {d['skip_reason']}")
    if n_skipped == 0:
        print("  (none)")
    print()

    print(f"=== Negative control: {args.n_permutation_nulls} random-split null repeats ===")
    null_sharpes = []
    for _ in range(args.n_permutation_nulls):
        null_returns, _ = run_walk_forward(panel, windows, args.min_price, args.cost_bps, N_QUINTILES, rng=rng)
        null_sharpes.append(annualized_sharpe(np.array(null_returns), windows_per_year))
    null_sharpes_arr = np.array(null_sharpes)
    beat_or_tied = int((null_sharpes_arr >= real_sharpe).sum())
    permutation_p_value = (1 + beat_or_tied) / (1 + args.n_permutation_nulls)

    print(f"Random-split null Sharpe: mean={null_sharpes_arr.mean():+.2f} p95={np.percentile(null_sharpes_arr, 95):+.2f}")
    print(f"Real (vol-sorted) Sharpe: {real_sharpe:+.2f}")
    print(f"Permutation p-value (fraction of random-split nulls >= real): {permutation_p_value:.4f}")
    print(
        "  -- if real doesn't clear this by a wide margin, the apparent edge is generic "
        "long-short construction, not a genuine volatility-sorted effect.\n"
    )

    print(f"=== Monte Carlo: bootstrap of real strategy's own window returns, {args.n_bootstrap} resamples ===")
    if len(real_returns_arr) >= 2:
        bootstrap = bootstrap_sharpe_distribution(real_returns_arr, windows_per_year, args.n_bootstrap, rng)
        print(
            f"Sharpe 90% CI: [{bootstrap['p5']:+.2f}, {bootstrap['p95']:+.2f}]  "
            f"median={bootstrap['p50']:+.2f}  P(Sharpe<=0)={bootstrap['prob_sharpe_le_zero']:.3f}"
        )
    else:
        bootstrap = {"insufficient_windows": True}
        print("Fewer than 2 windows produced a return -- cannot bootstrap.")

    verdict = "FAIL"
    if len(real_returns) > 0 and permutation_p_value <= 0.05 and real_sharpe > 0 and bootstrap.get("prob_sharpe_le_zero", 1.0) < 0.25:
        verdict = "CLEARS OWN NEGATIVE CONTROL -- worth a closer look, not yet a green light"
    print(f"\nVerdict: {verdict}")
    print(
        "Mechanical verdict (p<=0.05 vs. random-split null, positive real Sharpe, "
        "P(Sharpe<=0)<25% under bootstrap). Clearing it means the volatility sort itself carries "
        "real signal on this universe/period -- not that it's sized, costed for borrow, or "
        "survives sector-concentration risk. Those are separate, later questions."
    )

    summary = {
        "n_windows": len(windows), "n_windows_with_return": len(real_returns),
        "real_sharpe": real_sharpe, "real_window_returns": real_returns,
        "real_window_diagnostics": real_diagnostics, "null_sharpes": null_sharpes,
        "permutation_p_value": permutation_p_value, "bootstrap": bootstrap,
        "verdict": verdict, "args": vars(args),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote results to {output_dir}/")


if __name__ == "__main__":
    main()
