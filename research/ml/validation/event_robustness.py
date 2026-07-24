from __future__ import annotations

"""Deterministic, research-only episode versus event-family comparison."""

from collections import Counter
from hashlib import sha256
import json
import math
from typing import Any, Iterable

import pandas as pd

SPECIFICATION_VERSION = "1"
MEMBERSHIP_REQUIRED_COLUMNS = {
    "family_id", "family_ordinal", "episode_id", "member_ordinal",
    "intrinsic_subtype", "recovery_outcome",
}
FAMILY_REQUIRED_FIELDS = {
    "family_id", "family_ordinal", "episode_ids", "episode_count",
    "intrinsic_subtype_counts", "intrinsic_subtype_mixed",
    "recovery_outcome_counts", "recovery_outcome_mixed",
}


class EventRobustnessValidationError(ValueError):
    """Raised when governed Campaign #42 inputs fail closed validation."""


def _canonical_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ensure_ascii=False,
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _validate_count_map(value: Any, field: str) -> dict[str, int]:
    if not isinstance(value, dict) or not value:
        raise EventRobustnessValidationError(f"{field} must be a non-empty object")
    result: dict[str, int] = {}
    for raw_label, raw_count in value.items():
        label = str(raw_label)
        if not label:
            raise EventRobustnessValidationError(f"{field} contains an empty label")
        if isinstance(raw_count, bool) or not isinstance(raw_count, int) or raw_count <= 0:
            raise EventRobustnessValidationError(
                f"{field}[{label}] must be a positive integer"
            )
        result[label] = raw_count
    return {label: result[label] for label in sorted(result)}


def validate_governed_inputs(
    membership: pd.DataFrame,
    families: Iterable[dict[str, Any]],
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Validate and reconcile Campaign #41 canonical artifacts."""
    missing = MEMBERSHIP_REQUIRED_COLUMNS - set(membership.columns)
    if missing:
        raise EventRobustnessValidationError(
            f"membership missing required columns: {sorted(missing)}"
        )
    if membership.empty:
        raise EventRobustnessValidationError("membership must not be empty")
    if membership["episode_id"].duplicated().any():
        raise EventRobustnessValidationError("membership contains duplicate episode_id")
    if not pd.api.types.is_integer_dtype(membership["episode_id"]):
        raise EventRobustnessValidationError("episode_id must be integer typed")
    if membership[list(MEMBERSHIP_REQUIRED_COLUMNS)].isna().any().any():
        raise EventRobustnessValidationError("membership required fields must be non-null")

    rows = membership.sort_values(
        ["family_ordinal", "member_ordinal", "episode_id"], kind="mergesort"
    ).reset_index(drop=True)
    family_records = list(families)
    if not family_records:
        raise EventRobustnessValidationError("families must not be empty")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for family in sorted(family_records, key=lambda item: int(item["family_ordinal"])):
        missing_fields = FAMILY_REQUIRED_FIELDS - set(family)
        if missing_fields:
            raise EventRobustnessValidationError(
                f"family missing required fields: {sorted(missing_fields)}"
            )
        family_id = str(family["family_id"])
        if not family_id or family_id in seen_ids:
            raise EventRobustnessValidationError("family_id must be unique and non-empty")
        seen_ids.add(family_id)
        episode_ids = [int(value) for value in family["episode_ids"]]
        if len(episode_ids) != int(family["episode_count"]):
            raise EventRobustnessValidationError("family episode_count does not reconcile")
        subtype_counts = _validate_count_map(
            family["intrinsic_subtype_counts"], "intrinsic_subtype_counts"
        )
        recovery_counts = _validate_count_map(
            family["recovery_outcome_counts"], "recovery_outcome_counts"
        )
        if sum(subtype_counts.values()) != len(episode_ids):
            raise EventRobustnessValidationError("subtype counts do not reconcile")
        if sum(recovery_counts.values()) != len(episode_ids):
            raise EventRobustnessValidationError("recovery counts do not reconcile")
        if bool(family["intrinsic_subtype_mixed"]) != (len(subtype_counts) > 1):
            raise EventRobustnessValidationError("intrinsic mixed flag does not reconcile")
        if bool(family["recovery_outcome_mixed"]) != (len(recovery_counts) > 1):
            raise EventRobustnessValidationError("recovery mixed flag does not reconcile")

        members = rows[rows["family_id"].astype(str) == family_id]
        if members["episode_id"].astype(int).tolist() != episode_ids:
            raise EventRobustnessValidationError("family membership order does not reconcile")
        if Counter(members["intrinsic_subtype"].astype(str)) != Counter(subtype_counts):
            raise EventRobustnessValidationError("membership subtype counts disagree")
        if Counter(members["recovery_outcome"].astype(str)) != Counter(recovery_counts):
            raise EventRobustnessValidationError("membership recovery counts disagree")
        normalized.append({
            **family,
            "family_id": family_id,
            "episode_ids": episode_ids,
            "intrinsic_subtype_counts": subtype_counts,
            "recovery_outcome_counts": recovery_counts,
        })

    if set(rows["family_id"].astype(str)) != seen_ids:
        raise EventRobustnessValidationError("membership and family identifiers disagree")
    return rows, normalized


def _label_comparison(
    membership: pd.DataFrame,
    families: list[dict[str, Any]],
    *,
    membership_field: str,
    family_count_field: str,
) -> list[dict[str, Any]]:
    episode_counts = Counter(membership[membership_field].astype(str))
    labels = sorted(episode_counts)
    episode_total = len(membership)
    family_total = len(families)
    records: list[dict[str, Any]] = []
    for label in labels:
        present = sum(label in family[family_count_field] for family in families)
        homogeneous = sum(
            set(family[family_count_field]) == {label} for family in families
        )
        episode_share = episode_counts[label] / episode_total
        presence_share = present / family_total
        homogeneous_share = homogeneous / family_total
        records.append({
            "label": label,
            "episode_count": int(episode_counts[label]),
            "episode_share": float(episode_share),
            "event_family_presence_count": int(present),
            "event_family_presence_share": float(presence_share),
            "event_family_homogeneous_count": int(homogeneous),
            "event_family_homogeneous_share": float(homogeneous_share),
            "presence_minus_episode_share": float(presence_share - episode_share),
            "episode_amplification_ratio": float(episode_counts[label] / present),
        })
    return records


def build_event_robustness(
    membership: pd.DataFrame,
    families: Iterable[dict[str, Any]],
    *,
    source_artifacts: dict[str, str],
    specification_version: str = SPECIFICATION_VERSION,
) -> dict[str, Any]:
    """Build a threshold-free descriptive comparison at both resolutions."""
    if not isinstance(specification_version, str) or not specification_version:
        raise EventRobustnessValidationError("specification_version must be non-empty")
    if not isinstance(source_artifacts, dict) or not source_artifacts:
        raise EventRobustnessValidationError("source_artifacts must be non-empty")
    if any(not isinstance(key, str) or not isinstance(value, str) or not value
           for key, value in source_artifacts.items()):
        raise EventRobustnessValidationError("source_artifacts must map strings to strings")

    rows, family_records = validate_governed_inputs(membership, families)
    payload: dict[str, Any] = {
        "experiment": "core_v1_event_robustness",
        "specification_version": specification_version,
        "research_only": True,
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
        "source_artifacts": dict(sorted(source_artifacts.items())),
        "episode_count": int(len(rows)),
        "event_family_count": int(len(family_records)),
        "counting_rules": {
            "episode_resolution": "each governed episode contributes one label observation",
            "event_family_presence": "each family contributes at most one presence observation per label",
            "event_family_homogeneous": "a family contributes only when exactly one label is present",
            "mixed_family_dominant_label_inference": False,
        },
        "intrinsic_subtype": _label_comparison(
            rows, family_records,
            membership_field="intrinsic_subtype",
            family_count_field="intrinsic_subtype_counts",
        ),
        "recovery_outcome": _label_comparison(
            rows, family_records,
            membership_field="recovery_outcome",
            family_count_field="recovery_outcome_counts",
        ),
        "family_composition": {
            "intrinsic_subtype_homogeneous": sum(
                not bool(family["intrinsic_subtype_mixed"]) for family in family_records
            ),
            "intrinsic_subtype_mixed": sum(
                bool(family["intrinsic_subtype_mixed"]) for family in family_records
            ),
            "recovery_outcome_homogeneous": sum(
                not bool(family["recovery_outcome_mixed"]) for family in family_records
            ),
            "recovery_outcome_mixed": sum(
                bool(family["recovery_outcome_mixed"]) for family in family_records
            ),
        },
    }
    for section in ("intrinsic_subtype", "recovery_outcome"):
        for record in payload[section]:
            for field in (
                "episode_share", "event_family_presence_share",
                "event_family_homogeneous_share", "presence_minus_episode_share",
                "episode_amplification_ratio",
            ):
                if not math.isfinite(record[field]):
                    raise EventRobustnessValidationError(f"non-finite {field}")
    payload["deterministic_digest_sha256"] = _canonical_digest(payload)
    return payload
