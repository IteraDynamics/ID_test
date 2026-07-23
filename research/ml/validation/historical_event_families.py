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
CANONICAL_BAR_CADENCE = "PT1H"

SOURCE_REQUIRED_COLUMNS = {
    "window_start",
    "window_end",
    "reference_activation_rate",
    "observation_activation_rate",
    "activation_ratio",
    "feature_cosine_similarity_to_latest",
    "recovered_without_retraining",
    "recovery_rows",
}

CLASSIFIED_REQUIRED_COLUMNS = SOURCE_REQUIRED_COLUMNS | {
    "episode_id",
    "collapse_severity",
    "feature_displacement",
    "volatility_state",
    "recovery_outcome",
}

MEMBERSHIP_COLUMNS = [
    "family_id",
    "family_ordinal",
    "episode_id",
    "member_ordinal",
    "window_start",
    "window_end",
    "intrinsic_subtype",
    "recovery_outcome",
    "feature_cosine_similarity_to_latest",
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
    if path.is_absolute() or ".." in path.parts:
        raise EventFamilyValidationError("source_artifact must be repository-relative")
    canonical = path.as_posix()
    if canonical in {"", "."}:
        raise EventFamilyValidationError("source_artifact must identify a file")
    return canonical


def _canonical_timestamp(value: pd.Timestamp) -> str:
    if value.tzinfo is None:
        return value.isoformat(timespec="seconds")
    return value.isoformat(timespec="seconds")


def _timezone_awareness(values: Iterable[pd.Timestamp], field: str) -> bool:
    awareness = {value.tzinfo is not None for value in values}
    if len(awareness) != 1:
        raise EventFamilyValidationError(f"mixed timezone convention in {field}")
    return awareness.pop()


def _parse_timestamp_series(values: pd.Series, field: str) -> pd.Series:
    parsed: list[pd.Timestamp] = []
    for index, value in values.items():
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise EventFamilyValidationError(
                f"malformed {field} timestamp at row {index}"
            ) from exc
        if pd.isna(timestamp):
            raise EventFamilyValidationError(f"malformed {field} timestamp at row {index}")
        parsed.append(timestamp)
    _timezone_awareness(parsed, field)
    return pd.Series(parsed, index=values.index, dtype=object)


def parse_bar_cadence(value: str | pd.Timedelta) -> tuple[pd.Timedelta, str]:
    """Validate an explicit cadence and return its duration and canonical form."""
    if value is None:
        raise EventFamilyValidationError("bar_cadence is required and may not be inferred")
    if isinstance(value, str) and not value.strip():
        raise EventFamilyValidationError("bar_cadence is required and may not be inferred")
    try:
        cadence = pd.Timedelta(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise EventFamilyValidationError("bar_cadence must be a valid duration") from exc
    if cadence <= pd.Timedelta(0):
        raise EventFamilyValidationError("bar_cadence must be positive")
    if cadence.value % 1_000_000_000 != 0:
        raise EventFamilyValidationError("bar_cadence must be an exact whole-second duration")

    total_seconds = int(cadence.total_seconds())
    if total_seconds % 3600 == 0:
        canonical = f"PT{total_seconds // 3600}H"
    elif total_seconds % 60 == 0:
        canonical = f"PT{total_seconds // 60}M"
    else:
        canonical = f"PT{total_seconds}S"
    return cadence, canonical


def validate_prediction_timestamps(
    timestamps: Iterable[Any], *, bar_cadence: str | pd.Timedelta
) -> pd.Index:
    """Validate the governed prediction index without filling missing bars."""
    cadence, _ = parse_bar_cadence(bar_cadence)
    parsed: list[pd.Timestamp] = []
    for position, value in enumerate(timestamps):
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise EventFamilyValidationError(
                f"malformed prediction timestamp at position {position}"
            ) from exc
        if pd.isna(timestamp):
            raise EventFamilyValidationError(
                f"malformed prediction timestamp at position {position}"
            )
        parsed.append(timestamp)

    if not parsed:
        raise EventFamilyValidationError("prediction timestamp index must not be empty")
    _timezone_awareness(parsed, "prediction timestamp index")
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
    """Return a copy with zero-based episode identity from persisted row order."""
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
    """Reconcile classified rows exactly to source bytes represented as a DataFrame."""
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

    source_ids = source["episode_id"].tolist()
    classified_ids = classified_episodes["episode_id"].tolist()
    if set(source_ids) != set(classified_ids) or len(source_ids) != len(classified_ids):
        raise EventFamilyValidationError("source and classified episode identities must match exactly")

    classified = classified_episodes.set_index("episode_id", drop=False)
    for row in source.to_dict(orient="records"):
        episode_id = int(row["episode_id"])
        candidate = classified.loc[episode_id]
        for field in source.columns:
            expected = row[field]
            actual = candidate[field]
            if pd.isna(expected) and pd.isna(actual):
                continue
            if isinstance(expected, (list, dict)) or isinstance(actual, (list, dict)):
                equal = expected == actual
            else:
                equal = bool(expected == actual)
            if not equal:
                raise EventFamilyValidationError(
                    f"governed field disagreement for episode {episode_id}: {field}"
                )
    return classified_episodes.copy(deep=True)


def _sorted_counts(values: Iterable[str]) -> dict[str, int]:
    counts = Counter(str(value) for value in values)
    return {key: counts[key] for key in sorted(counts)}


def _family_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _validate_classified_rows(classified: pd.DataFrame) -> pd.DataFrame:
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

    result = classified.copy(deep=True)
    result["_window_start"] = _parse_timestamp_series(result["window_start"], "window_start")
    result["_window_end"] = _parse_timestamp_series(result["window_end"], "window_end")
    combined = list(result["_window_start"]) + list(result["_window_end"])
    _timezone_awareness(combined, "episode boundaries")
    if any(end < start for start, end in zip(result["_window_start"], result["_window_end"])):
        raise EventFamilyValidationError("window_end must not precede window_start")

    for field in ("collapse_severity", "feature_displacement", "volatility_state", "recovery_outcome"):
        if result[field].isna().any() or (result[field].astype(str).str.len() == 0).any():
            raise EventFamilyValidationError(f"{field} must be non-null and non-empty")
    result["_similarity"] = [
        _finite_float(value, "feature_cosine_similarity_to_latest")
        for value in result["feature_cosine_similarity_to_latest"]
    ]
    result["_intrinsic_subtype"] = (
        result["collapse_severity"].astype(str)
        + "__"
        + result["feature_displacement"].astype(str)
        + "__"
        + result["volatility_state"].astype(str)
    )
    return result


def build_event_families(
    classified_episodes: pd.DataFrame,
    *,
    prediction_timestamps: Iterable[Any],
    source_artifact: str,
    bar_cadence: str | pd.Timedelta,
    specification_version: str = SPECIFICATION_VERSION,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Build canonical family membership and family records without side effects."""
    if str(specification_version) != specification_version or not specification_version:
        raise EventFamilyValidationError("specification_version must be a non-empty string")
    cadence, canonical_cadence = parse_bar_cadence(bar_cadence)
    prediction_index = validate_prediction_timestamps(
        prediction_timestamps, bar_cadence=cadence
    )
    source_identifier = _canonical_source_artifact(source_artifact)
    rows = _validate_classified_rows(classified_episodes)

    prediction_awareness = prediction_index[0].tzinfo is not None
    episode_awareness = rows.iloc[0]["_window_start"].tzinfo is not None
    if prediction_awareness != episode_awareness:
        raise EventFamilyValidationError(
            "episode and prediction timestamps must use the same timezone convention"
        )

    prediction_set = set(prediction_index.tolist())
    for row in rows.itertuples(index=False):
        if row._window_start not in prediction_set or row._window_end not in prediction_set:
            raise EventFamilyValidationError(
                f"episode {row.episode_id} boundary absent from governed prediction index"
            )
        duration = row._window_end - row._window_start
        if duration.value % cadence.value != 0:
            raise EventFamilyValidationError(
                f"episode {row.episode_id} duration is not aligned to bar_cadence"
            )

    rows = rows.sort_values(
        ["_window_start", "_window_end", "episode_id"], kind="mergesort"
    ).reset_index(drop=True)

    grouped: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_end: pd.Timestamp | None = None
    for row in rows.to_dict(orient="records"):
        start = row["_window_start"]
        end = row["_window_end"]
        if current and current_end is not None and start > current_end + cadence:
            grouped.append(current)
            current = []
            current_end = None
        current.append(row)
        current_end = end if current_end is None else max(current_end, end)
    if current:
        grouped.append(current)

    family_records: list[dict[str, Any]] = []
    membership_rows: list[dict[str, Any]] = []
    for family_ordinal, members in enumerate(grouped):
        family_start = min(member["_window_start"] for member in members)
        family_end = max(member["_window_end"] for member in members)
        duration_units = (family_end - family_start).value
        if duration_units % cadence.value != 0:
            raise EventFamilyValidationError("family duration is not aligned to bar_cadence")
        duration_bars = duration_units // cadence.value + 1
        if duration_bars <= 0:
            raise EventFamilyValidationError("family duration_bars must be positive")

        episode_ids = [int(member["episode_id"]) for member in members]
        payload = {
            "bar_cadence": canonical_cadence,
            "episode_ids": episode_ids,
            "family_end": _canonical_timestamp(family_end),
            "family_start": _canonical_timestamp(family_start),
            "source_artifact": source_identifier,
            "specification_version": specification_version,
        }
        family_id = _family_id(payload)
        intrinsic_counts = _sorted_counts(
            member["_intrinsic_subtype"] for member in members
        )
        recovery_counts = _sorted_counts(member["recovery_outcome"] for member in members)
        latest_member = max(
            members,
            key=lambda member: (
                member["_window_end"],
                member["_window_start"],
                int(member["episode_id"]),
            ),
        )
        similarities = [float(member["_similarity"]) for member in members]

        record = {
            "bar_cadence": canonical_cadence,
            "duration_bars": int(duration_bars),
            "episode_count": len(members),
            "episode_ids": episode_ids,
            "exposure_mutation_allowed": False,
            "family_id": family_id,
            "family_ordinal": family_ordinal,
            "intrinsic_subtype_counts": intrinsic_counts,
            "intrinsic_subtype_mixed": len(intrinsic_counts) > 1,
            "latest_episode_id": int(latest_member["episode_id"]),
            "latest_episode_similarity_to_current": float(latest_member["_similarity"]),
            "maximum_similarity_to_current": float(max(similarities)),
            "median_similarity_to_current": float(np.median(np.asarray(similarities, dtype=float))),
            "observation_only": True,
            "recovery_outcome_counts": recovery_counts,
            "recovery_outcome_mixed": len(recovery_counts) > 1,
            "research_only": True,
            "runtime_integration_allowed": False,
            "window_end": _canonical_timestamp(family_end),
            "window_start": _canonical_timestamp(family_start),
        }
        family_records.append(record)

        for member_ordinal, member in enumerate(members):
            membership_rows.append(
                {
                    "family_id": family_id,
                    "family_ordinal": family_ordinal,
                    "episode_id": int(member["episode_id"]),
                    "member_ordinal": member_ordinal,
                    "window_start": _canonical_timestamp(member["_window_start"]),
                    "window_end": _canonical_timestamp(member["_window_end"]),
                    "intrinsic_subtype": member["_intrinsic_subtype"],
                    "recovery_outcome": str(member["recovery_outcome"]),
                    "feature_cosine_similarity_to_latest": float(member["_similarity"]),
                }
            )

    membership = pd.DataFrame(membership_rows, columns=MEMBERSHIP_COLUMNS)
    if membership["episode_id"].duplicated().any():
        raise EventFamilyValidationError("duplicate family membership")
    expected_ids = sorted(int(value) for value in classified_episodes["episode_id"])
    actual_ids = sorted(int(value) for value in membership["episode_id"])
    if expected_ids != actual_ids:
        raise EventFamilyValidationError("incomplete family membership")
    return membership, family_records
