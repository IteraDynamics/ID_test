from __future__ import annotations

"""Campaign #44 governed preflight, canonical generation, and replay verification."""

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Iterable, Mapping

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

from research.ml.validation.alpha_surface_discovery import (
    AlphaSurfaceDiscoveryValidationError,
    SCORE_DIMENSIONS,
    frozen_surface_inventory,
    rank_surfaces,
    validate_inventory,
)

DEFAULT_OUTPUT_DIR = "artifacts/alpha_surface_discovery"
OUTPUT_FILENAMES: tuple[str, ...] = (
    "alpha_surface_inventory.json",
    "alpha_surface_inventory.csv",
    "alpha_research_priorities.json",
    "alpha_research_priorities.csv",
    "alpha_research_roadmap.md",
    "alpha_surface_discovery_manifest.json",
)
INVENTORY_CSV_FIELDS: tuple[str, ...] = (
    "surface_id",
    "surface_name",
    "surface_class",
    "repository_sources",
    "governance_state",
    "anchor_availability",
    "leakage_state",
    "observation_unit",
    "independence_unit",
    "available_observation_count",
    "available_independence_count",
    "historical_span_start",
    "historical_span_end",
    "asset_scope",
    "candidate_horizons",
    "existing_evidence_state",
    "known_overlap_or_redundancy",
    "data_readiness_state",
    "estimated_implementation_complexity",
    "falsification_path",
    "portfolio_relevance_hypothesis",
    "notes",
    "rankable",
    "non_rankable_reasons",
    "scores",
)
PRIORITY_CSV_FIELDS: tuple[str, ...] = (
    "rank",
    "surface_id",
    "surface_name",
    "total_score",
    *SCORE_DIMENSIONS,
    "estimated_implementation_complexity",
    "falsification_path",
    "portfolio_relevance_hypothesis",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Campaign #44 governed preflight, generation, or replay verification."
    )
    parser.add_argument("--repository-root", default=str(REPOSITORY_ROOT))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--generate", action="store_true")
    mode.add_argument("--verify-replay", metavar="CANONICAL_DIR")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def sha256_path(path: Path) -> str:
    from research.artifact_io.v1 import sha256_file_v1
    return sha256_file_v1(path, chunk_size=1048576, factory=sha256)


def _repository_path(root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise AlphaSurfaceDiscoveryValidationError(
            f"repository source must be repository-relative: {relative_path}"
        )
    path = root / relative
    if not path.is_file():
        raise AlphaSurfaceDiscoveryValidationError(
            f"missing cited repository source: {relative_path}"
        )
    return path


def governed_preflight(root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Validate the frozen inventory and every cited source without reading outcomes."""
    inventory = validate_inventory(frozen_surface_inventory())
    source_hashes: dict[str, str] = {}
    for row in inventory:
        for relative_path in row["repository_sources"]:
            if relative_path not in source_hashes:
                source_hashes[relative_path] = sha256_path(
                    _repository_path(root, relative_path)
                )
    return inventory, dict(sorted(source_hashes.items()))


def _json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode(
        "utf-8"
    )


def _csv_bytes(rows: Iterable[Mapping[str, Any]], fields: tuple[str, ...]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for source in rows:
        row: dict[str, Any] = {}
        for field in fields:
            value = source.get(field, "")
            if isinstance(value, (dict, list, tuple)):
                value = _json_text(value)
            elif isinstance(value, bool):
                value = "true" if value else "false"
            row[field] = value
        writer.writerow(row)
    return stream.getvalue().encode("utf-8")


def _roadmap_text(
    inventory: list[dict[str, Any]], priorities: list[dict[str, Any]]
) -> bytes:
    non_rankable = [row for row in inventory if not row["rankable"]]
    top = priorities[0]
    lines = [
        "# Campaign #44 Alpha Research Roadmap",
        "",
        "## Governance",
        "",
        "This roadmap ranks research programs, not trading signals.",
        "It contains no new predictive-return calculation and makes no production, strategy, threshold, signal, order, portfolio, NAV, exposure, or execution recommendation.",
        "",
        "## Inventory reconciliation",
        "",
        f"- Inventory surfaces: {len(inventory)}",
        f"- Rankable surfaces: {len(priorities)}",
        f"- Non-rankable surfaces: {len(non_rankable)}",
        "- Registered Campaign #43 candidate A-001 rows: 1",
        "",
        "## Ranked research priorities",
        "",
        "| Rank | Surface | Total | Independent support | Uniqueness | Falsifiability | Portfolio relevance | Complexity |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in priorities:
        lines.append(
            "| {rank} | {surface_id} — {surface_name} | {total_score} | "
            "{independent_support_potential} | {uniqueness} | {falsifiability} | "
            "{portfolio_relevance} | {estimated_implementation_complexity} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Recommended finite next campaign",
            "",
            f"**Selected surface:** {top['surface_id']} — {top['surface_name']}",
            "",
            "**Immediate objective:** Freeze and test a finite inventory of anchor-local historical regime states and transitions for incremental association with forward BTC outcomes, using deterministic event-family or chronologically separated independence controls.",
            "",
            f"**Falsification path:** {top['falsification_path']}",
            "",
            "**Required data:** Existing governed historical regime configuration and episode artifacts; the governed BTC hourly close source; a pre-registered anchor-local field inventory; exact outcome horizons; independence rules; chronological folds; and simple BTC price-state controls.",
            "",
            "**Acceptance evidence:** Frozen sources, candidate fields, anchors, outcomes, horizons, independence rules, folds, support gates, null visibility, deterministic canonical outputs, and byte-identical replay established before predictive result inspection.",
            "",
            "**Authorization boundary:** Observation-only historical research. No runtime integration, model training or replacement, threshold, signal, strategy, intent, order, execution, portfolio, NAV, exposure, dashboard, or production change is authorized.",
            "",
            "## Registered candidate retained",
            "",
            "Campaign #43 Candidate A-001 remains a preliminary collapse-structure association requiring later independent falsification. Its overlapping severe-collapse and intrinsic-subtype rows are represented once and do not receive duplicated Research Expected Value credit.",
            "",
            "## Visible non-rankable surfaces",
            "",
        ]
    )
    for row in non_rankable:
        reasons = "; ".join(row["non_rankable_reasons"])
        lines.append(f"- `{row['surface_id']}` {row['surface_name']}: {reasons}.")
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def build_outputs(root: Path) -> dict[str, bytes]:
    inventory, source_hashes = governed_preflight(root)
    priorities = rank_surfaces(inventory)
    outputs: dict[str, bytes] = {
        "alpha_surface_inventory.json": _canonical_json(inventory),
        "alpha_surface_inventory.csv": _csv_bytes(inventory, INVENTORY_CSV_FIELDS),
        "alpha_research_priorities.json": _canonical_json(priorities),
        "alpha_research_priorities.csv": _csv_bytes(priorities, PRIORITY_CSV_FIELDS),
        "alpha_research_roadmap.md": _roadmap_text(inventory, priorities),
    }
    output_hashes = {
        name: sha256(payload).hexdigest() for name, payload in sorted(outputs.items())
    }
    manifest = {
        "campaign": "44",
        "classification": "deterministic observation-only alpha-surface inventory and research prioritization",
        "new_predictive_returns_generated": False,
        "inventory_surface_count": len(inventory),
        "rankable_surface_count": len(priorities),
        "non_rankable_surface_count": sum(not row["rankable"] for row in inventory),
        "registered_candidate_a_001_count": sum(
            row["surface_id"] == "S-001" for row in inventory
        ),
        "source_sha256": source_hashes,
        "output_sha256_excluding_manifest": output_hashes,
        "ranking_dimensions": list(SCORE_DIMENSIONS),
        "authorization_boundary": {
            "runtime_changes": False,
            "model_training_or_replacement": False,
            "threshold_or_signal_changes": False,
            "strategy_or_intent_changes": False,
            "orders_or_execution": False,
            "portfolio_construction": False,
            "nav_or_exposure_changes": False,
            "dashboard_changes": False,
        },
    }
    outputs["alpha_surface_discovery_manifest.json"] = _canonical_json(manifest)
    return outputs


def write_outputs(output_dir: Path, outputs: Mapping[str, bytes]) -> None:
    if set(outputs) != set(OUTPUT_FILENAMES):
        raise AlphaSurfaceDiscoveryValidationError(
            "generated output inventory does not match frozen filenames"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_FILENAMES:
        (output_dir / name).write_bytes(outputs[name])


def verify_lf_only(outputs: Mapping[str, bytes]) -> None:
    for name, payload in outputs.items():
        if b"\r" in payload:
            raise AlphaSurfaceDiscoveryValidationError(
                f"canonical text output is not LF-only: {name}"
            )
        if not payload.endswith(b"\n"):
            raise AlphaSurfaceDiscoveryValidationError(
                f"canonical text output lacks terminal LF: {name}"
            )


def replay_digest(outputs: Mapping[str, bytes]) -> str:
    digest = sha256()
    for name in OUTPUT_FILENAMES:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(outputs[name])
    return digest.hexdigest()


def verify_replay(root: Path, canonical_dir: Path) -> str:
    outputs = build_outputs(root)
    verify_lf_only(outputs)
    for name in OUTPUT_FILENAMES:
        canonical_path = canonical_dir / name
        if not canonical_path.is_file():
            raise AlphaSurfaceDiscoveryValidationError(
                f"missing canonical replay file: {canonical_path}"
            )
        if canonical_path.read_bytes() != outputs[name]:
            raise AlphaSurfaceDiscoveryValidationError(
                f"replay mismatch for canonical output: {name}"
            )
    return replay_digest(outputs)


def main() -> int:
    args = parse_args()
    root = Path(args.repository_root).resolve()
    try:
        if args.preflight_only:
            inventory, source_hashes = governed_preflight(root)
            print(
                json.dumps(
                    {
                        "preflight": "passed",
                        "inventory_surfaces": len(inventory),
                        "cited_sources": len(source_hashes),
                        "new_predictive_returns_generated": False,
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.generate:
            outputs = build_outputs(root)
            verify_lf_only(outputs)
            output_dir = root / args.output_dir
            if output_dir.exists():
                shutil.rmtree(output_dir)
            write_outputs(output_dir, outputs)
            print(
                json.dumps(
                    {
                        "generation": "passed",
                        "output_dir": str(output_dir),
                        "replay_digest": replay_digest(outputs),
                        "new_predictive_returns_generated": False,
                    },
                    sort_keys=True,
                )
            )
            return 0
        digest = verify_replay(root, Path(args.verify_replay).resolve())
        print(json.dumps({"replay": "passed", "replay_digest": digest}, sort_keys=True))
        return 0
    except (AlphaSurfaceDiscoveryValidationError, OSError, ValueError) as exc:
        print(f"Campaign #44 failed closed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
