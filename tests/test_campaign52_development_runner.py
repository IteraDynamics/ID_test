from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from research.harness.campaign52_target_replay import TARGET_HEADER, TargetRecord
from scripts.run_campaign52_development import (
    Campaign52DevelopmentRunnerError,
    import_development_targets,
    load_target_csv,
    replay_ready,
    verify_equivalence_root,
)
from scripts.run_campaign52_governed_equivalence import SOURCE_SHA256


def canonical_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def write_target(path: Path, fold: str, sleeve: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(TARGET_HEADER)
        writer.writerow((
            "development",
            fold,
            f"{fold}-01-01T00:00:00Z",
            sleeve,
            "BTC",
            "1H",
            "synthetic",
            "HOLD",
            "0.000000000000",
            "0.250000000000",
            0,
        ))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_equivalence_root(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    root = tmp_path / "equivalence"
    hashes: dict[str, str] = {}
    sleeves = [f"sleeve_{i}" for i in range(9)]
    for fold in ("2020", "2021", "2022"):
        for sleeve in sleeves:
            relative = f"development/{fold}/{sleeve}/targets.csv"
            hashes[relative] = write_target(root / "pass_1" / relative, fold, sleeve)
    manifest = {
        "status": "PASS",
        "campaign": 52,
        "canonical_capture_equal": True,
        "capture_replay_equal": True,
        "independent_passes": 2,
        "counterfactuals_generated": False,
        "performance_metrics_calculated": False,
        "bootstrap_run": False,
        "runtime_modified": False,
        "strategy_modified": False,
        "weights_modified": False,
        "source_sha256": SOURCE_SHA256,
        "artifact_sha256": hashes,
    }
    canonical_json(root / "equivalence_manifest.json", manifest)
    canonical_json(root / "pass_1" / "artifact_sha256.json", hashes)
    canonical_json(root / "pass_2" / "artifact_sha256.json", hashes)
    return root, hashes


def test_equivalence_identity_and_exact_development_import(tmp_path: Path):
    root, expected = make_equivalence_root(tmp_path)
    manifest, hashes = verify_equivalence_root(root)
    assert manifest["status"] == "PASS"
    assert hashes == expected
    imported = import_development_targets(root, hashes)
    assert len(imported) == 27
    assert all(len(records) == 1 for records in imported.values())


def test_target_csv_normalizes_utc_to_naive_without_changing_instant(tmp_path: Path):
    path = tmp_path / "development" / "2020" / "sleeve" / "targets.csv"
    write_target(path, "2020", "sleeve")
    record = load_target_csv(path)[0]
    assert record.timestamp == pd.Timestamp("2020-01-01 00:00:00")
    assert record.timestamp.tzinfo is None


def test_equivalence_hash_map_mismatch_fails_closed(tmp_path: Path):
    root, hashes = make_equivalence_root(tmp_path)
    broken = dict(hashes)
    broken["development/2020/sleeve_0/targets.csv"] = "0" * 64
    canonical_json(root / "pass_2" / "artifact_sha256.json", broken)
    with pytest.raises(Campaign52DevelopmentRunnerError, match="EQUIVALENCE_PASS_HASH_MAP_MISMATCH"):
        verify_equivalence_root(root)


def test_validation_target_path_is_never_opened(tmp_path: Path):
    path = tmp_path / "validation" / "2023" / "sleeve" / "targets.csv"
    path.parent.mkdir(parents=True)
    path.write_text("not even parsed", encoding="utf-8")
    with pytest.raises(Campaign52DevelopmentRunnerError, match="VALIDATION_TARGET_PATH_FORBIDDEN"):
        load_target_csv(path)


def test_import_rejects_missing_development_stream(tmp_path: Path):
    root, hashes = make_equivalence_root(tmp_path)
    reduced = dict(hashes)
    reduced.pop(next(iter(reduced)))
    with pytest.raises(Campaign52DevelopmentRunnerError, match="DEVELOPMENT_TARGET_FILE_COUNT:26"):
        import_development_targets(root, reduced)


def test_replay_normalization_preserves_signed_target_exactly():
    record = TargetRecord(
        stage="development",
        fold="2020",
        timestamp=pd.Timestamp("2020-01-01"),
        sleeve_label="BTC_1H_trend",
        asset="BTC",
        native_timeframe="1H",
        strategy_id="original",
        action="ENTER_LONG",
        desired_exposure_frac=0.75,
        signed_target_exposure=-0.375,
        sequence_number=0,
    )
    normalized = replay_ready([record], "lag_24h")[0]
    assert normalized.signed_target_exposure == -0.375
    assert normalized.action == "HOLD"
    assert normalized.desired_exposure_frac == 0.375
    assert normalized.strategy_id == "campaign52:lag_24h"
