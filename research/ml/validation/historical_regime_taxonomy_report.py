from __future__ import annotations

"""Deterministic, research-only reporting for historical regime taxonomy artifacts."""

from collections import Counter
from hashlib import sha256
import json
import math
from typing import Any

import numpy as np
import pandas as pd

COUNT_DIMENSIONS = (
    "collapse_severity",
    "feature_displacement",
    "volatility_state",
    "recovery_outcome",
    "similarity_band",
    "composite_regime_label",
)
INTRINSIC_DIMENSIONS = (
    "collapse_severity",
    "feature_displacement",
    "volatility_state",
)
REQUIRED_CLASSIFIED_COLUMNS = {
    "episode_id",
    "activation_ratio",
    "feature_cosine_similarity_to_latest",
    "recovered_without_retraining",
    "recovery_rows",
    *COUNT_DIMENSIONS,
}
CAVEATS = (
    "Historical episodes are overlapping rolling-window observations and are dependent observations, not independent Bernoulli trials.",
    "Persistent collapse means no recovery was observed within the configured bounded recovery horizon; it does not establish permanent non-recovery.",
    "Recovered fractions and recovery durations are descriptive historical summaries, not calibrated probabilities or forward forecasts.",
    "Subtype feature rankings use median absolute standardized signatures from the numeric episode-signature artifact; signed medians provide direction.",
    "This report is research-only and observation-only. It does not authorize runtime integration or threshold, order, NAV, or exposure mutation.",
)


def _sorted_counts(values: pd.Series) -> dict[str, int]:
    counts = Counter(str(value) for value in values)
    return {key: int(counts[key]) for key in sorted(counts)}


def _strict_numeric(values: pd.Series, field: str) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    array = numeric.to_numpy(dtype=float)
    if np.isnan(array).any() or not np.isfinite(array).all():
        raise ValueError(f"{field} contains missing or non-finite values")
    return numeric.astype(float)


def _integer_ids(values: pd.Series | pd.Index, field: str) -> pd.Index:
    numeric = pd.to_numeric(values, errors="coerce")
    array = np.asarray(numeric, dtype=float)
    if np.isnan(array).any() or not np.isfinite(array).all():
        raise ValueError(f"{field} contains invalid identifiers")
    if not np.equal(array, np.floor(array)).all():
        raise ValueError(f"{field} identifiers must be integers")
    return pd.Index(array.astype(int), name="episode_id")


def _canonical_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _validate_summary_counts(
    classified: pd.DataFrame,
    taxonomy_summary: dict[str, Any],
) -> dict[str, dict[str, int]]:
    summary_counts = taxonomy_summary.get("counts")
    if not isinstance(summary_counts, dict):
        raise ValueError("taxonomy summary missing counts")

    calculated: dict[str, dict[str, int]] = {}
    for dimension in COUNT_DIMENSIONS:
        expected = summary_counts.get(dimension)
        if not isinstance(expected, dict):
            raise ValueError(f"taxonomy summary missing count dimension {dimension}")
        actual = _sorted_counts(classified[dimension])
        normalized_expected = {
            str(key): int(value) for key, value in sorted(expected.items())
        }
        if actual != normalized_expected:
            raise ValueError(
                f"taxonomy summary count mismatch for {dimension}: "
                f"expected={normalized_expected}, actual={actual}"
            )
        if sum(actual.values()) != len(classified):
            raise ValueError(f"{dimension} counts do not sum to episode count")
        calculated[dimension] = actual
    return calculated


def _validate_recovery_summary(
    subtype_rows: list[dict[str, Any]],
    taxonomy_summary: dict[str, Any],
) -> None:
    expected = taxonomy_summary.get("recovery_by_intrinsic_subtype")
    if not isinstance(expected, dict):
        raise ValueError("taxonomy summary missing recovery_by_intrinsic_subtype")

    actual_by_name = {
        str(row["intrinsic_subtype"]): row for row in subtype_rows
    }
    if set(expected) != set(actual_by_name):
        raise ValueError("intrinsic subtype identifiers do not match taxonomy summary")

    for subtype in sorted(expected):
        expected_row = expected[subtype]
        actual = actual_by_name[subtype]
        if int(expected_row["episode_count"]) != int(actual["episode_count"]):
            raise ValueError(f"episode count mismatch for subtype {subtype}")
        if not math.isclose(
            float(expected_row["recovered_fraction"]),
            float(actual["recovered_fraction"]),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(f"recovered fraction mismatch for subtype {subtype}")

        expected_median = expected_row.get("median_recovery_rows")
        actual_median = actual.get("median_recovery_rows")
        if expected_median is None or actual_median is None:
            if expected_median is not None or actual_median is not None:
                raise ValueError(f"recovery median mismatch for subtype {subtype}")
        elif not math.isclose(
            float(expected_median),
            float(actual_median),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(f"recovery median mismatch for subtype {subtype}")


def build_report_model(
    classified: pd.DataFrame,
    signatures: pd.DataFrame,
    taxonomy_summary: dict[str, Any],
    *,
    top_features: int = 5,
    source_artifacts: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic compact report model without mutating inputs."""
    if top_features <= 0:
        raise ValueError("top_features must be positive")

    missing = REQUIRED_CLASSIFIED_COLUMNS - set(classified.columns)
    if missing:
        raise ValueError(f"classified episodes missing required columns: {sorted(missing)}")
    if classified.empty:
        raise ValueError("classified episodes cannot be empty")
    if signatures.empty:
        raise ValueError("episode signatures cannot be empty")

    episodes = classified.copy(deep=True)
    signature_frame = signatures.copy(deep=True)
    episodes["episode_id"] = _integer_ids(
        episodes["episode_id"], "classified episode"
    ).to_numpy()
    signature_frame.index = _integer_ids(
        signature_frame.index, "signature episode"
    )

    if episodes["episode_id"].duplicated().any():
        raise ValueError("duplicate classified episode identifiers")
    if signature_frame.index.duplicated().any():
        raise ValueError("duplicate signature episode identifiers")
    if set(episodes["episode_id"]) != set(signature_frame.index):
        raise ValueError("classified episode and signature identifiers must match exactly")
    if int(taxonomy_summary.get("episode_count", -1)) != len(episodes):
        raise ValueError("taxonomy summary episode count mismatch")

    taxonomy_digest = taxonomy_summary.get("deterministic_digest_sha256")
    if not isinstance(taxonomy_digest, str) or len(taxonomy_digest) != 64:
        raise ValueError("taxonomy summary missing deterministic digest")

    episodes["activation_ratio"] = _strict_numeric(
        episodes["activation_ratio"], "activation_ratio"
    )
    episodes["feature_cosine_similarity_to_latest"] = _strict_numeric(
        episodes["feature_cosine_similarity_to_latest"],
        "feature_cosine_similarity_to_latest",
    )

    if not episodes["recovered_without_retraining"].map(
        lambda value: isinstance(value, (bool, np.bool_))
    ).all():
        raise ValueError("recovered_without_retraining must contain booleans")
    recovered_mask = episodes["recovered_without_retraining"].astype(bool)
    recovery_rows = pd.to_numeric(episodes["recovery_rows"], errors="coerce")
    if recovery_rows.loc[recovered_mask].isna().any():
        raise ValueError("recovered episodes require recovery_rows")
    if (recovery_rows.loc[recovered_mask] <= 0).any():
        raise ValueError("recovered episodes require positive recovery_rows")
    if recovery_rows.loc[~recovered_mask].notna().any():
        raise ValueError("persistent episodes require null recovery_rows")
    episodes["recovery_rows"] = recovery_rows

    for dimension in COUNT_DIMENSIONS:
        if episodes[dimension].isna().any():
            raise ValueError(f"{dimension} contains missing labels")
        episodes[dimension] = episodes[dimension].astype(str)
        if (episodes[dimension].str.len() == 0).any():
            raise ValueError(f"{dimension} contains empty labels")

    numeric_signatures = signature_frame.apply(pd.to_numeric, errors="coerce")
    signature_values = numeric_signatures.to_numpy(dtype=float)
    if np.isnan(signature_values).any() or not np.isfinite(signature_values).all():
        raise ValueError("signature artifact contains missing or non-finite values")
    numeric_signatures.columns = numeric_signatures.columns.astype(str)
    numeric_signatures = numeric_signatures.reindex(
        columns=sorted(numeric_signatures.columns)
    )

    counts = _validate_summary_counts(episodes, taxonomy_summary)
    episodes["intrinsic_subtype"] = (
        episodes[INTRINSIC_DIMENSIONS[0]]
        + "__"
        + episodes[INTRINSIC_DIMENSIONS[1]]
        + "__"
        + episodes[INTRINSIC_DIMENSIONS[2]]
    )

    subtype_rows: list[dict[str, Any]] = []
    for subtype, group in episodes.groupby(
        "intrinsic_subtype", sort=True, dropna=False
    ):
        group = group.sort_values("episode_id", kind="mergesort")
        group_signatures = numeric_signatures.loc[group["episode_id"].tolist()]
        feature_rows = [
            {
                "feature": feature,
                "median_absolute_signature": float(
                    group_signatures[feature].abs().median()
                ),
                "median_signed_signature": float(
                    group_signatures[feature].median()
                ),
            }
            for feature in group_signatures.columns
        ]
        feature_rows.sort(
            key=lambda row: (
                -float(row["median_absolute_signature"]),
                str(row["feature"]),
            )
        )

        recovered = group[group["recovered_without_retraining"]]
        subtype_rows.append(
            {
                "intrinsic_subtype": str(subtype),
                "episode_count": int(len(group)),
                "recovered_count": int(len(recovered)),
                "recovered_fraction": float(len(recovered) / len(group)),
                "median_recovery_rows": (
                    None
                    if recovered.empty
                    else float(recovered["recovery_rows"].median())
                ),
                "median_activation_ratio": float(
                    group["activation_ratio"].median()
                ),
                "median_similarity_to_current": float(
                    group["feature_cosine_similarity_to_latest"].median()
                ),
                "mean_similarity_to_current": float(
                    group["feature_cosine_similarity_to_latest"].mean()
                ),
                "top_shifted_features": feature_rows[:top_features],
            }
        )

    subtype_rows.sort(key=lambda row: str(row["intrinsic_subtype"]))
    _validate_recovery_summary(subtype_rows, taxonomy_summary)
    dominant = sorted(
        subtype_rows,
        key=lambda row: (
            -int(row["episode_count"]),
            str(row["intrinsic_subtype"]),
        ),
    )

    recovered_count = int(
        counts["recovery_outcome"].get("RAPID_RECOVERY", 0)
        + counts["recovery_outcome"].get("DELAYED_RECOVERY", 0)
    )
    persistent_count = int(
        counts["recovery_outcome"].get("PERSISTENT_COLLAPSE", 0)
    )

    model: dict[str, Any] = {
        "experiment": "core_v1_jump_risk_historical_regime_taxonomy_report",
        "research_only": True,
        "observation_only": True,
        "runtime_integration_allowed": False,
        "exposure_mutation_allowed": False,
        "episode_count": int(len(episodes)),
        "source_taxonomy_digest_sha256": taxonomy_digest,
        "recovered_episode_count": recovered_count,
        "persistent_episode_count": persistent_count,
        "descriptive_recovered_fraction": float(recovered_count / len(episodes)),
        "counts": counts,
        "dominant_subtypes": [
            {
                "intrinsic_subtype": row["intrinsic_subtype"],
                "episode_count": row["episode_count"],
                "recovered_fraction": row["recovered_fraction"],
                "median_recovery_rows": row["median_recovery_rows"],
                "median_activation_ratio": row["median_activation_ratio"],
                "median_similarity_to_current": row["median_similarity_to_current"],
            }
            for row in dominant[:5]
        ],
        "intrinsic_subtypes": subtype_rows,
        "feature_ranking_method": {
            "source": "numeric episode-signature artifact",
            "ranking": "median absolute standardized signature descending",
            "tie_breaker": "feature name ascending",
            "direction": "median signed standardized signature",
            "features_per_subtype": int(top_features),
        },
        "matched_volatility_features": sorted(
            str(value)
            for value in taxonomy_summary.get("matched_volatility_features", [])
        ),
        "caveats": list(CAVEATS),
        "source_artifacts": dict(sorted((source_artifacts or {}).items())),
    }
    model["report_digest_sha256"] = _canonical_digest(model)
    return model


def _escape(value: Any) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend(
        "| " + " | ".join(_escape(value) for value in row) + " |"
        for row in rows
    )
    return "\n".join(lines)


def _format_optional(value: float | None, digits: int = 3) -> str:
    return "n/a" if value is None else f"{float(value):.{digits}f}"


def render_markdown(report: dict[str, Any]) -> str:
    """Render a concise deterministic Markdown report."""
    counts = report["counts"]
    dominant = report["dominant_subtypes"]
    subtypes = report["intrinsic_subtypes"]

    lines = [
        "# Core v1 Historical Regime Taxonomy Report",
        "",
        "**Status:** Historical research summary  ",
        "**Runtime impact:** None  ",
        f"**Episodes:** {report['episode_count']}  ",
        f"**Taxonomy digest:** `{report['source_taxonomy_digest_sha256']}`  ",
        f"**Report digest:** `{report['report_digest_sha256']}`",
        "",
        "## Executive Summary",
        "",
        (
            f"The taxonomy classified **{report['episode_count']}** historical collapse episodes. "
            f"**{report['recovered_episode_count']}** recovered within the bounded horizon and "
            f"**{report['persistent_episode_count']}** remained persistent, for a descriptive "
            f"recovered fraction of **{report['descriptive_recovered_fraction']:.3f}**."
        ),
        "",
    ]
    if dominant:
        leading = dominant[0]
        lines.extend(
            [
                (
                    "The dominant intrinsic subtype was "
                    f"`{leading['intrinsic_subtype']}` with "
                    f"**{leading['episode_count']}** episodes and a descriptive "
                    f"recovered fraction of **{leading['recovered_fraction']:.3f}**."
                ),
                "",
            ]
        )

    distribution_rows: list[list[Any]] = []
    for dimension in (
        "collapse_severity",
        "feature_displacement",
        "volatility_state",
        "recovery_outcome",
        "similarity_band",
    ):
        for label, count in counts[dimension].items():
            distribution_rows.append(
                [dimension, label, count, f"{count / report['episode_count']:.3f}"]
            )

    lines.extend(
        [
            "## Distribution",
            "",
            _markdown_table(
                ["Dimension", "Label", "Episodes", "Fraction"],
                distribution_rows,
            ),
            "",
            "## Dominant Intrinsic Subtypes",
            "",
            _markdown_table(
                [
                    "Intrinsic subtype",
                    "Episodes",
                    "Recovered fraction",
                    "Median recovery rows",
                    "Median activation ratio",
                    "Median similarity",
                ],
                [
                    [
                        row["intrinsic_subtype"],
                        row["episode_count"],
                        f"{row['recovered_fraction']:.3f}",
                        _format_optional(row["median_recovery_rows"], 1),
                        f"{row['median_activation_ratio']:.3f}",
                        f"{row['median_similarity_to_current']:.3f}",
                    ]
                    for row in dominant
                ],
            ),
            "",
            "## All Intrinsic Subtypes",
            "",
            _markdown_table(
                [
                    "Intrinsic subtype",
                    "Episodes",
                    "Recovered",
                    "Recovered fraction",
                    "Median recovery rows",
                    "Median activation ratio",
                    "Median similarity",
                ],
                [
                    [
                        row["intrinsic_subtype"],
                        row["episode_count"],
                        row["recovered_count"],
                        f"{row['recovered_fraction']:.3f}",
                        _format_optional(row["median_recovery_rows"], 1),
                        f"{row['median_activation_ratio']:.3f}",
                        f"{row['median_similarity_to_current']:.3f}",
                    ]
                    for row in subtypes
                ],
            ),
            "",
            "## Top Shifted Features by Subtype",
            "",
            (
                "Features are ranked by median absolute standardized signature within each "
                "subtype. The signed median appears in parentheses."
            ),
            "",
            _markdown_table(
                ["Intrinsic subtype", "Episodes", "Top shifted features"],
                [
                    [
                        subtype["intrinsic_subtype"],
                        subtype["episode_count"],
                        "; ".join(
                            f"{feature['feature']} "
                            f"{feature['median_absolute_signature']:.3f} "
                            f"({feature['median_signed_signature']:+.3f})"
                            for feature in subtype["top_shifted_features"]
                        ),
                    ]
                    for subtype in subtypes
                ],
            ),
            "",
            "## Composite Regime Labels",
            "",
            _markdown_table(
                ["Composite label", "Episodes"],
                [
                    [label, count]
                    for label, count in counts["composite_regime_label"].items()
                ],
            ),
            "",
            "## Methodological Caveats",
            "",
        ]
    )
    lines.extend(f"- {caveat}" for caveat in report["caveats"])
    lines.extend(
        [
            "",
            "## Safety Scope",
            "",
            "- Research-only: yes",
            "- Observation-only: yes",
            "- Runtime integration allowed: no",
            "- Exposure mutation allowed: no",
            "",
        ]
    )
    return "\n".join(lines)
