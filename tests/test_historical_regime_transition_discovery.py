from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.ml.validation.historical_regime_transition_discovery import (
    CONTROL_COLUMNS,
    HORIZONS,
    OUTPUT_FILENAMES,
    TRANSITION_COLUMNS,
    FrozenContract,
    SourcePaths,
    STATUS_BINARY,
    STATUS_OVERALL,
    STATUS_PARTITION,
    apply_scaling,
    benjamini_hochberg,
    build_anchor_inventory,
    build_candidate_inventory,
    candidate_id,
    compute_anchor_controls,
    compute_forward_outcomes,
    csv_text,
    development_scaling,
    directional_consistency,
    evaluate_candidates,
    generate_canonical_outputs,
    json_text,
    ols_hc3,
    preflight_sources,
    sha256_file,
    support_failures,
)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _source_frame(rows: int, start: str = "2018-01-01 00:00:00") -> pd.DataFrame:
    timestamps = pd.date_range(start, periods=rows, freq="h")
    index = np.arange(rows, dtype=float)
    close = 100.0 * np.exp(
        0.00015 * index + 0.015 * np.sin(index / 17.0) + 0.004 * np.cos(index / 5.0)
    )
    return pd.DataFrame(
        {
            "timestamp": timestamps.strftime("%Y-%m-%d %H:%M:%S"),
            "open": close * 0.999,
            "high": close * 1.003,
            "low": close * 0.997,
            "close": close,
            "volume": 1000.0 + index,
        }
    )


def _transition_row(
    ordinal: int,
    timestamp: str,
    prior: str,
    current: str,
) -> dict[str, object]:
    transition_id = hashlib.sha256(f"transition-{ordinal}".encode()).hexdigest()
    return {
        "transition_id": transition_id,
        "transition_ordinal": ordinal,
        "anchor_bar_index": ordinal + 1,
        "anchor_timestamp": timestamp.replace(" ", "T"),
        "prior_regime_label": prior,
        "current_regime_label": current,
        "ordered_transition": f"{prior} -> {current}",
        "prior_state_start_timestamp": timestamp.replace(" ", "T"),
        "prior_state_duration_bars": 1,
        "prior_transition_timestamp": "" if ordinal == 0 else timestamp.replace(" ", "T"),
        "spacing_since_prior_transition_bars": "" if ordinal == 0 else 1,
        "spacing_since_prior_transition_hours": "" if ordinal == 0 else 1,
        "current_state_age_bars": 1,
        "anchor_source_row_digest": hashlib.sha256(f"row-{ordinal}".encode()).hexdigest(),
    }


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n")


def _refresh_manifest(
    paths: SourcePaths,
    contract: FrozenContract,
    *,
    manifest_predictive: bool = False,
) -> None:
    manifest = {
        "counts": {
            "transitions": contract.total_transition_count,
            "eligible_transitions": contract.eligible_transition_count,
            "purged_transitions": contract.purged_transition_count,
            "folds": list(contract.partition_counts),
        },
        "feasibility_status": contract.feasibility_status,
        "predictive_outcomes_generated": manifest_predictive,
        "source": {
            "path": "data/btcusd_3600s_2018-01-01_to_2025-12-31.csv",
            "sha256": contract.btc_sha256,
            "byte_count": contract.btc_byte_count,
            "row_count": contract.btc_row_count,
            "first_timestamp": contract.btc_first_timestamp,
            "last_timestamp": contract.btc_last_timestamp,
        },
        "files": {
            "btc_hourly_regime_support_feasibility.json": sha256_file(paths.feasibility),
            "btc_hourly_regime_transitions.csv": sha256_file(paths.transitions),
        },
    }
    _write_text(paths.manifest, json_text(manifest))


def _bundle(
    root: Path,
    *,
    eligible: int = 42,
    partitions: tuple[int, int, int] = (14, 14, 14),
    source_rows: int = 1_500,
    assignment_indices: list[int] | None = None,
) -> tuple[SourcePaths, FrozenContract]:
    source = _source_frame(source_rows)
    btc_path = root / "data/btcusd_3600s_2018-01-01_to_2025-12-31.csv"
    _write_csv(btc_path, source)

    total = eligible + 1
    transition_rows = [
        _transition_row(0, source.loc[1, "timestamp"], "UNKNOWN", "TREND_UP")
    ]
    for index in range(eligible):
        source_index = index + 2
        prior, current = (
            ("RANGE", "TREND_UP")
            if index % 2 == 0
            else ("TREND_DOWN", "VOL_COMPRESSION")
        )
        transition_rows.append(
            _transition_row(index + 1, source.loc[source_index, "timestamp"], prior, current)
        )

    artifact_dir = root / "artifacts/full_historical_regime_state_sequence"
    transitions_path = artifact_dir / "btc_hourly_regime_transitions.csv"
    _write_text(transitions_path, csv_text(transition_rows, TRANSITION_COLUMNS))

    if assignment_indices is None:
        assignment_indices = list(range(1, 1 + sum(partitions)))
    assignments: list[dict[str, object]] = []
    cursor = 0
    for fold, count in enumerate(partitions):
        for row_index in assignment_indices[cursor : cursor + count]:
            row = transition_rows[row_index]
            assignments.append(
                {
                    "anchor_timestamp": row["anchor_timestamp"],
                    "fold": fold,
                    "transition_id": row["transition_id"],
                }
            )
        cursor += count
    feasibility = {
        "status": "CAMPAIGN_45_SOURCE_FEASIBLE",
        "total_transition_count": total,
        "eligible_non_unknown_transition_count": eligible,
        "purged_transition_count": len(assignments),
        "fold_counts": list(partitions),
        "predictive_outcomes_generated": False,
        "fold_assignments": assignments,
    }
    feasibility_path = artifact_dir / "btc_hourly_regime_support_feasibility.json"
    _write_text(feasibility_path, json_text(feasibility))

    paths = SourcePaths(
        manifest=artifact_dir / "btc_hourly_regime_state_manifest.json",
        feasibility=feasibility_path,
        transitions=transitions_path,
        btc=btc_path,
    )
    contract = FrozenContract(
        btc_sha256=sha256_file(btc_path),
        btc_byte_count=btc_path.stat().st_size,
        btc_row_count=source_rows,
        btc_first_timestamp=str(source.loc[0, "timestamp"]),
        btc_last_timestamp=str(source.loc[source_rows - 1, "timestamp"]),
        total_transition_count=total,
        eligible_transition_count=eligible,
        purged_transition_count=len(assignments),
        partition_counts=partitions,
    )
    _refresh_manifest(paths, contract)
    return paths, contract


def test_governed_source_hash_and_count_mismatch_fail_closed(tmp_path: Path) -> None:
    paths, contract = _bundle(tmp_path)
    original = paths.btc.read_bytes()
    paths.btc.write_bytes(original + b"x")
    with pytest.raises(RuntimeError, match="byte-count mismatch"):
        preflight_sources(paths, repo_root=tmp_path, contract=contract)

    paths.btc.write_bytes(original)
    bad_hash = FrozenContract(**{**contract.__dict__, "btc_sha256": "0" * 64})
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        preflight_sources(paths, repo_root=tmp_path, contract=bad_hash)


def test_campaign_46_feasibility_mismatch_fails_closed(tmp_path: Path) -> None:
    paths, contract = _bundle(tmp_path)
    payload = json.loads(paths.feasibility.read_text())
    payload["status"] = "NOT_FEASIBLE"
    _write_text(paths.feasibility, json_text(payload))
    _refresh_manifest(paths, contract)
    with pytest.raises(RuntimeError, match="feasibility mismatch: status"):
        preflight_sources(paths, repo_root=tmp_path, contract=contract)


def test_predictive_outcomes_generated_must_be_false(tmp_path: Path) -> None:
    paths, contract = _bundle(tmp_path)
    _refresh_manifest(paths, contract, manifest_predictive=True)
    with pytest.raises(RuntimeError, match="must be false"):
        preflight_sources(paths, repo_root=tmp_path, contract=contract)


def test_exact_242_purged_anchors_and_81_81_80_partitions_reconcile(
    tmp_path: Path,
) -> None:
    paths, contract = _bundle(
        tmp_path,
        eligible=2_788,
        partitions=(81, 81, 80),
        source_rows=3_000,
        assignment_indices=list(range(1, 243)),
    )
    evidence = preflight_sources(paths, repo_root=tmp_path, contract=contract)
    assert evidence["counts"] == {
        "total_transitions": 2_789,
        "eligible_non_unknown_transitions": 2_788,
        "purged_transitions": 242,
        "partitions": [81, 81, 80],
    }
    assert len(evidence["anchors"]) == 242


def test_unknown_and_self_transitions_are_excluded_from_candidates() -> None:
    anchors = [
        {"prior_regime_label": "UNKNOWN", "current_regime_label": "RANGE"},
        {"prior_regime_label": "RANGE", "current_regime_label": "RANGE"},
        {"prior_regime_label": "RANGE", "current_regime_label": "TREND_UP"},
    ]
    inventory = build_candidate_inventory(anchors)
    assert len(inventory) == 3
    assert {row["ordered_transition"] for row in inventory} == {"RANGE -> TREND_UP"}


def test_duplicate_frozen_anchors_fail_closed(tmp_path: Path) -> None:
    paths, contract = _bundle(tmp_path)
    feasibility = json.loads(paths.feasibility.read_text())
    feasibility["fold_assignments"][1] = dict(feasibility["fold_assignments"][0])
    _write_text(paths.feasibility, json_text(feasibility))
    _refresh_manifest(paths, contract)
    with pytest.raises(RuntimeError, match="duplicate frozen anchor"):
        preflight_sources(paths, repo_root=tmp_path, contract=contract)


def test_exact_timestamp_matching_without_interpolation_or_asof() -> None:
    frame = _source_frame(400)
    frame = frame.drop(index=224).reset_index(drop=True)
    close = pd.Series(
        frame["close"].to_numpy(),
        index=pd.DatetimeIndex(pd.to_datetime(frame["timestamp"])),
    )
    anchor = pd.Timestamp("2018-01-09 08:00:00")
    outcomes, reasons = compute_forward_outcomes(close, anchor)
    assert outcomes[24] is None
    assert reasons[24] == "MISSING_EXACT_HORIZON_TIMESTAMP"
    assert close.get(anchor + pd.Timedelta(hours=23)) is not None
    assert close.get(anchor + pd.Timedelta(hours=25)) is not None


def test_missing_horizon_timestamps_remain_unavailable() -> None:
    frame = _source_frame(250)
    close = pd.Series(
        frame["close"].to_numpy(),
        index=pd.DatetimeIndex(pd.to_datetime(frame["timestamp"])),
    )
    outcomes, reasons = compute_forward_outcomes(
        close, pd.Timestamp(frame.loc[200, "timestamp"])
    )
    assert outcomes[24] is not None
    assert outcomes[72] is None
    assert outcomes[168] is None
    assert reasons[72] == reasons[168] == "MISSING_EXACT_HORIZON_TIMESTAMP"


def test_trailing_controls_use_no_post_anchor_rows() -> None:
    frame = _source_frame(500)
    anchor = pd.Timestamp(frame.loc[250, "timestamp"])
    close = pd.Series(
        frame["close"].to_numpy(),
        index=pd.DatetimeIndex(pd.to_datetime(frame["timestamp"])),
    )
    first, reasons = compute_anchor_controls(close, anchor)
    assert not reasons
    mutated = close.copy()
    mutated.loc[mutated.index > anchor] *= 1000.0
    second, second_reasons = compute_anchor_controls(mutated, anchor)
    assert not second_reasons
    assert first == second


def test_control_calculations_use_exact_windows() -> None:
    frame = _source_frame(400)
    close = pd.Series(
        frame["close"].to_numpy(),
        index=pd.DatetimeIndex(pd.to_datetime(frame["timestamp"])),
    )
    anchor = pd.Timestamp(frame.loc[300, "timestamp"])
    controls, reasons = compute_anchor_controls(close, anchor)
    assert not reasons
    expected_return = math.log(frame.loc[300, "close"] / frame.loc[276, "close"])
    window = np.log(frame.loc[276:300, "close"].to_numpy())
    expected_rv = math.sqrt(float(np.dot(np.diff(window), np.diff(window))))
    assert controls["trailing_log_return_24h"] == pytest.approx(expected_return)
    assert controls["realized_volatility_24h"] == pytest.approx(expected_rv)


def test_development_only_scaling() -> None:
    development = np.arange(60, dtype=float).reshape(10, 6) + np.arange(6)
    evaluation = np.full((5, 6), 1_000_000.0)
    means, stds = development_scaling(development)
    means_after, stds_after = development_scaling(development)
    scaled_eval = apply_scaling(evaluation, means, stds)
    assert np.array_equal(means, means_after)
    assert np.array_equal(stds, stds_after)
    assert np.all(scaled_eval > 1_000)


def test_zero_variance_scaling_fails_closed() -> None:
    development = np.ones((10, 6))
    with pytest.raises(ValueError, match="standard deviation"):
        development_scaling(development)


def _ols_fixture() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = 20
    candidate = np.array([0] * 10 + [1] * 10, dtype=float)
    controls = np.column_stack(
        [
            np.linspace(-2, 2, n),
            np.sin(np.arange(n)),
            np.cos(np.arange(n) / 2),
            (np.arange(n) % 3) - 1,
            np.linspace(1, 3, n) ** 2,
            np.log1p(np.arange(n) + 1),
        ]
    )
    residual = np.array(
        [
            0.01,
            -0.02,
            0.015,
            -0.005,
            0.02,
            -0.01,
            0.005,
            -0.015,
            0.01,
            -0.005,
            0.015,
            -0.02,
            0.01,
            -0.005,
            0.02,
            -0.01,
            0.005,
            -0.015,
            0.01,
            -0.005,
        ]
    )
    outcome = (
        0.3
        + 0.12 * candidate
        + controls @ np.array([0.05, -0.02, 0.03, 0.01, -0.004, 0.02])
        + residual
    )
    return outcome, candidate, controls


def test_ols_coefficient_reconciles_against_frozen_fixture() -> None:
    outcome, candidate, controls = _ols_fixture()
    result = ols_hc3(outcome, candidate, controls)
    assert result.coefficient == pytest.approx(0.13888326596605288, abs=1e-14)
    assert result.rank == 8
    assert result.n_obs == 20


def test_hc3_covariance_reconciles_against_frozen_fixture() -> None:
    outcome, candidate, controls = _ols_fixture()
    result = ols_hc3(outcome, candidate, controls)
    assert result.standard_error == pytest.approx(0.03364156604727464, abs=1e-14)
    assert result.p_value == pytest.approx(3.654178542469978e-05, rel=1e-12)
    assert result.confidence_interval_low == pytest.approx(
        0.07294700812986908, abs=1e-14
    )
    assert result.confidence_interval_high == pytest.approx(
        0.20481952380223667, abs=1e-14
    )


def test_support_gates_and_candidate_present_absent_gates() -> None:
    failures = support_failures(
        overall_present=19,
        partition_present=[5, 5, 4],
        binary_samples={"pooled": [1] * 5 + [0] * 4},
    )
    assert failures == [STATUS_OVERALL, STATUS_PARTITION, STATUS_BINARY]
    assert (
        support_failures(
            overall_present=20,
            partition_present=[5, 5, 5],
            binary_samples={
                "a": [1] * 5 + [0] * 5,
                "b": [1] * 6 + [0] * 7,
            },
        )
        == []
    )


def test_rank_deficient_design_fails_closed() -> None:
    outcome = np.arange(20, dtype=float)
    candidate = np.array([0] * 10 + [1] * 10, dtype=float)
    controls = np.column_stack(
        [candidate]
        + [np.arange(20, dtype=float) ** power for power in range(1, 6)]
    )
    with pytest.raises(np.linalg.LinAlgError, match="rank deficient"):
        ols_hc3(outcome, candidate, controls)


def test_directional_consistency_pass_and_failure_cases() -> None:
    assert directional_consistency(0.1, 0.2, 0.15)
    assert directional_consistency(-0.1, -0.2, -0.15)
    assert not directional_consistency(0.1, -0.2, 0.15)
    assert not directional_consistency(0.0, 0.2, 0.15)
    assert not directional_consistency(None, 0.2, 0.15)


def test_bh_ties_monotonicity_and_unsupported_exclusion() -> None:
    rows = [
        {"candidate_id": "b", "rankable": True, "pooled_p_value": 0.01},
        {"candidate_id": "a", "rankable": True, "pooled_p_value": 0.01},
        {"candidate_id": "c", "rankable": True, "pooled_p_value": 0.03},
        {
            "candidate_id": "unsupported",
            "rankable": False,
            "pooled_p_value": 0.000001,
        },
    ]
    adjusted = benjamini_hochberg(rows)
    assert adjusted == {
        "c": pytest.approx(0.03),
        "b": pytest.approx(0.015),
        "a": pytest.approx(0.015),
    }
    ordered = [adjusted[candidate] for candidate in ("a", "b", "c")]
    assert ordered == sorted(ordered)
    assert "unsupported" not in adjusted
    assert all(0.0 <= value <= 1.0 for value in adjusted.values())


def test_null_fields_and_failure_reasons_remain_visible() -> None:
    anchors = []
    for index in range(15):
        anchors.append(
            {
                "partition": 1 + index // 5,
                "ordered_transition": "RANGE -> TREND_UP",
                **{name: None for name in CONTROL_COLUMNS},
                **{f"forward_log_return_{h}h": None for h in HORIZONS},
            }
        )
    candidates = [
        {
            "candidate_id": candidate_id("RANGE", "TREND_UP", 24),
            "candidate_ordinal": 0,
            "predictor_class": "P-003",
            "prior_regime_label": "RANGE",
            "current_regime_label": "TREND_UP",
            "ordered_transition": "RANGE -> TREND_UP",
            "horizon_hours": 24,
        }
    ]
    results = evaluate_candidates(anchors, candidates)
    assert len(results) == 1
    assert results[0]["rankable"] is False
    assert results[0]["pooled_coefficient"] is None
    assert results[0]["bh_adjusted_q_value"] is None
    assert results[0]["failure_reasons"]


def test_deterministic_candidate_ids_and_ordering() -> None:
    anchors = [
        {"prior_regime_label": "TREND_UP", "current_regime_label": "RANGE"},
        {"prior_regime_label": "RANGE", "current_regime_label": "TREND_UP"},
    ]
    first = build_candidate_inventory(anchors)
    second = build_candidate_inventory(list(reversed(anchors)))
    assert first == second
    assert [row["candidate_ordinal"] for row in first] == list(range(6))
    assert [row["horizon_hours"] for row in first[:3]] == [24, 72, 168]
    assert first[0]["candidate_id"] == candidate_id("RANGE", "TREND_UP", 24)


def test_strict_json_and_lf_only_serialization() -> None:
    text = json_text({"null": None, "finite": 1.25, "negative_zero": -0.0})
    assert text.endswith("\n")
    assert "\r" not in text
    assert "NaN" not in text and "Infinity" not in text
    assert json.loads(text) == {"finite": 1.25, "negative_zero": 0.0, "null": None}
    csv_payload = csv_text([{"x": 1.25, "y": None}], ["x", "y"])
    assert "\r" not in csv_payload
    assert csv_payload.endswith("\n")


def test_anchor_inventory_rejects_duplicate_anchors() -> None:
    frame = _source_frame(500)
    source = {
        "transition_id": "x",
        "anchor_timestamp": frame.loc[250, "timestamp"].replace(" ", "T"),
        "partition": 1,
        "prior_regime_label": "RANGE",
        "current_regime_label": "TREND_UP",
        "ordered_transition": "RANGE -> TREND_UP",
    }
    with pytest.raises(ValueError, match="duplicate"):
        build_anchor_inventory([source, source], frame)


def test_two_run_byte_identical_generation_and_source_immutability(
    tmp_path: Path,
) -> None:
    paths, contract = _bundle(tmp_path / "repo")
    source_hashes_before = {
        path: sha256_file(path)
        for path in (paths.manifest, paths.feasibility, paths.transitions, paths.btc)
    }
    output_one = tmp_path / "repo/artifacts/historical_regime_transitions_run_one"
    output_two = tmp_path / "repo/artifacts/historical_regime_transitions_run_two"
    generate_canonical_outputs(
        paths,
        repo_root=tmp_path / "repo",
        output_dir=output_one,
        contract=contract,
    )
    generate_canonical_outputs(
        paths,
        repo_root=tmp_path / "repo",
        output_dir=output_two,
        contract=contract,
    )
    for name in OUTPUT_FILENAMES:
        assert (output_one / name).read_bytes() == (output_two / name).read_bytes()
    assert source_hashes_before == {
        path: sha256_file(path)
        for path in (paths.manifest, paths.feasibility, paths.transitions, paths.btc)
    }
    for directory in (output_one, output_two):
        for path in directory.iterdir():
            data = path.read_bytes()
            assert b"\r" not in data
            if path.suffix == ".json":
                json.loads(
                    data.decode("utf-8"),
                    parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
                )


def test_preflight_only_runner_never_calls_generation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts/run_historical_regime_transition_discovery.py"
    )
    spec = importlib.util.spec_from_file_location("campaign45_runner_test", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    evidence = {
        "status": "PASS",
        "counts": {
            "total_transitions": 2789,
            "eligible_non_unknown_transitions": 2788,
            "purged_transitions": 242,
            "partitions": [81, 81, 80],
        },
        "source": {
            "path": "data/btc.csv",
            "sha256": "x",
            "byte_count": 1,
            "row_count": 1,
            "first_timestamp": "2018-01-01 00:00:00",
            "last_timestamp": "2018-01-01 00:00:00",
        },
        "campaign_46": {"feasibility_status": "CAMPAIGN_45_SOURCE_FEASIBLE"},
    }
    monkeypatch.setattr(
        module,
        "preflight_sources",
        lambda *args, **kwargs: evidence,
    )
    monkeypatch.setattr(
        module,
        "generate_canonical_outputs",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("generation called")
        ),
    )
    monkeypatch.setattr(sys, "argv", [str(script_path), "--preflight-only"])
    assert module.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["predictive_outcomes_generated"] is False
    assert "forward" not in json.dumps(payload).lower()
