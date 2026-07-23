from __future__ import annotations

"""Deterministic, research-only construction of historical event families."""

from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import PurePosixPath
from typing import Any, Iterable

import numpy as np
import pandas as pd

SPECIFICATION_VERSION = "1"
SOURCE_REQUIRED_COLUMNS = {
    "window_start", "window_end", "reference_activation_rate",
    "observation_activation_rate", "activation_ratio",
    "feature_cosine_similarity_to_latest", "recovered_without_retraining",
    "recovery_rows",
}
CLASSIFIED_REQUIRED_COLUMNS = SOURCE_REQUIRED_COLUMNS | {
    "episode_id", "collapse_severity", "feature_displacement",
    "volatility_state", "recovery_outcome",
}
MEMBERSHIP_COLUMNS = [
    "family_id", "family_ordinal", "episode_id", "member_ordinal",
    "window_start", "window_end", "intrinsic_subtype",
    "recovery_outcome", "feature_cosine_similarity_to_latest",
]


class EventFamilyValidationError(ValueError):
    """Raised when governed event-family input fails closed validation."""


def _finite_float(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise EventFamilyValidationError(f"{field} must be numeric") from exc
    if not math.isfinite(result):
        raise EventFamilyValidationError(f"{field} must be finite")
    return result


def _canonical_source_artifact(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EventFamilyValidationError("source_artifact must be a non-empty string")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        raise EventFamilyValidationError("source_artifact must be repository-relative")
    canonical = path.as_posix()
    if canonical in {"", "."}:
        raise EventFamilyValidationError("source_artifact must identify a file")
    return canonical


def _canonical_timestamp(value: pd.Timestamp) -> str:
    return value.isoformat(timespec="seconds")


def _parse_timestamp(value: Any, field: str, position: Any) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise EventFamilyValidationError(
            f"malformed {field} timestamp at {position}"
        ) from exc
    if pd.isna(timestamp):
        raise EventFamilyValidationError(f"malformed {field} timestamp at {position}")
    return timestamp


def _validate_uniform_timezone(values: Iterable[pd.Timestamp], field: str) -> bool:
    awareness = {value.tzinfo is not None for value in values}
    if len(awareness) != 1:
        raise EventFamilyValidationError(f"mixed timezone convention in {field}")
    return awareness.pop()


def parse_bar_cadence(value: str | pd.Timedelta) -> tuple[pd.Timedelta, str]:
    """Validate an explicit cadence and return duration plus canonical ISO form."""
    if value is None or (isinstance(value, str) and not value.strip()):
        raise EventFamilyValidationError("bar_cadence is required and may not be inferred")
    try:
        cadence = pd.Timedelta(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise EventFamilyValidationError("bar_cadence must be a valid duration") from exc
    if cadence <= pd.Timedelta(0):
        raise EventFamilyValidationError("bar_cadence must be positive")
    if cadence.value % 1_000_000_000 != 0:
        raise EventFamilyValidationError("bar_cadence must be an exact whole-second duration")
    seconds = int(cadence.total_seconds())
    if seconds % 3600 == 0:
        canonical = f"PT{seconds // 3600}H"
    elif seconds % 60 == 0:
        canonical = f"PT{seconds // 60}M"
    else:
        canonical = f"PT{seconds}S"
    return cadence, canonical


def validate_prediction_timestamps(
    timestamps: Iterable[Any], *, bar_cadence: str | pd.Timedelta
) -> pd.Index:
    """Validate the governed prediction index without filling missing bars."""
    cadence, _ = parse_bar_cadence(bar_cadence)
    parsed = [
        _parse_timestamp(value, "prediction", f"position {position}")
        for position, value in enumerate(timestamps)
    ]
    if not parsed:
        raise EventFamilyValidationError("prediction timestamp index must not be empty")
    _validate_uniform_timezone(parsed, "prediction timestamp index")
    index = pd.Index(parsed)
    if index.has_duplicates:
        raise EventFamilyValidationError("duplicate prediction timestamps")
    if not index.is_monotonic_increasing:
        raise EventFamilyValidationError("prediction timestamps must be strictly increasing")
    for prior, current in zip(parsed, parsed[1:]):
        delta = current - prior
        if delta <= pd.Timedelta(0):
            raise EventFamilyValidationError("prediction timestamps must be strictly increasing")
        if delta.value % cadence.value != 0:
            raise EventFamilyValidationError(
                "prediction timestamp deltas must be positive integer multiples of bar_cadence"
            )
    return index


def insert_episode_ids(source_episodes: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with zero-based identity from persisted source row order."""
    missing = SOURCE_REQUIRED_COLUMNS - set(source_episodes.columns)
    if missing:
        raise EventFamilyValidationError(
            f"source episodes missing required columns: {sorted(missing)}"
        )
    if "episode_id" in source_episodes.columns:
        raise EventFamilyValidationError("source episodes must not contain persisted episode_id")
    result = source_episodes.copy(deep=True)
    result.insert(0, "episode_id", np.arange(len(result), dtype=np.int64))
    return result


def reconcile_source_and_classified(
    source_episodes: pd.DataFrame, classified_episodes: pd.DataFrame
) -> pd.DataFrame:
    """Reconcile classified rows exactly to source rows and inserted identities."""
    source = insert_episode_ids(source_episodes)
    missing = CLASSIFIED_REQUIRED_COLUMNS - set(classified_episodes.columns)
    if missing:
        raise EventFamilyValidationError(
            f"classified episodes missing required columns: {sorted(missing)}"
        )
    if classified_episodes["episode_id"].duplicated().any():
        raise EventFamilyValidationError("duplicate episode identifiers")
    if not pd.api.types.is_integer_dtype(classified_episodes["episode_id"]):
        raise EventFamilyValidationError("episode identifiers must be integers")
    if set(source["episode_id"]) != set(classified_episodes["episode_id"]) or len(source) != len(classified_episodes):
        raise EventFamilyValidationError("source and classified episode identities must match exactly")

    classified = classified_episodes.set_index("episode_id", drop=False)
    for row in source.to_dict(orient="records"):
        episode_id = int(row["episode_id"])
        candidate = classified.loc[episode_id]
        for field, expected in row.items():
            actual = candidate[field]
            if pd.isna(expected) and pd.isna(actual):
                continue
            equal = expected == actual
            if isinstance(equal, (np.ndarray, pd.Series, list)):
                equal = bool(np.asarray(equal).all())
            if not bool(equal):
                raise EventFamilyValidationError(
                    f"governed field disagreement for episode {episode_id}: {field}"
                )
    return classified_episodes.copy(deep=True)


def _sorted_counts(values: Iterable[str]) -> dict[str, int]:
    counts = Counter(str(value) for value in values)
    return {key: counts[key] for key in sorted(counts)}


def _digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ensure_ascii=False,
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _validated_rows(classified: pd.DataFrame) -> pd.DataFrame:
    missing = CLASSIFIED_REQUIRED_COLUMNS - set(classified.columns)
    if missing:
        raise EventFamilyValidationError(
            f"classified episodes missing required columns: {sorted(missing)}"
        )
    if classified.empty:
        raise EventFamilyValidationError("classified episodes must not be empty")
    if classified["episode_id"].duplicated().any():
        raise EventFamilyValidationError("duplicate episode identifiers")
    if not pd.api.types.is_integer_dtype(classified["episode_id"]):
        raise EventFamilyValidationError("episode identifiers must be integers")

    rows = classified.copy(deep=True)
    starts = [
        _parse_timestamp(value, "window_start", f"row {index}")
        for index, value in rows["window_start"].items()
    ]
    ends = [
        _parse_timestamp(value, "window_end", f"row {index}")
        for index, value in rows["window_end"].items()
    ]
    _validate_uniform_timezone(starts + ends, "episode boundaries")
    rows["_window_start"] = pd.Series(starts, index=rows.index, dtype=object)
    rows["_window_end"] = pd.Series(ends, index=rows.index, dtype=object)
    if any(end < start for start, end in zip(starts, ends)):
        raise EventFamilyValidationError("window_end must not precede window_start")

    label_fields = (
        "collapse_severity", "feature_displacement", "volatility_state",
        "recovery_outcome",
    )
    for field in label_fields:
        if rows[field].isna().any() or (rows[field].astype(str).str.len() == 0).any():
            raise EventFamilyValidationError(f"{field} must be non-null and non-empty")
    rows["_similarity"] = [
        _finite_float(value, "feature_cosine_similarity_to_latest")
        for value in rows["feature_cosine_similarity_to_latest"]
    ]
    rows["_intrinsic_subtype"] = (
        rows["collapse_severity"].astype(str) + "__"
        + rows["feature_displacement"].astype(str) + "__"
        + rows["volatility_state"].astype(str)
    )
    return rows


def build_event_families(
    classified_episodes: pd.DataFrame,
    *,
    prediction_timestamps: Iterable[Any],
    source_artifact: str,
    bar_cadence: str | pd.Timedelta,
    specification_version: str = SPECIFICATION_VERSION,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Build canonical family membership and records without side effects."""
    if not isinstance(specification_version, str) or not specification_version:
        raise EventFamilyValidationError("specification_version must be a non-empty string")
    cadence, canonical_cadence = parse_bar_cadence(bar_cadence)
    prediction_index = validate_prediction_timestamps(
        prediction_timestamps, bar_cadence=cadence
    )
    source_identifier = _canonical_source_artifact(source_artifact)
    rows = _validated_rows(classified_episodes)

    prediction_aware = prediction_index[0].tzinfo is not None
    episode_aware = rows.iloc[0]["_window_start"].tzinfo is not None
    if prediction_aware != episode_aware:
        raise EventFamilyValidationError(
            "episode and prediction timestamps must use the same timezone convention"
        )
    prediction_set = set(prediction_index.tolist())
    for row in rows.to_dict(orient="records"):
        start, end, episode_id = row["_window_start"], row["_window_end"], int(row["episode_id"])
        if start not in prediction_set or end not in prediction_set:
            raise EventFamilyValidationError(
                f"episode {episode_id} boundary absent from governed prediction index"
            )
        if (end - start).value % cadence.value != 0:
            raise EventFamilyValidationError(
                f"episode {episode_id} duration is not aligned to bar_cadence"
            )

    rows = rows.sort_values(
        ["_window_start", "_window_end", "episode_id"], kind="mergesort"
    ).reset_index(drop=True)
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_end: pd.Timestamp | None = None
    for row in rows.to_dict(orient="records"):
        start, end = row["_window_start"], row["_window_end"]
        if current and current_end is not None and start > current_end + cadence:
            groups.append(current)
            current, current_end = [], None
        current.append(row)
        current_end = end if current_end is None else max(current_end, end)
    if current:
        groups.append(current)

    records: list[dict[str, Any]] = []
    membership_rows: list[dict[str, Any]] = []
    for family_ordinal, members in enumerate(groups):
        family_start = min(member["_window_start"] for member in members)
        family_end = max(member["_window_end"] for member in members)
        duration_units = (family_end - family_start).value
        if duration_units % cadence.value != 0:
            raise EventFamilyValidationError("family duration is not aligned to bar_cadence")
        duration_bars = duration_units // cadence.value + 1
        episode_ids = [int(member["episode_id"]) for member in members]
        identity_payload = {
            "bar_cadence": canonical_cadence,
            "episode_ids": episode_ids,
            "family_end": _canonical_timestamp(family_end),
            "family_start": _canonical_timestamp(family_start),
            "source_artifact": source_identifier,
            "specification_version": specification_version,
        }
        family_id = _digest(identity_payload)
        intrinsic_counts = _sorted_counts(member["_intrinsic_subtype"] for member in members)
        recovery_counts = _sorted_counts(member["recovery_outcome"] for member in members)
        latest = max(
            members,
            key=lambda member: (
                member["_window_end"], member["_window_start"], int(member["episode_id"])
            ),
        )
        similarities = [float(member["_similarity"]) for member in members]
        records.append({
            "family_id": family_id,
            "family_ordinal": family_ordinal,
            "window_start": _canonical_timestamp(family_start),
            "window_end": _canonical_timestamp(family_end),
            "duration_bars": int(duration_bars),
            "bar_cadence": canonical_cadence,
            "episode_ids": episode_ids,
            "episode_count": len(members),
            "intrinsic_subtype_counts": intrinsic_counts,
            "intrinsic_subtype_mixed": len(intrinsic_counts) > 1,
            "recovery_outcome_counts": recovery_counts,
            "recovery_outcome_mixed": len(recovery_counts) > 1,
            "latest_episode_id": int(latest["episode_id"]),
            "latest_episode_similarity_to_current": float(latest["_similarity"]),
            "maximum_similarity_to_current": float(max(similarities)),
            "median_similarity_to_current": float(np.median(np.asarray(similarities, dtype=float))),
            "research_only": True,
            "observation_only": True,
            "runtime_integration_allowed": False,
            "exposure_mutation_allowed": False,
        })
        for member_ordinal, member in enumerate(members):
            membership_rows.append({
                "family_id": family_id,
                "family_ordinal": family_ordinal,
                "episode_id": int(member["episode_id"]),
                "member_ordinal": member_ordinal,
                "window_start": _canonical_timestamp(member["_window_start"]),
                "window_end": _canonical_timestamp(member["_window_end"]),
                "intrinsic_subtype": member["_intrinsic_subtype"],
                "recovery_outcome": str(member["recovery_outcome"]),
                "feature_cosine_similarity_to_latest": float(member["_similarity"]),
            })

    membership = pd.DataFrame(membership_rows, columns=MEMBERSHIP_COLUMNS)
    expected_ids = sorted(int(value) for value in classified_episodes["episode_id"])
    actual_ids = sorted(int(value) for value in membership["episode_id"])
    if membership["episode_id"].duplicated().any():
        raise EventFamilyValidationError("duplicate family membership")
    if expected_ids != actual_ids:
        raise EventFamilyValidationError("incomplete family membership")
    return membership, records
