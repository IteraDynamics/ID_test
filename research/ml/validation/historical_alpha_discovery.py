from __future__ import annotations

"""Deterministic, research-only primitives for Campaign #43."""

from dataclasses import dataclass
import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

HORIZON_HOURS: tuple[int, ...] = (2, 6, 24, 72, 168)
RANKABLE_DESCRIPTORS: tuple[str, ...] = (
    "collapse_severity",
    "feature_displacement",
    "volatility_state",
    "intrinsic_subtype",
)
EXCLUDED_PREDICTOR_FIELDS: frozenset[str] = frozenset(
    {
        "recovery_outcome",
        "recovered_without_retraining",
        "recovery_rows",
        "feature_cosine_similarity_to_latest",
        "similarity_band",
    }
)
EVIDENCE_STATE_ORDER: Mapping[str, int] = {
    "SUPPORTED_ASSOCIATION": 0,
    "NULL_ASSOCIATION": 1,
    "UNSTABLE_OOS": 2,
    "CONTRADICTORY_RESOLUTION": 3,
    "INSUFFICIENT_SUPPORT": 4,
    "OUTCOME_UNAVAILABLE": 5,
}
FAMILY_FOLDS: tuple[tuple[range, range], ...] = (
    (range(0, 5), range(5, 8)),
    (range(0, 8), range(8, 11)),
    (range(0, 11), range(11, 14)),
)


class HistoricalAlphaDiscoveryValidationError(ValueError):
    """Raised when Campaign #43 inputs or calculations fail closed."""


@dataclass(frozen=True)
class ForwardOutcome:
    anchor: str
    horizon_hours: int
    forward_return: float
    positive_return: bool
    maximum_favorable_excursion: float
    maximum_adverse_excursion: float
    realized_volatility: float


def _canonical_timestamp(value: Any, field: str) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise HistoricalAlphaDiscoveryValidationError(
            f"{field} must be a valid timestamp"
        ) from exc
    if pd.isna(timestamp):
        raise HistoricalAlphaDiscoveryValidationError(
            f"{field} must be a valid timestamp"
        )
    return timestamp


def _finite_float(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise HistoricalAlphaDiscoveryValidationError(
            f"{field} must be numeric"
        ) from exc
    if not math.isfinite(result):
        raise HistoricalAlphaDiscoveryValidationError(
            f"{field} must be finite"
        )
    return result


def validate_candidate_inventory(fields: Iterable[str]) -> tuple[str, ...]:
    """Validate an exact rankable predictor inventory without silent expansion."""
    supplied = tuple(str(field) for field in fields)
    if len(supplied) != len(set(supplied)):
        raise HistoricalAlphaDiscoveryValidationError(
            "candidate inventory contains duplicate fields"
        )
    excluded = sorted(set(supplied) & EXCLUDED_PREDICTOR_FIELDS)
    if excluded:
        raise HistoricalAlphaDiscoveryValidationError(
            f"candidate inventory contains look-ahead or non-local fields: {excluded}"
        )
    unknown = sorted(set(supplied) - set(RANKABLE_DESCRIPTORS))
    if unknown:
        raise HistoricalAlphaDiscoveryValidationError(
            f"candidate inventory contains unauthorized fields: {unknown}"
        )
    if set(supplied) != set(RANKABLE_DESCRIPTORS):
        raise HistoricalAlphaDiscoveryValidationError(
            "candidate inventory must match the frozen rankable descriptors exactly"
        )
    return RANKABLE_DESCRIPTORS


def validate_price_series(frame: pd.DataFrame) -> pd.Series:
    """Return the exact governed close series after strict hourly validation."""
    if "close" not in frame.columns:
        raise HistoricalAlphaDiscoveryValidationError(
            "governed BTC series must contain exact close column"
        )
    if frame.empty:
        raise HistoricalAlphaDiscoveryValidationError(
            "governed BTC series must not be empty"
        )

    timestamps = [_canonical_timestamp(value, "price index") for value in frame.index]
    awareness = {timestamp.tzinfo is not None for timestamp in timestamps}
    if len(awareness) != 1:
        raise HistoricalAlphaDiscoveryValidationError(
            "price index contains mixed timezone conventions"
        )
    index = pd.DatetimeIndex(timestamps)
    if index.has_duplicates:
        raise HistoricalAlphaDiscoveryValidationError(
            "price index contains duplicate timestamps"
        )
    if not index.is_monotonic_increasing:
        raise HistoricalAlphaDiscoveryValidationError(
            "price index must be strictly increasing"
        )

    closes = pd.to_numeric(frame["close"], errors="coerce")
    if closes.isna().any():
        raise HistoricalAlphaDiscoveryValidationError(
            "close values must be numeric and non-null"
        )
    values = closes.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise HistoricalAlphaDiscoveryValidationError(
            "close values must be finite"
        )
    if (values <= 0).any():
        raise HistoricalAlphaDiscoveryValidationError(
            "close values must be strictly positive"
        )
    return pd.Series(values, index=index, name="close", dtype=float)


def build_forward_outcome(
    close: pd.Series,
    *,
    anchor: Any,
    horizon_hours: int,
) -> ForwardOutcome | None:
    """Calculate one exact-coverage forward outcome or return unavailable."""
    if horizon_hours not in HORIZON_HOURS:
        raise HistoricalAlphaDiscoveryValidationError(
            f"unauthorized horizon_hours: {horizon_hours}"
        )
    if not isinstance(close.index, pd.DatetimeIndex):
        raise HistoricalAlphaDiscoveryValidationError(
            "close series must use a DatetimeIndex"
        )
    timestamp = _canonical_timestamp(anchor, "anchor")
    expected = pd.date_range(
        timestamp,
        periods=horizon_hours + 1,
        freq="1h",
        tz=timestamp.tz,
    )
    if not expected.isin(close.index).all():
        return None

    path = close.reindex(expected)
    if path.isna().any():
        return None
    values = path.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise HistoricalAlphaDiscoveryValidationError(
            "outcome path must contain finite positive closes"
        )

    anchor_close = values[0]
    future = values[1:]
    forward_return = float(values[-1] / anchor_close - 1.0)
    log_returns = np.diff(np.log(values))
    realized_volatility = float(np.std(log_returns, ddof=0))

    return ForwardOutcome(
        anchor=timestamp.isoformat(timespec="seconds"),
        horizon_hours=horizon_hours,
        forward_return=forward_return,
        positive_return=bool(forward_return > 0.0),
        maximum_favorable_excursion=float(np.max(future) / anchor_close - 1.0),
        maximum_adverse_excursion=float(np.min(future) / anchor_close - 1.0),
        realized_volatility=realized_volatility,
    )


def order_event_families(families: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate and stably order the exact 14-family governed history."""
    if len(families) != 14:
        raise HistoricalAlphaDiscoveryValidationError(
            "Campaign #43 requires exactly 14 event families"
        )
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for position, source in enumerate(families):
        family_id = str(source.get("family_id", ""))
        if not family_id or family_id in seen_ids:
            raise HistoricalAlphaDiscoveryValidationError(
                "event families require unique non-empty family_id"
            )
        seen_ids.add(family_id)
        start = _canonical_timestamp(source.get("window_start"), "family window_start")
        end = _canonical_timestamp(source.get("window_end"), "family window_end")
        if end < start:
            raise HistoricalAlphaDiscoveryValidationError(
                f"family window_end precedes window_start at position {position}"
            )
        row = dict(source)
        row["_window_start"] = start
        row["_window_end"] = end
        normalized.append(row)
    return sorted(
        normalized,
        key=lambda row: (row["_window_end"], row["_window_start"], str(row["family_id"])),
    )


def family_fold_assignments(
    families: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return the frozen expanding-window family fold assignments."""
    ordered = order_event_families(families)
    records: list[dict[str, Any]] = []
    for fold_id, (train_positions, test_positions) in enumerate(FAMILY_FOLDS):
        for role, positions in (("train", train_positions), ("test", test_positions)):
            for position in positions:
                records.append(
                    {
                        "fold_id": fold_id,
                        "role": role,
                        "family_position": position,
                        "family_id": str(ordered[position]["family_id"]),
                        "family_anchor": ordered[position]["_window_end"].isoformat(
                            timespec="seconds"
                        ),
                    }
                )
    return records


def homogeneous_family_value(
    member_values: Iterable[Any],
) -> str | None:
    """Return one family value only when every member agrees exactly."""
    values = [str(value) for value in member_values]
    if not values or any(not value for value in values):
        raise HistoricalAlphaDiscoveryValidationError(
            "family candidate values must be non-empty"
        )
    unique = set(values)
    return values[0] if len(unique) == 1 else None


def sign(value: Any) -> int:
    """Return deterministic -1, 0, or 1 for a finite number."""
    number = _finite_float(value, "sign value")
    return 1 if number > 0 else -1 if number < 0 else 0


def evidence_state(
    *,
    outcome_available: bool,
    episode_support: int,
    family_support: int,
    supported_fold_count: int,
    episode_median_return: float,
    family_median_return: float,
    training_test_agreement_count: int,
    aggregate_direction_agreement_count: int,
) -> str:
    """Apply the frozen fail-closed Campaign #43 evidence-state ordering."""
    if not outcome_available:
        return "OUTCOME_UNAVAILABLE"
    if episode_support < 5 or family_support < 3 or supported_fold_count < 2:
        return "INSUFFICIENT_SUPPORT"
    episode_direction = sign(episode_median_return)
    family_direction = sign(family_median_return)
    if episode_direction != 0 and family_direction != 0 and episode_direction != family_direction:
        return "CONTRADICTORY_RESOLUTION"
    if (
        training_test_agreement_count < supported_fold_count
        or aggregate_direction_agreement_count < supported_fold_count
    ):
        return "UNSTABLE_OOS"
    if family_direction == 0:
        return "NULL_ASSOCIATION"
    return "SUPPORTED_ASSOCIATION"


def ranking_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    """Return the frozen lexicographic key for one candidate-horizon row."""
    state = str(row["evidence_state"])
    if state not in EVIDENCE_STATE_ORDER:
        raise HistoricalAlphaDiscoveryValidationError(
            f"unknown evidence_state: {state}"
        )
    magnitude = abs(_finite_float(row["family_median_forward_return"], "family median"))
    return (
        EVIDENCE_STATE_ORDER[state],
        -int(row["supported_fold_count"]),
        -int(row["training_test_direction_agreement_count"]),
        -int(row["aggregate_direction_agreement_count"]),
        -int(row["family_support"]),
        -magnitude,
        int(row["horizon_hours"]),
        str(row["descriptor"]),
        str(row["candidate_value"]),
    )


def rank_candidate_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return copied candidate rows in deterministic frozen order."""
    return sorted((dict(row) for row in rows), key=ranking_key)
