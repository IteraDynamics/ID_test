"""Deterministic, observation-only Campaign #47 regime-structure discovery."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.special import ndtr

SOURCE_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")
STATE_COLUMNS = (
    "bar_index", "timestamp", "regime_label", "confidence", "reason",
    "atr_pct", "atr_accel", "ema_roc", "ema_spread", "is_warmup",
    "source_row_digest",
)
RUN_COLUMNS = (
    "state_run_id", "state_run_ordinal", "regime_label", "start_bar_index",
    "end_bar_index", "start_timestamp", "end_timestamp", "duration_bars",
    "entered_from_regime_label", "exited_to_regime_label",
)
TRANSITION_COLUMNS = (
    "transition_id", "transition_ordinal", "anchor_bar_index", "anchor_timestamp",
    "prior_regime_label", "current_regime_label", "ordered_transition",
    "prior_state_start_timestamp", "prior_state_duration_bars",
    "prior_transition_timestamp", "spacing_since_prior_transition_bars",
    "spacing_since_prior_transition_hours", "current_state_age_bars",
    "anchor_source_row_digest",
)
PREDICTORS = (
    "log1p_current_state_age_hours",
    "log1p_previous_state_duration_hours",
    "log1p_hours_since_previous_transition",
    "transition_count_trailing_24h",
    "transition_count_trailing_72h",
    "transition_count_trailing_168h",
)
CONTROL_COLUMNS = (
    "trailing_log_return_24h",
    "trailing_log_return_72h",
    "trailing_log_return_168h",
    "realized_volatility_24h",
    "realized_volatility_168h",
    "distance_from_close_mean_168h",
)
OUTCOME_FAMILIES = ("R", "M", "V", "S")
HORIZONS = (24, 72, 168)
OUTPUT_FILENAMES = (
    "regime_structure_source_manifest.json",
    "regime_structure_anchor_inventory.json",
    "regime_structure_anchor_inventory.csv",
    "regime_structure_candidate_inventory.json",
    "regime_structure_candidate_inventory.csv",
    "regime_structure_fold_plan.json",
    "regime_structure_results.json",
    "regime_structure_results.csv",
    "regime_structure_report.md",
    "regime_structure_manifest.json",
)

STATUS_SUPPORTED = "SUPPORTED_RESEARCH_ASSOCIATION"
STATUS_MULTIPLICITY = "MULTIPLICITY_NOT_MET"
STATUS_DIRECTION = "DIRECTION_INCONSISTENT"
STATUS_SUPPORT = "INSUFFICIENT_SUPPORT"
STATUS_UNAVAILABLE = "OUTCOME_OR_PREDICTOR_UNAVAILABLE"
STATUS_UNSEEN = "DEVELOPMENT_ABSENT_REGIME_LEVEL"
STATUS_VARIANCE = "ZERO_OR_NONFINITE_VARIANCE"
STATUS_SINGULAR = "RANK_DEFICIENT_DESIGN"
STATUS_ESTIMATOR = "ESTIMATOR_FAILURE"


@dataclass(frozen=True)
class SourcePaths:
    manifest: Path
    states: Path
    runs: Path
    transitions: Path
    btc: Path


@dataclass(frozen=True)
class FrozenContract:
    btc_sha256: str = "d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079"
    btc_byte_count: int = 4_792_028
    btc_row_count: int = 70_069
    btc_first_timestamp: str = "2018-01-01 00:00:00"
    btc_last_timestamp: str = "2025-12-31 00:00:00"
    state_count: int = 70_069
    run_count: int = 2_790
    transition_count: int = 2_789
    candidate_count: int = 72


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


def strict_json(path: Path) -> Any:
    def reject(value: str) -> None:
        raise ValueError(f"non-strict JSON constant: {value}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return json.load(handle, parse_constant=reject)


def _normalise(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return 0.0 if value == 0.0 else float(format(value, ".17g"))
    if isinstance(value, dict):
        return {str(k): _normalise(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(v) for v in value]
    return value


def json_text(payload: Any) -> str:
    return json.dumps(
        _normalise(payload), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    ) + "\n"


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
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: _csv_scalar(row.get(name)) for name in fieldnames})
    return buffer.getvalue()


def write_lf(path: Path, text: str) -> None:
    if "\r" in text:
        raise ValueError("canonical text contains carriage returns")
    path.write_text(text, encoding="utf-8", newline="\n")


def _read_csv(path: Path, expected: Sequence[str]) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if tuple(frame.columns) != tuple(expected):
        raise ValueError(f"ordered schema mismatch for {path}: {tuple(frame.columns)}")
    return frame


def _parse_timestamps(series: pd.Series, name: str) -> pd.Series:
    parsed = pd.to_datetime(series, errors="raise")
    if getattr(parsed.dt, "tz", None) is not None:
        raise ValueError(f"{name} timestamps must be timezone-naive")
    if parsed.duplicated().any() or not parsed.is_monotonic_increasing:
        raise ValueError(f"{name} timestamps must be unique and increasing")
    if not ((parsed.dt.minute == 0) & (parsed.dt.second == 0) & (parsed.dt.microsecond == 0)).all():
        raise ValueError(f"{name} timestamps must be exact hours")
    return parsed


def preflight(paths: SourcePaths, contract: FrozenContract = DEFAULT_CONTRACT) -> dict[str, Any]:
    required = (paths.manifest, paths.states, paths.runs, paths.transitions, paths.btc)
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)

    manifest = strict_json(paths.manifest)
    expected_files = manifest.get("files", {})
    for path in (paths.states, paths.runs, paths.transitions):
        expected = expected_files.get(path.name)
        if not expected or sha256_file(path) != expected:
            raise ValueError(f"governed digest mismatch: {path.name}")

    if sha256_file(paths.btc) != contract.btc_sha256:
        raise ValueError("BTC digest mismatch")
    if paths.btc.stat().st_size != contract.btc_byte_count:
        raise ValueError("BTC byte-count mismatch")

    btc = pd.read_csv(paths.btc)
    if tuple(btc.columns) != SOURCE_COLUMNS or len(btc) != contract.btc_row_count:
        raise ValueError("BTC schema/count mismatch")
    btc_ts = _parse_timestamps(btc["timestamp"], "BTC")
    if btc_ts.iloc[0].strftime("%Y-%m-%d %H:%M:%S") != contract.btc_first_timestamp:
        raise ValueError("BTC first timestamp mismatch")
    if btc_ts.iloc[-1].strftime("%Y-%m-%d %H:%M:%S") != contract.btc_last_timestamp:
        raise ValueError("BTC last timestamp mismatch")

    states = _read_csv(paths.states, STATE_COLUMNS)
    runs = _read_csv(paths.runs, RUN_COLUMNS)
    transitions = _read_csv(paths.transitions, TRANSITION_COLUMNS)
    if (len(states), len(runs), len(transitions)) != (
        contract.state_count, contract.run_count, contract.transition_count
    ):
        raise ValueError("state/run/transition count mismatch")

    state_ts = _parse_timestamps(states["timestamp"], "state")
    if not state_ts.equals(btc_ts):
        raise ValueError("state/BTC timestamps do not reconcile")
    if states["bar_index"].astype(int).tolist() != list(range(len(states))):
        raise ValueError("state bar indices do not reconcile")
    if runs["state_run_ordinal"].astype(int).tolist() != list(range(len(runs))):
        raise ValueError("run ordinals do not reconcile")
    if transitions["transition_ordinal"].astype(int).tolist() != list(range(len(transitions))):
        raise ValueError("transition ordinals do not reconcile")

    return {
        "status": "PASS",
        "predictive_outcomes_generated": False,
        "counts": {
            "states": len(states),
            "runs": len(runs),
            "transitions": len(transitions),
        },
        "source": {
            "path": manifest["source"]["path"],
            "sha256": contract.btc_sha256,
            "byte_count": contract.btc_byte_count,
            "row_count": contract.btc_row_count,
            "first_timestamp": contract.btc_first_timestamp,
            "last_timestamp": contract.btc_last_timestamp,
        },
    }


def load_sources(paths: SourcePaths) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    btc = pd.read_csv(paths.btc)
    btc["timestamp"] = pd.to_datetime(btc["timestamp"], errors="raise")
    for column in SOURCE_COLUMNS[1:]:
        btc[column] = pd.to_numeric(btc[column], errors="raise")
    states = _read_csv(paths.states, STATE_COLUMNS)
    states["timestamp"] = pd.to_datetime(states["timestamp"], errors="raise")
    states["bar_index"] = states["bar_index"].astype(int)
    runs = _read_csv(paths.runs, RUN_COLUMNS)
    for column in ("state_run_ordinal", "start_bar_index", "end_bar_index", "duration_bars"):
        runs[column] = runs[column].astype(int)
    runs["start_timestamp"] = pd.to_datetime(runs["start_timestamp"], errors="raise")
    runs["end_timestamp"] = pd.to_datetime(runs["end_timestamp"], errors="raise")
    transitions = _read_csv(paths.transitions, TRANSITION_COLUMNS)
    transitions["anchor_timestamp"] = pd.to_datetime(transitions["anchor_timestamp"], errors="raise")
    transitions["transition_ordinal"] = transitions["transition_ordinal"].astype(int)
    return btc, states, runs, transitions


def _exact_window(frame: pd.DataFrame, timestamp: pd.Timestamp, hours: int) -> pd.DataFrame | None:
    start = timestamp - pd.Timedelta(hours=hours)
    window = frame[(frame["timestamp"] >= start) & (frame["timestamp"] <= timestamp)]
    expected = pd.date_range(start, timestamp, freq="h")
    if len(window) != len(expected) or not window["timestamp"].reset_index(drop=True).equals(pd.Series(expected)):
        return None
    return window


def controls_at(btc: pd.DataFrame, timestamp: pd.Timestamp) -> dict[str, float] | None:
    window = _exact_window(btc, timestamp, 168)
    if window is None:
        return None
    close = window["close"].to_numpy(float)
    current = close[-1]
    out: dict[str, float] = {}
    for hours in (24, 72, 168):
        out[f"trailing_log_return_{hours}h"] = float(math.log(current / close[-(hours + 1)]))
    returns = np.diff(np.log(close))
    out["realized_volatility_24h"] = float(math.sqrt(float(np.sum(returns[-24:] ** 2))))
    out["realized_volatility_168h"] = float(math.sqrt(float(np.sum(returns ** 2))))
    mean_close = float(np.mean(close))
    std_close = float(np.std(close, ddof=0))
    if not math.isfinite(std_close) or std_close <= 0:
        return None
    out["distance_from_close_mean_168h"] = (current - mean_close) / std_close
    return out


def _run_lookup(runs: pd.DataFrame, bar_index: int) -> tuple[pd.Series, pd.Series | None]:
    match = runs[(runs["start_bar_index"] <= bar_index) & (runs["end_bar_index"] >= bar_index)]
    if len(match) != 1:
        raise ValueError(f"run lookup failed at bar {bar_index}")
    current = match.iloc[0]
    ordinal = int(current["state_run_ordinal"])
    previous = None if ordinal == 0 else runs.iloc[ordinal - 1]
    return current, previous


def _transition_at_or_before(transitions: pd.DataFrame, timestamp: pd.Timestamp) -> pd.Series | None:
    matches = transitions[transitions["anchor_timestamp"] <= timestamp]
    return None if matches.empty else matches.iloc[-1]


def structural_predictors(
    anchor_timestamp: pd.Timestamp,
    bar_index: int,
    runs: pd.DataFrame,
    transitions: pd.DataFrame,
) -> dict[str, float | None]:
    current, previous = _run_lookup(runs, bar_index)
    age = int((anchor_timestamp - current["start_timestamp"]).total_seconds() // 3600)
    prior_transition = _transition_at_or_before(transitions, anchor_timestamp)
    result: dict[str, float | None] = {
        "log1p_current_state_age_hours": math.log1p(age),
        "log1p_previous_state_duration_hours": (
            None if previous is None else math.log1p(int(previous["duration_bars"]))
        ),
        "log1p_hours_since_previous_transition": (
            None if prior_transition is None else math.log1p(
                int((anchor_timestamp - prior_transition["anchor_timestamp"]).total_seconds() // 3600)
            )
        ),
    }
    for hours in (24, 72, 168):
        lower = anchor_timestamp - pd.Timedelta(hours=hours)
        count = int(((transitions["anchor_timestamp"] > lower) & (
            transitions["anchor_timestamp"] <= anchor_timestamp
        )).sum())
        result[f"transition_count_trailing_{hours}h"] = float(count)
    return result


def outcome_at(
    btc: pd.DataFrame,
    states: pd.DataFrame,
    timestamp: pd.Timestamp,
    family: str,
    horizon: int,
) -> float | None:
    future = timestamp + pd.Timedelta(hours=horizon)
    btc_window = btc[(btc["timestamp"] >= timestamp) & (btc["timestamp"] <= future)]
    expected = pd.date_range(timestamp, future, freq="h")
    if len(btc_window) != len(expected) or not btc_window["timestamp"].reset_index(drop=True).equals(pd.Series(expected)):
        return None
    closes = btc_window["close"].to_numpy(float)
    forward = float(math.log(closes[-1] / closes[0]))
    if family == "R":
        return forward
    if family == "M":
        return abs(forward)
    if family == "V":
        returns = np.diff(np.log(closes))
        return float(math.sqrt(float(np.sum(returns ** 2))))
    if family == "S":
        state_window = states[(states["timestamp"] >= timestamp) & (states["timestamp"] <= future)]
        if len(state_window) != len(expected) or not state_window["timestamp"].reset_index(drop=True).equals(pd.Series(expected)):
            return None
        anchor_label = str(state_window.iloc[0]["regime_label"])
        return float((state_window.iloc[1:]["regime_label"] == anchor_label).all())
    raise ValueError(f"unknown outcome family: {family}")


def build_anchor_inventory(
    btc: pd.DataFrame,
    states: pd.DataFrame,
    runs: pd.DataFrame,
    transitions: pd.DataFrame,
) -> list[dict[str, Any]]:
    merged = states[["bar_index", "timestamp", "regime_label"]].merge(
        btc[["timestamp"]], on="timestamp", how="inner", validate="one_to_one"
    )
    origin: pd.Timestamp | None = None
    for row in merged.itertuples(index=False):
        if row.regime_label != "UNKNOWN" and controls_at(btc, row.timestamp) is not None:
            origin = row.timestamp
            break
    if origin is None:
        raise ValueError("no eligible common-grid origin")

    state_map = states.set_index("timestamp")
    btc_timestamps = set(btc["timestamp"])
    rows: list[dict[str, Any]] = []
    timestamp = origin
    final_timestamp = btc["timestamp"].iloc[-1]
    while timestamp <= final_timestamp:
        if timestamp in btc_timestamps and timestamp in state_map.index:
            state_row = state_map.loc[timestamp]
            controls = controls_at(btc, timestamp)
            if str(state_row["regime_label"]) != "UNKNOWN" and controls is not None:
                predictors = structural_predictors(
                    timestamp, int(state_row["bar_index"]), runs, transitions
                )
                row: dict[str, Any] = {
                    "anchor_ordinal": len(rows),
                    "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "bar_index": int(state_row["bar_index"]),
                    "current_regime": str(state_row["regime_label"]),
                }
                row.update(controls)
                row.update(predictors)
                for family in OUTCOME_FAMILIES:
                    for horizon in HORIZONS:
                        row[f"outcome_{family}_{horizon}h"] = outcome_at(
                            btc, states, timestamp, family, horizon
                        )
                rows.append(row)
        timestamp += pd.Timedelta(hours=168)

    counts = partition_counts(len(rows))
    boundaries = np.cumsum((0,) + counts)
    for row in rows:
        ordinal = int(row["anchor_ordinal"])
        row["partition"] = 1 + next(
            i for i in range(3) if boundaries[i] <= ordinal < boundaries[i + 1]
        )
    return rows


def partition_counts(total: int) -> tuple[int, int, int]:
    base, remainder = divmod(total, 3)
    return tuple(base + (1 if i < remainder else 0) for i in range(3))  # type: ignore[return-value]


def candidate_inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for predictor in PREDICTORS:
        for family in OUTCOME_FAMILIES:
            for horizon in HORIZONS:
                rows.append({
                    "candidate_id": f"{predictor}__{family}__{horizon}h",
                    "predictor": predictor,
                    "outcome_family": family,
                    "horizon_hours": horizon,
                    "outcome_column": f"outcome_{family}_{horizon}h",
                })
    if len(rows) != DEFAULT_CONTRACT.candidate_count:
        raise AssertionError("candidate count mismatch")
    return rows


def _design(
    frame: pd.DataFrame,
    predictor: str,
    outcome: str,
    development: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    continuous = (predictor,) + CONTROL_COLUMNS
    means: dict[str, float] = {}
    stds: dict[str, float] = {}
    for column in continuous:
        values = development[column].to_numpy(float)
        mean = float(np.mean(values))
        std = float(np.std(values, ddof=0))
        if not math.isfinite(mean) or not math.isfinite(std) or std <= 0:
            raise ValueError(STATUS_VARIANCE)
        means[column], stds[column] = mean, std

    levels = sorted(str(v) for v in development["current_regime"].unique())
    if not levels:
        raise ValueError(STATUS_UNSEEN)
    unseen = sorted(set(str(v) for v in frame["current_regime"].unique()) - set(levels))
    if unseen:
        raise ValueError(STATUS_UNSEEN)
    reference = levels[0]
    columns = [np.ones(len(frame), dtype=float)]
    for column in continuous:
        columns.append((frame[column].to_numpy(float) - means[column]) / stds[column])
    for level in levels[1:]:
        columns.append((frame["current_regime"].astype(str) == level).to_numpy(float))
    x = np.column_stack(columns)
    y = frame[outcome].to_numpy(float)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError(STATUS_UNAVAILABLE)
    return x, y, {
        "means": means,
        "population_standard_deviations": stds,
        "regime_levels": levels,
        "reference_regime": reference,
    }


def ols_hc3(x: np.ndarray, y: np.ndarray) -> OLSResult:
    if x.ndim != 2 or y.ndim != 1 or len(x) != len(y):
        raise ValueError("invalid estimator shapes")
    rank = int(np.linalg.matrix_rank(x))
    if rank != x.shape[1]:
        raise ValueError(STATUS_SINGULAR)
    xtx_inv = np.linalg.inv(x.T @ x)
    beta = xtx_inv @ x.T @ y
    residual = y - x @ beta
    leverage = np.einsum("ij,jk,ik->i", x, xtx_inv, x)
    denominator = 1.0 - leverage
    if np.any(denominator <= 0):
        raise ValueError(STATUS_ESTIMATOR)
    scaled = residual / denominator
    meat = x.T @ ((scaled ** 2)[:, None] * x)
    covariance = xtx_inv @ meat @ xtx_inv
    variance = float(covariance[1, 1])
    if not math.isfinite(variance) or variance <= 0:
        raise ValueError(STATUS_ESTIMATOR)
    coefficient = float(beta[1])
    standard_error = math.sqrt(variance)
    z_value = coefficient / standard_error
    p_value = float(2.0 * ndtr(-abs(z_value)))
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
    columns = [
        "partition", "current_regime", candidate["predictor"], candidate["outcome_column"],
        *CONTROL_COLUMNS,
    ]
    frame = pd.DataFrame(anchors)
    for column in columns:
        if column not in frame:
            return pd.DataFrame(columns=columns)
    frame = frame[columns].copy()
    numeric = [candidate["predictor"], candidate["outcome_column"], *CONTROL_COLUMNS]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna().reset_index(drop=True)


def _fit_candidate_sample(
    sample: pd.DataFrame,
    development: pd.DataFrame,
    candidate: Mapping[str, Any],
) -> tuple[OLSResult, dict[str, Any]]:
    x, y, metadata = _design(
        sample, str(candidate["predictor"]), str(candidate["outcome_column"]), development
    )
    return ols_hc3(x, y), metadata


def evaluate_candidates(
    anchors: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    candidates = list(candidate_inventory() if candidates is None else candidates)
    results: list[dict[str, Any]] = []
    for candidate in candidates:
        row = dict(candidate)
        row.update({
            "rankable": False,
            "directional_consistency": False,
            "supported_association": False,
            "status": STATUS_UNAVAILABLE,
            "bh_adjusted_q_value": None,
        })
        frame = _complete_frame(anchors, candidate)
        partition_sizes = {
            part: int((frame["partition"] == part).sum()) if not frame.empty else 0
            for part in (1, 2, 3)
        }
        row["complete_pooled_anchors"] = len(frame)
        row["complete_partition_counts"] = [partition_sizes[i] for i in (1, 2, 3)]
        if len(frame) < 90 or min(partition_sizes.values()) < 25:
            row["status"] = STATUS_SUPPORT
            results.append(row)
            continue
        try:
            pooled, pooled_meta = _fit_candidate_sample(frame, frame, candidate)
            eval2 = frame[frame["partition"] == 2].reset_index(drop=True)
            dev2 = frame[frame["partition"] == 1].reset_index(drop=True)
            fit2, meta2 = _fit_candidate_sample(eval2, dev2, candidate)
            eval3 = frame[frame["partition"] == 3].reset_index(drop=True)
            dev3 = frame[frame["partition"].isin([1, 2])].reset_index(drop=True)
            fit3, meta3 = _fit_candidate_sample(eval3, dev3, candidate)
        except ValueError as exc:
            row["status"] = str(exc)
            results.append(row)
            continue
        row.update({
            "rankable": True,
            "status": STATUS_MULTIPLICITY,
            "pooled_coefficient": pooled.coefficient,
            "pooled_standard_error_hc3": pooled.standard_error,
            "pooled_p_value": pooled.p_value,
            "pooled_confidence_interval_95_low": pooled.confidence_interval_low,
            "pooled_confidence_interval_95_high": pooled.confidence_interval_high,
            "partition_2_evaluation_coefficient": fit2.coefficient,
            "partition_3_evaluation_coefficient": fit3.coefficient,
            "pooled_design": pooled_meta,
            "partition_2_design": meta2,
            "partition_3_design": meta3,
        })
        signs = [pooled.coefficient, fit2.coefficient, fit3.coefficient]
        row["directional_consistency"] = all(v > 0 for v in signs) or all(v < 0 for v in signs)
        results.append(row)

    for family in OUTCOME_FAMILIES:
        family_rows = [r for r in results if r["outcome_family"] == family and r["rankable"]]
        adjusted = benjamini_hochberg({
            str(r["candidate_id"]): float(r["pooled_p_value"]) for r in family_rows
        })
        for row in family_rows:
            row["bh_adjusted_q_value"] = adjusted[str(row["candidate_id"])]
            if row["bh_adjusted_q_value"] <= 0.05 and row["directional_consistency"]:
                row["status"] = STATUS_SUPPORTED
                row["supported_association"] = True
            elif row["bh_adjusted_q_value"] <= 0.05:
                row["status"] = STATUS_DIRECTION
            else:
                row["status"] = STATUS_MULTIPLICITY
    return results


def benjamini_hochberg(p_values: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    m = len(ordered)
    adjusted: dict[str, float] = {}
    running = 1.0
    for rank in range(m, 0, -1):
        candidate_id, p_value = ordered[rank - 1]
        running = min(running, p_value * m / rank)
        adjusted[candidate_id] = min(1.0, running)
    return adjusted


def source_manifest(paths: SourcePaths, preflight_result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "experiment": "campaign_47_historical_regime_structure_discovery",
        "observation_only": True,
        "predictive_outcomes_generated": True,
        "preflight": dict(preflight_result),
        "files": {
            path.name: {"sha256": sha256_file(path), "byte_count": path.stat().st_size}
            for path in (paths.manifest, paths.states, paths.runs, paths.transitions, paths.btc)
        },
    }


def render_report(results: Sequence[Mapping[str, Any]], anchor_count: int) -> str:
    rankable = sum(bool(row["rankable"]) for row in results)
    supported = sum(bool(row["supported_association"]) for row in results)
    lines = [
        "# Campaign #47 Historical Regime Structure Discovery",
        "",
        "Research-only, observation-only result.",
        "",
        f"- common-grid anchors: `{anchor_count}`",
        f"- frozen candidates: `{len(results)}`",
        f"- rankable candidates: `{rankable}`",
        f"- supported research associations: `{supported}`",
        "",
        "A supported association is not deployable alpha and does not authorize a Core v1 overlay.",
        "",
    ]
    return "\n".join(lines)


def generate(
    paths: SourcePaths,
    output_dir: Path,
    contract: FrozenContract = DEFAULT_CONTRACT,
) -> dict[str, Any]:
    before = {path: sha256_file(path) for path in (
        paths.manifest, paths.states, paths.runs, paths.transitions, paths.btc
    )}
    preflight_result = preflight(paths, contract)
    btc, states, runs, transitions = load_sources(paths)
    anchors = build_anchor_inventory(btc, states, runs, transitions)
    candidates = candidate_inventory()
    results = evaluate_candidates(anchors, candidates)
    counts = partition_counts(len(anchors))

    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        payloads: dict[str, str] = {}
        payloads[OUTPUT_FILENAMES[0]] = json_text(source_manifest(paths, preflight_result))
        payloads[OUTPUT_FILENAMES[1]] = json_text(anchors)
        payloads[OUTPUT_FILENAMES[2]] = csv_text(anchors, anchors[0].keys())
        payloads[OUTPUT_FILENAMES[3]] = json_text(candidates)
        payloads[OUTPUT_FILENAMES[4]] = csv_text(candidates, candidates[0].keys())
        payloads[OUTPUT_FILENAMES[5]] = json_text({
            "anchor_count": len(anchors),
            "partition_counts": list(counts),
            "partitions": [{"partition": i, "count": counts[i - 1]} for i in (1, 2, 3)],
        })
        payloads[OUTPUT_FILENAMES[6]] = json_text(results)
        result_columns = sorted({key for row in results for key in row})
        payloads[OUTPUT_FILENAMES[7]] = csv_text(results, result_columns)
        payloads[OUTPUT_FILENAMES[8]] = render_report(results, len(anchors))

        for name in OUTPUT_FILENAMES[:-1]:
            write_lf(staging / name, payloads[name])
        file_hashes = {name: sha256_file(staging / name) for name in OUTPUT_FILENAMES[:-1]}
        manifest = {
            "experiment": "campaign_47_historical_regime_structure_discovery",
            "counts": {
                "anchors": len(anchors),
                "partitions": list(counts),
                "candidates": len(candidates),
                "rankable_candidates": sum(bool(r["rankable"]) for r in results),
                "supported_associations": sum(bool(r["supported_association"]) for r in results),
            },
            "files": file_hashes,
            "aggregate_payload_digest": sha256_bytes(
                json.dumps(file_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ),
            "observation_only": True,
            "runtime_mutation_allowed": False,
            "strategy_mutation_allowed": False,
        }
        write_lf(staging / OUTPUT_FILENAMES[-1], json_text(manifest))
        after = {path: sha256_file(path) for path in before}
        if before != after:
            raise ValueError("governed source bytes changed during generation")
        if output_dir.exists():
            output_dir.rmdir()
        staging.replace(output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    return {
        "status": "PASS",
        "output": output_dir.as_posix(),
        "outcomes_generated": True,
        "counts": {
            "anchors": len(anchors),
            "partitions": list(counts),
            "candidates": len(candidates),
            "rankable_candidates": sum(bool(r["rankable"]) for r in results),
            "supported_associations": sum(bool(r["supported_association"]) for r in results),
        },
    }
