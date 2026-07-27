from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.ml.validation.historical_alpha_discovery import (
    HistoricalAlphaDiscoveryValidationError,
)
import scripts.run_core_v1_historical_alpha_discovery as runner


def _candidate_row() -> dict[str, object]:
    return {
        "descriptor": "collapse_severity",
        "candidate_value": "SEVERE_COLLAPSE",
        "horizon_hours": 2,
        "episode_support": 5,
        "unavailable_episode_count": 0,
        "family_support": 3,
        "mixed_family_count": 0,
        "unavailable_homogeneous_family_count": 0,
        "supported_fold_count": 2,
        "episode_mean_forward_return": 0.01,
        "episode_median_forward_return": 0.01,
        "family_mean_forward_return": 0.02,
        "family_median_forward_return": 0.02,
        "episode_positive_return_rate": 0.6,
        "family_positive_return_rate": 2.0 / 3.0,
        "family_mean_maximum_favorable_excursion": 0.03,
        "family_mean_maximum_adverse_excursion": -0.01,
        "family_mean_realized_volatility": 0.004,
        "training_test_direction_agreement_count": 2,
        "aggregate_direction_agreement_count": 2,
        "episode_family_median_sign_agreement": True,
        "episode_family_median_absolute_divergence": 0.01,
        "evidence_state": "SUPPORTED_ASSOCIATION",
    }


def _fold_row() -> dict[str, object]:
    return {
        "descriptor": "collapse_severity",
        "candidate_value": "SEVERE_COLLAPSE",
        "horizon_hours": 2,
        "fold_id": 0,
        "train_family_support": 2,
        "test_family_support": 1,
        "direction_comparison_supported": True,
        "training_direction": 1,
        "test_direction": 1,
        "aggregate_family_direction": 1,
        "training_test_direction_agree": True,
        "test_aggregate_direction_agree": True,
    }


def _metadata() -> dict[str, object]:
    return {
        "preflight": {},
        "candidate_reconstruction": {"episode_count": 122},
        "descriptor_mixed_family_counts": {},
        "source_hashes": {"btc_hourly": "a" * 64},
    }


def _canonical_payloads() -> dict[str, bytes]:
    payloads = {
        runner.OUTPUT_FILENAMES[0]: b"{}\n",
        runner.OUTPUT_FILENAMES[1]: b"header\nvalue\n",
        runner.OUTPUT_FILENAMES[2]: b"header\nvalue\n",
        runner.OUTPUT_FILENAMES[3]: b"# Report\n",
    }
    manifest = {
        "payload_digest_sha256": "b" * 64,
        "canonical_files": list(runner.OUTPUT_FILENAMES),
    }
    payloads[runner.OUTPUT_FILENAMES[4]] = (
        json.dumps(manifest, sort_keys=True) + "\n"
    ).encode("utf-8")
    return payloads


def test_canonical_bytes_are_deterministic_strict_and_lf_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        runner,
        "_build_results",
        lambda root: ([_candidate_row()], [_fold_row()], _metadata()),
    )

    first = runner.build_canonical_bytes(tmp_path)
    second = runner.build_canonical_bytes(tmp_path)

    assert first == second
    assert tuple(first) == runner.OUTPUT_FILENAMES
    assert all(b"\r" not in content for content in first.values())

    candidates = json.loads(first[runner.OUTPUT_FILENAMES[0]])
    manifest = json.loads(first[runner.OUTPUT_FILENAMES[4]])
    assert candidates["aliases"] == [
        {
            "alias_of": "collapse_severity",
            "descriptor": "activation_ratio_band",
            "ranked_independently": False,
        }
    ]
    assert manifest["generated_timestamp"] is None
    assert manifest["runtime_threshold_order_nav_exposure_changes"] is False
    assert set(manifest["canonical_file_hashes"]) == set(runner.OUTPUT_FILENAMES[:4])


def test_strict_json_rejects_nonfinite_values() -> None:
    with pytest.raises(HistoricalAlphaDiscoveryValidationError, match="nonfinite"):
        runner._json_bytes({"invalid": float("nan")})


def test_publication_requires_new_or_empty_directory_and_is_atomic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payloads = _canonical_payloads()
    monkeypatch.setattr(runner, "build_canonical_bytes", lambda root: payloads)

    output = tmp_path / "artifacts" / "run_one"
    result = runner.publish_canonical(tmp_path, output)
    assert result["file_count"] == len(runner.OUTPUT_FILENAMES)
    assert sorted(path.name for path in output.iterdir()) == sorted(runner.OUTPUT_FILENAMES)
    assert not (output.parent / f".{output.name}.staging").exists()

    with pytest.raises(
        HistoricalAlphaDiscoveryValidationError,
        match="newly created or explicitly empty",
    ):
        runner.publish_canonical(tmp_path, output)


def test_publication_fails_closed_when_staging_directory_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(runner, "build_canonical_bytes", lambda root: _canonical_payloads())
    output = tmp_path / "artifacts" / "run_one"
    staging = output.parent / f".{output.name}.staging"
    staging.mkdir(parents=True)

    with pytest.raises(HistoricalAlphaDiscoveryValidationError, match="staging directory"):
        runner.publish_canonical(tmp_path, output)


def test_replay_verification_detects_any_byte_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payloads = _canonical_payloads()
    monkeypatch.setattr(runner, "build_canonical_bytes", lambda root: payloads)
    reference = tmp_path / "canonical"
    reference.mkdir()
    for filename, content in payloads.items():
        (reference / filename).write_bytes(content)

    result = runner.verify_replay(tmp_path, reference)
    assert result["byte_identical"] is True
    assert result["file_count"] == len(runner.OUTPUT_FILENAMES)

    changed = runner.OUTPUT_FILENAMES[1]
    (reference / changed).write_bytes(payloads[changed] + b"mutation\n")
    with pytest.raises(HistoricalAlphaDiscoveryValidationError, match="byte mismatch"):
        runner.verify_replay(tmp_path, reference)


def test_replay_requires_exact_frozen_file_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payloads = _canonical_payloads()
    monkeypatch.setattr(runner, "build_canonical_bytes", lambda root: payloads)
    reference = tmp_path / "canonical"
    reference.mkdir()
    for filename, content in payloads.items():
        (reference / filename).write_bytes(content)
    (reference / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")

    with pytest.raises(HistoricalAlphaDiscoveryValidationError, match="file set"):
        runner.verify_replay(tmp_path, reference)
