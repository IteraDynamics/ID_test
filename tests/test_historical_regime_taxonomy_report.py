from __future__ import annotations

import copy
import json

import pandas as pd
import pytest

from research.ml.validation.historical_regime_taxonomy import (
    build_summary,
    classify_episodes,
)
from research.ml.validation.historical_regime_taxonomy_report import (
    build_report_model,
    render_markdown,
)


def _episodes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "episode_id": 2,
                "window_start": "2024-02-01",
                "window_end": "2024-02-29",
                "reference_activation_rate": 0.5,
                "observation_activation_rate": 0.05,
                "activation_ratio": 0.10,
                "feature_cosine_similarity_to_latest": 0.75,
                "recovered_without_retraining": True,
                "recovery_rows": 720,
            },
            {
                "episode_id": 1,
                "window_start": "2024-01-01",
                "window_end": "2024-01-31",
                "reference_activation_rate": 0.5,
                "observation_activation_rate": 0.10,
                "activation_ratio": 0.20,
                "feature_cosine_similarity_to_latest": 0.40,
                "recovered_without_retraining": False,
                "recovery_rows": None,
            },
            {
                "episode_id": 3,
                "window_start": "2024-03-01",
                "window_end": "2024-03-31",
                "reference_activation_rate": 0.5,
                "observation_activation_rate": 0.025,
                "activation_ratio": 0.05,
                "feature_cosine_similarity_to_latest": 0.20,
                "recovered_without_retraining": True,
                "recovery_rows": 1440,
            },
        ]
    )


def _signatures() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "zeta": [1.0, 0.0, -1.0],
            "alpha": [1.0, 0.0, -1.0],
            "slow_vol": [1.5, 0.0, 0.5],
            "feature_a": [2.5, 2.0, 0.25],
        },
        index=pd.Index([2, 1, 3], name="episode_id"),
    )


def _classified_and_summary() -> tuple[pd.DataFrame, dict[str, object]]:
    classified = classify_episodes(
        _episodes(),
        _signatures(),
        collapse_ratio=0.35,
        observation_rows=720,
    )
    summary = build_summary(
        classified,
        config={"collapse_ratio": 0.35, "observation_rows": 720},
        latest_window={"window_end": "2026-07-01"},
        source_artifacts={"episodes": "episodes.csv", "signatures": "signatures.csv"},
    )
    return classified, summary


def test_report_model_is_deterministic_and_preserves_inputs() -> None:
    classified, summary = _classified_and_summary()
    signatures = _signatures()
    classified_before = classified.copy(deep=True)
    signatures_before = signatures.copy(deep=True)

    first = build_report_model(
        classified,
        signatures,
        copy.deepcopy(summary),
        top_features=3,
        source_artifacts={"signatures": "b.csv", "episodes": "a.json"},
    )
    second = build_report_model(
        classified.sample(frac=1.0, random_state=3),
        signatures.sample(frac=1.0, random_state=4),
        copy.deepcopy(summary),
        top_features=3,
        source_artifacts={"episodes": "a.json", "signatures": "b.csv"},
    )

    assert first == second
    json.dumps(first, sort_keys=True, allow_nan=False)
    pd.testing.assert_frame_equal(classified, classified_before)
    pd.testing.assert_frame_equal(signatures, signatures_before)


def test_report_ranks_features_with_deterministic_tie_break() -> None:
    classified, summary = _classified_and_summary()
    report = build_report_model(
        classified,
        _signatures(),
        summary,
        top_features=4,
    )
    subtype = next(
        row
        for row in report["intrinsic_subtypes"]
        if row["intrinsic_subtype"].startswith("SEVERE_COLLAPSE")
        and row["episode_count"] == 2
    )
    feature_names = [row["feature"] for row in subtype["top_shifted_features"]]
    assert feature_names.index("alpha") < feature_names.index("zeta")


def test_report_fails_closed_on_identifier_or_summary_mismatch() -> None:
    classified, summary = _classified_and_summary()
    with pytest.raises(ValueError, match="identifiers must match exactly"):
        build_report_model(classified, _signatures().drop(index=3), summary)

    broken_summary = copy.deepcopy(summary)
    broken_summary["counts"]["recovery_outcome"]["RAPID_RECOVERY"] += 1
    with pytest.raises(ValueError, match="count mismatch"):
        build_report_model(classified, _signatures(), broken_summary)


def test_markdown_contains_required_metrics_and_caveats() -> None:
    classified, summary = _classified_and_summary()
    report = build_report_model(classified, _signatures(), summary)
    markdown = render_markdown(report)

    assert "# Core v1 Historical Regime Taxonomy Report" in markdown
    assert summary["deterministic_digest_sha256"] in markdown
    assert "## Top Shifted Features by Subtype" in markdown
    assert "overlapping rolling-window observations" in markdown
    assert "bounded recovery horizon" in markdown
    assert "Runtime integration allowed: no" in markdown
