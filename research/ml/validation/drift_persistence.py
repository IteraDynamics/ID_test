"""Rolling persistence classification for observation-only drift reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

import pandas as pd

from research.ml.validation.drift_detector import DriftReport, detect_drift


@dataclass(frozen=True)
class PersistenceAssessment:
    state: str
    current_severity: str
    persistence_breaches: int
    evaluated_windows: int
    requested_windows: int
    consecutive_high_windows: int
    consecutive_non_low_windows: int
    persistence_sufficient: bool
    window_severities: tuple[str, ...]
    window_digests: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _trailing_count(values: tuple[str, ...], accepted: set[str]) -> int:
    count = 0
    for value in reversed(values):
        if value not in accepted:
            break
        count += 1
    return count


def classify_persistence(
    severities: tuple[str, ...], *, required_consecutive: int = 2
) -> str:
    """Classify the newest window using only ordered historical severities."""
    if not severities:
        return "NO_DATA"
    current = severities[-1]
    consecutive_high = _trailing_count(severities, {"HIGH"})
    consecutive_non_low = _trailing_count(severities, {"MED", "HIGH"})

    if current == "HIGH":
        return (
            "HIGH_PERSISTENT"
            if consecutive_high >= required_consecutive
            else "HIGH_TRANSIENT"
        )
    if current == "MED":
        return (
            "MED_PERSISTENT"
            if consecutive_non_low >= required_consecutive
            else "MED_TRANSIENT"
        )
    if len(severities) >= 2 and severities[-2] != "LOW":
        return "RECOVERED"
    return "STABLE"


def evaluate_persistence(
    frame: pd.DataFrame,
    *,
    asset: str,
    model: str,
    reference_rows: int,
    observation_rows: int,
    requested_windows: int = 3,
    required_consecutive: int = 2,
    detect_kwargs: Mapping[str, Any] | None = None,
) -> tuple[DriftReport, PersistenceAssessment]:
    """Evaluate consecutive non-overlapping observation windows, oldest first.

    All evaluated observation windows are compared with the same frozen reference
    segment immediately preceding the oldest evaluated window. This prevents an
    earlier drifted observation from contaminating the baseline for later windows.
    When history is insufficient, the assessment remains deterministic and reports
    that persistence could not yet be confirmed.
    """
    if requested_windows < 1:
        raise ValueError("requested_windows must be >= 1")
    if required_consecutive < 2:
        raise ValueError("required_consecutive must be >= 2")

    clean = frame.sort_index()
    max_windows = (len(clean) - reference_rows) // observation_rows
    available = max(0, min(requested_windows, max_windows))
    if available < 1:
        needed = reference_rows + observation_rows
        raise ValueError(f"Need at least {needed} rows, received {len(clean)}")

    history_rows = available * observation_rows
    reference_start = len(clean) - history_rows - reference_rows
    reference_end = reference_start + reference_rows
    frozen_reference = clean.iloc[reference_start:reference_end]

    kwargs = dict(detect_kwargs or {})
    reports: list[DriftReport] = []
    for index in range(available):
        observation_start = reference_end + index * observation_rows
        observation_end = observation_start + observation_rows
        observed = clean.iloc[observation_start:observation_end]
        comparison = pd.concat([frozen_reference, observed])
        reports.append(
            detect_drift(
                comparison,
                asset=asset,
                model=model,
                reference_rows=reference_rows,
                observation_rows=observation_rows,
                **kwargs,
            )
        )

    severities = tuple(report.severity for report in reports)
    state = classify_persistence(
        severities, required_consecutive=required_consecutive
    )
    consecutive_high = _trailing_count(severities, {"HIGH"})
    consecutive_non_low = _trailing_count(severities, {"MED", "HIGH"})
    assessment = PersistenceAssessment(
        state=state,
        current_severity=severities[-1],
        persistence_breaches=sum(value == "HIGH" for value in severities),
        evaluated_windows=available,
        requested_windows=requested_windows,
        consecutive_high_windows=consecutive_high,
        consecutive_non_low_windows=consecutive_non_low,
        persistence_sufficient=available >= required_consecutive,
        window_severities=severities,
        window_digests=tuple(report.digest for report in reports),
    )
    return reports[-1], assessment
