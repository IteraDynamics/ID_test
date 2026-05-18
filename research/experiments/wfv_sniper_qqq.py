"""Walk-Forward Validation engine for MeanReversionSniper on QQQ.

Each fold:
  In-Sample  (3 yr) → Optuna study (n_trials=30) optimizing RoMaD → best params
  Out-of-Sample (1 yr) → run with those params under standard friction

All OOS equity curves are stitched into one continuous fiduciary curve;
aggregate CAGR, Max DD, and RoMaD are reported with a per-fold param table.

Usage
-----
# Real QQQ data:
python research/experiments/wfv_sniper_qqq.py --data data/QQQ_1D.csv

# Synthetic stub (no data required):
python research/experiments/wfv_sniper_qqq.py
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import optuna
from optuna.samplers import TPESampler

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import research.strategies.mean_reversion as _mr
from research.harness.backtest_engine import run_backtest
from research.harness.data_loader import load_ohlcv
from research.harness.execution_model import ExecutionConfig
from research.harness.metrics import compute_metrics

logging.basicConfig(level=logging.WARNING)
optuna.logging.set_verbosity(optuna.logging.WARNING)

# ── WFV hyper-parameters ────────────────────────────────────────────────────────
IN_SAMPLE_YEARS   = 3
OOS_YEARS         = 1
N_TRIALS          = 30
INITIAL_CAPITAL   = 100_000.0
TRADING_DAYS_YEAR = 252
ASSET             = "QQQ"
STRATEGY_BASE_ID  = "mr_sniper_wfv_qqq"

# Sniper participation bounds (per year), scaled to IS window
_MIN_TRADES_PER_YEAR = 2
_MAX_TRADES_PER_YEAR = 30
TRADE_PENALTY        = 0.001

# ── Fixed signal constants (not searched) ────────────────────────────────────
ATR_PERIOD   = 14
MAX_ATR_PCT  = 0.025
MIN_EXPOSURE = 0.25
MAX_EXPOSURE = 0.45
HORIZON_BARS = 1   # daily bars


# ── Parameterised strategy factory ─────────────────────────────────────────────

def _build_strategy(
    rsi_period: int,
    rsi_threshold: float,
    bb_period: int,
    bb_std: float,
) -> types.SimpleNamespace:
    """Return a module-like object satisfying run_backtest's strategy contract."""
    strategy_id = (
        f"{STRATEGY_BASE_ID}__rsi{rsi_period}"
        f"_th{rsi_threshold:.1f}_bb{bb_period}_std{bb_std:.2f}"
    )
    exit_rsi = rsi_threshold + 20.0

    def generate_intent(df, ctx, closed_only=True):
        min_bars = max(rsi_period, bb_period, ATR_PERIOD) + 10
        if len(df) < min_bars:
            return _mr._warmup_intent(ctx)

        close = df["close"]
        high  = df["high"]
        low   = df["low"]

        rsi_s        = _mr._rsi(close, rsi_period)
        bb_mid, bb_upper, bb_lower = _mr._bollinger(close, bb_period, bb_std)
        atr          = _mr._atr(high, low, close, ATR_PERIOD)
        atr_pct_s    = atr / close

        c           = float(close.iloc[-1])
        rsi         = float(rsi_s.iloc[-1])
        mid         = float(bb_mid.iloc[-1])
        upper       = float(bb_upper.iloc[-1])
        lower_b     = float(bb_lower.iloc[-1])
        atr_pct_now = float(atr_pct_s.iloc[-1])

        band_range = upper - lower_b
        bb_pos = ((c - lower_b) / band_range) if band_range > 1e-10 else 0.5

        meta = {
            "rsi": round(rsi, 2),
            "bb_pos": round(bb_pos, 4),
            "atr_pct": round(atr_pct_now, 5),
            "regime": ctx.regime.value,
            "params": {
                "rsi_period": rsi_period, "rsi_threshold": rsi_threshold,
                "bb_period": bb_period, "bb_std": bb_std,
            },
        }

        from research.regimes.contracts import RegimeLabel
        from research.strategies.contracts import Action, StrategyIntent

        # Regime exit
        regime_override = ctx.regime in (
            RegimeLabel.TREND_DOWN, RegimeLabel.HIGH_VOL,
            RegimeLabel.VOL_EXPANSION, RegimeLabel.TREND_UP,
        )
        if regime_override and ctx.current_exposure_frac > 0:
            return StrategyIntent(
                action=Action.EXIT_LONG, confidence=0.85,
                desired_exposure_frac=0.0, horizon_hours=HORIZON_BARS,
                reason=f"Regime {ctx.regime.value} — exit MR",
                meta=meta, strategy_id=strategy_id,
            )

        # Exit: mean restored
        if ctx.current_exposure_frac > 0 and (rsi >= exit_rsi or c >= mid):
            return StrategyIntent(
                action=Action.EXIT_LONG, confidence=0.75,
                desired_exposure_frac=0.0, horizon_hours=HORIZON_BARS,
                reason=f"Mean restored: RSI={rsi:.1f}",
                meta=meta, strategy_id=strategy_id,
            )

        # Entry
        from research.regimes.contracts import RegimeLabel as RL
        reversion_regime = ctx.regime in (RL.RANGE, RL.VOL_COMPRESSION)
        if (reversion_regime and rsi < rsi_threshold
                and bb_pos < 0.25 and atr_pct_now < MAX_ATR_PCT):
            oversold_depth = max(0.0, (rsi_threshold - rsi) / rsi_threshold)
            band_depth     = max(0.0, 0.25 - bb_pos) * 4
            exposure = MIN_EXPOSURE + (oversold_depth * 0.5 + band_depth * 0.5) * (
                MAX_EXPOSURE - MIN_EXPOSURE
            )
            exposure   = round(min(exposure, MAX_EXPOSURE), 4)
            confidence = round(0.50 + oversold_depth * 0.35, 4)
            return StrategyIntent(
                action=Action.ENTER_LONG, confidence=confidence,
                desired_exposure_frac=exposure, horizon_hours=HORIZON_BARS,
                reason=f"MR entry: RSI={rsi:.1f} bb_pos={bb_pos:.3f}",
                meta={**meta, "oversold_depth": round(oversold_depth, 4)},
                strategy_id=strategy_id,
            )

        # Hold
        if ctx.current_exposure_frac > 0:
            return StrategyIntent(
                action=Action.HOLD, confidence=0.55,
                desired_exposure_frac=ctx.current_exposure_frac,
                horizon_hours=HORIZON_BARS,
                reason="Holding — awaiting mean restoration",
                meta=meta, strategy_id=strategy_id,
            )

        from research.strategies.contracts import Action as A
        return StrategyIntent(
            action=A.FLAT, confidence=0.50,
            desired_exposure_frac=0.0, horizon_hours=0,
            reason="No oversold signal — flat",
            meta=meta, strategy_id=strategy_id,
        )

    mod = types.SimpleNamespace()
    mod.generate_intent = generate_intent
    mod.STRATEGY_ID     = strategy_id
    mod.__name__        = strategy_id
    return mod


# ── Fitness ─────────────────────────────────────────────────────────────────────

def _romd(total_return_pct: float, max_dd_pct: float) -> float:
    if abs(max_dd_pct) < 0.01:
        return 0.0
    return total_return_pct / abs(max_dd_pct)


def _fitness(total_return_pct: float, max_dd_pct: float, n_trades: int) -> float:
    return _romd(total_return_pct, max_dd_pct) - n_trades * TRADE_PENALTY


# ── Optuna objective ─────────────────────────────────────────────────────────────

def _make_objective(is_df: pd.DataFrame, exec_config: ExecutionConfig):
    n_years      = (is_df.index[-1] - is_df.index[0]).days / 365.25
    min_trades   = max(2, int(_MIN_TRADES_PER_YEAR * n_years))
    max_trades   = int(_MAX_TRADES_PER_YEAR * n_years)

    def objective(trial: optuna.Trial) -> float:
        rsi_period    = trial.suggest_int("rsi_period",    2,    14)
        rsi_threshold = trial.suggest_float("rsi_threshold", 15.0, 35.0)
        bb_period     = trial.suggest_int("bb_period",    10,    30)
        bb_std        = trial.suggest_float("bb_std",      1.5,   3.0)

        mod = _build_strategy(rsi_period, rsi_threshold, bb_period, bb_std)
        try:
            result = run_backtest(
                df=is_df, strategy_module=mod,
                asset=ASSET, initial_capital=INITIAL_CAPITAL,
                exec_config=exec_config,
            )
        except Exception as exc:
            trial.set_user_attr("error", str(exc))
            return -1000.0

        m = compute_metrics(result.equity_curve, result.trades, result.params)

        if m.n_trades < min_trades:
            trial.set_user_attr("rejection", "under_trading")
            return -999.0
        if m.n_trades > max_trades:
            trial.set_user_attr("rejection", "over_trading")
            return -999.0

        score = _fitness(m.total_return_pct, m.max_drawdown_pct, m.n_trades)
        trial.set_user_attr("total_return_pct",  round(m.total_return_pct, 4))
        trial.set_user_attr("max_drawdown_pct",  round(m.max_drawdown_pct, 4))
        trial.set_user_attr("romad",             round(_romd(m.total_return_pct, m.max_drawdown_pct), 4))
        trial.set_user_attr("n_trades",          m.n_trades)
        trial.set_user_attr("sharpe",            round(m.sharpe, 4))
        return score

    return objective


# ── Synthetic stub ───────────────────────────────────────────────────────────────

def _make_qqq_stub(n_bars: int = 1500, seed: int = 42) -> pd.DataFrame:
    """Synthetic QQQ-like daily OHLCV (GBM, ~10% drift, ~18% vol)."""
    rng = np.random.default_rng(seed)
    dt  = 1 / 252
    log_rets = (0.10 - 0.5 * 0.18 ** 2) * dt + 0.18 * math.sqrt(dt) * rng.standard_normal(n_bars)
    closes   = 350.0 * np.exp(np.cumsum(log_rets))
    spread   = closes * rng.uniform(0.002, 0.012, n_bars)
    highs    = closes + spread * rng.uniform(0.3, 1.0, n_bars)
    lows     = closes - spread * rng.uniform(0.3, 1.0, n_bars)
    opens    = closes * (1 + rng.uniform(-0.005, 0.005, n_bars))
    volume   = rng.uniform(50_000_000, 150_000_000, n_bars)
    idx      = pd.date_range("2019-01-01", periods=n_bars, freq="B")
    df       = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volume},
        index=idx,
    )
    df.index.name = "timestamp"
    df.attrs["asset"] = "QQQ"
    return df


# ── Equity curve stitching ───────────────────────────────────────────────────────

def _stitch_equity(curves: list[pd.Series]) -> pd.Series:
    """Chain equity curves so each period starts where the previous ended."""
    pieces = []
    running_nav = INITIAL_CAPITAL
    for eq in curves:
        scale  = running_nav / float(eq.iloc[0])
        scaled = eq * scale
        pieces.append(scaled)
        running_nav = float(scaled.iloc[-1])
    return pd.concat(pieces)


# ── Aggregate metrics on the stitched curve ──────────────────────────────────────

def _aggregate_metrics(equity: pd.Series) -> dict[str, float]:
    eq = equity.dropna().astype(float)
    if len(eq) < 2:
        return {"total_return_pct": 0.0, "cagr_pct": 0.0, "max_drawdown_pct": 0.0,
                "romad": 0.0, "sharpe": 0.0}

    years        = (eq.index[-1] - eq.index[0]).days / 365.25
    total_ret    = (eq.iloc[-1] / eq.iloc[0] - 1.0) * 100.0
    cagr         = ((eq.iloc[-1] / eq.iloc[0]) ** (1.0 / max(years, 1e-9)) - 1.0) * 100.0
    dd           = eq / eq.cummax() - 1.0
    max_dd       = float(dd.min()) * 100.0
    rets         = eq.pct_change(fill_method=None).dropna()
    std          = float(rets.std(ddof=0))
    sharpe       = (rets.mean() / std * math.sqrt(TRADING_DAYS_YEAR)) if std > 1e-12 else 0.0
    romd_val     = _romd(total_ret, max_dd)

    return {
        "total_return_pct": round(total_ret, 2),
        "cagr_pct":         round(cagr, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "romad":            round(romd_val, 4),
        "sharpe":           round(sharpe, 4),
    }


# ── Main WFV loop ────────────────────────────────────────────────────────────────

@dataclass
class FoldResult:
    fold_num:        int
    is_start:        str
    is_end:          str
    oos_start:       str
    oos_end:         str
    best_params:     dict[str, Any]
    is_best_fitness: float
    oos_return_pct:  float
    oos_max_dd_pct:  float
    oos_n_trades:    int
    oos_sharpe:      float
    oos_equity:      pd.Series = field(repr=False)


def run_wfv(
    df: pd.DataFrame,
    exec_config: ExecutionConfig,
    n_trials: int = N_TRIALS,
    seed: int = 42,
) -> list[FoldResult]:
    is_offset  = pd.DateOffset(years=IN_SAMPLE_YEARS)
    oos_offset = pd.DateOffset(years=OOS_YEARS)

    data_start = df.index[0]
    data_end   = df.index[-1]

    # Generate fold boundaries
    fold_dates: list[tuple] = []
    is_start = data_start
    while True:
        is_end    = is_start + is_offset
        oos_start = is_end
        oos_end   = oos_start + oos_offset
        if oos_end > data_end:
            break
        # Ensure enough IS bars for the indicator warmup (need > ~50 bars)
        is_df_check = df.loc[is_start:is_end]
        if len(is_df_check) < 100:
            break
        fold_dates.append((is_start, is_end, oos_start, oos_end))
        is_start = is_start + oos_offset  # step forward by one OOS year

    if not fold_dates:
        raise ValueError(
            f"Not enough data for any WFV fold.  Need at least "
            f"{IN_SAMPLE_YEARS + OOS_YEARS} years; got "
            f"{(data_end - data_start).days / 365.25:.1f} yr."
        )

    print(f"\n{'='*72}")
    print(f"  WFV MeanReversionSniper — QQQ — {len(fold_dates)} fold(s)")
    print(f"  IS={IN_SAMPLE_YEARS}yr  OOS={OOS_YEARS}yr  n_trials={n_trials}")
    print(f"  Data: {data_start.date()} → {data_end.date()}  ({len(df)} bars)")
    print(f"{'='*72}\n")

    results: list[FoldResult] = []

    for fold_num, (is_start, is_end, oos_start, oos_end) in enumerate(fold_dates, start=1):
        is_df  = df.loc[is_start:is_end]
        oos_df = df.loc[oos_start:oos_end]

        if len(oos_df) < 5:
            print(f"  [Fold {fold_num}] OOS window too short ({len(oos_df)} bars) — skipping")
            continue

        print(
            f"  [Fold {fold_num}/{len(fold_dates)}] "
            f"IS: {is_start.date()} → {is_end.date()} ({len(is_df)} bars)  "
            f"OOS: {oos_start.date()} → {oos_end.date()} ({len(oos_df)} bars)"
        )
        print(f"    Optimizing ({n_trials} trials)...", end=" ", flush=True)

        study = optuna.create_study(
            direction="maximize",
            sampler=TPESampler(seed=seed + fold_num),
        )
        study.optimize(
            _make_objective(is_df, exec_config),
            n_trials=n_trials,
            show_progress_bar=False,
        )

        best = study.best_trial
        best_params = best.params
        print(
            f"done  fitness={best.value:.4f}  "
            + "  ".join(f"{k}={v}" for k, v in best_params.items())
        )

        # OOS execution with best params
        oos_mod = _build_strategy(**best_params)
        oos_result = run_backtest(
            df=oos_df,
            strategy_module=oos_mod,
            asset=ASSET,
            initial_capital=INITIAL_CAPITAL,
            exec_config=exec_config,
        )
        oos_m = compute_metrics(oos_result.equity_curve, oos_result.trades, oos_result.params)

        print(
            f"    OOS → return={oos_m.total_return_pct:.2f}%  "
            f"maxDD={oos_m.max_drawdown_pct:.2f}%  "
            f"sharpe={oos_m.sharpe:.3f}  trades={oos_m.n_trades}"
        )

        results.append(FoldResult(
            fold_num        = fold_num,
            is_start        = str(is_start.date()),
            is_end          = str(is_end.date()),
            oos_start       = str(oos_start.date()),
            oos_end         = str(oos_end.date()),
            best_params     = best_params,
            is_best_fitness = round(float(best.value or 0.0), 4),
            oos_return_pct  = oos_m.total_return_pct,
            oos_max_dd_pct  = oos_m.max_drawdown_pct,
            oos_n_trades    = oos_m.n_trades,
            oos_sharpe      = oos_m.sharpe,
            oos_equity      = oos_result.equity_curve,
        ))

    return results


# ── Report ────────────────────────────────────────────────────────────────────────

def _print_report(results: list[FoldResult]) -> None:
    if not results:
        print("\nNo completed folds — cannot produce report.")
        return

    # Stitch OOS equity curves
    stitched = _stitch_equity([r.oos_equity for r in results])
    agg      = _aggregate_metrics(stitched)

    print(f"\n{'='*72}")
    print("  AGGREGATED OOS METRICS (fiduciary equity curve)")
    print(f"{'='*72}")
    print(f"  Total OOS Return   : {agg['total_return_pct']:>8.2f}%")
    print(f"  CAGR               : {agg['cagr_pct']:>8.2f}%")
    print(f"  Max OOS Drawdown   : {agg['max_drawdown_pct']:>8.2f}%")
    print(f"  Aggregated RoMaD   : {agg['romad']:>8.4f}")
    print(f"  Sharpe (OOS)       : {agg['sharpe']:>8.4f}")
    print(f"{'='*72}")

    print(f"\n  PER-FOLD PARAMETER TABLE (n={len(results)} folds)\n")
    header = (
        f"  {'Fold':<5}  {'OOS Period':<25}  "
        f"{'rsi_p':>5}  {'rsi_th':>6}  {'bb_p':>4}  {'bb_std':>6}  "
        f"{'IS fit':>7}  {'OOS ret%':>8}  {'OOS DD%':>7}  {'trades':>6}"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))
    for r in results:
        p = r.best_params
        print(
            f"  {r.fold_num:<5}  "
            f"{r.oos_start} → {r.oos_end}  "
            f"{p.get('rsi_period', '?'):>5}  "
            f"{p.get('rsi_threshold', 0.0):>6.1f}  "
            f"{p.get('bb_period', '?'):>4}  "
            f"{p.get('bb_std', 0.0):>6.2f}  "
            f"{r.is_best_fitness:>7.4f}  "
            f"{r.oos_return_pct:>8.2f}%  "
            f"{r.oos_max_dd_pct:>7.2f}%  "
            f"{r.oos_n_trades:>6}"
        )

    # Edge stability note
    all_rsi_th = [r.best_params.get("rsi_threshold", 0.0) for r in results]
    all_bb_std = [r.best_params.get("bb_std", 0.0) for r in results]
    print(f"\n  Edge stability:")
    print(f"    rsi_threshold range : {min(all_rsi_th):.1f} – {max(all_rsi_th):.1f}")
    print(f"    bb_std range        : {min(all_bb_std):.2f} – {max(all_bb_std):.2f}")

    # Quick overfitting signal
    mean_oos = float(np.mean([r.oos_return_pct for r in results]))
    pct_positive = sum(1 for r in results if r.oos_return_pct > 0) / len(results) * 100
    print(f"    Mean OOS return     : {mean_oos:.2f}%")
    print(f"    Folds with OOS > 0  : {pct_positive:.0f}%")
    print(f"\n{'='*72}\n")


# ── CLI ────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Walk-Forward Validation for MeanReversionSniper on QQQ.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--data",      default=None,  help="Path to QQQ daily OHLCV CSV (optional; synthetic stub used if omitted)")
    p.add_argument("--n-trials",  type=int, default=N_TRIALS,    help="Optuna trials per IS fold")
    p.add_argument("--seed",      type=int, default=42,          help="Random seed")
    p.add_argument("--fee",       type=float, default=0.0005,    help="Taker fee rate (e.g. 0.0005 = 0.05%%)")
    p.add_argument("--slippage",  type=float, default=5.0,       help="Base slippage bps (equity default: 5bps)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    exec_config = ExecutionConfig(
        taker_fee_rate   = args.fee,
        base_slippage_bps = args.slippage,
    )

    if args.data:
        path = Path(args.data)
        if not path.exists():
            print(f"ERROR: data file not found: {path}", file=sys.stderr)
            sys.exit(1)
        print(f"Loading QQQ data from {path} ...")
        df = load_ohlcv(str(path), asset=ASSET)
    else:
        print("No --data supplied. Using synthetic QQQ-like stub (n=2000 daily bars).")
        df = _make_qqq_stub(n_bars=2000, seed=args.seed)

    print(f"  {len(df)} bars  |  {df.index[0].date()} → {df.index[-1].date()}\n")

    results = run_wfv(df, exec_config, n_trials=args.n_trials, seed=args.seed)
    _print_report(results)


if __name__ == "__main__":
    main()
