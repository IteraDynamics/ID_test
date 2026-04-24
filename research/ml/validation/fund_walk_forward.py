"""Fund-level walk-forward validation for multi-sleeve portfolios.

This module validates the *portfolio structure*, not a single strategy in
isolation.  Each fold follows the same chronological discipline as the
single-strategy walk-forward runner:

- Training data is sliced only through ``train_end``.
- A calibrator is fit only from the training slice.
- The test slice is strictly future data.
- Baseline and calibrated portfolio runs are compared only on the test slice.

The default fund structure is the current Itera winning baseline:
BTC/ETH × 1H/4H, equal-weight, using trend_following_v8_ecap60_add80.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from research.harness.backtest_engine import BacktestResult, run_backtest
from research.harness.execution_model import ExecutionConfig
from research.harness.metrics import BacktestMetrics, compute_metrics
from research.harness.resampler import align_equity_curves, resample_ohlcv
from research.ml.calibration.platt_calibrator import MIN_SAMPLES_PLATT, PlattCalibrator
from research.ml.calibration.training_data import extract_calibration_samples
from research.ml.validation.fold_spec import FoldSpec

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FundSleeveSpec:
    """One asset × timeframe sleeve in the fund portfolio."""

    label: str
    asset: str
    timeframe: str
    weight: float


@dataclass
class SleeveFoldMetrics:
    """Per-sleeve test metrics for one fund walk-forward fold."""

    label: str
    asset: str
    timeframe: str
    weight: float
    baseline: dict[str, Any]
    calibrated: dict[str, Any]
    n_train_samples: int
    calibrator_fitted: bool
    calibration_method: str


@dataclass
class FundFoldResult:
    """Complete fund-level result for one walk-forward fold."""

    fold_spec: FoldSpec
    baseline: dict[str, Any] = field(default_factory=dict)
    calibrated: dict[str, Any] = field(default_factory=dict)
    delta: dict[str, Any] = field(default_factory=dict)
    sleeves: list[SleeveFoldMetrics] = field(default_factory=list)
    baseline_corr: dict[str, dict[str, float]] = field(default_factory=dict)
    calibrated_corr: dict[str, dict[str, float]] = field(default_factory=dict)
    skipped: bool = False
    skip_reason: str = ""
    cal_improved_sharpe: bool = False
    cal_improved_calmar: bool = False
    cal_improved_dd: bool = False
    cal_improved_slippage: bool = False


def default_fund_sleeves() -> list[FundSleeveSpec]:
    """Return the current winning 4-sleeve equal-weight structure."""
    return [
        FundSleeveSpec("BTC_1H", "BTC", "1H", 0.25),
        FundSleeveSpec("BTC_4H", "BTC", "4H", 0.25),
        FundSleeveSpec("ETH_1H", "ETH", "1H", 0.25),
        FundSleeveSpec("ETH_4H", "ETH", "4H", 0.25),
    ]


def _slice(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    return df.loc[start:end]


def _sleeve_df(raw_data: dict[str, pd.DataFrame], sleeve: FundSleeveSpec, start: str, end: str) -> pd.DataFrame:
    df = _slice(raw_data[sleeve.asset], start, end)
    if sleeve.timeframe.upper() == "4H":
        return resample_ohlcv(df, "4h")
    if sleeve.timeframe.upper() == "1H":
        return df
    raise ValueError(f"Unsupported timeframe for {sleeve.label}: {sleeve.timeframe}")


def _fit_calibrator_for_sleeve(
    train_df: pd.DataFrame,
    strategy_module: Any,
    strategy_id: str,
    exec_config: ExecutionConfig,
    initial_capital: float,
    rebalance_threshold: float,
    asset: str,
    min_train_samples: int,
) -> tuple[PlattCalibrator, int]:
    """Fit a calibrator from the training slice for one sleeve only."""
    train_result = run_backtest(
        df=train_df,
        strategy_module=strategy_module,
        initial_capital=initial_capital,
        exec_config=exec_config,
        rebalance_threshold=rebalance_threshold,
        asset=asset,
    )
    samples = extract_calibration_samples(train_result, strategy_id=strategy_id)
    n = len(samples)
    if n < min_train_samples:
        return PlattCalibrator(strategy_id=strategy_id, n_samples=n), n

    raw = np.array([s.heuristic_confidence for s in samples])
    if float(np.std(raw)) < 1e-5:
        return PlattCalibrator.fit_multivariate(samples, strategy_id=strategy_id), n

    labels = np.array([s.outcome_label for s in samples], dtype=float)
    return PlattCalibrator.fit(raw, labels, strategy_id=strategy_id), n


def _run_sleeve(
    test_df: pd.DataFrame,
    strategy_module: Any,
    exec_config: ExecutionConfig,
    initial_capital: float,
    rebalance_threshold: float,
    asset: str,
    calibrator: PlattCalibrator | None,
    strategy_id: str,
) -> BacktestResult:
    calibrators = {strategy_id: calibrator} if calibrator is not None else None
    return run_backtest(
        df=test_df,
        strategy_module=strategy_module,
        initial_capital=initial_capital,
        exec_config=exec_config,
        rebalance_threshold=rebalance_threshold,
        asset=asset,
        calibrators=calibrators,
    )


def _portfolio_metrics(
    sleeve_results: dict[str, BacktestResult],
    initial_capital: float,
    params: dict[str, Any],
) -> tuple[BacktestMetrics, pd.DataFrame, pd.DataFrame]:
    curves = {label: r.equity_curve for label, r in sleeve_results.items()}
    aligned = align_equity_curves(curves, base_freq="1h")
    portfolio_equity = aligned.sum(axis=1)
    portfolio_equity.name = "equity"
    trades = [t for r in sleeve_results.values() for t in r.trades]
    metrics = compute_metrics(portfolio_equity, trades, {**params, "initial_capital": initial_capital})
    daily = aligned.resample("1D").last().dropna(how="all")
    corr = daily.pct_change().dropna(how="all").corr()
    return metrics, aligned, corr


def _metric_delta(baseline: dict[str, Any], calibrated: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "total_return_pct",
        "cagr_pct",
        "max_drawdown_pct",
        "sharpe",
        "calmar",
        "volatility_ann_pct",
        "total_slippage_cost",
        "total_fees_paid",
        "turnover_x_nav_adj",
        "n_trades",
    ]
    out: dict[str, Any] = {}
    for key in keys:
        try:
            out[f"delta_{key}"] = round(float(calibrated[key]) - float(baseline[key]), 6)
        except Exception:
            out[f"delta_{key}"] = None
    return out


def _corr_to_dict(corr: pd.DataFrame) -> dict[str, dict[str, float]]:
    return {
        str(row): {str(col): round(float(corr.loc[row, col]), 6) for col in corr.columns}
        for row in corr.index
    }


def run_fund_fold(
    raw_data: dict[str, pd.DataFrame],
    strategy_module: Any,
    foldsleeves: list[FundSleeveSpec],
    fold: FoldSpec,
    exec_config: ExecutionConfig,
    initial_capital: float = 100_000.0,
    rebalance_threshold: float = 0.05,
    min_train_samples: int = MIN_SAMPLES_PLATT,
    calibration_mode: str = "per_sleeve",
) -> FundFoldResult:
    """Run one fund-level walk-forward fold.

    ``calibration_mode`` may be:
    - ``per_sleeve``: train one calibrator per asset × timeframe sleeve.
    - ``global``: train one calibrator on BTC_1H and cross-apply it to all sleeves.
    """
    strategy_id = getattr(strategy_module, "STRATEGY_ID", "unknown")
    sleeve_capitals = {s.label: initial_capital * s.weight for s in foldsleeves}

    log.info("═" * 60)
    log.info("%s", fold)

    calibrators_by_sleeve: dict[str, PlattCalibrator | None] = {}
    train_sample_counts: dict[str, int] = {}

    if calibration_mode not in {"per_sleeve", "global"}:
        raise ValueError("calibration_mode must be 'per_sleeve' or 'global'")

    if calibration_mode == "global":
        anchor = next((s for s in foldsleeves if s.label == "BTC_1H"), foldsleeves[0])
        train_df = _sleeve_df(raw_data, anchor, fold.train_start, fold.train_end)
        cal, n = _fit_calibrator_for_sleeve(
            train_df=train_df,
            strategy_module=strategy_module,
            strategy_id=strategy_id,
            exec_config=exec_config,
            initial_capital=sleeve_capitals[anchor.label],
            rebalance_threshold=rebalance_threshold,
            asset=anchor.asset,
            min_train_samples=min_train_samples,
        )
        for s in foldsleeves:
            calibrators_by_sleeve[s.label] = cal
            train_sample_counts[s.label] = n
        log.info("  [TRAIN] Global calibrator from %s: n=%d fitted=%s", anchor.label, n, cal.is_fitted)
    else:
        for s in foldsleeves:
            train_df = _sleeve_df(raw_data, s, fold.train_start, fold.train_end)
            if len(train_df) < 100:
                return FundFoldResult(fold_spec=fold, skipped=True, skip_reason=f"Insufficient train bars for {s.label}")
            cal, n = _fit_calibrator_for_sleeve(
                train_df=train_df,
                strategy_module=strategy_module,
                strategy_id=strategy_id,
                exec_config=exec_config,
                initial_capital=sleeve_capitals[s.label],
                rebalance_threshold=rebalance_threshold,
                asset=s.asset,
                min_train_samples=min_train_samples,
            )
            calibrators_by_sleeve[s.label] = cal
            train_sample_counts[s.label] = n
            log.info("  [TRAIN] %s calibrator: n=%d fitted=%s method=%s", s.label, n, cal.is_fitted, cal.calibration_method)

    baseline_results: dict[str, BacktestResult] = {}
    calibrated_results: dict[str, BacktestResult] = {}
    sleeve_metrics: list[SleeveFoldMetrics] = []

    for s in foldsleeves:
        test_df = _sleeve_df(raw_data, s, fold.test_start, fold.test_end)
        if len(test_df) < 10:
            return FundFoldResult(fold_spec=fold, skipped=True, skip_reason=f"Insufficient test bars for {s.label}")

        cap = sleeve_capitals[s.label]
        base = _run_sleeve(test_df, strategy_module, exec_config, cap, rebalance_threshold, s.asset, None, strategy_id)
        cal = _run_sleeve(test_df, strategy_module, exec_config, cap, rebalance_threshold, s.asset, calibrators_by_sleeve[s.label], strategy_id)
        baseline_results[s.label] = base
        calibrated_results[s.label] = cal

        base_m = compute_metrics(base.equity_curve, base.trades, {"strategy_id": strategy_id, "asset": s.asset, "timeframe": s.timeframe})
        cal_m = compute_metrics(cal.equity_curve, cal.trades, {"strategy_id": strategy_id, "asset": s.asset, "timeframe": s.timeframe})
        calibrator = calibrators_by_sleeve[s.label]
        sleeve_metrics.append(
            SleeveFoldMetrics(
                label=s.label,
                asset=s.asset,
                timeframe=s.timeframe,
                weight=s.weight,
                baseline=base_m.to_dict(),
                calibrated=cal_m.to_dict(),
                n_train_samples=train_sample_counts.get(s.label, 0),
                calibrator_fitted=bool(calibrator and calibrator.is_fitted),
                calibration_method=(calibrator.calibration_method if calibrator else "passthrough"),
            )
        )

    base_port_m, _, base_corr = _portfolio_metrics(
        baseline_results,
        initial_capital,
        {"strategy_id": "fund_portfolio_baseline", "asset": "BTC_ETH", "fold": fold.fold_id},
    )
    cal_port_m, _, cal_corr = _portfolio_metrics(
        calibrated_results,
        initial_capital,
        {"strategy_id": "fund_portfolio_calibrated", "asset": "BTC_ETH", "fold": fold.fold_id},
    )

    baseline = base_port_m.to_dict()
    calibrated = cal_port_m.to_dict()
    delta = _metric_delta(baseline, calibrated)
    d_sharpe = delta.get("delta_sharpe") or 0.0
    d_calmar = delta.get("delta_calmar") or 0.0
    d_dd = delta.get("delta_max_drawdown_pct") or 0.0
    d_slip = delta.get("delta_total_slippage_cost") or 0.0

    log.info(
        "  [TEST] Portfolio baseline:   CAGR=%.1f%% DD=%.1f%% Sharpe=%.3f Calmar=%.3f",
        base_port_m.cagr_pct,
        base_port_m.max_drawdown_pct,
        base_port_m.sharpe,
        base_port_m.calmar,
    )
    log.info(
        "  [TEST] Portfolio calibrated: CAGR=%.1f%% DD=%.1f%% Sharpe=%.3f Calmar=%.3f",
        cal_port_m.cagr_pct,
        cal_port_m.max_drawdown_pct,
        cal_port_m.sharpe,
        cal_port_m.calmar,
    )

    return FundFoldResult(
        fold_spec=fold,
        baseline=baseline,
        calibrated=calibrated,
        delta=delta,
        sleeves=sleeve_metrics,
        baseline_corr=_corr_to_dict(base_corr),
        calibrated_corr=_corr_to_dict(cal_corr),
        cal_improved_sharpe=d_sharpe > 0,
        cal_improved_calmar=d_calmar > 0,
        cal_improved_dd=d_dd > 0,
        cal_improved_slippage=d_slip < 0,
    )


def run_fund_walk_forward(
    raw_data: dict[str, pd.DataFrame],
    strategy_module: Any,
    folds: list[FoldSpec],
    exec_config: ExecutionConfig,
    initial_capital: float = 100_000.0,
    rebalance_threshold: float = 0.05,
    min_train_samples: int = MIN_SAMPLES_PLATT,
    calibration_mode: str = "per_sleeve",
    sleeves: list[FundSleeveSpec] | None = None,
) -> list[FundFoldResult]:
    """Run fund-level walk-forward across all folds."""
    foldsleeves = sleeves or default_fund_sleeves()
    results: list[FundFoldResult] = []
    for fold in folds:
        results.append(
            run_fund_fold(
                raw_data=raw_data,
                strategy_module=strategy_module,
                foldsleeves=foldsleeves,
                fold=fold,
                exec_config=exec_config,
                initial_capital=initial_capital,
                rebalance_threshold=rebalance_threshold,
                min_train_samples=min_train_samples,
                calibration_mode=calibration_mode,
            )
        )
    return results
