"""Extract calibration training samples from BacktestResult objects.

A ``CalibrationSample`` is created for each completed holding cycle
(BUY entry → SELL exit) found in a backtest.  Features come from the
``StrategyIntent.meta`` dict at the entry bar; the label is whether the
equity curve rose from entry to exit.

No-lookahead guarantee: every feature value is taken from ``intent.meta``
at ``buy_bar``.  The outcome is ``equity_curve[sell_bar]`` where
``sell_bar > buy_bar`` by construction — this is a valid supervised label,
not a lookahead into the feature.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


# Avoid circular import: import BacktestResult type hint lazily
_BACKTEST_RESULT_TYPE = Any  # type alias for BacktestResult


# ── Feature extraction ────────────────────────────────────────────────────────

# Feature keys to pull from StrategyIntent.meta — each strategy stores
# different keys; we collect what's present and zero-fill the rest.
_COMMON_FEATURES = [
    "ema_spread",
    "spread_momentum",
    "price_vs_slow_ema",
    "spread_strength",
    # VolatilityBreakout
    "atr_pct",
    "compressed_count",
    "vol_ratio",
    "consolidation_strength",
    # MeanReversion
    "rsi",
    "bb_pos",
    # shared
    "regime_confidence",
]


@dataclass
class CalibrationSample:
    """A single training example for the Platt calibrator.

    Attributes
    ----------
    bar_index : int
        Bar index of the ENTER_LONG signal (BUY trade).
    timestamp : str
        Timestamp string of that bar.
    strategy_id : str
        Strategy that generated this entry signal.
    regime : str
        Regime label at entry bar.
    heuristic_confidence : float
        Raw confidence emitted by the strategy (before calibration).
    features : dict[str, float]
        Indicator values from intent.meta at entry bar.
    outcome_label : int
        1 = winning cycle (equity rose from entry to exit), 0 = losing.
    cycle_return_pct : float
        Percentage return of the equity curve over the cycle.
    """

    bar_index: int
    timestamp: str
    strategy_id: str
    regime: str
    heuristic_confidence: float
    features: dict[str, float] = field(default_factory=dict)
    outcome_label: int = 0
    cycle_return_pct: float = 0.0


def _detect_cycles(trades: list) -> list[tuple[int, int]]:
    """Return list of (entry_bar_index, exit_bar_index) for completed cycles.

    Logic mirrors ``research.harness.metrics._trade_stats`` cycle detection:
    a cycle spans from the first BUY to the closing SELL (the SELL followed
    by either another BUY or end-of-trades).
    """
    sorted_trades = sorted(trades, key=lambda t: t.bar_index)
    cycles: list[tuple[int, int]] = []
    cycle_start: int | None = None

    i = 0
    while i < len(sorted_trades):
        t = sorted_trades[i]
        if t.direction == "BUY" and cycle_start is None:
            cycle_start = t.bar_index
        elif t.direction == "SELL":
            next_is_buy_or_end = (
                i + 1 >= len(sorted_trades)
                or sorted_trades[i + 1].direction == "BUY"
            )
            if next_is_buy_or_end and cycle_start is not None:
                cycles.append((cycle_start, t.bar_index))
                cycle_start = None
        i += 1

    return cycles


def _extract_features(intent_meta: dict, regime_confidence: float) -> dict[str, float]:
    """Build a feature dict from intent.meta + regime confidence."""
    features: dict[str, float] = {}
    for key in _COMMON_FEATURES:
        if key == "regime_confidence":
            features[key] = float(regime_confidence)
        else:
            val = intent_meta.get(key)
            if val is not None:
                try:
                    features[key] = float(val)
                except (TypeError, ValueError):
                    pass
    return features


# ── Public API ────────────────────────────────────────────────────────────────

def extract_calibration_samples(
    result: _BACKTEST_RESULT_TYPE,
    strategy_id: str = "",
) -> list[CalibrationSample]:
    """Extract training samples from a completed BacktestResult.

    Parameters
    ----------
    result :
        ``BacktestResult`` from ``run_backtest()``.  Must have non-empty
        ``trades``, ``intent_series``, and ``equity_curve``.
    strategy_id :
        Override for strategy identifier (default: from result params).

    Returns
    -------
    list[CalibrationSample]
        One sample per completed holding cycle.  Incomplete cycles (position
        still open at end of backtest) are excluded.
    """
    trades = result.trades
    intents = result.intent_series
    equity = result.equity_curve
    regime_series = result.regime_series

    if not trades or not intents or len(equity) == 0:
        return []

    sid = strategy_id or result.params.get("strategy_id", "unknown")

    # Detect completed BUY→SELL cycles
    cycles = _detect_cycles(trades)
    if not cycles:
        return []

    # Build a bar_index → intent lookup for fast access
    intent_by_bar: dict[int, Any] = {}
    for intent in intents:
        # intents are indexed by their position in the intent_series list,
        # which aligns 1-to-1 with the bar loop in backtest_engine.
        pass

    # intent_series[i] corresponds to bar i of the backtest loop.
    # Build bar_index → (intent, regime_label) from the parallel series.
    bar_to_intent: dict[int, Any] = {i: intents[i] for i in range(len(intents))}

    # Build bar_index → regime_confidence from regime_series (pd.Series of RegimeLabel)
    # The regime_series stores labels; confidence requires re-running the engine OR
    # reading from intent.meta["regime"] + sub_signals. We use a simpler approach:
    # extract regime_confidence from the RegimeSignal if stored, else default 0.5.
    # For training purposes the raw confidence is the primary feature; regime_confidence
    # is a secondary feature available from intent.meta if the strategy stored it.

    samples: list[CalibrationSample] = []

    for entry_bar, exit_bar in cycles:
        # Safety: both bars must be in range
        if entry_bar >= len(equity) or exit_bar >= len(equity):
            continue
        if entry_bar >= exit_bar:
            continue

        eq_entry = float(equity.iloc[entry_bar])
        eq_exit = float(equity.iloc[exit_bar])
        if eq_entry <= 0:
            continue

        cycle_return = (eq_exit / eq_entry - 1.0) * 100.0
        outcome_label = 1 if cycle_return > 0.0 else 0

        # Retrieve the intent at the entry bar
        intent = bar_to_intent.get(entry_bar)
        if intent is None:
            continue

        raw_conf = float(intent.confidence)
        meta = intent.meta if intent.meta else {}

        # Regime label at entry bar
        regime_label = ""
        if regime_series is not None and entry_bar < len(regime_series):
            lbl = regime_series.iloc[entry_bar]
            regime_label = str(lbl.value) if hasattr(lbl, "value") else str(lbl)

        # Extract regime_confidence from meta if strategy stored it
        regime_confidence = float(meta.get("regime_confidence", 0.5))

        features = _extract_features(meta, regime_confidence)
        # Always include the raw confidence as a feature
        features["raw_confidence"] = raw_conf

        ts = ""
        try:
            ts = str(equity.index[entry_bar])
        except Exception:
            pass

        samples.append(
            CalibrationSample(
                bar_index=entry_bar,
                timestamp=ts,
                strategy_id=sid,
                regime=regime_label,
                heuristic_confidence=raw_conf,
                features=features,
                outcome_label=outcome_label,
                cycle_return_pct=round(cycle_return, 4),
            )
        )

    return samples


def samples_to_arrays(
    samples: list[CalibrationSample],
) -> tuple[np.ndarray, np.ndarray]:
    """Convert a list of CalibrationSamples to (raw_confidences, labels) arrays.

    Returns
    -------
    (raw_confidences, labels) :
        Shape (n,) arrays suitable for ``PlattCalibrator.fit()``.
    """
    if not samples:
        return np.array([]), np.array([])

    raw_confs = np.array([s.heuristic_confidence for s in samples], dtype=float)
    labels = np.array([s.outcome_label for s in samples], dtype=float)
    return raw_confs, labels


def time_split(
    samples: list[CalibrationSample],
    test_frac: float = 0.30,
) -> tuple[list[CalibrationSample], list[CalibrationSample]]:
    """Split samples into train/test by bar_index (time-ordered, no shuffle).

    Parameters
    ----------
    samples :
        Must be ordered by bar_index (as produced by extract_calibration_samples).
    test_frac :
        Fraction of samples to reserve for testing (taken from the end).

    Returns
    -------
    (train_samples, test_samples)
    """
    if not samples:
        return [], []
    n = len(samples)
    split_idx = max(1, int(n * (1.0 - test_frac)))
    # Sort by bar_index to guarantee temporal ordering
    ordered = sorted(samples, key=lambda s: s.bar_index)
    return ordered[:split_idx], ordered[split_idx:]
