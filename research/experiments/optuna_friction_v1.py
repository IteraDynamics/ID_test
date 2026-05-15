"""Layer 3 — Bayesian optimisation of the PortfolioAllocator rebalance_threshold.

"Friction Shield" experiment: finds the optimal cross-asset rebalance trigger
by maximising the fund's RoMaD across a configurable number of Optuna trials.

Search space
------------
    rebalance_threshold ∈ [0.02, 0.15]

Fitness
-------
    Fitness = total_return_pct / |max_portfolio_drawdown_pct|   (RoMaD)

    Frictional cost is already embedded in NAV by the broker simulator, so the
    GP naturally penalises both extremes:
      · Low threshold (≈ 0.02): frequent small transfers bleed NAV to fees
      · High threshold (≈ 0.15): wild beta drift deepens max drawdown

Architecture
------------
Layer 2 — Strategy signals
    · Crypto sleeve : trend_following_v8_ecap75  (BTC 1H + ETH 1H, blended 50/50)
    · Equity sleeve : trend_following            (SPY 1D + QQQ 1D, blended 50/50)
    All four sleeve backtests run ONCE before the study. Hourly BTC/ETH equity
    curves are resampled to daily end-of-day NAV before blending. Equity curves
    are fixed across all trials; only the allocation simulation changes.

Layer 3 — Fund-level allocation (per-trial, O(n))
    1. Pre-compute per-bar target weights via vectorised EWM trend scores
       (causal; identical to itera_allocator_v1._trend_score logic).
    2. Apply sequential threshold gating with the trial's threshold value.
    3. When weights change, execute a cross-asset transfer:
         · Crypto leg  : compute_fill() with standard ExecutionConfig
                         (dynamic slippage from ATR + trade size)
         · Equity leg  : fixed 2 bps all-in (commission + slippage)
    4. Deduct friction from fund NAV; track frictional cost separately.

Note on proportional HWM (runtime/argus/state/runtime_state.py)
----------------------------------------------------------------
RuntimeState.update_from_broker applies a proportional HWM reduction on
capital outflows so the live drawdown governor does not mis-trigger after
a sleeve reduction.  In this research simulation, HWM is tracked implicitly
via the equity curve's cummax (standard drawdown computation), which is
mathematically equivalent. RuntimeState is not imported here — it is a
Layer 3 live-runtime concern only.

Usage
-----
# Auto-detect data files at their default paths (recommended)
python -m research.experiments.optuna_friction_v1

# Explicit paths
python -m research.experiments.optuna_friction_v1 \\
    --btc-data data/btcusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --eth-data data/ethusd_3600s_2019-01-01_to_2025-12-30.csv \\
    --spy-data data/SPY_1D.csv \\
    --qqq-data data/QQQ_1D.csv

# Custom trial count
python -m research.experiments.optuna_friction_v1 --n-trials 100
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import optuna
import pandas as pd

# ── Layer 2: allocator (scoring logic imported, not duplicated) ────────────────
from research.allocators.itera_allocator_v1 import AllocatorConfig

# ── Layer 3: harness ───────────────────────────────────────────────────────────
from research.harness.backtest_engine import run_backtest
from research.harness.data_loader import load_ohlcv
from research.harness.execution_model import (
    ExecutionConfig,
    compute_atr_pct_series,
    compute_fill,
)
from research.harness.resampler import resample_ohlcv
from research.strategies import REGISTRY as STRATEGY_REGISTRY

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.WARNING)
optuna.logging.set_verbosity(optuna.logging.WARNING)

# ── Constants ──────────────────────────────────────────────────────────────────
CRYPTO_STRATEGY_KEY = "trend_following_v8_ecap75"
EQUITY_STRATEGY_KEY = "trend_following"
INITIAL_CAPITAL = 100_000.0
INITIAL_CRYPTO_WEIGHT = 0.70
EQUITY_COST_BPS = 2.0   # fixed all-in cost for equity leg of each transfer


# ── Data stubs ─────────────────────────────────────────────────────────────────

def _make_btc_stub(n_bars: int = 1500, seed: int = 42) -> pd.DataFrame:
    """Synthetic BTC-like daily OHLCV.  High vol, upward drift, crypto-scale."""
    rng = np.random.default_rng(seed)
    dt = 1 / 252
    mu, sigma = 0.40, 0.80
    closes = 20_000.0 * np.exp(
        np.cumsum((mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(n_bars))
    )
    spread = closes * rng.uniform(0.005, 0.020, size=n_bars)
    df = pd.DataFrame(
        {
            "open":   closes * (1 + rng.uniform(-0.010, 0.010, size=n_bars)),
            "high":   closes + spread * rng.uniform(0.3, 1.0, size=n_bars),
            "low":    closes - spread * rng.uniform(0.3, 1.0, size=n_bars),
            "close":  closes,
            "volume": rng.uniform(1e9, 5e9, size=n_bars),
        },
        index=pd.date_range("2019-01-01", periods=n_bars, freq="B"),
    )
    df.index.name = "timestamp"
    df.attrs["asset"] = "BTC"
    return df


def _make_qqq_stub(n_bars: int = 1500, seed: int = 43) -> pd.DataFrame:
    """Synthetic QQQ-like daily OHLCV.  Equity-index characteristics."""
    rng = np.random.default_rng(seed)
    dt = 1 / 252
    mu, sigma = 0.10, 0.18
    closes = 350.0 * np.exp(
        np.cumsum((mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(n_bars))
    )
    spread = closes * rng.uniform(0.002, 0.008, size=n_bars)
    df = pd.DataFrame(
        {
            "open":   closes * (1 + rng.uniform(-0.003, 0.003, size=n_bars)),
            "high":   closes + spread * rng.uniform(0.3, 1.0, size=n_bars),
            "low":    closes - spread * rng.uniform(0.3, 1.0, size=n_bars),
            "close":  closes,
            "volume": rng.uniform(5e7, 1.5e8, size=n_bars),
        },
        index=pd.date_range("2019-01-01", periods=n_bars, freq="B"),
    )
    df.index.name = "timestamp"
    df.attrs["asset"] = "QQQ"
    return df


def _make_eth_stub(n_bars: int = 36_000, seed: int = 44) -> pd.DataFrame:
    """Synthetic ETH-like hourly OHLCV (higher vol than BTC, same drift)."""
    rng = np.random.default_rng(seed)
    dt = 1 / (365 * 24)
    mu, sigma = 0.45, 0.95
    closes = 150.0 * np.exp(
        np.cumsum((mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(n_bars))
    )
    spread = closes * rng.uniform(0.005, 0.025, size=n_bars)
    df = pd.DataFrame(
        {
            "open":   closes * (1 + rng.uniform(-0.010, 0.010, size=n_bars)),
            "high":   closes + spread * rng.uniform(0.3, 1.0, size=n_bars),
            "low":    closes - spread * rng.uniform(0.3, 1.0, size=n_bars),
            "close":  closes,
            "volume": rng.uniform(5e8, 3e9, size=n_bars),
        },
        index=pd.date_range("2019-01-01", periods=n_bars, freq="h"),
    )
    df.index.name = "timestamp"
    df.attrs["asset"] = "ETH"
    return df


def _make_spy_stub(n_bars: int = 1500, seed: int = 45) -> pd.DataFrame:
    """Synthetic SPY-like daily OHLCV (lower vol, dividend-adjusted drift)."""
    rng = np.random.default_rng(seed)
    dt = 1 / 252
    mu, sigma = 0.09, 0.15
    closes = 280.0 * np.exp(
        np.cumsum((mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(n_bars))
    )
    spread = closes * rng.uniform(0.001, 0.006, size=n_bars)
    df = pd.DataFrame(
        {
            "open":   closes * (1 + rng.uniform(-0.003, 0.003, size=n_bars)),
            "high":   closes + spread * rng.uniform(0.3, 1.0, size=n_bars),
            "low":    closes - spread * rng.uniform(0.3, 1.0, size=n_bars),
            "close":  closes,
            "volume": rng.uniform(6e7, 2e8, size=n_bars),
        },
        index=pd.date_range("2019-01-01", periods=n_bars, freq="B"),
    )
    df.index.name = "timestamp"
    df.attrs["asset"] = "SPY"
    return df


# ── Sleeve blending ────────────────────────────────────────────────────────────

def _blend_sleeve_navs(
    nav_a: pd.Series,
    nav_b: pd.Series,
    weight_a: float = 0.5,
) -> pd.Series:
    """Combine two NAV curves into a single sleeve NAV by return-averaging.

    Both curves are normalised to 1.0 at the start of the common period so
    that capital-weighting is symmetric regardless of their absolute levels.
    The returned series starts at 1.0 and represents blended daily returns.
    """
    common_idx = nav_a.index.intersection(nav_b.index)
    a = nav_a.reindex(common_idx).ffill()
    b = nav_b.reindex(common_idx).ffill()

    ret_a = (a / float(a.iloc[0])).pct_change().fillna(0.0)
    ret_b = (b / float(b.iloc[0])).pct_change().fillna(0.0)

    blended = weight_a * ret_a + (1.0 - weight_a) * ret_b
    nav = (1.0 + blended).cumprod()
    nav.name = "blended_nav"
    return nav


# ── Vectorised allocator signal (replicated from itera_allocator_v1) ───────────

def _score_series(
    curve: pd.Series,
    fast_days: int,
    slow_days: int,
    momentum_days: int,
) -> pd.Series:
    """Causal EWM trend score ∈ [-1, +1] for every bar.

    Vectorised replica of itera_allocator_v1._trend_score so the full
    series can be computed in one pass (O(n)) rather than O(n²) in the
    trial loop.  EWM is a recursive causal filter — applying it to the
    full series is identical to computing it bar-by-bar.
    """
    s = curve.ffill().astype(float)
    ewm_fast = s.ewm(span=fast_days, adjust=False).mean()
    ewm_slow = s.ewm(span=slow_days, adjust=False).mean()
    mom = s.pct_change(momentum_days)

    fast_comp = np.where(ewm_fast > ewm_slow,  0.5, -0.5)
    slow_comp = np.where(s > ewm_slow,          0.3, -0.3)
    mom_comp  = np.where(mom > 0,               0.2, -0.2)

    score = pd.Series(
        np.clip(fast_comp + slow_comp + mom_comp, -1.0, 1.0),
        index=s.index,
        dtype=float,
    )

    # Zero out warmup period — same guard as the scalar version
    warmup = max(slow_days, momentum_days) + 5
    score.iloc[:warmup] = 0.0
    return score


def _compute_raw_target_weights(
    crypto_nav: pd.Series,
    equity_nav: pd.Series,
) -> pd.Series:
    """Per-bar target crypto weight BEFORE threshold gating.

    Vectorised equivalent of itera_allocator_v1.decide_weights() with the
    threshold check removed.  Possible output values: 0.50, 0.70, 0.80.
    Precomputed once per study; re-used across all 50 trials.
    """
    cfg = AllocatorConfig()   # scoring params only; threshold not used here

    c_score = _score_series(crypto_nav, cfg.fast_ma_days, cfg.slow_ma_days, cfg.momentum_days)
    e_score = _score_series(equity_nav, cfg.fast_ma_days, cfg.slow_ma_days, cfg.momentum_days)
    spread = c_score - e_score

    target = np.select(
        [
            spread >= 0.75,
            (spread <= -0.75) | ((c_score < 0) & (e_score < 0)),
        ],
        [cfg.max_crypto_weight, cfg.min_crypto_weight],
        default=cfg.base_crypto_weight,
    )
    return pd.Series(target, index=crypto_nav.index, dtype=float)


# ── Fund-level simulation ──────────────────────────────────────────────────────

def _simulate_fund(
    crypto_daily_ret: pd.Series,
    equity_daily_ret: pd.Series,
    btc_close: pd.Series,
    btc_atr_pct: pd.Series,
    raw_target_weights: pd.Series,
    rebalance_threshold: float,
    initial_capital: float,
    exec_config: ExecutionConfig,
) -> tuple[pd.Series, float, int]:
    """Run a single fund-level allocation simulation for one trial.

    Parameters
    ----------
    crypto_daily_ret / equity_daily_ret
        Daily pct-change of each sleeve's NAV (post-strategy-friction).
    btc_close / btc_atr_pct
        BTC close prices and ATR% at each bar — used for ExecutionConfig
        in the crypto leg of every cross-asset transfer.
    raw_target_weights
        Pre-computed per-bar target crypto weights (before gating).
    rebalance_threshold
        The trial parameter: minimum weight delta to execute a transfer.
    exec_config
        Standard ExecutionConfig (identical to strategy backtests).

    Returns
    -------
    (fund_nav_series, total_frictional_cost_usd, n_rebalances)
    """
    n = len(crypto_daily_ret)
    index = crypto_daily_ret.index

    current_w = INITIAL_CRYPTO_WEIGHT
    crypto_nav = initial_capital * current_w
    equity_nav = initial_capital * (1.0 - current_w)

    fund_navs = np.empty(n, dtype=float)
    total_friction = 0.0
    n_rebalances = 0

    for i in range(n):
        # ── Grow sleeves by today's strategy returns ──────────────────
        crypto_nav *= 1.0 + float(crypto_daily_ret.iloc[i])
        equity_nav *= 1.0 + float(equity_daily_ret.iloc[i])
        fund_nav = crypto_nav + equity_nav

        if fund_nav <= 0.0:
            fund_navs[i:] = 0.0
            break

        # ── Threshold gating (sequential — can't be vectorised) ───────
        raw_w = float(raw_target_weights.iloc[i])
        new_w = raw_w if abs(raw_w - current_w) >= rebalance_threshold else current_w

        # ── Execute cross-asset transfer ──────────────────────────────
        if new_w != current_w:
            target_crypto_nav = fund_nav * new_w
            transfer_notional = abs(target_crypto_nav - crypto_nav)

            if transfer_notional > 1.0:   # skip dust transfers
                direction = "SELL" if new_w < current_w else "BUY"

                # Crypto leg: full ExecutionConfig (dynamic ATR-scaled slippage)
                fill = compute_fill(
                    mid_price=float(btc_close.iloc[i]),
                    notional=transfer_notional,
                    nav=fund_nav,
                    atr_pct=float(btc_atr_pct.iloc[i]),
                    direction=direction,
                    config=exec_config,
                )
                crypto_friction = fill.fee_usd + fill.slippage_usd + fill.spread_usd

                # Equity leg: fixed 2 bps all-in (commission + slippage)
                equity_friction = transfer_notional * EQUITY_COST_BPS / 10_000.0

                friction = crypto_friction + equity_friction
                fund_nav -= friction
                total_friction += friction
                n_rebalances += 1

                # Proportional rebalance — respects HWM accounting:
                # reducing a sleeve's capital proportionally mirrors the
                # runtime_state.py HWM reduction on capital outflows.
                crypto_nav = fund_nav * new_w
                equity_nav = fund_nav * (1.0 - new_w)
                current_w = new_w

        fund_navs[i] = fund_nav

    return (
        pd.Series(fund_navs, index=index, name="fund_nav"),
        total_friction,
        n_rebalances,
    )


# ── Metrics ────────────────────────────────────────────────────────────────────

def _compute_fund_metrics(
    nav: pd.Series,
    initial_capital: float,
) -> tuple[float, float, float]:
    """Return (total_return_pct, max_drawdown_pct, romad).

    max_drawdown_pct is a negative number (e.g. -15.3 means 15.3% peak-to-trough).
    romad is total_return / |max_drawdown|; 0.0 if drawdown is negligible.
    """
    eq = nav[nav > 0].dropna()
    if len(eq) < 2:
        return 0.0, 0.0, 0.0

    total_ret = (float(eq.iloc[-1]) / initial_capital - 1.0) * 100.0
    running_max = eq.cummax()
    max_dd = float(((eq - running_max) / running_max).min()) * 100.0

    romad = total_ret / abs(max_dd) if abs(max_dd) >= 0.01 else 0.0
    return total_ret, max_dd, romad


# ── Optuna objective ───────────────────────────────────────────────────────────

def _make_objective(
    crypto_daily_ret: pd.Series,
    equity_daily_ret: pd.Series,
    btc_close: pd.Series,
    btc_atr_pct: pd.Series,
    raw_target_weights: pd.Series,
    exec_config: ExecutionConfig,
    initial_capital: float,
):
    """Return a closure over the precomputed data for use by Optuna."""

    def objective(trial: optuna.Trial) -> float:
        threshold = trial.suggest_float("rebalance_threshold", 0.02, 0.15)

        nav_series, total_friction, n_rebalances = _simulate_fund(
            crypto_daily_ret=crypto_daily_ret,
            equity_daily_ret=equity_daily_ret,
            btc_close=btc_close,
            btc_atr_pct=btc_atr_pct,
            raw_target_weights=raw_target_weights,
            rebalance_threshold=threshold,
            initial_capital=initial_capital,
            exec_config=exec_config,
        )

        total_ret, max_dd, romad = _compute_fund_metrics(nav_series, initial_capital)

        # Frictional cost as % of initial NAV (for reporting)
        friction_pct = total_friction / initial_capital * 100.0

        trial.set_user_attr("total_return_pct",          round(total_ret, 4))
        trial.set_user_attr("max_drawdown_pct",          round(max_dd, 4))
        trial.set_user_attr("romad",                     round(romad, 4))
        trial.set_user_attr("n_rebalances",              n_rebalances)
        trial.set_user_attr("total_frictional_cost_usd", round(total_friction, 2))
        trial.set_user_attr("frictional_cost_pct_nav",   round(friction_pct, 4))

        return romad

    return objective


# ── CLI entry point ────────────────────────────────────────────────────────────

def _load_data(path_arg: str | None, stub_fn, asset: str, label: str) -> pd.DataFrame:
    """Load a dataset from path_arg if provided, else auto-detect default path or stub."""
    candidates = [Path(path_arg)] if path_arg else []
    candidates += [
        Path(f"data/btcusd_3600s_2019-01-01_to_2025-12-30.csv") if asset == "BTC" else None,
        Path(f"data/ethusd_3600s_2019-01-01_to_2025-12-30.csv") if asset == "ETH" else None,
        Path("data/SPY_1D.csv") if asset == "SPY" else None,
        Path("data/QQQ_1D.csv") if asset == "QQQ" else None,
    ]
    for p in candidates:
        if p is not None and p.exists():
            print(f"  {label}: loading from {p}")
            df = load_ohlcv(str(p), asset=asset)
            print(f"    {len(df)} bars  {df.index[0].date()} → {df.index[-1].date()}")
            return df
    print(f"  {label}: file not found — using synthetic stub")
    return stub_fn()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Friction Shield: Bayesian optimisation of cross-asset rebalance_threshold."
    )
    parser.add_argument(
        "--btc-data", type=str, default=None,
        help="BTC hourly CSV (default: data/btcusd_3600s_2019-01-01_to_2025-12-30.csv).",
    )
    parser.add_argument(
        "--eth-data", type=str, default=None,
        help="ETH hourly CSV (default: data/ethusd_3600s_2019-01-01_to_2025-12-30.csv).",
    )
    parser.add_argument(
        "--spy-data", type=str, default=None,
        help="SPY daily CSV (default: data/SPY_1D.csv).",
    )
    parser.add_argument(
        "--qqq-data", type=str, default=None,
        help="QQQ daily CSV (default: data/QQQ_1D.csv).",
    )
    parser.add_argument(
        "--n-trials", type=int, default=50,
        help="Number of Optuna trials (default: 50).",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42).",
    )
    args = parser.parse_args(argv)

    # ── Load all four datasets ────────────────────────────────────────
    print("Loading datasets...")
    btc_df = _load_data(args.btc_data, lambda: _make_btc_stub(seed=args.seed),       "BTC", "BTC 1H")
    eth_df = _load_data(args.eth_data, lambda: _make_eth_stub(seed=args.seed + 1),   "ETH", "ETH 1H")
    spy_df = _load_data(args.spy_data, lambda: _make_spy_stub(seed=args.seed + 2),   "SPY", "SPY 1D")
    qqq_df = _load_data(args.qqq_data, lambda: _make_qqq_stub(seed=args.seed + 3),   "QQQ", "QQQ 1D")

    # ── Run all four sleeve backtests (once, shared across all trials) ─
    print("\nRunning sleeve backtests (once, shared across all trials)...")
    exec_config = ExecutionConfig()

    crypto_capital = INITIAL_CAPITAL * INITIAL_CRYPTO_WEIGHT          # $70k
    equity_capital = INITIAL_CAPITAL * (1.0 - INITIAL_CRYPTO_WEIGHT)  # $30k

    btc_result = run_backtest(
        df=btc_df,
        strategy_module=STRATEGY_REGISTRY[CRYPTO_STRATEGY_KEY],
        asset="BTC",
        initial_capital=crypto_capital * 0.5,   # 50% of crypto sleeve
        exec_config=exec_config,
    )
    eth_result = run_backtest(
        df=eth_df,
        strategy_module=STRATEGY_REGISTRY[CRYPTO_STRATEGY_KEY],
        asset="ETH",
        initial_capital=crypto_capital * 0.5,   # 50% of crypto sleeve
        exec_config=exec_config,
    )
    spy_result = run_backtest(
        df=spy_df,
        strategy_module=STRATEGY_REGISTRY[EQUITY_STRATEGY_KEY],
        asset="SPY",
        initial_capital=equity_capital * 0.5,   # 50% of equity sleeve
        exec_config=exec_config,
    )
    qqq_result = run_backtest(
        df=qqq_df,
        strategy_module=STRATEGY_REGISTRY[EQUITY_STRATEGY_KEY],
        asset="QQQ",
        initial_capital=equity_capital * 0.5,   # 50% of equity sleeve
        exec_config=exec_config,
    )
    print(
        f"  BTC : {btc_result.n_trades:>4} trades  final ${btc_result.final_equity:>10,.0f}\n"
        f"  ETH : {eth_result.n_trades:>4} trades  final ${eth_result.final_equity:>10,.0f}\n"
        f"  SPY : {spy_result.n_trades:>4} trades  final ${spy_result.final_equity:>10,.0f}\n"
        f"  QQQ : {qqq_result.n_trades:>4} trades  final ${qqq_result.final_equity:>10,.0f}"
    )

    # ── Resample hourly crypto curves to daily end-of-day NAV ─────────
    # Equity curves from hourly backtests are indexed hourly; the allocator
    # and fund simulation work on daily bars.
    btc_eq_daily = btc_result.equity_curve.resample("D").last().dropna()
    eth_eq_daily = eth_result.equity_curve.resample("D").last().dropna()

    # SPY/QQQ equity curves are already daily
    spy_eq_daily = spy_result.equity_curve
    qqq_eq_daily = qqq_result.equity_curve

    # ── Blend each pair into a single sleeve NAV (normalised to 1.0) ──
    crypto_sleeve_nav = _blend_sleeve_navs(btc_eq_daily, eth_eq_daily, weight_a=0.5)
    equity_sleeve_nav = _blend_sleeve_navs(spy_eq_daily, qqq_eq_daily, weight_a=0.5)

    # ── Align both sleeve NAVs to a common daily index ────────────────
    common_index = crypto_sleeve_nav.index.intersection(equity_sleeve_nav.index)
    if len(common_index) < 250:
        print("[ERROR] Common data period too short for allocation study.", file=sys.stderr)
        sys.exit(1)

    crypto_nav = crypto_sleeve_nav.reindex(common_index).ffill()
    equity_nav = equity_sleeve_nav.reindex(common_index).ffill()

    crypto_daily_ret = crypto_nav.pct_change().fillna(0.0)
    equity_daily_ret = equity_nav.pct_change().fillna(0.0)

    # ── BTC daily price + ATR% for the rebalance cost model ───────────
    # Resample hourly BTC OHLCV to daily so compute_fill receives a
    # price and ATR that match the daily simulation timestep.
    btc_daily_ohlcv = resample_ohlcv(btc_df, "1D")
    btc_close   = btc_daily_ohlcv["close"].reindex(common_index, method="ffill")
    btc_atr_pct = compute_atr_pct_series(btc_daily_ohlcv).reindex(common_index, method="ffill")

    # ── Precompute raw target weights (vectorised, once per study) ────
    print("\nPrecomputing allocator target weights (vectorised)...")
    raw_target_weights = _compute_raw_target_weights(crypto_nav, equity_nav)
    unique_targets = sorted(raw_target_weights.unique())
    print(f"  Possible target weights: {unique_targets}")
    print(f"  Common simulation period: {len(common_index)} bars")

    # ── Create and run Optuna study ───────────────────────────────────
    sampler = optuna.samplers.TPESampler(seed=args.seed)
    study = optuna.create_study(
        direction="maximize",
        sampler=sampler,
        study_name="friction_shield_v1",
    )

    print(f"\nRunning Optuna study: {args.n_trials} trials  (direction=maximize)\n")
    study.optimize(
        _make_objective(
            crypto_daily_ret=crypto_daily_ret,
            equity_daily_ret=equity_daily_ret,
            btc_close=btc_close,
            btc_atr_pct=btc_atr_pct,
            raw_target_weights=raw_target_weights,
            exec_config=exec_config,
            initial_capital=INITIAL_CAPITAL,
        ),
        n_trials=args.n_trials,
        show_progress_bar=True,
    )

    # ── Report ────────────────────────────────────────────────────────
    best = study.best_trial
    print("\n" + "=" * 60)
    print("FRICTION SHIELD OPTIMISATION COMPLETE")
    print("=" * 60)
    print(f"\nBest trial:  #{best.number}")
    print(f"\nBest rebalance_threshold : {best.params['rebalance_threshold']:.4f}"
          f"  ({best.params['rebalance_threshold']:.1%})")
    print(f"\nDiagnostics:")
    labels = {
        "romad":                     "Fund RoMaD",
        "total_return_pct":          "Total Return (%)",
        "max_drawdown_pct":          "Max Drawdown (%)",
        "n_rebalances":              "Rebalance transfers",
        "total_frictional_cost_usd": "Total frictional cost (USD)",
        "frictional_cost_pct_nav":   "Frictional cost (% initial NAV)",
    }
    for attr, label in labels.items():
        val = best.user_attrs.get(attr, "N/A")
        print(f"  {label:<35} {val}")

    # ── Top-5 summary ─────────────────────────────────────────────────
    print("\nTop 5 trials by RoMaD:")
    print(
        f"  {'#':<6} {'Threshold':>10}  {'RoMaD':>8}  "
        f"{'TotRet%':>9}  {'MaxDD%':>8}  {'Rebalances':>11}  {'Friction$':>10}"
    )
    sorted_trials = sorted(
        study.trials,
        key=lambda t: t.value if t.value is not None else float("-inf"),
        reverse=True,
    )
    for t in sorted_trials[:5]:
        if t.value is None:
            continue
        th      = t.params.get("rebalance_threshold", "?")
        romad   = t.user_attrs.get("romad", "?")
        ret     = t.user_attrs.get("total_return_pct", "?")
        mdd     = t.user_attrs.get("max_drawdown_pct", "?")
        nreb    = t.user_attrs.get("n_rebalances", "?")
        friction= t.user_attrs.get("total_frictional_cost_usd", "?")
        th_str  = f"{th:.4f}" if isinstance(th, float) else str(th)
        fri_str = f"${friction:,.2f}" if isinstance(friction, float) else str(friction)
        print(
            f"  {t.number:<6} {th_str:>10}  {romad:>8}  "
            f"{ret:>9}  {mdd:>8}  {nreb:>11}  {fri_str:>10}"
        )

    print()


if __name__ == "__main__":
    main()
