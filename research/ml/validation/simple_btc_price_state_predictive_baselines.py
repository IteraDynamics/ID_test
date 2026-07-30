"""Deterministic, observation-only Campaign #48 BTC price-state discovery."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.special import ndtr

CAMPAIGN_ID = 48
SPECIFICATION_FREEZE = "e8777df3442d093fd84fb92c25d13aadc2bfe1ed"
HANDOFF_FREEZE = "a16c152608df481a66a2e29f7a1d7795b5490459"
SERIALIZATION_CONTRACT_VERSION = "campaign-48-v1"
SOURCE_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
PREDICTORS = (
    "return_trailing_24h",
    "return_trailing_72h",
    "return_trailing_168h",
    "realized_volatility_trailing_24h",
    "realized_volatility_trailing_168h",
    "distance_from_mean_trailing_168h",
    "range_position_trailing_168h",
    "drawdown_from_high_trailing_168h",
)
OUTCOME_FAMILIES = ("R", "M", "V")
HORIZONS = (24, 72, 168)
OUTPUT_FILENAMES = (
    "price_state_anchor_inventory.csv",
    "price_state_anchor_inventory.json",
    "price_state_candidate_inventory.csv",
    "price_state_candidate_inventory.json",
    "price_state_fold_plan.json",
    "price_state_results.csv",
    "price_state_results.json",
    "price_state_report.md",
    "price_state_source_manifest.json",
    "price_state_manifest.json",
)
ANCHOR_COLUMNS = (
    "anchor_ordinal", "anchor_timestamp", "partition", *PREDICTORS,
)
CANDIDATE_COLUMNS = (
    "candidate_ordinal", "candidate_id", "predictor", "outcome_family",
    "horizon_hours", "outcome_column",
)
RESULT_COLUMNS = (
    "candidate_ordinal", "candidate_id", "predictor", "outcome_family",
    "horizon_hours", "status", "rankable", "directionally_consistent",
    "pooled_n_obs", "partition_1_complete_n", "partition_2_complete_n",
    "partition_3_complete_n", "pooled_development_mean",
    "pooled_development_population_std", "pooled_coefficient",
    "pooled_standard_error_hc3", "pooled_p_value",
    "pooled_confidence_interval_low", "pooled_confidence_interval_high",
    "partition_2_development_mean", "partition_2_development_population_std",
    "partition_2_coefficient", "partition_2_standard_error_hc3",
    "partition_2_p_value", "partition_2_confidence_interval_low",
    "partition_2_confidence_interval_high", "partition_3_development_mean",
    "partition_3_development_population_std", "partition_3_coefficient",
    "partition_3_standard_error_hc3", "partition_3_p_value",
    "partition_3_confidence_interval_low", "partition_3_confidence_interval_high",
    "family_bh_rank", "family_bh_adjusted_q_value", "failure_reason",
)
STATUS_ORDER = (
    "SUPPORTED_RESEARCH_ASSOCIATION",
    "MULTIPLICITY_NOT_MET",
    "DIRECTION_INCONSISTENT",
    "INSUFFICIENT_SUPPORT",
    "OUTCOME_OR_PREDICTOR_UNAVAILABLE",
    "ZERO_OR_NONFINITE_VARIANCE",
    "RANK_DEFICIENT_DESIGN",
    "ESTIMATOR_FAILURE",
)


@dataclass(frozen=True)
class FrozenContract:
    source_path: str = "data/btcusd_3600s_2018-01-01_to_2025-12-31.csv"
    source_sha256: str = "d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079"
    source_byte_count: int = 4_792_028
    source_row_count: int = 70_069
    first_timestamp: str = "2018-01-01 00:00:00"
    last_timestamp: str = "2025-12-31 00:00:00"
    candidate_count: int = 72
    anchor_spacing_hours: int = 168


DEFAULT_CONTRACT = FrozenContract()


@dataclass(frozen=True)
class OLSResult:
    coefficient: float
    standard_error: float
    p_value: float
    confidence_interval_low: float
    confidence_interval_high: float
    n_obs: int
    rank: int


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return 0.0 if value == 0.0 else float(format(value, ".17g"))
    if isinstance(value, dict):
        return {str(key): _normalise(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    return value


def json_text(payload: Any) -> str:
    return json.dumps(
        _normalise(payload), sort_keys=True, indent=2, ensure_ascii=False,
        allow_nan=False,
    ) + "\n"


def strict_json(path: Path) -> Any:
    def reject(value: str) -> None:
        raise ValueError(f"non-strict JSON constant: {value}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return json.load(handle, parse_constant=reject)


def _csv_scalar(value: Any) -> str:
    value = _normalise(value)
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".17g")
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return str(value)


def csv_text(rows: Sequence[Mapping[str, Any]], columns: Iterable[str]) -> str:
    buffer = io.StringIO(newline="")
    fieldnames = list(columns)
    writer = csv.DictWriter(
        buffer, fieldnames=fieldnames, lineterminator="\n", extrasaction="raise"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({name: _csv_scalar(row.get(name)) for name in fieldnames})
    return buffer.getvalue()


def write_lf(path: Path, text: str) -> None:
    if "\r" in text:
        raise ValueError("canonical text contains carriage returns")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def load_source(path: Path, contract: FrozenContract = DEFAULT_CONTRACT) -> pd.DataFrame:
    data = path.read_bytes()
    if sha256_bytes(data) != contract.source_sha256:
        raise ValueError("SOURCE_SHA256_MISMATCH")
    if len(data) != contract.source_byte_count:
        raise ValueError("SOURCE_BYTE_COUNT_MISMATCH")
    frame = pd.read_csv(io.BytesIO(data))
    if tuple(frame.columns) != SOURCE_COLUMNS:
        raise ValueError("SOURCE_SCHEMA_MISMATCH")
    if len(frame) != contract.source_row_count:
        raise ValueError("SOURCE_ROW_COUNT_MISMATCH")
    timestamps = pd.to_datetime(frame["timestamp"], errors="raise")
    if timestamps.duplicated().any() or not timestamps.is_monotonic_increasing:
        raise ValueError("SOURCE_TIMESTAMP_ORDER_FAILURE")
    expected = pd.date_range(timestamps.iloc[0], timestamps.iloc[-1], freq="h")
    if len(expected) != len(timestamps) or not np.array_equal(
        expected.to_numpy(), timestamps.to_numpy()
    ):
        raise ValueError("SOURCE_CADENCE_FAILURE")
    if timestamps.iloc[0].strftime("%Y-%m-%d %H:%M:%S") != contract.first_timestamp:
        raise ValueError("SOURCE_FIRST_TIMESTAMP_MISMATCH")
    if timestamps.iloc[-1].strftime("%Y-%m-%d %H:%M:%S") != contract.last_timestamp:
        raise ValueError("SOURCE_LAST_TIMESTAMP_MISMATCH")
    close = pd.to_numeric(frame["close"], errors="raise").to_numpy(float)
    if not np.isfinite(close).all() or np.any(close <= 0):
        raise ValueError("SOURCE_CLOSE_FAILURE")
    return pd.DataFrame({"timestamp": timestamps, "close": close}).set_index("timestamp")


def partition_counts(total: int) -> tuple[int, int, int]:
    base, remainder = divmod(total, 3)
    return tuple(base + (1 if index < remainder else 0) for index in range(3))  # type: ignore[return-value]


def _window(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> np.ndarray:
    values = frame.loc[start:end, "close"].to_numpy(float)
    expected = int((end - start) / pd.Timedelta(hours=1)) + 1
    if len(values) != expected:
        raise ValueError("WINDOW_TIMESTAMP_FAILURE")
    return values


def predictor_values(frame: pd.DataFrame, timestamp: pd.Timestamp) -> dict[str, float | None]:
    closes_168 = _window(frame, timestamp - pd.Timedelta(hours=168), timestamp)
    closes_72 = _window(frame, timestamp - pd.Timedelta(hours=72), timestamp)
    closes_24 = _window(frame, timestamp - pd.Timedelta(hours=24), timestamp)
    returns_168 = np.diff(np.log(closes_168))
    returns_24 = np.diff(np.log(closes_24))
    high = float(np.max(closes_168))
    low = float(np.min(closes_168))
    current = float(closes_168[-1])
    range_position = None if high == low else (current - low) / (high - low)
    return {
        "return_trailing_24h": float(np.log(closes_24[-1] / closes_24[0])),
        "return_trailing_72h": float(np.log(closes_72[-1] / closes_72[0])),
        "return_trailing_168h": float(np.log(closes_168[-1] / closes_168[0])),
        "realized_volatility_trailing_24h": float(np.sqrt(np.sum(returns_24 ** 2))),
        "realized_volatility_trailing_168h": float(np.sqrt(np.sum(returns_168 ** 2))),
        "distance_from_mean_trailing_168h": float(current / np.mean(closes_168) - 1.0),
        "range_position_trailing_168h": None if range_position is None else float(range_position),
        "drawdown_from_high_trailing_168h": float(current / high - 1.0),
    }


def build_anchors(frame: pd.DataFrame) -> list[dict[str, Any]]:
    origin = frame.index[0] + pd.Timedelta(hours=168)
    rows: list[dict[str, Any]] = []
    timestamp = origin
    while timestamp <= frame.index[-1]:
        values = predictor_values(frame, timestamp)
        if all(value is not None and math.isfinite(float(value)) for value in values.values()):
            rows.append({
                "anchor_ordinal": len(rows),
                "anchor_timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                **values,
            })
        timestamp += pd.Timedelta(hours=168)
    counts = partition_counts(len(rows))
    boundaries = np.cumsum((0,) + counts)
    for row in rows:
        ordinal = int(row["anchor_ordinal"])
        row["partition"] = 1 + next(
            index for index in range(3)
            if boundaries[index] <= ordinal < boundaries[index + 1]
        )
    return rows


def candidate_inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for predictor in PREDICTORS:
        for family in OUTCOME_FAMILIES:
            for horizon in HORIZONS:
                rows.append({
                    "candidate_ordinal": len(rows),
                    "candidate_id": f"{predictor}__{family}__{horizon}h",
                    "predictor": predictor,
                    "outcome_family": family,
                    "horizon_hours": horizon,
                    "outcome_column": f"outcome_{family}_{horizon}h",
                })
    if len(rows) != DEFAULT_CONTRACT.candidate_count:
        raise AssertionError("candidate count mismatch")
    return rows


def add_outcomes(frame: pd.DataFrame, anchors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for anchor in anchors:
        row = dict(anchor)
        timestamp = pd.Timestamp(anchor["anchor_timestamp"])
        current = float(frame.loc[timestamp, "close"])
        for horizon in HORIZONS:
            end = timestamp + pd.Timedelta(hours=horizon)
            if end not in frame.index:
                values = {family: None for family in OUTCOME_FAMILIES}
            else:
                closes = _window(frame, timestamp, end)
                forward = float(np.log(float(closes[-1]) / current))
                returns = np.diff(np.log(closes))
                values = {
                    "R": forward,
                    "M": abs(forward),
                    "V": float(np.sqrt(np.sum(returns ** 2))),
                }
            for family, value in values.items():
                row[f"outcome_{family}_{horizon}h"] = value
        output.append(row)
    return output


def ols_hc3(x: np.ndarray, y: np.ndarray) -> OLSResult:
    if x.ndim != 2 or y.ndim != 1 or len(x) != len(y):
        raise ValueError("ESTIMATOR_FAILURE")
    rank = int(np.linalg.matrix_rank(x))
    if rank != x.shape[1]:
        raise ValueError("RANK_DEFICIENT_DESIGN")
    xtx_inv = np.linalg.inv(x.T @ x)
    beta = xtx_inv @ x.T @ y
    residual = y - x @ beta
    leverage = np.einsum("ij,jk,ik->i", x, xtx_inv, x)
    denominator = 1.0 - leverage
    if np.any(denominator <= 0):
        raise ValueError("ESTIMATOR_FAILURE")
    scaled = residual / denominator
    covariance = xtx_inv @ (x.T @ ((scaled ** 2)[:, None] * x)) @ xtx_inv
    variance = float(covariance[1, 1])
    if not math.isfinite(variance) or variance <= 0:
        raise ValueError("ESTIMATOR_FAILURE")
    coefficient = float(beta[1])
    standard_error = math.sqrt(variance)
    p_value = float(2.0 * ndtr(-abs(coefficient / standard_error)))
    margin = 1.959963984540054 * standard_error
    return OLSResult(
        coefficient=coefficient,
        standard_error=standard_error,
        p_value=p_value,
        confidence_interval_low=coefficient - margin,
        confidence_interval_high=coefficient + margin,
        n_obs=len(y),
        rank=rank,
    )


def _complete_frame(anchors: Sequence[Mapping[str, Any]], candidate: Mapping[str, Any]) -> pd.DataFrame:
    columns = ["partition", candidate["predictor"], candidate["outcome_column"]]
    frame = pd.DataFrame(anchors)
    if any(column not in frame.columns for column in columns):
        return pd.DataFrame(columns=columns)
    frame = frame[columns].copy()
    frame[candidate["predictor"]] = pd.to_numeric(frame[candidate["predictor"]], errors="coerce")
    frame[candidate["outcome_column"]] = pd.to_numeric(frame[candidate["outcome_column"]], errors="coerce")
    return frame.dropna().reset_index(drop=True)


def _fit(sample: pd.DataFrame, development: pd.DataFrame, predictor: str, outcome: str) -> tuple[OLSResult, float, float]:
    values = development[predictor].to_numpy(float)
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=0))
    if not math.isfinite(mean) or not math.isfinite(std) or std <= 0:
        raise ValueError("ZERO_OR_NONFINITE_VARIANCE")
    standardized = (sample[predictor].to_numpy(float) - mean) / std
    y = sample[outcome].to_numpy(float)
    if not np.isfinite(standardized).all() or not np.isfinite(y).all():
        raise ValueError("OUTCOME_OR_PREDICTOR_UNAVAILABLE")
    x = np.column_stack((np.ones(len(sample), dtype=float), standardized))
    return ols_hc3(x, y), mean, std


def _blank_result(candidate: Mapping[str, Any], counts: Mapping[int, int]) -> dict[str, Any]:
    row = {name: None for name in RESULT_COLUMNS}
    row.update({name: candidate[name] for name in CANDIDATE_COLUMNS if name != "outcome_column"})
    row.update({
        "rankable": False,
        "directionally_consistent": False,
        "pooled_n_obs": sum(counts.values()),
        "partition_1_complete_n": counts.get(1, 0),
        "partition_2_complete_n": counts.get(2, 0),
        "partition_3_complete_n": counts.get(3, 0),
    })
    return row


def evaluate_candidate(anchors: Sequence[Mapping[str, Any]], candidate: Mapping[str, Any]) -> dict[str, Any]:
    frame = _complete_frame(anchors, candidate)
    counts = {partition: int((frame["partition"] == partition).sum()) for partition in (1, 2, 3)} if len(frame) else {1: 0, 2: 0, 3: 0}
    row = _blank_result(candidate, counts)
    predictor = str(candidate["predictor"])
    outcome = str(candidate["outcome_column"])
    if frame.empty:
        row.update(status="OUTCOME_OR_PREDICTOR_UNAVAILABLE", failure_reason="no candidate-complete rows")
        return row
    if len(frame) < 90 or any(counts[p] < 25 for p in (1, 2, 3)):
        row.update(status="INSUFFICIENT_SUPPORT", failure_reason="minimum support gate failed")
        return row
    fits = {
        "pooled": (frame, frame),
        "partition_2": (frame[frame["partition"] == 2], frame[frame["partition"] == 1]),
        "partition_3": (frame[frame["partition"] == 3], frame[frame["partition"].isin((1, 2))]),
    }
    results: dict[str, OLSResult] = {}
    try:
        for name, (sample, development) in fits.items():
            result, mean, std = _fit(sample, development, predictor, outcome)
            results[name] = result
            row[f"{name}_development_mean"] = mean
            row[f"{name}_development_population_std"] = std
            row[f"{name}_coefficient"] = result.coefficient
            row[f"{name}_standard_error_hc3"] = result.standard_error
            row[f"{name}_p_value"] = result.p_value
            row[f"{name}_confidence_interval_low"] = result.confidence_interval_low
            row[f"{name}_confidence_interval_high"] = result.confidence_interval_high
    except ValueError as exc:
        status = str(exc)
        if status not in STATUS_ORDER:
            status = "ESTIMATOR_FAILURE"
        row.update(status=status, failure_reason=str(exc))
        return row
    coefficients = [results[name].coefficient for name in ("pooled", "partition_2", "partition_3")]
    if any(not math.isfinite(value) or value == 0 for value in coefficients):
        row.update(status="ESTIMATOR_FAILURE", failure_reason="nonfinite or zero coefficient")
        return row
    signs = {1 if value > 0 else -1 for value in coefficients}
    row.update(
        rankable=True,
        directionally_consistent=len(signs) == 1,
        status="MULTIPLICITY_NOT_MET",
        failure_reason=None,
    )
    return row


def apply_bh(rows: list[dict[str, Any]]) -> None:
    for family in OUTCOME_FAMILIES:
        eligible = [row for row in rows if row["outcome_family"] == family and row["rankable"]]
        ordered = sorted(eligible, key=lambda row: (row["pooled_p_value"], row["candidate_id"]))
        m = len(ordered)
        adjusted = [float(row["pooled_p_value"]) * m / rank for rank, row in enumerate(ordered, 1)]
        running = 1.0
        for index in range(m - 1, -1, -1):
            running = min(running, adjusted[index], 1.0)
            row = ordered[index]
            row["family_bh_rank"] = index + 1
            row["family_bh_adjusted_q_value"] = running
        for row in eligible:
            if float(row["family_bh_adjusted_q_value"]) > 0.05:
                row["status"] = "MULTIPLICITY_NOT_MET"
            elif not row["directionally_consistent"]:
                row["status"] = "DIRECTION_INCONSISTENT"
            else:
                row["status"] = "SUPPORTED_RESEARCH_ASSOCIATION"


def evaluate_all(anchors_with_outcomes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [evaluate_candidate(anchors_with_outcomes, candidate) for candidate in candidate_inventory()]
    apply_bh(rows)
    return rows


def fold_plan(anchors: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    partitions: list[dict[str, Any]] = []
    for number in (1, 2, 3):
        rows = [row for row in anchors if row["partition"] == number]
        partitions.append({
            "partition": number,
            "count": len(rows),
            "start_ordinal": rows[0]["anchor_ordinal"] if rows else None,
            "end_ordinal": rows[-1]["anchor_ordinal"] if rows else None,
            "start_timestamp": rows[0]["anchor_timestamp"] if rows else None,
            "end_timestamp": rows[-1]["anchor_timestamp"] if rows else None,
        })
    return {
        "anchor_count": len(anchors),
        "anchor_spacing_hours": 168,
        "remainder_assignment_rule": "earlier_partitions_first",
        "partitions": partitions,
        "partition_2_evaluation": {"development_partitions": [1], "evaluation_partition": 2},
        "partition_3_evaluation": {"development_partitions": [1, 2], "evaluation_partition": 3},
        "pooled_partitions": [1, 2, 3],
    }


def source_manifest(path: Path, predictive_outcomes_generated: bool) -> dict[str, Any]:
    return {
        "source_path": DEFAULT_CONTRACT.source_path,
        "sha256": sha256_file(path),
        "byte_count": path.stat().st_size,
        "data_row_count": DEFAULT_CONTRACT.source_row_count,
        "ordered_schema": list(SOURCE_COLUMNS),
        "first_timestamp": DEFAULT_CONTRACT.first_timestamp,
        "last_timestamp": DEFAULT_CONTRACT.last_timestamp,
        "cadence_hours": 1,
        "source_reconciliation_status": "PASS",
        "predictive_outcomes_generated": predictive_outcomes_generated,
    }


def report_text(source: Mapping[str, Any], anchors: Sequence[Mapping[str, Any]], results: Sequence[Mapping[str, Any]]) -> str:
    status_counts = {status: sum(row["status"] == status for row in results) for status in STATUS_ORDER}
    supported = [row for row in results if row["status"] == "SUPPORTED_RESEARCH_ASSOCIATION"]
    lines = [
        "# Campaign #48 — Simple BTC Price-State Predictive Baselines", "",
        "## Source", "", f"- Path: `{source['source_path']}`", f"- SHA-256: `{source['sha256']}`", "",
        "## Inventory", "", f"- Anchors: `{len(anchors)}`", f"- Predictors: `{len(PREDICTORS)}`",
        f"- Outcome families: `{len(OUTCOME_FAMILIES)}`", f"- Horizons: `{len(HORIZONS)}`",
        f"- Candidates: `{len(results)}`", f"- Rankable: `{sum(bool(row['rankable']) for row in results)}`", "",
        "## Status counts", "",
    ]
    lines.extend(f"- `{status}`: `{status_counts[status]}`" for status in STATUS_ORDER)
    lines.extend(["", "## Supported candidates", ""])
    if supported:
        lines.extend(["| Candidate | Coefficient | Adjusted q |", "|---|---:|---:|"])
        lines.extend(
            f"| `{row['candidate_id']}` | {format(float(row['pooled_coefficient']), '.17g')} | {format(float(row['family_bh_adjusted_q_value']), '.17g')} |"
            for row in supported
        )
    else:
        lines.append("None.")
    lines.extend([
        "", "## Interpretation boundary", "",
        "This is a research-only association study. A supported association does not establish deployable alpha, economic value, transaction-cost robustness, portfolio improvement, superiority to Core v1, or production readiness.",
        "", "No runtime, threshold, regime, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change is authorized.", "",
    ])
    return "\n".join(lines)


def canonical_payload_digest(anchors: Sequence[Mapping[str, Any]], candidates: Sequence[Mapping[str, Any]], fold: Mapping[str, Any], results: Sequence[Mapping[str, Any]], source: Mapping[str, Any]) -> str:
    payload = {"anchors": anchors, "candidates": candidates, "fold_plan": fold, "results": results, "source": source}
    return sha256_bytes(json_text(payload).encode("utf-8"))


def build_output_texts(source_path: Path, frame: pd.DataFrame) -> dict[str, str]:
    anchors = build_anchors(frame)
    candidates = candidate_inventory()
    with_outcomes = add_outcomes(frame, anchors)
    results = evaluate_all(with_outcomes)
    fold = fold_plan(anchors)
    source = source_manifest(source_path, predictive_outcomes_generated=True)
    texts: dict[str, str] = {
        "price_state_anchor_inventory.csv": csv_text(anchors, ANCHOR_COLUMNS),
        "price_state_anchor_inventory.json": json_text(anchors),
        "price_state_candidate_inventory.csv": csv_text(candidates, CANDIDATE_COLUMNS),
        "price_state_candidate_inventory.json": json_text(candidates),
        "price_state_fold_plan.json": json_text(fold),
        "price_state_results.csv": csv_text(results, RESULT_COLUMNS),
        "price_state_results.json": json_text(results),
        "price_state_report.md": report_text(source, anchors, results),
        "price_state_source_manifest.json": json_text(source),
    }
    files = [
        {"path": name, "byte_count": len(text.encode("utf-8")), "sha256": sha256_bytes(text.encode("utf-8"))}
        for name, text in texts.items()
    ]
    manifest = {
        "campaign_id": CAMPAIGN_ID,
        "specification_freeze_commit": SPECIFICATION_FREEZE,
        "implementation_handoff_freeze_commit": HANDOFF_FREEZE,
        "source_manifest_digest": sha256_bytes(texts["price_state_source_manifest.json"].encode("utf-8")),
        "predictors": list(PREDICTORS),
        "outcome_families": list(OUTCOME_FAMILIES),
        "horizons": list(HORIZONS),
        "candidate_count": len(candidates),
        "anchor_count": len(anchors),
        "partition_counts": partition_counts(len(anchors)),
        "canonical_files": list(OUTPUT_FILENAMES),
        "files": files,
        "payload_digest": canonical_payload_digest(anchors, candidates, fold, results, source),
        "serialization_contract_version": SERIALIZATION_CONTRACT_VERSION,
        "research_only": True,
        "observation_only": True,
        "predictive_outcomes_generated": True,
    }
    texts["price_state_manifest.json"] = json_text(manifest)
    return texts


def preflight(path: Path) -> dict[str, Any]:
    frame = load_source(path)
    anchors = build_anchors(frame)
    candidates = candidate_inventory()
    return {
        "status": "PASS",
        "source": source_manifest(path, predictive_outcomes_generated=False),
        "anchor_count": len(anchors),
        "partition_counts": partition_counts(len(anchors)),
        "predictor_count": len(PREDICTORS),
        "candidate_count": len(candidates),
        "predictive_outcomes_generated": False,
    }


def validate_output_directory(path: Path) -> None:
    names = tuple(sorted(item.name for item in path.iterdir() if item.is_file()))
    if names != tuple(sorted(OUTPUT_FILENAMES)):
        raise ValueError("CANONICAL_FILE_SET_MISMATCH")
    for name in OUTPUT_FILENAMES:
        data = (path / name).read_bytes()
        data.decode("utf-8")
        if b"\r" in data:
            raise ValueError(f"CRLF_NOT_ALLOWED:{name}")
    results_json = strict_json(path / "price_state_results.json")
    if len(results_json) != 72:
        raise ValueError("RESULT_COUNT_MISMATCH")
    manifest = strict_json(path / "price_state_manifest.json")
    if manifest["canonical_files"] != list(OUTPUT_FILENAMES):
        raise ValueError("MANIFEST_FILE_ORDER_MISMATCH")
    for item in manifest["files"]:
        target = path / item["path"]
        if target.stat().st_size != item["byte_count"] or sha256_file(target) != item["sha256"]:
            raise ValueError(f"MANIFEST_RECONCILIATION_FAILURE:{item['path']}")
