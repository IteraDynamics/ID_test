from __future__ import annotations

"""Generate deterministic Campaign #42 event-robustness artifacts."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
from typing import Any

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from research.ml.validation.event_robustness import (
    EventRobustnessValidationError,
    build_event_robustness,
)

STREAM = "btc_extended_up"
ARTIFACT_ROOT = Path("artifacts/core_v1_event_robustness")
OUTPUT_FILENAMES = (
    f"{STREAM}_event_robustness.json",
    f"{STREAM}_event_robustness_labels.csv",
    f"{STREAM}_event_robustness_report.md",
    f"{STREAM}_event_robustness_manifest.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare Core v1 taxonomy at episode and event-family resolution."
    )
    parser.add_argument("--event-families", required=True)
    parser.add_argument("--event-family-membership", required=True)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def _sha256_path(path: Path) -> str:
    from research.artifact_io.v1 import sha256_file_v1
    return sha256_file_v1(path, chunk_size=1048576, factory=sha256)


def _repo_identifier(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPOSITORY_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise EventRobustnessValidationError(
            f"governed source must be inside repository: {path}"
        ) from exc


def _strict_json(value: Any) -> str:
    from research.artifact_io.v1 import strict_json_text_v1
    return strict_json_text_v1(value)


def _write_lf(path: Path, text: str) -> None:
    if "\r" in text:
        raise EventRobustnessValidationError("generated text contains carriage returns")
    path.write_text(text, encoding="utf-8", newline="\n")


def _validate_output_directory(out_dir: Path, source_paths: tuple[Path, ...]) -> tuple[Path, bool]:
    resolved_root = (REPOSITORY_ROOT / ARTIFACT_ROOT).resolve()
    resolved_out = out_dir.resolve()
    try:
        resolved_out.relative_to(resolved_root)
    except ValueError as exc:
        raise EventRobustnessValidationError(
            f"out-dir must be inside {ARTIFACT_ROOT.as_posix()}"
        ) from exc
    existed_empty = False
    if resolved_out.exists():
        if not resolved_out.is_dir() or any(resolved_out.iterdir()):
            raise EventRobustnessValidationError("out-dir must be newly created or explicitly empty")
        existed_empty = True
    outputs = {resolved_out / name for name in OUTPUT_FILENAMES}
    if outputs & {path.resolve() for path in source_paths}:
        raise EventRobustnessValidationError("refusing to overwrite a governed source artifact")
    return resolved_out, existed_empty


def _label_rows(result: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for dimension in ("intrinsic_subtype", "recovery_outcome"):
        for record in result[dimension]:
            rows.append({"dimension": dimension, **record})
    columns = [
        "dimension", "label", "episode_count", "episode_share",
        "event_family_presence_count", "event_family_presence_share",
        "event_family_homogeneous_count", "event_family_homogeneous_share",
        "presence_minus_episode_share", "episode_amplification_ratio",
    ]
    return pd.DataFrame(rows, columns=columns)


def _report(result: dict[str, Any]) -> str:
    lines = [
        "# Core v1 Episode vs Event-Family Taxonomy",
        "",
        "## Scope",
        "",
        "Deterministic, replay-safe, research-only, and observation-only comparison.",
        "No runtime, model-training, threshold, order, NAV, exposure, or dashboard behavior changed.",
        "",
        "## Governed counts",
        "",
        f"- Episodes: {result['episode_count']}",
        f"- Event families: {result['event_family_count']}",
        f"- Deterministic digest: `{result['deterministic_digest_sha256']}`",
        "",
        "## Counting interpretation",
        "",
        "Episode share counts every governed rolling-window episode.",
        "Event-family presence counts each label at most once per family.",
        "Event-family homogeneous share counts only families containing exactly one label.",
        "Mixed families remain mixed; no dominant label is inferred.",
        "",
    ]
    composition = result["family_composition"]
    lines.extend([
        "## Family composition",
        "",
        f"- Intrinsic-subtype homogeneous families: {composition['intrinsic_subtype_homogeneous']}",
        f"- Intrinsic-subtype mixed families: {composition['intrinsic_subtype_mixed']}",
        f"- Recovery-outcome homogeneous families: {composition['recovery_outcome_homogeneous']}",
        f"- Recovery-outcome mixed families: {composition['recovery_outcome_mixed']}",
        "",
    ])
    for title, key in (("Intrinsic subtype", "intrinsic_subtype"), ("Recovery outcome", "recovery_outcome")):
        lines.extend([f"## {title}", ""])
        for record in result[key]:
            lines.append(
                f"- `{record['label']}`: episodes {record['episode_count']} "
                f"({record['episode_share']:.6f}); family presence "
                f"{record['event_family_presence_count']} "
                f"({record['event_family_presence_share']:.6f}); homogeneous families "
                f"{record['event_family_homogeneous_count']} "
                f"({record['event_family_homogeneous_share']:.6f}); amplification "
                f"{record['episode_amplification_ratio']:.6f}"
            )
        lines.append("")
    lines.extend([
        "## Limits",
        "",
        "These are descriptive counts, not predictive estimates or statistical-independence claims.",
        "Only 14 governed event families are available, so the artifact does not assign confidence labels, significance, or alpha conclusions.",
        "",
    ])
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    families_path = Path(args.event_families)
    membership_path = Path(args.event_family_membership)
    source_paths = (families_path, membership_path)
    for path in source_paths:
        if not path.is_file():
            raise FileNotFoundError(path)

    out_dir, existed_empty = _validate_output_directory(Path(args.out_dir), source_paths)
    staging = out_dir.parent / f".{out_dir.name}.staging"
    if staging.exists():
        raise EventRobustnessValidationError(f"staging directory already exists: {staging}")

    source_hashes_before = {path: _sha256_path(path) for path in source_paths}
    membership = pd.read_csv(membership_path)
    families = json.loads(families_path.read_text(encoding="utf-8"))
    if not isinstance(families, list):
        raise EventRobustnessValidationError("event-families artifact must be a JSON array")

    source_artifacts = {
        "event_families": _repo_identifier(families_path),
        "event_family_membership": _repo_identifier(membership_path),
    }
    result = build_event_robustness(
        membership, families, source_artifacts=source_artifacts
    )
    labels = _label_rows(result)

    staging.mkdir(parents=False, exist_ok=False)
    try:
        result_path = staging / OUTPUT_FILENAMES[0]
        labels_path = staging / OUTPUT_FILENAMES[1]
        report_path = staging / OUTPUT_FILENAMES[2]
        manifest_path = staging / OUTPUT_FILENAMES[3]

        _write_lf(result_path, _strict_json(result))
        labels.to_csv(labels_path, index=False, lineterminator="\n")
        _write_lf(report_path, _report(result))

        manifest = {
            "experiment": "core_v1_event_robustness",
            "research_only": True,
            "observation_only": True,
            "runtime_integration_allowed": False,
            "exposure_mutation_allowed": False,
            "source_artifacts": {
                key: {
                    "artifact": source_artifacts[key],
                    "sha256": source_hashes_before[path],
                }
                for key, path in (
                    ("event_families", families_path),
                    ("event_family_membership", membership_path),
                )
            },
            "outputs": {
                path.name: {"sha256": _sha256_path(path)}
                for path in (result_path, labels_path, report_path)
            },
        }
        _write_lf(manifest_path, _strict_json(manifest))

        source_hashes_after = {path: _sha256_path(path) for path in source_paths}
        if source_hashes_before != source_hashes_after:
            raise EventRobustnessValidationError("governed source artifact changed during run")
        if out_dir.exists() and existed_empty:
            out_dir.rmdir()
        staging.replace(out_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return result


def main() -> int:
    run(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
