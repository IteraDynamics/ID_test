from __future__ import annotations

"""Build deterministic, research-only historical event-family artifacts."""

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from research.ml.validation.historical_event_families import (
    CANONICAL_BAR_CADENCE,
    SPECIFICATION_VERSION,
    EventFamilyValidationError,
    build_event_families,
    reconcile_source_and_classified,
    validate_prediction_timestamps,
)
from research.ml.validation.historical_regime_taxonomy import classify_episodes

STREAM = "btc_extended_up"
ARTIFACT_ROOT = Path("artifacts/core_v1_historical_event_families")
PREDICTION_SHA256 = "36b6ffcc9e993f4869dd8f75cde13e7058e101949a577bd24c84e79e58f1dca7"
PREDICTION_ROWS = 52453
PREDICTION_FIRST = "2020-01-01 01:00:00"
PREDICTION_LAST = "2025-12-26 00:00:00"

OUTPUT_FILENAMES = (
    f"{STREAM}_event_family_membership.csv",
    f"{STREAM}_event_families.json",
    f"{STREAM}_event_family_summary.json",
    f"{STREAM}_event_family_report.md",
    f"{STREAM}_event_family_manifest.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic Core v1 historical event families.",
    )
    parser.add_argument("--historical-json", required=True)
    parser.add_argument("--historical-episodes", required=True)
    parser.add_argument("--episode-signatures", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--bar-cadence", required=True)
    return parser.parse_args()


def _sha256_path(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_identifier(path: Path) -> str:
    resolved = path.resolve()
    root = REPOSITORY_ROOT.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise EventFamilyValidationError(
            f"governed source must be inside repository: {path}"
        ) from exc


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)


def _strict_json(value: Any) -> str:
    return json.dumps(
        value,
        indent=2,
        sort_keys=True,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ": "),
    ) + "\n"


def _write_lf(path: Path, text: str) -> None:
    if "\r" in text:
        raise EventFamilyValidationError("generated text contains carriage returns")
    path.write_text(text, encoding="utf-8", newline="\n")


def _read_boolean_series(values: pd.Series) -> pd.Series:
    parsed = values.astype(str).str.strip().str.lower().map({"true": True, "false": False})
    if parsed.isna().any():
        raise EventFamilyValidationError("could not parse recovered_without_retraining")
    return parsed.astype(bool)


def _load_prediction_timestamps(path: Path) -> pd.Index:
    frame = pd.read_csv(path, index_col=0)
    return validate_prediction_timestamps(frame.index.tolist(), bar_cadence=CANONICAL_BAR_CADENCE)


def _source_record(path: Path, row_count: int) -> dict[str, Any]:
    return {
        "artifact": _repo_identifier(path),
        "sha256": _sha256_path(path),
        "row_count": int(row_count),
    }


def _sorted_counts(values: list[Any]) -> dict[str, int]:
    counts = Counter(str(value) for value in values)
    return {key: counts[key] for key in sorted(counts)}


def _build_summary(
    membership: pd.DataFrame,
    families: list[dict[str, Any]],
    source_artifacts: dict[str, str],
) -> dict[str, Any]:
    subtype_totals: Counter[str] = Counter()
    recovery_totals: Counter[str] = Counter()
    for family in families:
        subtype_totals.update(family["intrinsic_subtype_counts"])
        recovery_totals.update(family["recovery_outcome_counts"])

    summary: dict[str, Any] = {
        "experiment": "core_v1_historical_event_families",
        "specification_version": SPECIFICATION_VERSION,
        "research_only": True,
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
        "configuration": {"bar_cadence": CANONICAL_BAR_CADENCE},
        "source_artifacts": dict(sorted(source_artifacts.items())),
        "source_episode_count": int(len(membership)),
        "event_family_count": int(len(families)),
        "family_size_distribution": _sorted_counts(
            [family["episode_count"] for family in families]
        ),
        "intrinsic_subtype_family_composition": {
            "homogeneous": sum(not family["intrinsic_subtype_mixed"] for family in families),
            "mixed": sum(family["intrinsic_subtype_mixed"] for family in families),
        },
        "recovery_outcome_family_composition": {
            "homogeneous": sum(not family["recovery_outcome_mixed"] for family in families),
            "mixed": sum(family["recovery_outcome_mixed"] for family in families),
        },
        "intrinsic_subtype_episode_totals": {
            key: subtype_totals[key] for key in sorted(subtype_totals)
        },
        "recovery_outcome_episode_totals": {
            key: recovery_totals[key] for key in sorted(recovery_totals)
        },
    }
    canonical = json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False)
    summary["deterministic_digest_sha256"] = sha256(canonical.encode("utf-8")).hexdigest()
    return summary


def _build_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Core v1 Historical Event Families",
        "",
        "## Scope",
        "",
        "This is a deterministic, research-only, observation-only interval rollup.",
        "No runtime, threshold, model, order, NAV, exposure, or dashboard behavior changed.",
        "",
        "## Results",
        "",
        f"- Source episode rows: {summary['source_episode_count']}",
        f"- Event families: {summary['event_family_count']}",
        f"- Canonical cadence: {summary['configuration']['bar_cadence']}",
        f"- Deterministic summary digest: `{summary['deterministic_digest_sha256']}`",
        "",
        "## Interpretation controls",
        "",
        "Episode rows are dependent rolling-window observations.",
        "Event-family counts are deterministic interval rollups and are not proof of statistical independence.",
        "One-bar adjacency is configuration-governed and larger missing-bar gaps are preserved.",
        "Recovery outcomes remain bounded-horizon descriptions rather than forecasts.",
        "",
        "## Family-size distribution",
        "",
    ]
    for size, count in summary["family_size_distribution"].items():
        lines.append(f"- {size} episode(s): {count} family/families")
    lines.extend(["", "## Composition", ""])
    subtype = summary["intrinsic_subtype_family_composition"]
    recovery = summary["recovery_outcome_family_composition"]
    lines.extend(
        [
            f"- Intrinsic subtype homogeneous families: {subtype['homogeneous']}",
            f"- Intrinsic subtype mixed families: {subtype['mixed']}",
            f"- Recovery homogeneous families: {recovery['homogeneous']}",
            f"- Recovery mixed families: {recovery['mixed']}",
            "",
        ]
    )
    return "\n".join(lines)


def _validate_output_directory(out_dir: Path, source_paths: tuple[Path, ...]) -> tuple[Path, bool]:
    resolved_root = (REPOSITORY_ROOT / ARTIFACT_ROOT).resolve()
    resolved_out = out_dir.resolve()
    try:
        resolved_out.relative_to(resolved_root)
    except ValueError as exc:
        raise EventFamilyValidationError(
            f"out-dir must be inside {ARTIFACT_ROOT.as_posix()}"
        ) from exc

    existed_empty = False
    if resolved_out.exists():
        if not resolved_out.is_dir() or any(resolved_out.iterdir()):
            raise EventFamilyValidationError("out-dir must be newly created or explicitly empty")
        existed_empty = True

    output_paths = {resolved_out / name for name in OUTPUT_FILENAMES}
    source_resolved = {path.resolve() for path in source_paths}
    if output_paths & source_resolved:
        raise EventFamilyValidationError("refusing to overwrite a governed source artifact")
    return resolved_out, existed_empty


def _reconcile_outputs(
    membership: pd.DataFrame,
    families: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    if len(membership) != summary["source_episode_count"]:
        raise EventFamilyValidationError("membership and summary episode counts disagree")
    if len(families) != summary["event_family_count"]:
        raise EventFamilyValidationError("family records and summary counts disagree")
    if membership["episode_id"].duplicated().any():
        raise EventFamilyValidationError("membership contains duplicate episode identities")
    family_ids = [family["family_id"] for family in families]
    if set(membership["family_id"]) != set(family_ids):
        raise EventFamilyValidationError("membership and family identifiers disagree")
    for family in families:
        members = membership[membership["family_id"] == family["family_id"]]
        if members["episode_id"].tolist() != family["episode_ids"]:
            raise EventFamilyValidationError("family membership order does not reconcile")


def run(args: argparse.Namespace) -> dict[str, Any]:
    historical_json_path = Path(args.historical_json)
    episodes_path = Path(args.historical_episodes)
    signatures_path = Path(args.episode_signatures)
    predictions_path = Path(args.predictions)
    source_paths = (
        historical_json_path,
        episodes_path,
        signatures_path,
        predictions_path,
    )
    for path in source_paths:
        _require_file(path)

    if args.bar_cadence != CANONICAL_BAR_CADENCE:
        raise EventFamilyValidationError(
            f"Campaign #41 requires canonical cadence {CANONICAL_BAR_CADENCE}"
        )

    out_dir, existed_empty = _validate_output_directory(Path(args.out_dir), source_paths)
    staging = out_dir.parent / f".{out_dir.name}.staging"
    if staging.exists():
        raise EventFamilyValidationError(f"staging directory already exists: {staging}")

    source_hashes_before = {path: _sha256_path(path) for path in source_paths}
    if source_hashes_before[predictions_path] != PREDICTION_SHA256:
        raise EventFamilyValidationError("governed prediction source SHA-256 mismatch")

    historical = json.loads(historical_json_path.read_text(encoding="utf-8"))
    config = historical.get("config")
    if not isinstance(config, dict):
        raise EventFamilyValidationError("historical JSON missing config object")

    source_episodes = pd.read_csv(episodes_path)
    episodes_for_classification = source_episodes.copy(deep=True)
    episodes_for_classification.insert(
        0, "episode_id", range(len(episodes_for_classification))
    )
    episodes_for_classification["recovered_without_retraining"] = _read_boolean_series(
        episodes_for_classification["recovered_without_retraining"]
    )
    source_for_reconciliation = source_episodes.copy(deep=True)
    source_for_reconciliation["recovered_without_retraining"] = _read_boolean_series(
        source_for_reconciliation["recovered_without_retraining"]
    )

    signatures = pd.read_csv(signatures_path, index_col="episode_id")
    signatures.index = signatures.index.astype(int)
    classified = classify_episodes(
        episodes_for_classification,
        signatures,
        collapse_ratio=float(config["collapse_ratio"]),
        observation_rows=int(config["observation_rows"]),
    )
    reconciled = reconcile_source_and_classified(source_for_reconciliation, classified)

    prediction_timestamps = _load_prediction_timestamps(predictions_path)
    if len(prediction_timestamps) != PREDICTION_ROWS:
        raise EventFamilyValidationError("governed prediction row count mismatch")
    if str(prediction_timestamps[0]) != PREDICTION_FIRST:
        raise EventFamilyValidationError("governed prediction first timestamp mismatch")
    if str(prediction_timestamps[-1]) != PREDICTION_LAST:
        raise EventFamilyValidationError("governed prediction last timestamp mismatch")

    membership, families = build_event_families(
        reconciled,
        prediction_timestamps=prediction_timestamps,
        source_artifact=_repo_identifier(episodes_path),
        bar_cadence=CANONICAL_BAR_CADENCE,
    )
    source_identifiers = {
        "historical_json": _repo_identifier(historical_json_path),
        "historical_episodes": _repo_identifier(episodes_path),
        "episode_signatures": _repo_identifier(signatures_path),
        "predictions": _repo_identifier(predictions_path),
    }
    summary = _build_summary(membership, families, source_identifiers)
    _reconcile_outputs(membership, families, summary)

    staging.mkdir(parents=False, exist_ok=False)
    try:
        membership_path = staging / OUTPUT_FILENAMES[0]
        families_path = staging / OUTPUT_FILENAMES[1]
        summary_path = staging / OUTPUT_FILENAMES[2]
        report_path = staging / OUTPUT_FILENAMES[3]
        manifest_path = staging / OUTPUT_FILENAMES[4]

        membership.to_csv(
            membership_path,
            index=False,
            lineterminator="\n",
            float_format="%.17g",
        )
        _write_lf(families_path, _strict_json(families))
        _write_lf(summary_path, _strict_json(summary))
        _write_lf(report_path, _build_report(summary))

        primary_outputs = {
            path.name: {"sha256": _sha256_path(path)}
            for path in (membership_path, families_path, summary_path, report_path)
        }
        source_rows = {
            historical_json_path: 1,
            episodes_path: len(source_episodes),
            signatures_path: len(signatures),
            predictions_path: len(prediction_timestamps),
        }
        manifest = {
            "experiment": "core_v1_historical_event_families",
            "specification_version": SPECIFICATION_VERSION,
            "canonical_bar_cadence": CANONICAL_BAR_CADENCE,
            "research_only": True,
            "observation_only": True,
            "runtime_integration_allowed": False,
            "exposure_mutation_allowed": False,
            "source_episode_count": len(membership),
            "event_family_count": len(families),
            "source_timestamp_evidence": {
                "first": PREDICTION_FIRST,
                "last": PREDICTION_LAST,
                "row_count": PREDICTION_ROWS,
                "timezone_convention": "timezone-naive",
                "duplicate_timestamps": 0,
                "strictly_increasing": True,
                "larger_gaps_preserved": True,
            },
            "sources": {
                key: _source_record(path, source_rows[path])
                for key, path in sorted(
                    {
                        "historical_json": historical_json_path,
                        "historical_episodes": episodes_path,
                        "episode_signatures": signatures_path,
                        "predictions": predictions_path,
                    }.items()
                )
            },
            "outputs": dict(sorted(primary_outputs.items())),
            "manifest_filename": manifest_path.name,
            "replay_verification_status": "pending_second_run",
        }
        _write_lf(manifest_path, _strict_json(manifest))

        for path in staging.iterdir():
            if path.read_bytes().find(b"\r") != -1:
                raise EventFamilyValidationError(f"generated artifact is not LF-only: {path.name}")

        source_hashes_after = {path: _sha256_path(path) for path in source_paths}
        if source_hashes_before != source_hashes_after:
            raise EventFamilyValidationError("governed source mutation detected")

        if existed_empty:
            out_dir.rmdir()
        os.replace(staging, out_dir)
        return manifest
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def main() -> None:
    manifest = run(parse_args())
    print("Core v1 historical event-family artifacts complete")
    print(f"Episodes: {manifest['source_episode_count']}")
    print(f"Families: {manifest['event_family_count']}")
    print("Observation only: no runtime, threshold, order, NAV, or exposure changed.")


if __name__ == "__main__":
    main()
