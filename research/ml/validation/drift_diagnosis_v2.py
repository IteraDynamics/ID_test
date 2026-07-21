"""Evidence-aware, observation-only diagnosis for Jump Risk drift.

Version 2 supplements prediction behavior with aligned feature and market-context
frames. It remains fail-closed and never changes thresholds, exposure, orders,
NAV, or runtime state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Mapping

import numpy as np
import pandas as pd

from research.ml.validation.drift_detector import ks_statistic, population_stability_index
from research.ml.validation.drift_diagnosis import DriftDiagnosis, diagnose_stream


@dataclass(frozen=True)
class EvidenceComparison:
    reference_mean: float | None
    observation_mean: float | None
    standardized_mean_shift: float
    psi: float
    ks_statistic: float
    reference_missing_fraction: float
    observation_missing_fraction: float


@dataclass(frozen=True)
class EvidenceAwareDiagnosis:
    asset: str
    model: str
    classification: str
    confidence: str
    reasons: tuple[str, ...]
    prediction_diagnosis: DriftDiagnosis
    feature_evidence: Mapping[str, EvidenceComparison]
    market_context_evidence: Mapping[str, EvidenceComparison]
    evidence_sufficient: bool
    observation_only: bool
    runtime_integration_allowed: bool
    exposure_mutation_allowed: bool
    digest: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _align(frame: pd.DataFrame | None, index: pd.Index) -> pd.DataFrame | None:
    if frame is None:
        return None
    aligned = frame.copy().sort_index()
    if aligned.index.has_duplicates:
        raise ValueError("Evidence timestamps must be unique")
    return aligned.reindex(index)


def _compare(
    frame: pd.DataFrame | None,
    *,
    reference_rows: int,
    observation_rows: int,
) -> dict[str, EvidenceComparison]:
    if frame is None:
        return {}
    needed = reference_rows + observation_rows
    if len(frame) < needed:
        raise ValueError(f"Need at least {needed} aligned evidence rows, received {len(frame)}")
    reference = frame.iloc[-needed:-observation_rows]
    observation = frame.iloc[-observation_rows:]
    output: dict[str, EvidenceComparison] = {}
    for column in sorted(set(frame.columns)):
        ref_raw = _numeric(reference[column])
        obs_raw = _numeric(observation[column])
        ref = ref_raw.dropna()
        obs = obs_raw.dropna()
        ref_mean = float(ref.mean()) if not ref.empty else None
        obs_mean = float(obs.mean()) if not obs.empty else None
        shift = 0.0
        psi = 0.0
        ks = 0.0
        if ref_mean is not None and obs_mean is not None:
            shift = abs(obs_mean - ref_mean) / max(float(ref.std(ddof=0)), 1e-9)
            psi = population_stability_index(ref.to_numpy(), obs.to_numpy())
            ks = ks_statistic(ref.to_numpy(), obs.to_numpy())
        output[column] = EvidenceComparison(
            reference_mean=ref_mean,
            observation_mean=obs_mean,
            standardized_mean_shift=float(shift),
            psi=float(psi),
            ks_statistic=float(ks),
            reference_missing_fraction=float(ref_raw.isna().mean()),
            observation_missing_fraction=float(obs_raw.isna().mean()),
        )
    return output


def _material(metric: EvidenceComparison) -> bool:
    return (
        metric.standardized_mean_shift >= 0.50
        or metric.psi >= 0.25
        or metric.ks_statistic >= 0.20
    )


def _pipeline_suspect(metric: EvidenceComparison) -> bool:
    return (
        metric.observation_missing_fraction >= 0.10
        or metric.observation_missing_fraction - metric.reference_missing_fraction >= 0.05
    )


def diagnose_stream_v2(
    prediction_frame: pd.DataFrame,
    *,
    asset: str,
    model: str,
    reference_rows: int,
    observation_rows: int,
    feature_frame: pd.DataFrame | None = None,
    market_context_frame: pd.DataFrame | None = None,
) -> EvidenceAwareDiagnosis:
    """Diagnose drift using prediction, feature, and market-context evidence."""
    base = diagnose_stream(
        prediction_frame,
        asset=asset,
        model=model,
        reference_rows=reference_rows,
        observation_rows=observation_rows,
    )
    feature_aligned = _align(feature_frame, prediction_frame.sort_index().index)
    context_aligned = _align(market_context_frame, prediction_frame.sort_index().index)
    features = _compare(
        feature_aligned,
        reference_rows=reference_rows,
        observation_rows=observation_rows,
    )
    context = _compare(
        context_aligned,
        reference_rows=reference_rows,
        observation_rows=observation_rows,
    )

    evidence = {**features, **{f"market:{k}": v for k, v in context.items()}}
    material_names = sorted(name for name, metric in evidence.items() if _material(metric))
    pipeline_names = sorted(name for name, metric in evidence.items() if _pipeline_suspect(metric))
    evidence_sufficient = bool(evidence)

    activation_collapsed = (
        base.reference.activation_rate >= 0.05
        and base.activation_rate_ratio is not None
        and base.activation_rate_ratio <= 0.35
        and base.activation_rate_change <= -0.05
    )
    near_threshold_mass = base.threshold_distance.below_within_002 >= 0.10
    prediction_shift = base.standardized_probability_mean_shift >= 0.35

    reasons: list[str] = []
    if pipeline_names:
        classification = "DATA_PIPELINE_SUSPECT"
        confidence = "HIGH"
        reasons.append("recent missingness increased in: " + ", ".join(pipeline_names[:5]))
    elif base.classification == "MODEL_DEGRADATION":
        classification = "MODEL_DEGRADATION"
        confidence = "HIGH"
        reasons.extend(base.reasons)
    elif activation_collapsed and near_threshold_mass:
        classification = "THRESHOLD_MISMATCH"
        confidence = "MED"
        reasons.append("activation collapsed while predictions cluster just below threshold")
    elif activation_collapsed and prediction_shift and material_names:
        classification = "REGIME_CHANGE"
        confidence = "HIGH" if len(material_names) >= 2 else "MED"
        reasons.append("activation collapsed alongside material external evidence shifts")
        reasons.append("material evidence: " + ", ".join(material_names[:5]))
    else:
        classification = "INCONCLUSIVE"
        confidence = "LOW"
        if not evidence_sufficient:
            reasons.append("feature and market-context evidence were not supplied")
        elif not material_names:
            reasons.append("supplied evidence did not show a material distribution shift")
        else:
            reasons.append("evidence did not isolate one dominant cause")

    if activation_collapsed:
        reasons.append("recent activation is at most 35% of the reference rate")
    if prediction_shift:
        reasons.append("prediction mean shifted at least 0.35 reference standard deviations")

    payload = {
        "asset": asset,
        "model": model,
        "classification": classification,
        "confidence": confidence,
        "reasons": reasons,
        "prediction_diagnosis": base.to_dict(),
        "feature_evidence": {k: asdict(v) for k, v in features.items()},
        "market_context_evidence": {k: asdict(v) for k, v in context.items()},
        "evidence_sufficient": evidence_sufficient,
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return EvidenceAwareDiagnosis(
        asset=asset,
        model=model,
        classification=classification,
        confidence=confidence,
        reasons=tuple(reasons),
        prediction_diagnosis=base,
        feature_evidence=features,
        market_context_evidence=context,
        evidence_sufficient=evidence_sufficient,
        observation_only=True,
        runtime_integration_allowed=False,
        exposure_mutation_allowed=False,
        digest=digest,
    )
