"""Deterministic research-only core for Campaign #51."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy.special import ndtr

SPECIFICATION_COMMIT = "c2f4770ac84e460a387ad2c341d7a4129034b720"
SOURCE_SHA256 = "d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079"
SOURCE_BYTE_COUNT = 4_792_028
SOURCE_ROW_COUNT = 70_069
SOURCE_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
DIRECTIONAL_VARIABLES = ("return_trailing_24h", "return_trailing_168h")
MOVEMENT_STATES = ("realized_volatility_trailing_24h", "drawdown_from_high_trailing_168h")
HORIZONS = (24, 72, 168)
FAMILY_SIZE = 12
MODEL_TERM_COUNT = 4
SUPPORT_GATES = {
    "development": {24: 220, 72: 220, 168: 219},
    "validation": {24: 90, 72: 89, 168: 89},
    "confirmation": {24: 40, 72: 39, 168: 39},
}


class Campaign51Error(ValueError):
    pass


@dataclass(frozen=True)
class Candidate:
    directional_variable: str
    movement_state: str
    horizon_hours: int

    @property
    def key(self) -> str:
        return (
            f"{self.directional_variable}__x__{self.movement_state}"
            f"__fwd_log_return_{self.horizon_hours}h"
        )


@dataclass(frozen=True)
class Standardization:
    directional_mean: float
    directional_sd: float
    state_mean: float
    state_sd: float


@dataclass(frozen=True)
class OLSInteractionResult:
    beta0: float
    beta_directional: float
    beta_state: float
    beta_interaction: float
    se_interaction_hc3: float
    t_stat: float
    p_value: float
    ci_low: float
    ci_high: float
    n: int
    rank: int


def candidate_inventory() -> list[Candidate]:
    rows = [
        Candidate(directional, state, horizon)
        for directional in DIRECTIONAL_VARIABLES
        for state in MOVEMENT_STATES
        for horizon in HORIZONS
    ]
    if len(rows) != FAMILY_SIZE or len({row.key for row in rows}) != FAMILY_SIZE:
        raise Campaign51Error("CANDIDATE_INVENTORY_FAILURE")
    return rows


def parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require_finite(values: Iterable[float], code: str) -> None:
    if not all(math.isfinite(float(value)) for value in values):
        raise Campaign51Error(code)


def predictor_values(close_by_time: Mapping[datetime, float], anchor: datetime) -> dict[str, float]:
    required = [anchor - timedelta(hours=offset) for offset in range(168, -1, -1)]
    try:
        closes = np.asarray([float(close_by_time[timestamp]) for timestamp in required], dtype=float)
    except KeyError as exc:
        raise Campaign51Error("WINDOW_TIMESTAMP_FAILURE") from exc
    _require_finite(closes, "NONFINITE_CLOSE")
    if np.any(closes <= 0):
        raise Campaign51Error("NONPOSITIVE_CLOSE")
    returns_24 = np.diff(np.log(closes[-25:]))
    current = float(closes[-1])
    high = float(np.max(closes))
    return {
        "return_trailing_24h": float(np.log(current / closes[-25])),
        "return_trailing_168h": float(np.log(current / closes[0])),
        "realized_volatility_trailing_24h": float(np.sqrt(np.sum(returns_24 ** 2))),
        "drawdown_from_high_trailing_168h": float(current / high - 1.0),
    }


def forward_log_return(
    close_by_time: Mapping[datetime, float],
    anchor: datetime,
    horizon_hours: int,
    stage_end: datetime,
) -> float:
    endpoint = anchor + timedelta(hours=horizon_hours)
    if endpoint > stage_end:
        raise Campaign51Error("OUTCOME_STAGE_BOUNDARY_FAILURE")
    try:
        start = float(close_by_time[anchor])
        end = float(close_by_time[endpoint])
    except KeyError as exc:
        raise Campaign51Error("OUTCOME_TIMESTAMP_FAILURE") from exc
    _require_finite((start, end), "NONFINITE_CLOSE")
    if start <= 0 or end <= 0:
        raise Campaign51Error("NONPOSITIVE_CLOSE")
    return math.log(end / start)


def standardization_params(
    directional_values: Sequence[float], state_values: Sequence[float]
) -> Standardization:
    if len(directional_values) != len(state_values) or not directional_values:
        raise Campaign51Error("STANDARDIZATION_SUPPORT_FAILURE")
    directional = np.asarray(directional_values, dtype=float)
    state = np.asarray(state_values, dtype=float)
    _require_finite(directional, "NONFINITE_DIRECTIONAL")
    _require_finite(state, "NONFINITE_STATE")
    directional_sd = float(np.std(directional, ddof=0))
    state_sd = float(np.std(state, ddof=0))
    if directional_sd <= 0 or state_sd <= 0:
        raise Campaign51Error("ZERO_OR_NONFINITE_VARIANCE")
    return Standardization(
        directional_mean=float(np.mean(directional)),
        directional_sd=directional_sd,
        state_mean=float(np.mean(state)),
        state_sd=state_sd,
    )


def transform_predictors(
    directional_values: Sequence[float],
    state_values: Sequence[float],
    params: Standardization,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    directional = (np.asarray(directional_values, dtype=float) - params.directional_mean) / params.directional_sd
    state = (np.asarray(state_values, dtype=float) - params.state_mean) / params.state_sd
    interaction = directional * state
    _require_finite(directional, "NONFINITE_DIRECTIONAL")
    _require_finite(state, "NONFINITE_STATE")
    _require_finite(interaction, "NONFINITE_INTERACTION")
    return directional, state, interaction


def design_matrix(directional_z: Sequence[float], state_z: Sequence[float]) -> np.ndarray:
    directional = np.asarray(directional_z, dtype=float)
    state = np.asarray(state_z, dtype=float)
    if len(directional) != len(state) or len(directional) == 0:
        raise Campaign51Error("DESIGN_SUPPORT_FAILURE")
    matrix = np.column_stack((np.ones(len(directional)), directional, state, directional * state))
    if np.linalg.matrix_rank(matrix) != MODEL_TERM_COUNT:
        raise Campaign51Error("RANK_DEFICIENT_DESIGN")
    return matrix


def ols_hc3_interaction(
    directional_z: Sequence[float], state_z: Sequence[float], outcomes: Sequence[float]
) -> OLSInteractionResult:
    x = design_matrix(directional_z, state_z)
    y = np.asarray(outcomes, dtype=float)
    if len(y) != len(x):
        raise Campaign51Error("OUTCOME_LENGTH_FAILURE")
    _require_finite(y, "NONFINITE_OUTCOME")
    xtx_inv = np.linalg.inv(x.T @ x)
    beta = xtx_inv @ x.T @ y
    residual = y - x @ beta
    leverage = np.einsum("ij,jk,ik->i", x, xtx_inv, x)
    if np.any(leverage >= 1.0):
        raise Campaign51Error("HC3_LEVERAGE_FAILURE")
    adjusted = residual / (1.0 - leverage)
    meat = x.T @ ((adjusted ** 2)[:, None] * x)
    covariance = xtx_inv @ meat @ xtx_inv
    variance = float(covariance[3, 3])
    if not math.isfinite(variance) or variance <= 0:
        raise Campaign51Error("HC3_STANDARD_ERROR_FAILURE")
    se = math.sqrt(variance)
    interaction = float(beta[3])
    t_stat = interaction / se
    p_value = float(2.0 * ndtr(-abs(t_stat)))
    return OLSInteractionResult(
        beta0=float(beta[0]),
        beta_directional=float(beta[1]),
        beta_state=float(beta[2]),
        beta_interaction=interaction,
        se_interaction_hc3=se,
        t_stat=t_stat,
        p_value=p_value,
        ci_low=interaction - 1.959963984540054 * se,
        ci_high=interaction + 1.959963984540054 * se,
        n=len(y),
        rank=int(np.linalg.matrix_rank(x)),
    )


def support_gate(stage: str, horizon_hours: int, n: int) -> str | None:
    try:
        minimum = SUPPORT_GATES[stage][horizon_hours]
    except KeyError as exc:
        raise Campaign51Error("UNKNOWN_SUPPORT_GATE") from exc
    return None if n >= minimum else "INSUFFICIENT_SUPPORT"


def holm_adjust(raw_p: Mapping[str, float], family_size: int = FAMILY_SIZE) -> dict[str, float]:
    if family_size != FAMILY_SIZE:
        raise Campaign51Error("MULTIPLICITY_FAMILY_FAILURE")
    canonical_order = {candidate.key: index for index, candidate in enumerate(candidate_inventory())}
    for key, value in raw_p.items():
        if key not in canonical_order or not math.isfinite(value) or not 0 <= value <= 1:
            raise Campaign51Error("INVALID_RAW_P")
    ordered = sorted(raw_p.items(), key=lambda item: (item[1], canonical_order[item[0]]))
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (key, value) in enumerate(ordered, start=1):
        running = max(running, min(1.0, (family_size - rank + 1) * value))
        adjusted[key] = running
    return adjusted


def same_nonzero_sign(left: float, right: float) -> bool:
    return left != 0 and right != 0 and math.copysign(1.0, left) == math.copysign(1.0, right)


def compatible_ratio(reference: float, comparison: float) -> bool:
    if reference == 0 or not math.isfinite(reference) or not math.isfinite(comparison):
        return False
    ratio = abs(comparison) / abs(reference)
    return 0.25 <= ratio <= 4.0


def classify_development(rankable: bool, holm_p: float | None) -> str:
    if not rankable:
        return "UNRANKABLE"
    return "DISCOVERY_SUPPORTED" if holm_p is not None and holm_p <= 0.05 else "DISCOVERY_NOT_SUPPORTED"


def classify_validation(
    development_status: str,
    rankable: bool,
    development_beta: float | None,
    validation_beta: float | None,
    validation_holm_p: float | None,
) -> str:
    if not rankable:
        return "UNRANKABLE"
    if development_status != "DISCOVERY_SUPPORTED":
        return "VALIDATION_NOT_ELIGIBLE"
    supported = (
        development_beta is not None
        and validation_beta is not None
        and validation_holm_p is not None
        and same_nonzero_sign(development_beta, validation_beta)
        and validation_holm_p <= 0.10
        and compatible_ratio(development_beta, validation_beta)
    )
    return "VALIDATION_SUPPORTED" if supported else "VALIDATION_NOT_SUPPORTED"


def canonical_json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def canonical_csv_bytes(fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in fieldnames})
    return buffer.getvalue().encode("utf-8")
