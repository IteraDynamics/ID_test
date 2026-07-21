from __future__ import annotations

import pandas as pd
import pytest

from scripts.summarize_core_v1_jump_risk_diagnosis_v2 import rank_evidence


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "feature": ["quiet", "shifted", "psi_only", "ks_only"],
            "reference_mean": [0.0, 1.0, 2.0, 3.0],
            "observation_mean": [0.1, 2.0, 2.1, 3.1],
            "standardized_mean_shift": [0.10, 0.75, 0.10, 0.10],
            "psi": [0.05, 0.10, 0.30, 0.10],
            "ks_statistic": [0.05, 0.10, 0.10, 0.25],
            "reference_missing_fraction": [0.0, 0.0, 0.0, 0.02],
            "observation_missing_fraction": [0.0, 0.0, 0.0, 0.07],
        }
    )


def test_rank_evidence_marks_each_material_threshold() -> None:
    ranked = rank_evidence(_frame()).set_index("feature")

    assert not bool(ranked.loc["quiet", "material"])
    assert bool(ranked.loc["shifted", "material"])
    assert bool(ranked.loc["psi_only", "material"])
    assert bool(ranked.loc["ks_only", "material"])


def test_rank_evidence_orders_material_rows_before_quiet_rows() -> None:
    ranked = rank_evidence(_frame())

    assert ranked.iloc[-1]["feature"] == "quiet"
    assert ranked.iloc[0]["feature"] == "shifted"


def test_rank_evidence_calculates_missingness_increase() -> None:
    ranked = rank_evidence(_frame()).set_index("feature")

    assert ranked.loc["ks_only", "missingness_increase"] == pytest.approx(0.05)


def test_rank_evidence_is_stable_for_ties() -> None:
    frame = _frame().iloc[[0, 0]].copy()
    frame["feature"] = ["beta", "alpha"]

    ranked = rank_evidence(frame)

    assert ranked["feature"].tolist() == ["alpha", "beta"]


def test_rank_evidence_rejects_missing_contract_column() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        rank_evidence(_frame().drop(columns=["psi"]))
