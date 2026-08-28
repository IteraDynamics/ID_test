from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


CANONICAL_FILES = (
    "campaign50_preflight.json",
    "campaign50_candidate_inventory.csv",
    "campaign50_development_results.csv",
    "campaign50_validation_results.csv",
    "campaign50_shortlist.csv",
    "campaign50_stage_manifest.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def verify_replay_identity(run1: Path, run2: Path) -> list[dict[str, Any]]:
    if not run1.is_dir() or not run2.is_dir():
        raise ValueError("REPLAY_DIRECTORY_MISSING")
    names1 = sorted(path.name for path in run1.iterdir() if path.is_file())
    names2 = sorted(path.name for path in run2.iterdir() if path.is_file())
    if tuple(names1) != tuple(sorted(CANONICAL_FILES)):
        raise ValueError("RUN1_CANONICAL_FILESET_FAILURE")
    if names1 != names2:
        raise ValueError("REPLAY_FILESET_MISMATCH")

    records: list[dict[str, Any]] = []
    for name in names1:
        path1 = run1 / name
        path2 = run2 / name
        record = {
            "name": name,
            "run1_byte_count": path1.stat().st_size,
            "run2_byte_count": path2.stat().st_size,
            "run1_sha256": sha256_file(path1),
            "run2_sha256": sha256_file(path2),
        }
        record["byte_identical"] = (
            record["run1_byte_count"] == record["run2_byte_count"]
            and record["run1_sha256"] == record["run2_sha256"]
        )
        if not record["byte_identical"]:
            raise ValueError(f"REPLAY_IDENTITY_FAILURE: {name}")
        records.append(record)
    return records


def build_review(run1: Path, run2: Path) -> dict[str, Any]:
    replay = verify_replay_identity(run1, run2)
    preflight = json.loads((run1 / "campaign50_preflight.json").read_text(encoding="utf-8"))
    manifest = json.loads((run1 / "campaign50_stage_manifest.json").read_text(encoding="utf-8"))
    development = read_csv(run1 / "campaign50_development_results.csv")
    validation = read_csv(run1 / "campaign50_validation_results.csv")
    shortlist = read_csv(run1 / "campaign50_shortlist.csv")

    development_counts = Counter(row["status"] for row in development)
    validation_counts = Counter(row["status"] for row in validation)

    return {
        "review_type": "campaign50_development_validation_read_only",
        "status": "PASS",
        "replay_identity": replay,
        "candidate_count": len(development),
        "development_status_counts": dict(sorted(development_counts.items())),
        "validation_status_counts": dict(sorted(validation_counts.items())),
        "shortlist_count": len(shortlist),
        "shortlist": shortlist,
        "manifest_summary": {
            "repository_commit_sha": manifest.get("repository_commit_sha"),
            "execution_go_commit_sha": manifest.get("execution_go_commit_sha"),
            "support_gate_amendment_commit_sha": manifest.get(
                "support_gate_amendment_commit_sha"
            ),
            "discovery_supported_count": manifest.get("discovery_supported_count"),
            "validation_supported_count": manifest.get("validation_supported_count"),
            "shortlist_count": manifest.get("shortlist_count"),
            "holdout_loaded": manifest.get("holdout_loaded"),
            "confirmation_enabled": manifest.get("confirmation_enabled"),
            "method_mutation": manifest.get("method_mutation"),
        },
        "preflight_summary": {
            "status": preflight.get("status"),
            "candidate_count": preflight.get("candidate_count"),
            "holdout_loaded": preflight.get("holdout_loaded"),
            "confirmation_enabled": preflight.get("confirmation_enabled"),
            "method_mutation": preflight.get("method_mutation"),
        },
        "holdout_loaded": False,
        "confirmation_enabled": False,
        "artifacts_modified": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only review of Campaign 50 development/validation replays."
    )
    parser.add_argument("--run1", required=True)
    parser.add_argument("--run2", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    review = build_review(Path(args.run1), Path(args.run2))
    print(json.dumps(review, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
