from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

import pytest

from research.campaign50_equity_breadth import (
    BREADTH_MEMBERS,
    Campaign50Error,
    TARGETS,
    anchor_indices,
    build_predictors,
    candidate_inventory,
    canonical_csv_bytes,
    canonical_json_bytes,
    compatibility_matches,
    confirmation_boundary,
    expected_sign_matches,
    forward_returns,
    holm_adjust,
    load_close_series,
    moving_average,
    ols_hc3,
    support_gate,
)


def synthetic_closes(length: int = 320) -> dict[str, list[float]]:
    result: dict[str, list[float]] = {}
    for index, symbol in enumerate((*TARGETS, *BREADTH_MEMBERS)):
        base = 100.0 + index
        result[symbol] = [base + 0.15 * i + ((i + index) % 7) * 0.01 for i in range(length)]
    return result


def write_source(path: Path, sessions: list[date]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["timestamp", "open", "high", "low", "close", "volume"],
            lineterminator="\n",
        )
        writer.writeheader()
        for index, session in enumerate(sessions):
            close = 100.0 + index
            writer.writerow(
                {
                    "timestamp": session.isoformat(),
                    "open": close,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "volume": 1000,
                }
            )


def test_candidate_inventory_is_exact_and_stable() -> None:
    candidates = candidate_inventory()
    assert len(candidates) == 24
    assert len({candidate.key for candidate in candidates}) == 24
    assert candidates[0].key == "breadth50__SPY__fwd_return_5"
    assert candidates[-1].key == "broad_recovery__QQQ__fwd_return_60"


def test_moving_average_and_forward_returns() -> None:
    assert moving_average([1.0, 2.0, 3.0, 4.0], 3) == [None, None, 2.0, 3.0]
    returns = forward_returns([100.0, 110.0, 121.0], 1)
    assert returns[:2] == pytest.approx([0.1, 0.1])
    assert returns[2] is None


def test_predictor_formulas_produce_expected_domains() -> None:
    closes = synthetic_closes()
    predictors = build_predictors(closes)
    assert set(predictors) == set(TARGETS)
    for target in TARGETS:
        assert set(predictors[target]) == {
            "breadth50",
            "breadth_change20",
            "narrow_strength",
            "broad_recovery",
        }
        finite_breadth = [value for value in predictors[target]["breadth50"] if value is not None]
        assert finite_breadth
        assert all(0.0 <= value <= 1.0 for value in finite_breadth)
        binary = [
            value
            for name in ("narrow_strength", "broad_recovery")
            for value in predictors[target][name]
            if value is not None
        ]
        assert all(value in (0.0, 1.0) for value in binary)


def test_anchor_indices_are_nonoverlapping() -> None:
    sessions = [date(2018, 1, 1) + timedelta(days=i) for i in range(500)]
    anchors = anchor_indices(
        sessions,
        start=sessions[220],
        end=sessions[400],
        horizon=20,
        required_lookback=220,
    )
    assert anchors
    assert all(right - left == 20 for left, right in zip(anchors, anchors[1:]))


def test_ols_hc3_detects_positive_relationship() -> None:
    x = [float(i) for i in range(1, 101)]
    y = [2.0 + 0.5 * value + ((i % 3) - 1) * 0.01 for i, value in enumerate(x)]
    result = ols_hc3(x, y, standardize=True)
    assert result.n == 100
    assert result.beta1 > 0
    assert result.p_value < 0.001
    assert result.ci_low > 0


def test_holm_is_deterministic_and_monotone() -> None:
    adjusted = holm_adjust({"b": 0.02, "a": 0.001, "c": 0.04}, family_size=24)
    assert list(adjusted) == ["a", "b", "c"]
    assert adjusted["a"] <= adjusted["b"] <= adjusted["c"]
    assert adjusted == holm_adjust({"c": 0.04, "a": 0.001, "b": 0.02}, family_size=24)


def test_support_gates_and_sign_rules() -> None:
    status, n, event_n, non_event_n = support_gate(
        "development", "narrow_strength", 20, [1.0] * 7 + [0.0] * 60
    )
    assert status == "INSUFFICIENT_EVENT_SUPPORT"
    assert (n, event_n, non_event_n) == (67, 7, 60)
    assert expected_sign_matches("breadth50", 0.1)
    assert expected_sign_matches("narrow_strength", -0.1)
    assert compatibility_matches(2.0, 0.5)
    assert compatibility_matches(2.0, 8.0)
    assert not compatibility_matches(2.0, 8.1)


def test_canonical_serialization_is_replay_identical() -> None:
    payload = {"b": 2, "a": [3, 1]}
    assert canonical_json_bytes(payload) == canonical_json_bytes(payload)
    rows = [{"b": 2, "a": 1}, {"b": 4, "a": 3}]
    assert canonical_csv_bytes(["a", "b"], rows) == canonical_csv_bytes(["a", "b"], rows)
    assert b"\r\n" not in canonical_csv_bytes(["a", "b"], rows)


def test_discovery_loader_rejects_holdout_before_return(tmp_path: Path) -> None:
    source = tmp_path / "SPY_1D.csv"
    write_source(source, [date(2024, 12, 31), date(2025, 1, 2)])
    with pytest.raises(Campaign50Error, match="HOLDOUT_ACCESS_VIOLATION"):
        load_close_series(source)


def test_confirmation_boundary_always_fails_closed() -> None:
    with pytest.raises(Campaign50Error, match="HOLDOUT_ACCESS_VIOLATION"):
        confirmation_boundary()
