from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.ml.validation.historical_regime_structure_discovery import (
    CONTROL_COLUMNS,
    OUTPUT_FILENAMES,
    PREDICTORS,
    STATUS_SUPPORT,
    STATUS_UNSEEN,
    benjamini_hochberg,
    candidate_inventory,
    controls_at,
    csv_text,
    evaluate_candidates,
    json_text,
    ols_hc3,
    outcome_at,
    partition_counts,
    structural_predictors,
    write_lf,
)


def _btc(hours: int = 500) -> pd.DataFrame:
    timestamps = pd.date_range("2020-01-01", periods=hours, freq="h")
    close = np.exp(np.linspace(math.log(100.0), math.log(180.0), hours))
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": close,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": np.arange(hours, dtype=float),
    })


def _states(hours: int = 500, switch: int = 250) -> pd.DataFrame:
    timestamps = pd.date_range("2020-01-01", periods=hours, freq="h")
    labels = ["TREND_UP" if i < switch else "RANGE" for i in range(hours)]
    return pd.DataFrame({
        "bar_index": np.arange(hours),
        "timestamp": timestamps,
        "regime_label": labels,
    })


def _runs() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "state_run_id": "run_0",
            "state_run_ordinal": 0,
            "regime_label": "TREND_UP",
            "start_bar_index": 0,
            "end_bar_index": 249,
            "start_timestamp": pd.Timestamp("2020-01-01 00:00:00"),
            "end_timestamp": pd.Timestamp("2020-01-11 09:00:00"),
            "duration_bars": 250,
        },
        {
            "state_run_id": "run_1",
            "state_run_ordinal": 1,
            "regime_label": "RANGE",
            "start_bar_index": 250,
            "end_bar_index": 499,
            "start_timestamp": pd.Timestamp("2020-01-11 10:00:00"),
            "end_timestamp": pd.Timestamp("2020-01-21 19:00:00"),
            "duration_bars": 250,
        },
    ])


def _transitions() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "transition_id": "transition_0",
            "transition_ordinal": 0,
            "anchor_timestamp": pd.Timestamp("2020-01-11 10:00:00"),
        }
    ])


def test_candidate_inventory_is_frozen_and_deterministic() -> None:
    rows = candidate_inventory()
    assert len(rows) == 72
    assert rows[0]["candidate_id"] == f"{PREDICTORS[0]}__R__24h"
    assert rows[-1]["candidate_id"] == f"{PREDICTORS[-1]}__S__168h"
    assert len({row["candidate_id"] for row in rows}) == 72


@pytest.mark.parametrize(
    ("total", "expected"),
    [(0, (0, 0, 0)), (1, (1, 0, 0)), (2, (1, 1, 0)), (8, (3, 3, 2))],
)
def test_partition_counts_assign_remainder_to_earlier_partitions(
    total: int, expected: tuple[int, int, int]
) -> None:
    assert partition_counts(total) == expected


def test_controls_use_exact_168_hour_window() -> None:
    btc = _btc(300)
    result = controls_at(btc, btc.iloc[200]["timestamp"])
    assert result is not None
    assert tuple(result) == CONTROL_COLUMNS
    assert all(math.isfinite(value) for value in result.values())


def test_controls_fail_when_exact_hour_is_missing() -> None:
    btc = _btc(300).drop(index=100).reset_index(drop=True)
    assert controls_at(btc, pd.Timestamp("2020-01-09 08:00:00")) is None


def test_structural_predictor_age_and_previous_duration_conventions() -> None:
    result = structural_predictors(
        pd.Timestamp("2020-01-11 10:00:00"), 250, _runs(), _transitions()
    )
    assert result["log1p_current_state_age_hours"] == 0.0
    assert result["log1p_previous_state_duration_hours"] == pytest.approx(math.log1p(250))
    assert result["log1p_hours_since_previous_transition"] == 0.0


def test_transition_counts_are_left_open_right_closed() -> None:
    transitions = pd.DataFrame({
        "anchor_timestamp": [
            pd.Timestamp("2020-01-08 10:00:00"),
            pd.Timestamp("2020-01-10 10:00:00"),
            pd.Timestamp("2020-01-11 10:00:00"),
        ]
    })
    result = structural_predictors(
        pd.Timestamp("2020-01-11 10:00:00"), 250, _runs(), transitions
    )
    assert result["transition_count_trailing_24h"] == 1.0
    assert result["transition_count_trailing_72h"] == 2.0
    assert result["transition_count_trailing_168h"] == 3.0


def test_directional_and_magnitude_outcomes() -> None:
    btc = _btc(300)
    states = _states(300)
    timestamp = pd.Timestamp("2020-01-05 00:00:00")
    directional = outcome_at(btc, states, timestamp, "R", 24)
    magnitude = outcome_at(btc, states, timestamp, "M", 24)
    assert directional is not None and directional > 0
    assert magnitude == abs(directional)


def test_realized_volatility_requires_every_exact_hour() -> None:
    btc = _btc(300).drop(index=110).reset_index(drop=True)
    states = _states(300)
    assert outcome_at(btc, states, pd.Timestamp("2020-01-05 00:00:00"), "V", 24) is None


def test_survival_requires_uninterrupted_same_label() -> None:
    btc = _btc(300)
    states = _states(300, switch=110)
    timestamp = pd.Timestamp("2020-01-05 00:00:00")
    assert outcome_at(btc, states, timestamp, "S", 12) == 0.0


def test_return_to_original_label_is_not_survival() -> None:
    btc = _btc(300)
    states = _states(300)
    states.loc[101, "regime_label"] = "RANGE"
    timestamp = pd.Timestamp("2020-01-05 00:00:00")
    assert outcome_at(btc, states, timestamp, "S", 12) == 0.0


def test_ols_hc3_reconciles_synthetic_coefficient() -> None:
    predictor = np.linspace(-2.0, 2.0, 40)
    control = np.sin(np.linspace(0.0, 3.0, 40))
    x = np.column_stack([np.ones(40), predictor, control])
    y = 0.4 + 1.75 * predictor - 0.2 * control + 0.01 * np.cos(np.arange(40))
    result = ols_hc3(x, y)
    assert result.coefficient == pytest.approx(1.75, abs=5e-3)
    assert result.standard_error > 0
    assert 0 <= result.p_value <= 1
    assert result.rank == 3


def test_ols_rejects_rank_deficient_design() -> None:
    x = np.column_stack([np.ones(20), np.arange(20), np.arange(20)])
    with pytest.raises(ValueError, match="RANK_DEFICIENT_DESIGN"):
        ols_hc3(x, np.arange(20, dtype=float))


def test_bh_is_deterministic_and_monotone() -> None:
    adjusted = benjamini_hochberg({"b": 0.02, "a": 0.01, "c": 0.20})
    assert adjusted["a"] == pytest.approx(0.03)
    assert adjusted["b"] == pytest.approx(0.03)
    assert adjusted["c"] == pytest.approx(0.20)


def _anchor_rows(count: int = 90) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(count):
        partition = 1 + index // 30
        row: dict[str, object] = {
            "partition": partition,
            "current_regime": "RANGE" if index % 2 else "TREND_UP",
        }
        for offset, column in enumerate(CONTROL_COLUMNS):
            row[column] = math.sin(index / (4.0 + offset)) + index * 0.001 * (offset + 1)
        for offset, predictor in enumerate(PREDICTORS):
            row[predictor] = math.cos(index / (5.0 + offset)) + index * 0.002 * (offset + 1)
        for family in ("R", "M", "V", "S"):
            for horizon in (24, 72, 168):
                base = float(row[PREDICTORS[0]])
                row[f"outcome_{family}_{horizon}h"] = base * 0.1 + math.sin(index / 7.0) * 0.01
        rows.append(row)
    return rows


def test_insufficient_support_candidate_remains_visible() -> None:
    candidate = candidate_inventory()[0]
    results = evaluate_candidates(_anchor_rows(30), [candidate])
    assert len(results) == 1
    assert results[0]["rankable"] is False
    assert results[0]["status"] == STATUS_SUPPORT
    assert results[0]["bh_adjusted_q_value"] is None


def test_unseen_evaluation_regime_fails_closed() -> None:
    anchors = _anchor_rows()
    for index, row in enumerate(anchors):
        if index >= 60:
            row["current_regime"] = "HIGH_VOL"
    result = evaluate_candidates(anchors, [candidate_inventory()[0]])[0]
    assert result["rankable"] is False
    assert result["status"] == STATUS_UNSEEN


def test_family_specific_bh_does_not_cross_families(monkeypatch: pytest.MonkeyPatch) -> None:
    anchors = _anchor_rows()
    candidates = [candidate_inventory()[0], candidate_inventory()[3]]
    results = evaluate_candidates(anchors, candidates)
    assert {row["outcome_family"] for row in results} == {"R", "M"}
    assert all(row["bh_adjusted_q_value"] is not None for row in results if row["rankable"])


def test_json_and_csv_are_lf_only_and_strict(tmp_path: Path) -> None:
    json_payload = json_text({"b": 2, "a": 1, "missing": float("nan")})
    csv_payload = csv_text([{"a": 1, "b": None}], ["a", "b"])
    assert "\r" not in json_payload
    assert "\r" not in csv_payload
    assert json.loads(json_payload)["missing"] is None
    target = tmp_path / "output.json"
    write_lf(target, json_payload)
    assert b"\r" not in target.read_bytes()


def test_canonical_output_names_are_exact() -> None:
    assert len(OUTPUT_FILENAMES) == 10
    assert OUTPUT_FILENAMES[0] == "regime_structure_source_manifest.json"
    assert OUTPUT_FILENAMES[-1] == "regime_structure_manifest.json"
