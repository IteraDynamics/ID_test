from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import NormalDist
from typing import Iterable, Mapping, Sequence


TARGETS = ("SPY", "QQQ")
BREADTH_MEMBERS = (
    "RSP", "MDY", "IWM", "IWD", "IWF", "XLB", "XLE",
    "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY",
)
PREDICTORS = ("breadth50", "breadth_change20", "narrow_strength", "broad_recovery")
HORIZONS = (5, 20, 60)
EXPECTED_SIGNS = {
    "breadth50": 1,
    "breadth_change20": 1,
    "narrow_strength": -1,
    "broad_recovery": 1,
}
BINARY_PREDICTORS = {"narrow_strength", "broad_recovery"}
EXPECTED_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
DISCOVERY_CUTOFF = date(2024, 12, 31)


class Campaign50Error(ValueError):
    pass


@dataclass(frozen=True)
class Candidate:
    predictor: str
    target: str
    horizon: int

    @property
    def key(self) -> str:
        return f"{self.predictor}__{self.target}__fwd_return_{self.horizon}"


@dataclass(frozen=True)
class RegressionResult:
    n: int
    beta0: float
    beta1: float
    se_beta1: float
    t_stat: float
    p_value: float
    ci_low: float
    ci_high: float


@dataclass(frozen=True)
class StageDecision:
    candidate_key: str
    status: str
    rankable: bool
    n: int
    event_n: int | None
    non_event_n: int | None
    beta1: float | None
    raw_p: float | None
    holm_p: float | None
    ci_low: float | None
    ci_high: float | None


def candidate_inventory() -> list[Candidate]:
    return [Candidate(p, t, h) for p in PREDICTORS for t in TARGETS for h in HORIZONS]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def canonical_csv_bytes(fieldnames: Sequence[str], rows: Iterable[Mapping[str, object]]) -> bytes:
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(fieldnames), lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in fieldnames})
    return stream.getvalue().encode("utf-8")


def parse_timestamp(raw: str) -> datetime:
    try:
        return datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise Campaign50Error(f"SOURCE_SCHEMA_FAILURE: invalid timestamp {raw!r}") from exc


def load_close_series(
    path: Path,
    *,
    expected_sha256: str | None = None,
    reject_after: date | None = DISCOVERY_CUTOFF,
) -> tuple[list[date], list[float]]:
    if not path.exists():
        raise Campaign50Error(f"SOURCE_IDENTITY_FAILURE: missing {path.name}")
    if expected_sha256 is not None and sha256_file(path) != expected_sha256:
        raise Campaign50Error(f"SOURCE_IDENTITY_FAILURE: hash mismatch {path.name}")

    sessions: list[date] = []
    closes: list[float] = []
    previous: date | None = None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
            raise Campaign50Error(f"SOURCE_SCHEMA_FAILURE: {path.name}")
        for row_number, row in enumerate(reader, start=2):
            session = parse_timestamp(row["timestamp"]).date()
            if reject_after is not None and session > reject_after:
                raise Campaign50Error(
                    f"HOLDOUT_ACCESS_VIOLATION: {path.name}:{row_number}:{session.isoformat()}"
                )
            if previous is not None and session <= previous:
                raise Campaign50Error(f"SOURCE_ORDER_FAILURE: {path.name}:{row_number}")
            try:
                close = float(row["close"])
            except ValueError as exc:
                raise Campaign50Error(f"SOURCE_SCHEMA_FAILURE: {path.name}:{row_number}") from exc
            if not math.isfinite(close) or close <= 0:
                raise Campaign50Error(f"SOURCE_SCHEMA_FAILURE: {path.name}:{row_number}")
            sessions.append(session)
            closes.append(close)
            previous = session
    return sessions, closes


def moving_average(values: Sequence[float], window: int) -> list[float | None]:
    if window <= 0:
        raise Campaign50Error("LOOKBACK_UNAVAILABLE: nonpositive window")
    out: list[float | None] = [None] * len(values)
    running = 0.0
    for index, value in enumerate(values):
        running += value
        if index >= window:
            running -= values[index - window]
        if index >= window - 1:
            out[index] = running / window
    return out


def build_predictors(
    closes: Mapping[str, Sequence[float]],
) -> dict[str, dict[str, list[float | None]]]:
    required = set(TARGETS) | set(BREADTH_MEMBERS)
    if set(closes) != required:
        missing = sorted(required - set(closes))
        extra = sorted(set(closes) - required)
        raise Campaign50Error(f"SOURCE_SCHEMA_FAILURE: missing={missing} extra={extra}")
    lengths = {len(values) for values in closes.values()}
    if len(lengths) != 1:
        raise Campaign50Error("SOURCE_ORDER_FAILURE: unequal aligned lengths")
    length = lengths.pop()

    above50: dict[str, list[float | None]] = {}
    for member in BREADTH_MEMBERS:
        ma = moving_average(closes[member], 50)
        above50[member] = [
            None if avg is None else float(closes[member][i] > avg)
            for i, avg in enumerate(ma)
        ]

    breadth50: list[float | None] = [None] * length
    for i in range(length):
        values = [above50[m][i] for m in BREADTH_MEMBERS]
        if all(value is not None for value in values):
            breadth50[i] = sum(float(value) for value in values) / len(BREADTH_MEMBERS)

    breadth_change20: list[float | None] = [None] * length
    broad_recovery: list[float | None] = [None] * length
    for i in range(20, length):
        current = breadth50[i]
        previous = breadth50[i - 20]
        if current is None or previous is None:
            continue
        change = current - previous
        breadth_change20[i] = change
        broad_recovery[i] = float(current >= 0.70 and change > 0 and previous <= 0.50)

    result: dict[str, dict[str, list[float | None]]] = {}
    for target in TARGETS:
        target_ma200 = moving_average(closes[target], 200)
        narrow: list[float | None] = [None] * length
        for i in range(length):
            current = breadth50[i]
            change = breadth_change20[i]
            ma200 = target_ma200[i]
            if current is None or change is None or ma200 is None:
                continue
            narrow[i] = float(closes[target][i] > ma200 and current <= 0.50 and change < 0)
        result[target] = {
            "breadth50": list(breadth50),
            "breadth_change20": list(breadth_change20),
            "narrow_strength": narrow,
            "broad_recovery": list(broad_recovery),
        }
    return result


def forward_returns(values: Sequence[float], horizon: int) -> list[float | None]:
    if horizon <= 0:
        raise Campaign50Error("LOOKBACK_UNAVAILABLE: nonpositive horizon")
    out: list[float | None] = [None] * len(values)
    for i in range(0, len(values) - horizon):
        out[i] = values[i + horizon] / values[i] - 1.0
    return out


def anchor_indices(
    sessions: Sequence[date],
    *,
    start: date,
    end: date,
    horizon: int,
    required_lookback: int = 220,
) -> list[int]:
    eligible = [
        i for i, session in enumerate(sessions)
        if start <= session <= end and i >= required_lookback - 1 and i + horizon < len(sessions)
    ]
    if not eligible:
        return []
    first = eligible[0]
    eligible_set = set(eligible)
    return [i for i in range(first, eligible[-1] + 1, horizon) if i in eligible_set]


def _invert_2x2(a: float, b: float, c: float, d: float) -> tuple[tuple[float, float], tuple[float, float]]:
    det = a * d - b * c
    if abs(det) <= 1e-18:
        raise Campaign50Error("ZERO_VARIANCE_PREDICTOR")
    return ((d / det, -b / det), (-c / det, a / det))


def ols_hc3(x_raw: Sequence[float], y: Sequence[float], *, standardize: bool) -> RegressionResult:
    if len(x_raw) != len(y) or len(x_raw) < 3:
        raise Campaign50Error("INSUFFICIENT_TOTAL_SUPPORT")
    if not all(math.isfinite(value) for value in [*x_raw, *y]):
        raise Campaign50Error("NONFINITE_MODEL_RESULT")

    x = list(float(v) for v in x_raw)
    if standardize:
        mean_x = sum(x) / len(x)
        variance = sum((v - mean_x) ** 2 for v in x) / len(x)
        if variance <= 0:
            raise Campaign50Error("ZERO_VARIANCE_PREDICTOR")
        scale = math.sqrt(variance)
        x = [(v - mean_x) / scale for v in x]
    elif max(x) == min(x):
        raise Campaign50Error("ZERO_VARIANCE_PREDICTOR")

    n = len(x)
    sx = sum(x)
    sxx = sum(v * v for v in x)
    sy = sum(y)
    sxy = sum(v * yy for v, yy in zip(x, y))
    inv = _invert_2x2(float(n), sx, sx, sxx)
    beta0 = inv[0][0] * sy + inv[0][1] * sxy
    beta1 = inv[1][0] * sy + inv[1][1] * sxy

    meat00 = meat01 = meat11 = 0.0
    for xv, yv in zip(x, y):
        fitted = beta0 + beta1 * xv
        residual = yv - fitted
        h = inv[0][0] + 2.0 * inv[0][1] * xv + inv[1][1] * xv * xv
        denom = 1.0 - h
        if denom <= 1e-12:
            raise Campaign50Error("NONFINITE_MODEL_RESULT")
        scaled = residual / denom
        weight = scaled * scaled
        meat00 += weight
        meat01 += weight * xv
        meat11 += weight * xv * xv

    cov11 = (
        inv[1][0] * (meat00 * inv[0][1] + meat01 * inv[1][1])
        + inv[1][1] * (meat01 * inv[0][1] + meat11 * inv[1][1])
    )
    if cov11 < 0 and abs(cov11) < 1e-15:
        cov11 = 0.0
    if cov11 <= 0 or not math.isfinite(cov11):
        raise Campaign50Error("NONFINITE_MODEL_RESULT")
    se = math.sqrt(cov11)
    t_stat = beta1 / se
    normal = NormalDist()
    p_value = 2.0 * (1.0 - normal.cdf(abs(t_stat)))
    z = normal.inv_cdf(0.975)
    return RegressionResult(n, beta0, beta1, se, t_stat, p_value, beta1 - z * se, beta1 + z * se)


def holm_adjust(raw_p_values: Mapping[str, float], family_size: int = 24) -> dict[str, float]:
    if family_size < len(raw_p_values):
        raise Campaign50Error("NONFINITE_MODEL_RESULT: Holm family too small")
    ordered = sorted(raw_p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (key, p_value) in enumerate(ordered, start=1):
        candidate = min(1.0, (family_size - rank + 1) * p_value)
        running = max(running, candidate)
        adjusted[key] = running
    return adjusted


def support_gate(stage: str, predictor: str, horizon: int, values: Sequence[float]) -> tuple[str | None, int, int | None, int | None]:
    minimums = {
        "development": {5: 180, 20: 55, 60: 18},
        "validation": {5: 80, 20: 22, 60: 8},
        "holdout": {5: 40, 20: 11, 60: 4},
    }
    event_minimums = {"development": 8, "validation": 4, "holdout": 3}
    n = len(values)
    if n < minimums[stage][horizon]:
        return "INSUFFICIENT_TOTAL_SUPPORT", n, None, None
    if predictor in BINARY_PREDICTORS:
        event_n = sum(1 for value in values if value == 1.0)
        non_event_n = n - event_n
        if event_n < event_minimums[stage] or non_event_n < event_minimums[stage]:
            return "INSUFFICIENT_EVENT_SUPPORT", n, event_n, non_event_n
        return None, n, event_n, non_event_n
    return None, n, None, None


def expected_sign_matches(predictor: str, coefficient: float) -> bool:
    return coefficient * EXPECTED_SIGNS[predictor] > 0


def compatibility_matches(development_beta: float, stage_beta: float) -> bool:
    if development_beta == 0:
        return False
    ratio = abs(stage_beta) / abs(development_beta)
    return 0.25 <= ratio <= 4.0


def confirmation_boundary(*_: object, **__: object) -> None:
    raise Campaign50Error("HOLDOUT_ACCESS_VIOLATION: confirmation path not authorized")
