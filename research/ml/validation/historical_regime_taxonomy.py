from __future__ import annotations

"""Deterministic, research-only taxonomy for historical Jump Risk episodes."""

from collections import Counter, defaultdict
from hashlib import sha256
import json
from typing import Any

import numpy as np
import pandas as pd

VOLATILITY_TOKENS = (
    "atr",
    "volatility",
    "realized_vol",
    "bollinger",
    "bb_width",
    "abs_return",
    "downside",
)

REQUIRED_EPISODE_COLUMNS = {
    "episode_id",
    "window_start",
    "window_end",
    "reference_activation_rate",
    "observation_activation_rate",
    "activation_ratio",
    "feature_cosine_similarity_to_latest",
    "recovered_without_retraining",
    "recovery_rows",
}


def _finite_float(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not np.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _collapse_severity(activation_ratio: float, collapse_ratio: float) -> str:
    if activation_ratio < 0 or activation_ratio > collapse_ratio:
        raise ValueError("activation_ratio is outside the configured collapse candidate range")
    if activation_ratio <= 0.10:
        return "SEVERE_COLLAPSE"
    if activation_ratio <= 0.20:
        return "MAJOR_COLLAPSE"
    return "MODERATE_COLLAPSE"


def _feature_displacement(signature: pd.Series) -> tuple[float, float, int, float, str]:
    values = signature.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("signature values must be finite")
    if len(values) == 0:
        raise ValueError("signature must contain at least one feature")

    absolute = np.abs(values)
    signature_l2 = float(np.linalg.norm(values))
    max_abs_shift = float(absolute.max())
    shifted_count = int((absolute >= 1.0).sum())
    shifted_fraction = float(shifted_count / len(values))

    if shifted_fraction >= 0.25:
        label = "BROAD_SHIFT"
    elif max_abs_shift >= 2.0:
        label = "CONCENTRATED_SHIFT"
    else:
        label = "LOW_DISPLACEMENT_COLLAPSE"
    return signature_l2, max_abs_shift, shifted_count, shifted_fraction, label


def _volatility_state(signature: pd.Series) -> tuple[list[str], float | None, str]:
    matched = sorted(
        name for name in signature.index.astype(str)
        if any(token in name.lower() for token in VOLATILITY_TOKENS)
    )
    if not matched:
        return [], None, "VOLATILITY_UNAVAILABLE"

    median = float(signature.loc[matched].median())
    if median >= 1.0:
        label = "VOLATILITY_EXPANSION"
    elif median <= -1.0:
        label = "VOLATILITY_COMPRESSION"
    else:
        label = "VOLATILITY_NEUTRAL"
    return matched, median, label


def _recovery_outcome(recovered: bool, recovery_rows: Any, observation_rows: int) -> tuple[int | None, str]:
    if recovered:
        if pd.isna(recovery_rows):
            raise ValueError("recovered episode requires positive recovery_rows")
        rows = int(recovery_rows)
        if rows <= 0:
            raise ValueError("recovered episode requires positive recovery_rows")
        return rows, "RAPID_RECOVERY" if rows <= observation_rows else "DELAYED_RECOVERY"

    if not pd.isna(recovery_rows):
        raise ValueError("persistent episode must have null recovery_rows")
    return None, "PERSISTENT_COLLAPSE"


def _similarity_band(similarity: float) -> str:
    if similarity >= 0.75:
        return "HIGH_SIMILARITY"
    if similarity >= 0.40:
        return "MEDIUM_SIMILARITY"
    return "LOW_SIMILARITY"


def classify_episodes(
    episodes: pd.DataFrame,
    signatures: pd.DataFrame,
    *,
    collapse_ratio: float,
    observation_rows: int,
) -> pd.DataFrame:
    """Return a classified copy of episode rows without mutating either input."""
    missing = REQUIRED_EPISODE_COLUMNS - set(episodes.columns)
    if missing:
        raise ValueError(f"episodes missing required columns: {sorted(missing)}")
    if episodes["episode_id"].duplicated().any():
        raise ValueError("duplicate episode identifiers")
    if signatures.index.duplicated().any():
        raise ValueError("duplicate signature episode identifiers")
    if observation_rows <= 0:
        raise ValueError("observation_rows must be positive")
    collapse_ratio = _finite_float(collapse_ratio, "collapse_ratio")
    if collapse_ratio <= 0:
        raise ValueError("collapse_ratio must be positive")

    signature_ids = set(signatures.index.tolist())
    episode_ids = set(episodes["episode_id"].tolist())
    if episode_ids != signature_ids:
        raise ValueError("episode and signature identifiers must match exactly")

    rows: list[dict[str, Any]] = []
    for source in episodes.to_dict(orient="records"):
        episode_id = source["episode_id"]
        signature = pd.to_numeric(signatures.loc[episode_id], errors="coerce")
        if signature.isna().any():
            raise ValueError(f"non-numeric or missing signature values for episode {episode_id}")

        activation_ratio = _finite_float(source["activation_ratio"], "activation_ratio")
        similarity = _finite_float(
            source["feature_cosine_similarity_to_latest"],
            "feature_cosine_similarity_to_latest",
        )
        recovered = bool(source["recovered_without_retraining"])
        recovery_rows, recovery_outcome = _recovery_outcome(
            recovered, source["recovery_rows"], observation_rows
        )
        signature_l2, max_abs_shift, shifted_count, shifted_fraction, displacement = (
            _feature_displacement(signature)
        )
        volatility_features, volatility_median, volatility_state = _volatility_state(signature)
        severity = _collapse_severity(activation_ratio, collapse_ratio)

        classified = dict(source)
        classified.update(
            {
                "activation_ratio": activation_ratio,
                "collapse_severity": severity,
                "feature_cosine_similarity_to_latest": similarity,
                "similarity_band": _similarity_band(similarity),
                "signature_l2": signature_l2,
                "max_abs_shift": max_abs_shift,
                "shifted_feature_count": shifted_count,
                "shifted_feature_fraction": shifted_fraction,
                "feature_displacement": displacement,
                "volatility_feature_count": len(volatility_features),
                "volatility_features": volatility_features,
                "volatility_median_signature": volatility_median,
                "volatility_state": volatility_state,
                "recovery_rows": recovery_rows,
                "recovery_outcome": recovery_outcome,
                "composite_regime_label": "__".join(
                    [severity, displacement, volatility_state, recovery_outcome]
                ),
            }
        )
        rows.append(classified)

    return pd.DataFrame(rows).sort_values("episode_id", kind="mergesort").reset_index(drop=True)


def _sorted_counts(values: pd.Series) -> dict[str, int]:
    counts = Counter(str(value) for value in values)
    return {key: counts[key] for key in sorted(counts)}


def build_summary(
    classified: pd.DataFrame,
    *,
    config: dict[str, Any],
    latest_window: dict[str, Any],
    source_artifacts: dict[str, str],
) -> dict[str, Any]:
    subtype_recovery: dict[str, dict[str, Any]] = {}
    grouped = classified.groupby(
        ["collapse_severity", "feature_displacement", "volatility_state"],
        sort=True,
        dropna=False,
    )
    for keys, group in grouped:
        intrinsic = "__".join(str(value) for value in keys)
        recovered = group[group["recovered_without_retraining"].astype(bool)]
        subtype_recovery[intrinsic] = {
            "episode_count": int(len(group)),
            "recovered_fraction": float(len(recovered) / len(group)),
            "median_recovery_rows": (
                None if recovered.empty else float(pd.to_numeric(recovered["recovery_rows"]).median())
            ),
        }

    volatility_features = sorted(
        {name for values in classified["volatility_features"] for name in values}
    )
    summary = {
        "experiment": "core_v1_jump_risk_historical_regime_taxonomy",
        "research_only": True,
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
        "config": dict(sorted(config.items())),
        "episode_count": int(len(classified)),
        "counts": {
            "collapse_severity": _sorted_counts(classified["collapse_severity"]),
            "feature_displacement": _sorted_counts(classified["feature_displacement"]),
            "volatility_state": _sorted_counts(classified["volatility_state"]),
            "recovery_outcome": _sorted_counts(classified["recovery_outcome"]),
            "similarity_band": _sorted_counts(classified["similarity_band"]),
            "composite_regime_label": _sorted_counts(classified["composite_regime_label"]),
        },
        "recovery_by_intrinsic_subtype": subtype_recovery,
        "latest_window": latest_window,
        "matched_volatility_features": volatility_features,
        "volatility_feature_name_tokens": list(VOLATILITY_TOKENS),
        "source_artifacts": dict(sorted(source_artifacts.items())),
    }
    canonical = json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False)
    summary["deterministic_digest_sha256"] = sha256(canonical.encode("utf-8")).hexdigest()
    return summary
