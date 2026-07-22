"""Deterministic, observation-only diagnosis for Jump Risk prediction drift.

The module explains *why* a stream may have drifted. It never changes model
thresholds, exposure, orders, NAV, or runtime state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Mapping

import numpy as np
import pandas as pd

_RESERVED_COLUMNS = {"probability", "train_threshold", "label"}


@dataclass(frozen=True)
class WindowQuality:
    rows: int
    probability_mean: float
    probability_std: float
    threshold_mean: float
    activation_rate: float
    event_rate: float | None
    brier_score: float | None
    calibration_error: float | None
    threshold_precision: float | None
    missing_probability: float
    missing_threshold: float


@dataclass(frozen=True)
class ThresholdDistance:
    mean_signed_distance: float
    median_signed_distance: float
    below_within_001: float
    below_within_002: float
    below_within_005: float


@dataclass(frozen=True)
class FeatureComparison:
    reference_mean: float | None
    observation_mean: float | None
    standardized_mean_shift: float
    reference_missing_fraction: float
    observation_missing_fraction: float


@dataclass(frozen=True)
class DriftDiagnosis:
    asset: str
    model: str
    classification: str
    confidence: str
    reasons: tuple[str, ...]
    reference: WindowQuality
    observation: WindowQuality
    activation_rate_change: float
    activation_rate_ratio: float | None
    probability_mean_shift: float
    standardized_probability_mean_shift: float
    threshold_distance: ThresholdDistance
    feature_comparisons: Mapping[str, FeatureComparison]
    probability_buckets: tuple[Mapping[str, Any], ...]
    observation_only: bool
    runtime_integration_allowed: bool
    exposure_mutation_allowed: bool
    digest: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _validate(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted({"probability", "train_threshold"} - set(frame.columns))
    if missing:
        raise ValueError(f"Missing probability columns: {missing}")
    out = frame.copy().sort_index()
    if out.index.has_duplicates:
        raise ValueError("Prediction timestamps must be unique")
    for column in ("probability", "train_threshold"):
        out[column] = _numeric(out[column])
        invalid = out[column].notna() & ~out[column].between(0.0, 1.0)
        if bool(invalid.any()):
            raise ValueError(f"{column} contains values outside [0, 1]")
    if "label" in out.columns:
        out["label"] = _numeric(out["label"])
    return out


def _split(frame: pd.DataFrame, reference_rows: int, observation_rows: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    if reference_rows < 50 or observation_rows < 24:
        raise ValueError("reference_rows must be >= 50 and observation_rows >= 24")
    needed = reference_rows + observation_rows
    if len(frame) < needed:
        raise ValueError(f"Need at least {needed} rows, received {len(frame)}")
    return frame.iloc[-needed:-observation_rows], frame.iloc[-observation_rows:]


def _quality(frame: pd.DataFrame) -> WindowQuality:
    probability = _numeric(frame["probability"])
    threshold = _numeric(frame["train_threshold"])
    valid = pd.DataFrame({"probability": probability, "threshold": threshold}).dropna()
    activation = float((valid["probability"] >= valid["threshold"]).mean()) if not valid.empty else 0.0

    event_rate = brier = calibration = precision = None
    if "label" in frame.columns:
        outcome = pd.DataFrame(
            {"probability": probability, "threshold": threshold, "label": _numeric(frame["label"])}
        ).dropna()
        if not outcome.empty:
            labels = outcome["label"].astype(float)
            probs = outcome["probability"].astype(float)
            active = probs >= outcome["threshold"].astype(float)
            event_rate = float(labels.mean())
            brier = float(np.mean((probs - labels) ** 2))
            calibration = abs(float(probs.mean()) - event_rate)
            precision = float(labels[active].mean()) if bool(active.any()) else None

    return WindowQuality(
        rows=len(frame),
        probability_mean=float(probability.mean()),
        probability_std=float(probability.std(ddof=0)),
        threshold_mean=float(threshold.mean()),
        activation_rate=activation,
        event_rate=event_rate,
        brier_score=brier,
        calibration_error=calibration,
        threshold_precision=precision,
        missing_probability=float(probability.isna().mean()),
        missing_threshold=float(threshold.isna().mean()),
    )


def _threshold_distance(frame: pd.DataFrame) -> ThresholdDistance:
    valid = frame[["probability", "train_threshold"]].apply(_numeric).dropna()
    signed = valid["probability"] - valid["train_threshold"]
    below = -signed[signed < 0.0]
    denominator = max(len(valid), 1)
    return ThresholdDistance(
        mean_signed_distance=float(signed.mean()) if not signed.empty else 0.0,
        median_signed_distance=float(signed.median()) if not signed.empty else 0.0,
        below_within_001=float((below <= 0.01).sum() / denominator),
        below_within_002=float((below <= 0.02).sum() / denominator),
        below_within_005=float((below <= 0.05).sum() / denominator),
    )


def _features(reference: pd.DataFrame, observation: pd.DataFrame) -> dict[str, FeatureComparison]:
    output: dict[str, FeatureComparison] = {}
    for column in sorted((set(reference.columns) & set(observation.columns)) - _RESERVED_COLUMNS):
        ref_raw = _numeric(reference[column])
        obs_raw = _numeric(observation[column])
        ref = ref_raw.dropna()
        obs = obs_raw.dropna()
        ref_mean = float(ref.mean()) if not ref.empty else None
        obs_mean = float(obs.mean()) if not obs.empty else None
        shift = 0.0
        if ref_mean is not None and obs_mean is not None:
            shift = abs(obs_mean - ref_mean) / max(float(ref.std(ddof=0)), 1e-9)
        output[column] = FeatureComparison(
            reference_mean=ref_mean,
            observation_mean=obs_mean,
            standardized_mean_shift=float(shift),
            reference_missing_fraction=float(ref_raw.isna().mean()),
            observation_missing_fraction=float(obs_raw.isna().mean()),
        )
    return output


def _bucket_rows(frame: pd.DataFrame) -> tuple[Mapping[str, Any], ...]:
    columns = ["probability"] + (["label"] if "label" in frame.columns else [])
    valid = frame[columns].apply(_numeric).dropna(subset=["probability"])
    if valid.empty:
        return ()
    rank = valid["probability"].rank(method="first")
    bucket_count = min(5, len(valid))
    valid = valid.assign(bucket=pd.qcut(rank, q=bucket_count, labels=False, duplicates="drop"))
    rows: list[Mapping[str, Any]] = []
    for bucket, group in valid.groupby("bucket", observed=True):
        labels = group["label"].dropna() if "label" in group.columns else pd.Series(dtype=float)
        rows.append(
            {
                "bucket": int(bucket),
                "rows": int(len(group)),
                "probability_min": float(group["probability"].min()),
                "probability_max": float(group["probability"].max()),
                "probability_mean": float(group["probability"].mean()),
                "event_rate": float(labels.mean()) if not labels.empty else None,
            }
        )
    return tuple(rows)


def _positive_deterioration(observed: float | None, reference: float | None) -> float:
    if observed is None or reference is None:
        return 0.0
    return max(0.0, observed - reference)


def diagnose_stream(
    frame: pd.DataFrame,
    *,
    asset: str,
    model: str,
    reference_rows: int,
    observation_rows: int,
) -> DriftDiagnosis:
    """Diagnose the latest observation window against a frozen reference window."""
    clean = _validate(frame)
    reference_frame, observation_frame = _split(clean, reference_rows, observation_rows)
    reference = _quality(reference_frame)
    observation = _quality(observation_frame)
    distances = _threshold_distance(observation_frame)
    features = _features(reference_frame, observation_frame)

    activation_change = observation.activation_rate - reference.activation_rate
    activation_ratio = (
        observation.activation_rate / reference.activation_rate
        if reference.activation_rate > 0.0
        else None
    )
    probability_shift = observation.probability_mean - reference.probability_mean
    standardized_shift = abs(probability_shift) / max(reference.probability_std, 1e-9)
    brier_deterioration = _positive_deterioration(observation.brier_score, reference.brier_score)
    calibration_deterioration = _positive_deterioration(
        observation.calibration_error, reference.calibration_error
    )
    precision_drop = 0.0
    if reference.threshold_precision is not None and observation.threshold_precision is not None:
        precision_drop = max(0.0, reference.threshold_precision - observation.threshold_precision)

    feature_pipeline_suspect = any(
        metric.observation_missing_fraction >= 0.10
        or metric.observation_missing_fraction - metric.reference_missing_fraction >= 0.05
        for metric in features.values()
    )
    pipeline_suspect = (
        observation.missing_probability > 0.0
        or observation.missing_threshold > 0.0
        or feature_pipeline_suspect
    )
    quality_degraded = (
        brier_deterioration >= 0.05
        or calibration_deterioration >= 0.05
        or precision_drop >= 0.10
    )
    activation_collapsed = (
        reference.activation_rate >= 0.05
        and (activation_ratio is not None and activation_ratio <= 0.35)
        and activation_change <= -0.05
    )
    near_threshold_mass = distances.below_within_002 >= 0.10
    material_distribution_shift = standardized_shift >= 0.50

    reasons: list[str] = []
    if pipeline_suspect:
        classification = "DATA_PIPELINE_SUSPECT"
        confidence = "HIGH"
        reasons.append("missing or invalid recent model inputs/predictions increased")
    elif quality_degraded:
        classification = "MODEL_DEGRADATION"
        confidence = "HIGH"
        reasons.append("recent predictive quality deteriorated beyond diagnosis thresholds")
    elif activation_collapsed and near_threshold_mass:
        classification = "THRESHOLD_MISMATCH"
        confidence = "MED"
        reasons.append("activation collapsed while many predictions remain just below threshold")
    elif activation_collapsed and material_distribution_shift:
        classification = "REGIME_CHANGE"
        confidence = "MED"
        reasons.append("activation collapsed alongside a broad probability distribution shift")
    else:
        classification = "INCONCLUSIVE"
        confidence = "LOW"
        reasons.append("available evidence does not isolate one dominant cause")

    if activation_collapsed:
        reasons.append("recent threshold activation is less than 35% of the reference rate")
    if material_distribution_shift:
        reasons.append("recent mean probability moved at least 0.5 reference standard deviations")
    if near_threshold_mass:
        reasons.append("at least 10% of recent predictions sit within 0.02 below threshold")
    if not quality_degraded and observation.brier_score is not None:
        reasons.append("Brier/calibration deterioration did not cross degradation thresholds")

    payload = {
        "asset": asset,
        "model": model,
        "classification": classification,
        "confidence": confidence,
        "reasons": reasons,
        "reference": asdict(reference),
        "observation": asdict(observation),
        "activation_rate_change": activation_change,
        "activation_rate_ratio": activation_ratio,
        "probability_mean_shift": probability_shift,
        "standardized_probability_mean_shift": standardized_shift,
        "threshold_distance": asdict(distances),
        "feature_comparisons": {name: asdict(value) for name, value in features.items()},
        "probability_buckets": list(_bucket_rows(observation_frame)),
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return DriftDiagnosis(
        asset=asset,
        model=model,
        classification=classification,
        confidence=confidence,
        reasons=tuple(reasons),
        reference=reference,
        observation=observation,
        activation_rate_change=float(activation_change),
        activation_rate_ratio=float(activation_ratio) if activation_ratio is not None else None,
        probability_mean_shift=float(probability_shift),
        standardized_probability_mean_shift=float(standardized_shift),
        threshold_distance=distances,
        feature_comparisons=features,
        probability_buckets=_bucket_rows(observation_frame),
        observation_only=True,
        runtime_integration_allowed=False,
        exposure_mutation_allowed=False,
        digest=digest,
    )
