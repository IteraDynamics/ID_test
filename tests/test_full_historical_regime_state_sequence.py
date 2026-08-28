from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from research.ml.validation.full_historical_regime_state_sequence import (
    FROZEN_DEFAULTS,
    allocate_folds,
    build_state_rows,
    build_state_runs,
    build_transitions,
    classify_source,
    json_text,
    purge_transitions,
    support_summary,
    validate_engine,
    validate_ohlcv,
)
from research.regimes.baseline_engine import BaselineRegimeEngine
from research.regimes.contracts import RegimeLabel, RegimeSignal


def sample_df(rows: int = 80) -> pd.DataFrame:
    ts = pd.date_range("2024-01-01", periods=rows, freq="h")
    close = [100.0 + i * 0.1 for i in range(rows)]
    return pd.DataFrame({
        "timestamp": ts,
        "open": close,
        "high": [v + 1 for v in close],
        "low": [v - 1 for v in close],
        "close": close,
        "volume": [1.0] * rows,
    })


def signal(i: int, ts: pd.Timestamp, label: RegimeLabel) -> RegimeSignal:
    warmup = label == RegimeLabel.UNKNOWN
    return RegimeSignal(
        label=label,
        confidence=0.0 if warmup else 0.5,
        bar_index=i,
        timestamp=str(ts),
        sub_signals={"reason": "warmup" if warmup else "test", "atr_pct": 0.02},
    )


def test_validate_engine_defaults_and_labels() -> None:
    validate_engine(BaselineRegimeEngine())
    engine = BaselineRegimeEngine(fast_ema=22)
    with pytest.raises(ValueError, match="defaults mismatch"):
        validate_engine(engine)


def test_validate_ohlcv_and_gap_evidence() -> None:
    df = sample_df(5)
    evidence = validate_ohlcv(df)
    assert evidence["row_count"] == 5
    assert evidence["missing_timestamp_count"] == 0
    df.loc[4, "timestamp"] = pd.Timestamp("2024-01-01 05:00:00")
    evidence = validate_ohlcv(df)
    assert evidence["discontinuity_count"] == 1
    assert evidence["missing_timestamp_count"] == 1


def test_validate_ohlcv_rejects_bad_schema_and_duplicates() -> None:
    df = sample_df(5)
    with pytest.raises(ValueError, match="schema mismatch"):
        validate_ohlcv(df[["timestamp", "open", "high", "low", "volume", "close"]])
    df.loc[4, "timestamp"] = df.loc[3, "timestamp"]
    with pytest.raises(ValueError, match="unique"):
        validate_ohlcv(df)


def test_state_rows_preserve_warmup_and_reconcile() -> None:
    df = sample_df(3)
    signals = [signal(i, df.loc[i, "timestamp"], RegimeLabel.UNKNOWN if i < 2 else RegimeLabel.RANGE) for i in range(3)]
    rows = build_state_rows(df, signals)
    assert rows[0]["is_warmup"] is True
    assert rows[2]["regime_label"] == "RANGE"
    assert all(len(row["source_row_digest"]) == 64 for row in rows)
    bad = list(signals)
    bad[2] = signal(1, df.loc[2, "timestamp"], RegimeLabel.RANGE)
    with pytest.raises(ValueError, match="reconciliation"):
        build_state_rows(df, bad)


def test_runs_and_transitions_reconcile() -> None:
    df = sample_df(6)
    labels = [RegimeLabel.UNKNOWN, RegimeLabel.UNKNOWN, RegimeLabel.RANGE, RegimeLabel.RANGE, RegimeLabel.TREND_UP, RegimeLabel.RANGE]
    states = build_state_rows(df, [signal(i, df.loc[i, "timestamp"], label) for i, label in enumerate(labels)])
    runs = build_state_runs(states)
    transitions = build_transitions(states, runs)
    assert [r["duration_bars"] for r in runs] == [2, 2, 1, 1]
    assert len(transitions) == len(runs) - 1
    assert transitions[0]["ordered_transition"] == "UNKNOWN -> RANGE"
    assert transitions[1]["prior_state_duration_bars"] == 2
    assert transitions[2]["spacing_since_prior_transition_bars"] == 1


def test_greedy_168_hour_purge_and_duplicate_rejection() -> None:
    base = pd.Timestamp("2024-01-01")
    transitions = []
    for i, hour in enumerate([0, 100, 168, 300, 336]):
        transitions.append({
            "transition_id": str(i),
            "anchor_timestamp": (base + pd.Timedelta(hours=hour)).strftime("%Y-%m-%dT%H:%M:%S"),
            "anchor_bar_index": hour,
            "prior_regime_label": "RANGE",
            "current_regime_label": "TREND_UP",
            "ordered_transition": "RANGE -> TREND_UP",
        })
    purged = purge_transitions(transitions)
    assert [r["anchor_bar_index"] for r in purged] == [0, 168, 336]
    transitions[1]["anchor_timestamp"] = transitions[0]["anchor_timestamp"]
    with pytest.raises(ValueError, match="duplicate"):
        purge_transitions(transitions)


def test_fold_allocation_remainder_goes_to_earlier_folds() -> None:
    purged = [{"transition_id": str(i), "anchor_timestamp": f"2024-01-{i+1:02d}T00:00:00"} for i in range(8)]
    folds = allocate_folds(purged)
    assert [sum(1 for row in folds if row["fold"] == i) for i in range(3)] == [3, 3, 2]


def test_support_feasibility_states() -> None:
    transitions = [{
        "transition_id": str(i),
        "anchor_timestamp": f"2024-01-{(i % 28)+1:02d}T00:00:00",
        "prior_regime_label": "RANGE",
        "current_regime_label": "TREND_UP",
        "ordered_transition": "RANGE -> TREND_UP",
    } for i in range(21)]
    short = support_summary(transitions, transitions[:19], allocate_folds(transitions[:19]))
    assert short["status"] == "INSUFFICIENT_OVERALL_SUPPORT"
    feasible = support_summary(transitions, transitions[:21], allocate_folds(transitions[:21]))
    assert feasible["status"] == "CAMPAIGN_45_SOURCE_FEASIBLE"
    assert feasible["predictive_outcomes_generated"] is False


def test_json_is_strict_and_lf_terminated() -> None:
    text = json_text({"x": None, "y": 1.0})
    assert text.endswith("\n")
    assert "NaN" not in text
    assert json.loads(text) == {"x": None, "y": 1.0}


def test_classification_is_deterministic_and_one_to_one() -> None:
    df = sample_df(90)
    first = classify_source(df)
    second = classify_source(df)
    assert first == second
    states, runs, transitions, folds, summary = first
    assert len(states) == len(df)
    assert sum(run["duration_bars"] for run in runs) == len(df)
    assert len(transitions) == max(len(runs) - 1, 0)
    assert summary["predictive_outcomes_generated"] is False
