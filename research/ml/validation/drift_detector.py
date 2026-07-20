"""Deterministic, observation-only drift monitoring for frozen Jump Risk streams.

The monitor compares a recent observation window with an earlier reference
window.  It never mutates Core state, changes exposure, or makes trading
choices.  A HIGH result is an operator-review signal only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

SEVERITY_ORDER = {"LOW": 0, "MED": 1, "HIGH": 2}


@dataclass(frozen=True)
class DistributionDrift:
    reference_rows: int
    observation_rows: int
    reference_mean: float
    observation_mean: float
    standardized_mean_shift: float
    psi: float
    ks_statistic: float
    reference_exceedance_rate: float
    observation_exceedance_rate: float
    exceedance_rate_shift: float


@dataclass(frozen=True)
class OutcomeQuality:
    rows: int
    event_rate: float | None
    brier_score: float | None
    calibration_error: float | None
    threshold_precision: float | None


@dataclass(frozen=True)
class FeatureDrift:
    standardized_mean_shift: float
    missing_fraction: float


@dataclass(frozen=True)
class DriftReport:
    asset: str
    model: str
    severity: str
    drift_detected: bool
    reasons: tuple[str, ...]
    probability: DistributionDrift
    outcomes: OutcomeQuality
    feature_drifts: Mapping[str, FeatureDrift]
    data_quality: Mapping[str, Any]
    config: Mapping[str, Any]
    digest: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _finite(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().astype(float)


def _validate_probability_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"probability", "train_threshold"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing probability columns: {missing}")
    out = frame.copy().sort_index()
    if not out.index.is_monotonic_increasing or out.index.has_duplicates:
        raise ValueError("Probability timestamps must be unique and increasing")
    for col in required:
        values = pd.to_numeric(out[col], errors="coerce")
        invalid = values.notna() & ~values.between(0.0, 1.0)
        if bool(invalid.any()):
            raise ValueError(f"{col} contains values outside [0, 1]")
        out[col] = values
    return out


def _split_windows(frame: pd.DataFrame, reference_rows: int, observation_rows: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    if reference_rows < 50 or observation_rows < 24:
        raise ValueError("reference_rows must be >= 50 and observation_rows >= 24")
    needed = reference_rows + observation_rows
    if len(frame) < needed:
        raise ValueError(f"Need at least {needed} rows, received {len(frame)}")
    return frame.iloc[-needed:-observation_rows], frame.iloc[-observation_rows:]


def population_stability_index(reference: Sequence[float], observed: Sequence[float], bins: int = 10) -> float:
    ref = np.asarray(reference, dtype=float)
    obs = np.asarray(observed, dtype=float)
    ref = ref[np.isfinite(ref)]
    obs = obs[np.isfinite(obs)]
    if len(ref) == 0 or len(obs) == 0:
        return 0.0
    quantiles = np.linspace(0.0, 1.0, bins + 1)
    edges = np.unique(np.quantile(ref, quantiles))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    ref_counts, _ = np.histogram(ref, bins=edges)
    obs_counts, _ = np.histogram(obs, bins=edges)
    eps = 1e-6
    ref_pct = np.maximum(ref_counts / max(ref_counts.sum(), 1), eps)
    obs_pct = np.maximum(obs_counts / max(obs_counts.sum(), 1), eps)
    return float(np.sum((obs_pct - ref_pct) * np.log(obs_pct / ref_pct)))


def ks_statistic(reference: Sequence[float], observed: Sequence[float]) -> float:
    ref = np.sort(np.asarray(reference, dtype=float))
    obs = np.sort(np.asarray(observed, dtype=float))
    ref = ref[np.isfinite(ref)]
    obs = obs[np.isfinite(obs)]
    if len(ref) == 0 or len(obs) == 0:
        return 0.0
    values = np.sort(np.unique(np.concatenate([ref, obs])))
    ref_cdf = np.searchsorted(ref, values, side="right") / len(ref)
    obs_cdf = np.searchsorted(obs, values, side="right") / len(obs)
    return float(np.max(np.abs(ref_cdf - obs_cdf)))


def _distribution(reference: pd.DataFrame, observed: pd.DataFrame) -> DistributionDrift:
    ref_p = _finite(reference["probability"])
    obs_p = _finite(observed["probability"])
    ref_t = _finite(reference["train_threshold"])
    obs_t = _finite(observed["train_threshold"])
    ref_std = float(ref_p.std(ddof=0))
    shift = abs(float(obs_p.mean()) - float(ref_p.mean())) / max(ref_std, 1e-9)
    ref_exc = float((ref_p.to_numpy() >= ref_t.reindex(ref_p.index).to_numpy()).mean())
    obs_exc = float((obs_p.to_numpy() >= obs_t.reindex(obs_p.index).to_numpy()).mean())
    return DistributionDrift(
        reference_rows=len(ref_p),
        observation_rows=len(obs_p),
        reference_mean=float(ref_p.mean()),
        observation_mean=float(obs_p.mean()),
        standardized_mean_shift=float(shift),
        psi=population_stability_index(ref_p, obs_p),
        ks_statistic=ks_statistic(ref_p, obs_p),
        reference_exceedance_rate=ref_exc,
        observation_exceedance_rate=obs_exc,
        exceedance_rate_shift=abs(obs_exc - ref_exc),
    )


def _outcomes(observed: pd.DataFrame) -> OutcomeQuality:
    if "label" not in observed.columns:
        return OutcomeQuality(0, None, None, None, None)
    valid = observed[["probability", "train_threshold", "label"]].apply(pd.to_numeric, errors="coerce").dropna()
    if valid.empty:
        return OutcomeQuality(0, None, None, None, None)
    labels = valid["label"].astype(float)
    probs = valid["probability"].astype(float)
    active = probs >= valid["train_threshold"].astype(float)
    precision = float(labels[active].mean()) if bool(active.any()) else None
    return OutcomeQuality(
        rows=len(valid),
        event_rate=float(labels.mean()),
        brier_score=float(np.mean((probs - labels) ** 2)),
        calibration_error=abs(float(probs.mean()) - float(labels.mean())),
        threshold_precision=precision,
    )


def _features(reference: pd.DataFrame | None, observed: pd.DataFrame | None) -> dict[str, FeatureDrift]:
    if reference is None or observed is None:
        return {}
    common = sorted(set(reference.columns) & set(observed.columns))
    output: dict[str, FeatureDrift] = {}
    for col in common:
        ref_raw = pd.to_numeric(reference[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        obs_raw = pd.to_numeric(observed[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        ref = ref_raw.dropna()
        obs = obs_raw.dropna()
        if ref.empty or obs.empty:
            shift = 0.0
        else:
            shift = abs(float(obs.mean()) - float(ref.mean())) / max(float(ref.std(ddof=0)), 1e-9)
        output[col] = FeatureDrift(float(shift), float(obs_raw.isna().mean()))
    return output


def _severity(reasons: list[str]) -> str:
    high_prefixes = ("probability_psi_high", "probability_mean_shift_high", "missing_probability_high", "feature_shift_high")
    if any(reason.startswith(high_prefixes) for reason in reasons):
        return "HIGH"
    return "MED" if reasons else "LOW"


def detect_drift(
    frame: pd.DataFrame,
    *,
    asset: str,
    model: str,
    reference_rows: int = 24 * 90,
    observation_rows: int = 24 * 14,
    reference_features: pd.DataFrame | None = None,
    observation_features: pd.DataFrame | None = None,
    psi_med: float = 0.10,
    psi_high: float = 0.25,
    mean_shift_med: float = 0.50,
    mean_shift_high: float = 1.00,
    ks_med: float = 0.15,
    exceedance_shift_med: float = 0.10,
    feature_shift_med: float = 1.00,
    feature_shift_high: float = 2.00,
) -> DriftReport:
    """Compare recent frozen-model outputs with an earlier reference window."""
    clean = _validate_probability_frame(frame)
    reference, observed = _split_windows(clean, reference_rows, observation_rows)
    probability = _distribution(reference, observed)
    outcomes = _outcomes(observed)
    feature_drifts = _features(reference_features, observation_features)

    missing_probability = float(observed["probability"].isna().mean())
    missing_threshold = float(observed["train_threshold"].isna().mean())
    reasons: list[str] = []
    if probability.psi >= psi_high:
        reasons.append("probability_psi_high")
    elif probability.psi >= psi_med:
        reasons.append("probability_psi_med")
    if probability.standardized_mean_shift >= mean_shift_high:
        reasons.append("probability_mean_shift_high")
    elif probability.standardized_mean_shift >= mean_shift_med:
        reasons.append("probability_mean_shift_med")
    if probability.ks_statistic >= ks_med:
        reasons.append("probability_ks_med")
    if probability.exceedance_rate_shift >= exceedance_shift_med:
        reasons.append("threshold_exceedance_shift_med")
    if missing_probability >= 0.10:
        reasons.append("missing_probability_high")
    elif missing_probability > 0.0:
        reasons.append("missing_probability_med")
    if missing_threshold > 0.0:
        reasons.append("missing_threshold_med")
    for name, metric in feature_drifts.items():
        if metric.standardized_mean_shift >= feature_shift_high:
            reasons.append(f"feature_shift_high:{name}")
        elif metric.standardized_mean_shift >= feature_shift_med:
            reasons.append(f"feature_shift_med:{name}")

    config = {
        "reference_rows": reference_rows,
        "observation_rows": observation_rows,
        "psi_med": psi_med,
        "psi_high": psi_high,
        "mean_shift_med": mean_shift_med,
        "mean_shift_high": mean_shift_high,
        "ks_med": ks_med,
        "exceedance_shift_med": exceedance_shift_med,
        "feature_shift_med": feature_shift_med,
        "feature_shift_high": feature_shift_high,
        "observation_only": True,
    }
    severity = _severity(reasons)
    payload = {
        "asset": str(asset).upper(),
        "model": str(model),
        "severity": severity,
        "reasons": reasons,
        "probability": asdict(probability),
        "outcomes": asdict(outcomes),
        "feature_drifts": {k: asdict(v) for k, v in feature_drifts.items()},
        "data_quality": {"missing_probability_fraction": missing_probability, "missing_threshold_fraction": missing_threshold},
        "config": config,
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return DriftReport(
        asset=payload["asset"], model=payload["model"], severity=severity,
        drift_detected=severity != "LOW", reasons=tuple(reasons), probability=probability,
        outcomes=outcomes, feature_drifts=feature_drifts, data_quality=payload["data_quality"],
        config=config, digest=digest,
    )


def aggregate_severity(reports: Sequence[DriftReport]) -> str:
    if not reports:
        return "LOW"
    return max((report.severity for report in reports), key=lambda value: SEVERITY_ORDER[value])
