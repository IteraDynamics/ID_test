"""Layer 3 — Bayesian optimisation of MeanReversionStrategy via Optuna.

Searches the RSI / Bollinger parameter space and maximises a composite
fitness score:

    Fitness = CAGR - |MaxDrawdown| × 0.5 - TotalTrades × 0.001

Death-penalty guards enforce a participation window of 3–25 trades/year:
    n_trades <  60 → -999.0  (under-trading / "do nothing" rejected)
    n_trades > 500 → -999.0  (over-trading / non-sniper rejected)

Usage
-----
# Use synthetic QQQ-stub data (default)
python -m research.experiments.optuna_sniper_v1

# Supply real QQQ daily CSV
python -m research.experiments.optuna_sniper_v1 --data data/QQQ_1D.csv

# Custom trial count and seed
python -m research.experiments.optuna_sniper_v1 --n-trials 100 --seed 0

Architecture notes
------------------
- Layer 2 responsibility stays in research/strategies/mean_reversion.py.
  The indicator helpers (_rsi, _bollinger, _atr) are imported and reused here
  rather than duplicated, keeping the maths single-source-of-truth.
- This script is Layer 3: it only orchestrates the search and calls the
  harness — it never embeds trading logic directly.
- Per trial, a lightweight SimpleNamespace module is constructed so the
  harness API (run_backtest takes any object with generate_intent) is
  satisfied without mutating the shared strategy module.
"""

from __future__ import annotations

import argparse
import logging
import sys
import types
from pathlib import Path

import numpy as np
import optuna
import pandas as pd

# ── Layer 2: strategy indicators (no logic copied — imported directly) ─────────
import research.strategies.mean_reversion as _mr

# ── Layer 3: harness ───────────────────────────────────────────────────────────
from research.harness.backtest_engine import run_backtest
from research.harness.data_loader import load_ohlcv
from research.harness.metrics import compute_metrics
from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyContext, StrategyIntent

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.WARNING)
optuna.logging.set_verbosity(optuna.logging.WARNING)

# ── Fixed constants shared across all trials ───────────────────────────────────
ATR_PERIOD = 14
MAX_ATR_PCT = 0.025
MIN_EXPOSURE = 0.25
MAX_EXPOSURE = 0.45
HORIZON_HOURS = 12
STRATEGY_BASE_ID = "mean_reversion_optuna_v1"

# Overtrading penalty weight (per round-trip trade)
TRADE_PENALTY = 0.001


# ── Parameterised strategy factory ─────────────────────────────────────────────

def _build_strategy_module(
    rsi_period: int,
    rsi_threshold: float,
    bb_period: int,
    bb_std: float,
) -> types.SimpleNamespace:
    """Return a module-like object satisfying the run_backtest strategy contract.

    The returned object exposes generate_intent(df, ctx, closed_only) using the
    supplied parameter values.  Indicator maths are delegated back to the
    mean_reversion module helpers so there is no logic duplication.
    """
    strategy_id = (
        f"{STRATEGY_BASE_ID}__rsi{rsi_period}"
        f"_th{rsi_threshold:.1f}"
        f"_bb{bb_period}"
        f"_std{bb_std:.2f}"
    )
    # Exit RSI is set symmetrically above entry threshold (same gap as default)
    exit_rsi = rsi_threshold + 20.0

    def generate_intent(
        df: pd.DataFrame,
        ctx: StrategyContext,
        closed_only: bool = True,
    ) -> StrategyIntent:
        min_bars = max(rsi_period, bb_period, ATR_PERIOD) + 10
        if len(df) < min_bars:
            return _mr._warmup_intent(ctx)

        close = df["close"]
        high = df["high"]
        low = df["low"]

        rsi_series = _mr._rsi(close, rsi_period)
        bb_mid, bb_upper, bb_lower = _mr._bollinger(close, bb_period, bb_std)
        atr = _mr._atr(high, low, close, ATR_PERIOD)
        atr_pct = atr / close

        c = float(close.iloc[-1])
        rsi = float(rsi_series.iloc[-1])
        mid = float(bb_mid.iloc[-1])
        upper = float(bb_upper.iloc[-1])
        lower = float(bb_lower.iloc[-1])
        atr_pct_now = float(atr_pct.iloc[-1])

        band_range = upper - lower
        bb_pos = ((c - lower) / band_range) if band_range > 1e-10 else 0.5

        meta = {
            "rsi": round(rsi, 2),
            "bb_pos": round(bb_pos, 4),
            "bb_mid": round(mid, 4),
            "atr_pct": round(atr_pct_now, 5),
            "regime": ctx.regime.value,
            "params": {
                "rsi_period": rsi_period,
                "rsi_threshold": rsi_threshold,
                "bb_period": bb_period,
                "bb_std": bb_std,
            },
        }

        # ── Regime exit ───────────────────────────────────────────────
        regime_override = ctx.regime in (
            RegimeLabel.TREND_DOWN,
            RegimeLabel.HIGH_VOL,
            RegimeLabel.VOL_EXPANSION,
            RegimeLabel.TREND_UP,
        )
        if regime_override and ctx.current_exposure_frac > 0:
            return StrategyIntent(
                action=Action.EXIT_LONG,
                confidence=0.85,
                desired_exposure_frac=0.0,
                horizon_hours=2,
                reason=f"Regime {ctx.regime.value} incompatible with mean-reversion — exit",
                meta=meta,
                strategy_id=strategy_id,
            )

        # ── Exit: RSI normalised or price above midline ───────────────
        if ctx.current_exposure_frac > 0:
            if rsi >= exit_rsi or c >= mid:
                return StrategyIntent(
                    action=Action.EXIT_LONG,
                    confidence=0.75,
                    desired_exposure_frac=0.0,
                    horizon_hours=2,
                    reason=f"Mean restored: RSI={rsi:.1f}, price vs mid={c:.2f}/{mid:.2f}",
                    meta=meta,
                    strategy_id=strategy_id,
                )

        # ── Entry ─────────────────────────────────────────────────────
        reversion_regime = ctx.regime in (
            RegimeLabel.RANGE,
            RegimeLabel.VOL_COMPRESSION,
        )
        if (
            reversion_regime
            and rsi < rsi_threshold
            and bb_pos < 0.25
            and atr_pct_now < MAX_ATR_PCT
        ):
            oversold_depth = max(0.0, (rsi_threshold - rsi) / rsi_threshold)
            band_depth = max(0.0, 0.25 - bb_pos) * 4

            exposure = MIN_EXPOSURE + (oversold_depth * 0.5 + band_depth * 0.5) * (
                MAX_EXPOSURE - MIN_EXPOSURE
            )
            exposure = round(min(exposure, MAX_EXPOSURE), 4)
            confidence = round(0.50 + oversold_depth * 0.35, 4)

            return StrategyIntent(
                action=Action.ENTER_LONG,
                confidence=confidence,
                desired_exposure_frac=exposure,
                horizon_hours=HORIZON_HOURS,
                reason=(
                    f"Mean-reversion entry: RSI={rsi:.1f} oversold, "
                    f"bb_pos={bb_pos:.3f}, regime={ctx.regime.value}"
                ),
                meta={**meta, "oversold_depth": round(oversold_depth, 4), "band_depth": round(band_depth, 4)},
                strategy_id=strategy_id,
            )

        # ── Hold ──────────────────────────────────────────────────────
        if ctx.current_exposure_frac > 0:
            return StrategyIntent(
                action=Action.HOLD,
                confidence=0.55,
                desired_exposure_frac=ctx.current_exposure_frac,
                horizon_hours=HORIZON_HOURS,
                reason="Holding mean-reversion position — awaiting normalisation",
                meta=meta,
                strategy_id=strategy_id,
            )

        # ── Flat ──────────────────────────────────────────────────────
        return StrategyIntent(
            action=Action.FLAT,
            confidence=0.50,
            desired_exposure_frac=0.0,
            horizon_hours=0,
            reason="No oversold condition in ranging regime — flat",
            meta=meta,
            strategy_id=strategy_id,
        )

    mod = types.SimpleNamespace()
    mod.generate_intent = generate_intent
    mod.STRATEGY_ID = strategy_id
    mod.__name__ = strategy_id
    return mod


# ── Synthetic QQQ-like daily data stub ────────────────────────────────────────

def _make_qqq_stub(n_bars: int = 1500, seed: int = 42) -> pd.DataFrame:
    """Synthetic QQQ-like daily OHLCV data for use when no real data is provided.

    Parameters reflect equity-index characteristics: lower volatility than
    crypto, mild upward drift, occasional range-bound consolidation periods.
    """
    rng = np.random.default_rng(seed)
    dt = 1 / 252  # one trading day as fraction of year
    mu = 0.10     # ~10% annual drift (QQQ long-run approx)
    sigma = 0.18  # ~18% annual vol (QQQ approx)
    initial_price = 350.0

    log_returns = (
        (mu - 0.5 * sigma ** 2) * dt
        + sigma * np.sqrt(dt) * rng.standard_normal(n_bars)
    )
    closes = initial_price * np.exp(np.cumsum(log_returns))

    spread = closes * rng.uniform(0.002, 0.012, size=n_bars)
    highs = closes + spread * rng.uniform(0.3, 1.0, size=n_bars)
    lows = closes - spread * rng.uniform(0.3, 1.0, size=n_bars)
    opens = closes * (1 + rng.uniform(-0.005, 0.005, size=n_bars))
    volume = rng.uniform(50_000_000, 150_000_000, size=n_bars)

    idx = pd.date_range(start="2019-01-01", periods=n_bars, freq="B")
    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volume},
        index=idx,
    )
    df.index.name = "timestamp"
    df.attrs["asset"] = "QQQ"
    return df


# ── Fitness calculation ────────────────────────────────────────────────────────

def _fitness(cagr_pct: float, max_dd_pct: float, n_trades: int) -> float:
    """Composite fitness targeting absolute return while gating risk.

    Fitness = CAGR - |MaxDrawdown| × 0.5 - TotalTrades × TRADE_PENALTY

    All terms are in percentage-point units so the formula rewards raw
    CAGR, penalises drawdown at half-weight, and applies a per-trade
    friction cost to discourage high-churn parameter sets.
    """
    return cagr_pct - abs(max_dd_pct) * 0.5 - n_trades * TRADE_PENALTY


# ── Optuna objective ───────────────────────────────────────────────────────────

def _make_objective(df: pd.DataFrame):
    """Close over df so the objective has access to the dataset."""

    def objective(trial: optuna.Trial) -> float:
        rsi_period = trial.suggest_int("rsi_period", 5, 21)
        rsi_threshold = trial.suggest_float("rsi_threshold", 20.0, 40.0)
        bb_period = trial.suggest_int("bb_period", 10, 30)
        bb_std = trial.suggest_float("bb_std", 1.5, 3.0)

        strategy_mod = _build_strategy_module(
            rsi_period=rsi_period,
            rsi_threshold=rsi_threshold,
            bb_period=bb_period,
            bb_std=bb_std,
        )

        try:
            result = run_backtest(
                df=df,
                strategy_module=strategy_mod,
                asset=df.attrs.get("asset", "QQQ"),
                initial_capital=100_000.0,
            )
        except Exception as exc:
            # Penalise trials that crash (e.g. insufficient data for wide BB periods)
            trial.set_user_attr("error", str(exc))
            return -1000.0

        metrics = compute_metrics(
            equity_curve=result.equity_curve,
            trades=result.trades,
            params=result.params,
        )

        # ── Participation guards (death penalty) ──────────────────────
        # 21 years of daily data → valid sniper range is 3–25 trades/yr.
        if metrics.n_trades < 60:    # < 3 trades/yr: "do nothing" system
            trial.set_user_attr("n_trades", metrics.n_trades)
            trial.set_user_attr("rejection", "under_trading")
            return -999.0
        if metrics.n_trades > 500:   # > 25 trades/yr: not a sniper
            trial.set_user_attr("n_trades", metrics.n_trades)
            trial.set_user_attr("rejection", "over_trading")
            return -999.0

        score = _fitness(
            cagr_pct=metrics.cagr_pct,
            max_dd_pct=metrics.max_drawdown_pct,
            n_trades=metrics.n_trades,
        )

        # Store diagnostics for post-hoc inspection
        trial.set_user_attr("cagr_pct", round(metrics.cagr_pct, 4))
        trial.set_user_attr("max_drawdown_pct", round(metrics.max_drawdown_pct, 4))
        trial.set_user_attr("n_trades", metrics.n_trades)
        trial.set_user_attr("calmar", round(metrics.calmar, 4))
        trial.set_user_attr("sharpe", round(metrics.sharpe, 4))
        trial.set_user_attr("total_return_pct", round(metrics.total_return_pct, 4))

        return score

    return objective


# ── CLI entry point ────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Bayesian optimisation of MeanReversionStrategy (Optuna)."
    )
    parser.add_argument(
        "--data",
        type=str,
        default=None,
        help="Path to QQQ daily OHLCV CSV. Falls back to synthetic stub if omitted.",
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=50,
        help="Number of Optuna trials (default: 50).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    parser.add_argument(
        "--asset",
        type=str,
        default="QQQ",
        help="Asset label used in backtest context (default: QQQ).",
    )
    args = parser.parse_args(argv)

    # ── Load data ─────────────────────────────────────────────────────
    if args.data:
        data_path = Path(args.data)
        if not data_path.exists():
            print(f"[ERROR] Data file not found: {data_path}", file=sys.stderr)
            sys.exit(1)
        print(f"Loading OHLCV data from {data_path} ...")
        df = load_ohlcv(str(data_path), asset=args.asset)
        print(f"  {len(df)} bars  |  {df.index[0].date()} → {df.index[-1].date()}")
    else:
        print("No --data supplied. Using synthetic QQQ-stub data (n=1500 daily bars).")
        df = _make_qqq_stub(n_bars=1500, seed=args.seed)
        print(f"  {len(df)} bars  |  {df.index[0].date()} → {df.index[-1].date()}")

    # ── Create and run study ──────────────────────────────────────────
    sampler = optuna.samplers.TPESampler(seed=args.seed)
    study = optuna.create_study(
        direction="maximize",
        sampler=sampler,
        study_name="mean_reversion_sniper_v1",
    )

    print(f"\nRunning Optuna study: {args.n_trials} trials  (direction=maximize)\n")
    study.optimize(
        _make_objective(df),
        n_trials=args.n_trials,
        show_progress_bar=True,
    )

    # ── Report results ────────────────────────────────────────────────
    best = study.best_trial
    print("\n" + "=" * 60)
    print("OPTIMISATION COMPLETE")
    print("=" * 60)
    print(f"\nBest trial:  #{best.number}")
    print(f"  Fitness score : {best.value:.4f}")
    print("\nBest parameters:")
    for k, v in best.params.items():
        print(f"  {k:<20} {v}")
    print("\nDiagnostics:")
    attrs_to_show = [
        "cagr_pct",
        "max_drawdown_pct",
        "n_trades",
        "calmar",
        "sharpe",
        "total_return_pct",
    ]
    for attr in attrs_to_show:
        val = best.user_attrs.get(attr, "N/A")
        print(f"  {attr:<25} {val}")

    # ── Top-5 summary ─────────────────────────────────────────────────
    print("\nTop 5 trials by fitness:")
    print(f"  {'#':<6} {'Fitness':>10}  {'CAGR%':>8}  {'MaxDD%':>8}  {'Trades':>7}  Parameters")
    sorted_trials = sorted(study.trials, key=lambda t: t.value or float("-inf"), reverse=True)
    for t in sorted_trials[:5]:
        if t.value is None:
            continue
        cagr = t.user_attrs.get("cagr_pct", "?")
        mdd = t.user_attrs.get("max_drawdown_pct", "?")
        ntrades = t.user_attrs.get("n_trades", "?")
        param_str = "  ".join(f"{k}={v}" for k, v in t.params.items())
        print(f"  {t.number:<6} {t.value:>10.4f}  {cagr:>8}  {mdd:>8}  {ntrades:>7}  {param_str}")

    print()


if __name__ == "__main__":
    main()
