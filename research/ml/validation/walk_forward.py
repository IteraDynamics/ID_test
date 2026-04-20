"""Walk-forward validation runner.

No-leakage guarantee (enforced throughout):
  - train_df   = df.loc[fold.train_start : fold.train_end]
                 Only past bars visible during calibrator training.
  - Calibration samples extracted from train_result only.
  - Calibrator fitted on train samples only — never sees test labels.
  - test_df    = df.loc[fold.test_start : fold.test_end]
                 Strictly future bars, no overlap with train_df.
  - Test outcomes (labels) are computed after the fact from test equity curves
    and are never used to fit or adjust the calibrator.
  - The calibrator used on the test fold is the one fitted on train data;
    it is not re-fitted or tuned on any test information.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from research.harness.backtest_engine import run_backtest
from research.harness.execution_model import ExecutionConfig
from research.harness.metrics import compute_metrics
from research.ml.calibration.platt_calibrator import PlattCalibrator, MIN_SAMPLES_PLATT
from research.ml.calibration.training_data import extract_calibration_samples
from research.ml.validation.fold_spec import FoldSpec

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _brier_score(probs: np.ndarray, labels: np.ndarray) -> float:
    """Mean squared error between predicted probabilities and binary labels."""
    return float(np.mean((probs - labels) ** 2))


def _ece(probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error: weighted mean absolute calibration gap."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    n = len(probs)
    ece = 0.0
    for i in range(n_bins):
        mask = (probs >= bins[i]) & (probs < bins[i + 1])
        if mask.sum() > 0:
            ece += mask.sum() / n * abs(probs[mask].mean() - labels[mask].mean())
    return float(ece)


def _compute_delta(baseline: dict, calibrated: dict) -> dict:
    """Compute delta = calibrated - baseline for key strategy metrics.

    Positive delta on DD means calibration reduced drawdown (improvement).
    Negative delta on slippage means calibration reduced costs (improvement).
    """
    keys = [
        "cagr_pct",
        "max_drawdown_pct",
        "sharpe",
        "calmar",
        "volatility_ann_pct",
        "total_slippage_cost",
        "total_fees_paid",
        "turnover_x_nav_adj",
        "avg_cost_per_trade_bps",
        "avg_exit_entry_notional_ratio",
        "n_trades",
        "win_rate_pct",
    ]
    delta: dict[str, Any] = {}
    for k in keys:
        b = baseline.get(k)
        c = calibrated.get(k)
        if b is not None and c is not None:
            try:
                delta[f"delta_{k}"] = round(float(c) - float(b), 6)
            except (TypeError, ValueError):
                delta[f"delta_{k}"] = None
        else:
            delta[f"delta_{k}"] = None
    return delta


def _fit_calibrator(
    train_samples: list,
    strategy_id: str,
    min_samples: int,
) -> PlattCalibrator:
    """Fit calibrator on training samples only.

    Automatically selects multivariate logistic when confidence variance is
    near-zero (strategy emits constant confidence), otherwise Platt scaling.

    Returns an unfitted (passthrough) calibrator when sample count is too low.
    """
    n = len(train_samples)
    if n < min_samples:
        return PlattCalibrator(strategy_id=strategy_id)  # is_fitted=False → passthrough

    raw_confs = np.array([s.heuristic_confidence for s in train_samples])
    if float(np.std(raw_confs)) < 1e-5:
        # Near-constant confidence — use full indicator feature vector
        return PlattCalibrator.fit_multivariate(train_samples, strategy_id=strategy_id)

    labels = np.array([s.outcome_label for s in train_samples], dtype=float)
    return PlattCalibrator.fit(
        raw_confidences=raw_confs,
        outcome_labels=labels,
        strategy_id=strategy_id,
    )


def _calibration_quality(
    baseline_test_result: Any,
    calibrator: PlattCalibrator,
    strategy_id: str,
) -> dict:
    """Compute calibration quality metrics on the test fold.

    The TRAIN calibrator predicts on TEST trade features; TEST labels (outcomes)
    are only used here to score predictions — they never influenced calibrator
    fitting.  No leakage.
    """
    # Extract test-fold cycles from the baseline (uncalibrated) test run.
    # Using the baseline result ensures features come from unmodified intents.
    test_samples = extract_calibration_samples(baseline_test_result, strategy_id=strategy_id)

    if not test_samples:
        return {
            "n_test_cycles": 0,
            "win_rate_test": float("nan"),
            "brier_before": None,
            "brier_after": None,
            "ece_before": None,
            "ece_after": None,
        }

    raw_confs = np.array([s.heuristic_confidence for s in test_samples])
    labels = np.array([s.outcome_label for s in test_samples], dtype=float)

    # Apply TRAIN calibrator to TEST features — no leakage
    if calibrator.is_fitted:
        cal_confs = np.array([
            calibrator.predict_from_features(s.features, s.heuristic_confidence)
            for s in test_samples
        ])
    else:
        cal_confs = raw_confs  # passthrough

    return {
        "n_test_cycles": len(test_samples),
        "win_rate_test": round(float(labels.mean()), 4),
        "brier_before": round(_brier_score(raw_confs, labels), 4),
        "brier_after": round(_brier_score(cal_confs, labels), 4),
        "ece_before": round(_ece(raw_confs, labels), 4),
        "ece_after": round(_ece(cal_confs, labels), 4),
    }


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class FoldResult:
    """Complete results for one walk-forward fold."""

    fold_spec: FoldSpec

    # Training phase
    n_train_samples: int = 0
    calibrator_fitted: bool = False
    calibration_method: str = "passthrough"

    # Test phase — calibration quality metrics
    n_test_trades: int = 0
    n_test_cycles: int = 0
    win_rate_test: float = float("nan")
    brier_before: float | None = None
    brier_after: float | None = None
    ece_before: float | None = None
    ece_after: float | None = None

    # Strategy performance on TEST period only
    baseline: dict[str, Any] = field(default_factory=dict)    # uncalibrated
    calibrated: dict[str, Any] = field(default_factory=dict)  # calibrated
    delta: dict[str, Any] = field(default_factory=dict)       # calibrated − baseline

    # Status
    skipped: bool = False
    skip_reason: str = ""

    # Convenience booleans (set in run_fold)
    cal_improved_sharpe: bool = False
    cal_improved_calmar: bool = False
    cal_improved_dd: bool = False
    cal_improved_slippage: bool = False


# ── Core fold runner ──────────────────────────────────────────────────────────

def run_fold(
    df: pd.DataFrame,
    strategy_module: Any,
    fold: FoldSpec,
    exec_config: ExecutionConfig,
    initial_capital: float = 100_000.0,
    rebalance_threshold: float = 0.05,
    asset: str = "BTC",
    min_train_samples: int = MIN_SAMPLES_PLATT,
) -> FoldResult:
    """Execute one walk-forward fold end-to-end.

    Procedure (strictly chronological, no leakage):
      1. Slice training data to fold.train_start → fold.train_end.
      2. Run baseline backtest on TRAIN data (needed to extract trade outcomes).
      3. Extract calibration samples from TRAIN result only.
      4. Fit calibrator on TRAIN samples only.
      5. Slice test data to fold.test_start → fold.test_end.
      6. Run BASELINE backtest on TEST data (no calibrator).
      7. Run CALIBRATED backtest on TEST data (using TRAIN calibrator).
      8. Score calibration quality using TEST outcomes + TRAIN calibrator.
      9. Compute delta metrics.

    Parameters
    ----------
    df :
        Full OHLCV DataFrame (DatetimeIndex).
    strategy_module :
        Strategy with generate_intent() interface.
    fold :
        FoldSpec defining train/test date ranges.
    exec_config :
        Execution cost parameters (same for baseline and calibrated runs).
    initial_capital :
        Starting NAV for each test run (fixed per fold for comparability).
    rebalance_threshold :
        Minimum exposure change to trigger a simulated trade.
    asset :
        Asset label for logging.
    min_train_samples :
        Minimum completed trade cycles required to fit a calibrator.
    """
    strategy_id = getattr(strategy_module, "STRATEGY_ID", "unknown")
    log.info("═" * 60)
    log.info("%s", fold)

    # ── 1. Slice training data ─────────────────────────────────────────────
    # No-leakage: only bars up to and including train_end are visible.
    train_df = df.loc[fold.train_start : fold.train_end]

    if len(train_df) < 100:
        log.warning("  Skipping: insufficient training bars (%d).", len(train_df))
        return FoldResult(fold_spec=fold, skipped=True,
                          skip_reason=f"Insufficient training bars: {len(train_df)}")

    # ── 2. Run baseline backtest on TRAIN data ─────────────────────────────
    log.info("  [TRAIN] Running backtest on %d bars…", len(train_df))
    train_result = run_backtest(
        df=train_df,
        strategy_module=strategy_module,
        initial_capital=initial_capital,
        exec_config=exec_config,
        rebalance_threshold=rebalance_threshold,
        asset=asset,
    )
    log.info("  [TRAIN] %d trades.", len(train_result.trades))

    # ── 3. Extract calibration samples from TRAIN result only ──────────────
    # Features = intent.meta at entry bar (train period only).
    # Labels   = equity-curve outcome of each BUY→SELL cycle (train only).
    train_samples = extract_calibration_samples(train_result, strategy_id=strategy_id)
    n_train = len(train_samples)
    log.info("  [TRAIN] Extracted %d calibration samples.", n_train)

    # ── 4. Fit calibrator on TRAIN samples only ────────────────────────────
    # No-leakage: calibrator never sees test labels or test features.
    calibrator = _fit_calibrator(train_samples, strategy_id, min_train_samples)
    cal_fitted = calibrator.is_fitted
    cal_method = calibrator.calibration_method
    if cal_fitted:
        log.info("  [TRAIN] Calibrator fitted: method=%s.", cal_method)
    else:
        log.warning("  [TRAIN] Calibrator not fitted (n=%d < min=%d) — passthrough.",
                    n_train, min_train_samples)

    # ── 5. Slice test data (strictly future) ──────────────────────────────
    # No-leakage: test_start is strictly after train_end (enforced by FoldSpec).
    test_df = df.loc[fold.test_start : fold.test_end]

    if len(test_df) < 10:
        log.warning("  Skipping: insufficient test bars (%d).", len(test_df))
        return FoldResult(
            fold_spec=fold,
            n_train_samples=n_train,
            calibrator_fitted=cal_fitted,
            calibration_method=cal_method,
            skipped=True,
            skip_reason=f"Insufficient test bars: {len(test_df)}",
        )

    log.info("  [TEST]  Running BASELINE backtest on %d bars…", len(test_df))

    # ── 6. Baseline test backtest (uncalibrated) ──────────────────────────
    baseline_result = run_backtest(
        df=test_df,
        strategy_module=strategy_module,
        initial_capital=initial_capital,
        exec_config=exec_config,
        rebalance_threshold=rebalance_threshold,
        asset=asset,
    )
    baseline_metrics = compute_metrics(
        baseline_result.equity_curve,
        baseline_result.trades,
        baseline_result.params,
    )
    log.info("  [TEST]  Baseline: CAGR=%.1f%%  DD=%.1f%%  Sharpe=%.3f  Calmar=%.3f",
             baseline_metrics.cagr_pct, baseline_metrics.max_drawdown_pct,
             baseline_metrics.sharpe, baseline_metrics.calmar)

    # ── 7. Calibrated test backtest ───────────────────────────────────────
    # Uses calibrator fitted on TRAIN only — no leakage.
    log.info("  [TEST]  Running CALIBRATED backtest…")
    calibrated_result = run_backtest(
        df=test_df,
        strategy_module=strategy_module,
        initial_capital=initial_capital,
        exec_config=exec_config,
        rebalance_threshold=rebalance_threshold,
        asset=asset,
        calibrators={strategy_id: calibrator},
    )
    calibrated_metrics = compute_metrics(
        calibrated_result.equity_curve,
        calibrated_result.trades,
        calibrated_result.params,
    )
    log.info("  [TEST]  Calibrated: CAGR=%.1f%%  DD=%.1f%%  Sharpe=%.3f  Calmar=%.3f",
             calibrated_metrics.cagr_pct, calibrated_metrics.max_drawdown_pct,
             calibrated_metrics.sharpe, calibrated_metrics.calmar)

    # ── 8. Score calibration quality on test fold ─────────────────────────
    # TRAIN calibrator predicts on TEST features; TEST labels only used to score.
    cal_q = _calibration_quality(baseline_result, calibrator, strategy_id)

    # ── 9. Compute delta and improvement flags ────────────────────────────
    baseline_dict = baseline_metrics.to_dict()
    calibrated_dict = calibrated_metrics.to_dict()
    delta = _compute_delta(baseline_dict, calibrated_dict)

    d_sharpe = delta.get("delta_sharpe") or 0.0
    d_calmar = delta.get("delta_calmar") or 0.0
    d_dd = delta.get("delta_max_drawdown_pct") or 0.0
    d_slip = delta.get("delta_total_slippage_cost") or 0.0

    return FoldResult(
        fold_spec=fold,
        n_train_samples=n_train,
        calibrator_fitted=cal_fitted,
        calibration_method=cal_method,
        n_test_trades=len(baseline_result.trades),
        n_test_cycles=cal_q["n_test_cycles"],
        win_rate_test=cal_q["win_rate_test"],
        brier_before=cal_q["brier_before"],
        brier_after=cal_q["brier_after"],
        ece_before=cal_q["ece_before"],
        ece_after=cal_q["ece_after"],
        baseline=baseline_dict,
        calibrated=calibrated_dict,
        delta=delta,
        cal_improved_sharpe=d_sharpe > 0,
        cal_improved_calmar=d_calmar > 0,
        cal_improved_dd=d_dd > 0,
        cal_improved_slippage=d_slip < 0,
    )


# ── Multi-fold runner ─────────────────────────────────────────────────────────

def run_walk_forward(
    df: pd.DataFrame,
    strategy_module: Any,
    folds: list[FoldSpec],
    exec_config: ExecutionConfig,
    initial_capital: float = 100_000.0,
    rebalance_threshold: float = 0.05,
    asset: str = "BTC",
    min_train_samples: int = MIN_SAMPLES_PLATT,
) -> list[FoldResult]:
    """Run all folds sequentially and return results.

    Each fold is fully independent — no state leaks between folds.
    """
    results: list[FoldResult] = []
    for fold in folds:
        result = run_fold(
            df=df,
            strategy_module=strategy_module,
            fold=fold,
            exec_config=exec_config,
            initial_capital=initial_capital,
            rebalance_threshold=rebalance_threshold,
            asset=asset,
            min_train_samples=min_train_samples,
        )
        results.append(result)
    return results
