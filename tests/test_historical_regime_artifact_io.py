from __future__ import annotations

from research.ml.validation.historical_regime_artifact_io import (
    normalize_artifact_identifier,
    stable_artifact_identifier,
    write_text_lf,
)


def test_artifact_identifier_normalizes_path_separators() -> None:
    assert normalize_artifact_identifier(
        r"artifacts\taxonomy\summary.json"
    ) == "artifacts/taxonomy/summary.json"
    assert normalize_artifact_identifier(
        "artifacts/taxonomy/summary.json"
    ) == "artifacts/taxonomy/summary.json"


def test_artifact_identifier_is_repository_relative(tmp_path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    artifact_path = repository_root / "artifacts" / "taxonomy" / "summary.json"

    assert stable_artifact_identifier(
        artifact_path,
        repository_root,
    ) == "artifacts/taxonomy/summary.json"


def test_write_text_lf_uses_portable_newlines(tmp_path) -> None:
    output_path = tmp_path / "report.md"
    write_text_lf(output_path, "first\nsecond\n")

    assert output_path.read_bytes() == b"first\nsecond\n"
