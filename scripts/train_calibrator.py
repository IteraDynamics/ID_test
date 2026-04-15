#!/usr/bin/env python
"""IteraDynamics — Confidence Calibrator Training CLI.

Runs a backtest for one or more strategy sleeves, extracts calibration
training samples from the results, fits a Platt-scaling model per strategy,
and saves the models as JSON files.

Usage examples:
    # Train all strategies on 6 years of hourly BTC data
    python scripts/train_calibrator.py --data data/btc_1h.csv

    # Train specific strategies, hold out last 20% for evaluation
    python scripts/train_calibrator.py --data data/btc_1h.csv \\
        --strategies trend_following,volatility_breakout \\
        --test-split 0.20

    # Use a custom output directory
    python scripts/train_calibrator.py --data data/btc_1h.csv \\
        --output artifacts/ml_models/

    # Also fit regime confidence calibrators
    python scripts/train_calibrator.py --data data/btc_1h.csv \\
        --train-regime-calibrator
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("train_calibrator")

import numpy as np

from research.harness.data_loader import load_ohlcv, validate_ohlcv
from research.harness.backtest_engine import run_backtest
from research.harness.execution_model import ExecutionConfig
from research.strategies import REGISTRY as STRATEGY_REGISTRY
from research.ml.calibration.training_data import (
    extract_calibration_samples,
    samples_to_arrays,
    time_split,
)
from research.ml.calibration.platt_calibrator import PlattCalibrator
from research.ml.calibration.model_store import save_calibrator
from research.ml.calibration.regime_calibrator import RegimeCalibrator
from research.regimes.baseline_engine import BaselineRegimeEngine


# ── Calibration quality metrics ───────────────────────────────────────────────

def _brier_score(probs: np.ndarray, labels: np.ndarray) -> float:
    """Mean squared error of probability predictions (lower = better)."""
    return float(np.mean((probs - labels) ** 2))


def _expected_calibration_error(
    probs: np.ndarray,
    labels: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Expected Calibration Error (ECE) via equal-width binning."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(probs)
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (probs >= lo) & (probs < hi)
        if not np.any(mask):
            continue
        avg_conf = float(np.mean(probs[mask]))
        avg_acc = float(np.mean(labels[mask]))
        ece += np.sum(mask) / n * abs(avg_conf - avg_acc)
    return ece


def _evaluate_calibrator(
    calibrator: PlattCalibrator,
    raw_confs: np.ndarray,
    labels: np.ndarray,
    tag: str = "",
) -> dict:
    """Compute before/after quality metrics for a calibrator."""
    raw_brier = _brier_score(raw_confs, labels)
    raw_ece = _expected_calibration_error(raw_confs, labels)

    calibrated_probs = np.array([calibrator.predict(c) for c in raw_confs])
    cal_brier = _brier_score(calibrated_probs, labels)
    cal_ece = _expected_calibration_error(calibrated_probs, labels)

    win_rate = float(np.mean(labels))
    return {
        "tag": tag,
        "n_samples": len(labels),
        "win_rate": round(win_rate, 4),
        "brier_score_before": round(raw_brier, 4),
        "brier_score_after": round(cal_brier, 4),
        "brier_improvement": round(raw_brier - cal_brier, 4),
        "ece_before": round(raw_ece, 4),
        "ece_after": round(cal_ece, 4),
        "ece_improvement": round(raw_ece - cal_ece, 4),
        "fitted": calibrator.is_fitted,
        "method": calibrator.calibration_method,
    }


# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Train Platt-scaling confidence calibrators for IteraDynamics strategies",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--data", required=True, help="Path to OHLCV CSV file")
    p.add_argument(
        "--strategies",
        default="trend_following,volatility_breakout,mean_reversion",
        help="Comma-separated list of strategy names from REGISTRY",
    )
    p.add_argument(
        "--test-split",
        type=float,
        default=0.30,
        help="Fraction of samples reserved for evaluation (time-based, from the end)",
    )
    p.add_argument(
        "--output",
        default="artifacts/ml_models",
        help="Directory to write calibrator JSON files",
    )
    p.add_argument(
        "--train-regime-calibrator",
        action="store_true",
        help="Also fit and save per-label regime confidence calibrators",
    )
    p.add_argument(
        "--regime-horizon-bars",
        type=int,
        default=24,
        help="Horizon (bars) for regime stability label when training regime calibrator",
    )
    p.add_argument(
        "--capital",
        type=float,
        default=100_000.0,
        help="Initial capital for backtest",
    )
    p.add_argument(
        "--asset",
        default="BTC",
        help="Asset label",
    )
    # Execution params — should match whatever you'll use in run_backtest.py --calibrate
    p.add_argument("--fee", type=float, default=None,
                   help="Taker fee rate (e.g. 0.0008 = 8 bps). Matches --fee in run_backtest.py")
    p.add_argument("--base-slippage", type=float, default=None,
                   help="Base slippage floor in bps. Matches --base-slippage in run_backtest.py")
    p.add_argument("--slippage-vol-factor", type=float, default=None,
                   help="Slippage bps per 100%% ATR. Matches --slippage-vol-factor in run_backtest.py")
    p.add_argument("--cooldown", type=int, default=None,
                   help="Minimum bars between trades. Matches --cooldown in run_backtest.py")
    p.add_argument("--rebalance-threshold", type=float, default=None,
                   help="Min exposure delta to trigger a trade. Matches --rebalance-threshold in run_backtest.py")
    return p.parse_args()


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # ── Load data ─────────────────────────────────────────────────────────
    data_path = Path(args.data)
    if not data_path.exists():
        log.error("Data file not found: %s", data_path)
        sys.exit(1)

    log.info("Loading data from %s", data_path)
    df = load_ohlcv(str(data_path))
    validate_ohlcv(df)
    log.info("Loaded %d bars  (%s → %s)", len(df), df.index[0], df.index[-1])

    strategy_names = [s.strip() for s in args.strategies.split(",") if s.strip()]
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_reports: list[dict] = []

    # ── Train per-strategy calibrators ───────────────────────────────────
    for name in strategy_names:
        module = STRATEGY_REGISTRY.get(name)
        if module is None:
            log.warning("Unknown strategy '%s' — skipping. Available: %s", name, list(STRATEGY_REGISTRY))
            continue

        log.info("=" * 60)
        log.info("Strategy: %s", name)
        log.info("Running backtest (%d bars)…", len(df))

        exec_config = ExecutionConfig()
        if args.fee is not None:
            exec_config.taker_fee_rate = args.fee
        if args.base_slippage is not None:
            exec_config.base_slippage_bps = args.base_slippage
        if args.slippage_vol_factor is not None:
            exec_config.slippage_vol_factor = args.slippage_vol_factor
        if args.cooldown is not None:
            exec_config.cooldown_bars = args.cooldown

        rebalance_threshold = args.rebalance_threshold if args.rebalance_threshold is not None else 0.02

        result = run_backtest(
            df, module,
            initial_capital=args.capital,
            asset=args.asset,
            exec_config=exec_config,
            rebalance_threshold=rebalance_threshold,
        )
        log.info("Backtest complete: %d trades", result.n_trades)

        samples = extract_calibration_samples(result, strategy_id=name)
        log.info("Extracted %d calibration samples", len(samples))

        if len(samples) == 0:
            log.warning("No completed trade cycles found for %s — skipping calibration.", name)
            continue

        # Time-based train/test split
        train_samples, test_samples = time_split(samples, test_frac=args.test_split)
        log.info(
            "Train/test split: %d train, %d test (%.0f%% / %.0f%%)",
            len(train_samples), len(test_samples),
            100 * (1 - args.test_split), 100 * args.test_split,
        )

        train_raw, train_labels = samples_to_arrays(train_samples)
        test_raw, test_labels = samples_to_arrays(test_samples)

        # Fit calibrator on training split
        calibrator = PlattCalibrator.fit(
            raw_confidences=train_raw.tolist(),
            outcome_labels=train_labels.astype(int).tolist(),
            strategy_id=name,
        )

        if not calibrator.is_fitted:
            log.warning(
                "Insufficient training samples (%d < min_samples) for %s — calibrator not fitted.",
                len(train_samples), name,
            )

        # Evaluate on test split (if we have test data)
        report: dict = {
            "strategy": name,
            "n_total_samples": len(samples),
            "n_train": len(train_samples),
            "n_test": len(test_samples),
            "calibrator_fitted": calibrator.is_fitted,
            "calibration_method": calibrator.calibration_method,
        }

        if calibrator.is_fitted and len(test_samples) > 0:
            test_metrics = _evaluate_calibrator(calibrator, test_raw, test_labels, tag="test")
            report.update(test_metrics)
            log.info(
                "Test set — Brier: %.4f → %.4f (Δ=%.4f)  |  ECE: %.4f → %.4f  |  Win rate: %.1f%%",
                test_metrics["brier_score_before"],
                test_metrics["brier_score_after"],
                test_metrics["brier_improvement"],
                test_metrics["ece_before"],
                test_metrics["ece_after"],
                test_metrics["win_rate"] * 100,
            )
        elif calibrator.is_fitted:
            # Evaluate on all samples (no test split possible)
            all_raw, all_labels = samples_to_arrays(samples)
            all_metrics = _evaluate_calibrator(calibrator, all_raw, all_labels, tag="all")
            report.update(all_metrics)

        # Re-fit final calibrator on ALL samples for deployment
        final_calibrator = PlattCalibrator.fit(
            raw_confidences=[s.heuristic_confidence for s in samples],
            outcome_labels=[s.outcome_label for s in samples],
            strategy_id=name,
        )

        saved_path = save_calibrator(
            final_calibrator,
            strategy_id=name,
            models_dir=output_dir,
            training_summary=report,
        )
        log.info("Saved calibrator → %s", saved_path)
        all_reports.append(report)

    # ── Train regime calibrator (optional) ───────────────────────────────
    if args.train_regime_calibrator:
        log.info("=" * 60)
        log.info("Training regime confidence calibrator (horizon=%d bars)…", args.regime_horizon_bars)
        engine = BaselineRegimeEngine()
        regime_signals = engine.classify_dataframe(df)
        regime_cal = RegimeCalibrator.fit(
            regime_signals,
            horizon_bars=args.regime_horizon_bars,
        )

        regime_model_path = output_dir / "regime_calibrator.json"
        with open(regime_model_path, "w") as f:
            json.dump(regime_cal.to_dict(), f, indent=2)
        log.info("Saved regime calibrator → %s", regime_model_path)

        # Log per-label fit status
        for label, cal in regime_cal.calibrators.items():
            status = f"fitted (n={cal.n_samples}, method={cal.calibration_method})" if cal.is_fitted else "NOT fitted (insufficient samples)"
            log.info("  Regime %s: %s", label, status)

    # ── Write summary report ──────────────────────────────────────────────
    report_path = output_dir / "training_report.json"
    with open(report_path, "w") as f:
        json.dump(all_reports, f, indent=2)
    log.info("=" * 60)
    log.info("Training complete. Report → %s", report_path)
    log.info(
        "Fitted %d / %d strategy calibrators.",
        sum(1 for r in all_reports if r.get("calibrator_fitted")),
        len(all_reports),
    )


if __name__ == "__main__":
    main()
