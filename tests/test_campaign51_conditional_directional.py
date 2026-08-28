from __future__ import annotations

import json
from datetime import datetime, timedelta

import numpy as np
import pytest

from research.campaign51_conditional_directional import (
    FAMILY_SIZE,
    SUPPORT_GATES,
    Campaign51Error,
    Standardization,
    candidate_inventory,
    canonical_csv_bytes,
    canonical_json_bytes,
    classify_development,
    classify_validation,
    compatible_ratio,
    design_matrix,
    forward_log_return,
    holm_adjust,
    ols_hc3_interaction,
    predictor_values,
    same_nonzero_sign,
    standardization_params,
    support_gate,
    transform_predictors,
)


def _hourly_closes(count: int = 400) -> tuple[datetime, dict[datetime, float]]:
    start = datetime(2020, 1, 1)
    return start, {
        start + timedelta(hours=index): 100.0 * np.exp(0.001 * index + 0.002 * np.sin(index / 7.0))
        for index in range(count)
    }


def test_candidate_inventory_is_exact_and_canonical() -> None:
    candidates = candidate_inventory()
    assert len(candidates) == FAMILY_SIZE == 12
    assert len({candidate.key for candidate in candidates}) == 12
    assert candidates[0].key == (
        "return_trailing_24h__x__realized_volatility_trailing_24h__fwd_log_return_24h"
    )
    assert candidates[-1].key == (
        "return_trailing_168h__x__drawdown_from_high_trailing_168h__fwd_log_return_168h"
    )


def test_predictor_formulas_match_direct_calculation() -> None:
    start, closes = _hourly_closes()
    anchor = start + timedelta(hours=200)
    values = predictor_values(closes, anchor)
    c = np.asarray([closes[anchor - timedelta(hours=i)] for i in range(168, -1, -1)])
    assert values["return_trailing_24h"] == pytest.approx(np.log(c[-1] / c[-25]))
    assert values["return_trailing_168h"] == pytest.approx(np.log(c[-1] / c[0]))
    assert values["realized_volatility_trailing_24h"] == pytest.approx(
        np.sqrt(np.sum(np.diff(np.log(c[-25:])) ** 2))
    )
    assert values["drawdown_from_high_trailing_168h"] == pytest.approx(c[-1] / np.max(c) - 1.0)


def test_predictor_window_fails_closed_on_missing_timestamp() -> None:
    start, closes = _hourly_closes()
    anchor = start + timedelta(hours=200)
    del closes[anchor - timedelta(hours=50)]
    with pytest.raises(Campaign51Error, match="WINDOW_TIMESTAMP_FAILURE"):
        predictor_values(closes, anchor)


def test_forward_outcome_requires_exact_endpoint_and_stage_containment() -> None:
    start, closes = _hourly_closes()
    anchor = start + timedelta(hours=200)
    expected = np.log(closes[anchor + timedelta(hours=24)] / closes[anchor])
    assert forward_log_return(closes, anchor, 24, anchor + timedelta(hours=24)) == pytest.approx(expected)
    with pytest.raises(Campaign51Error, match="OUTCOME_STAGE_BOUNDARY_FAILURE"):
        forward_log_return(closes, anchor, 24, anchor + timedelta(hours=23))
    del closes[anchor + timedelta(hours=24)]
    with pytest.raises(Campaign51Error, match="OUTCOME_TIMESTAMP_FAILURE"):
        forward_log_return(closes, anchor, 24, anchor + timedelta(hours=24))


def test_development_standardization_is_reused_unchanged() -> None:
    params = standardization_params([1.0, 2.0, 3.0], [10.0, 20.0, 40.0])
    validation_d, validation_s, interaction = transform_predictors([4.0], [50.0], params)
    assert params.directional_mean == pytest.approx(2.0)
    assert validation_d[0] == pytest.approx((4.0 - 2.0) / np.std([1.0, 2.0, 3.0], ddof=0))
    assert validation_s[0] == pytest.approx((50.0 - params.state_mean) / params.state_sd)
    assert interaction[0] == pytest.approx(validation_d[0] * validation_s[0])


def test_standardization_rejects_zero_variance() -> None:
    with pytest.raises(Campaign51Error, match="ZERO_OR_NONFINITE_VARIANCE"):
        standardization_params([1.0, 1.0], [1.0, 2.0])


def test_design_contains_intercept_main_effects_and_interaction() -> None:
    directional = np.asarray([-1.0, 0.0, 1.0, 2.0])
    state = np.asarray([2.0, -1.0, 1.0, 0.5])
    matrix = design_matrix(directional, state)
    assert matrix.shape == (4, 4)
    assert np.all(matrix[:, 0] == 1.0)
    assert np.allclose(matrix[:, 1], directional)
    assert np.allclose(matrix[:, 2], state)
    assert np.allclose(matrix[:, 3], directional * state)


def test_rank_deficient_design_fails_closed() -> None:
    with pytest.raises(Campaign51Error, match="RANK_DEFICIENT_DESIGN"):
        design_matrix([1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 8.0])


def test_ols_hc3_recovers_interaction_fixture() -> None:
    directional = np.asarray([-2.0, -1.5, -1.0, -0.4, 0.1, 0.7, 1.2, 1.8, 2.3, 2.9])
    state = np.asarray([1.1, -0.8, 0.4, -1.5, 2.0, -0.2, 1.7, -1.1, 0.6, -2.0])
    noise = np.asarray([0.03, -0.02, 0.01, -0.04, 0.02, 0.01, -0.03, 0.04, -0.01, 0.02])
    outcomes = 0.2 + 0.5 * directional - 0.3 * state + 0.8 * directional * state + noise
    result = ols_hc3_interaction(directional, state, outcomes)
    assert result.rank == 4
    assert result.n == 10
    assert result.beta_interaction == pytest.approx(0.8, abs=0.03)
    assert result.se_interaction_hc3 > 0
    assert 0 <= result.p_value <= 1
    assert result.ci_low < result.beta_interaction < result.ci_high


@pytest.mark.parametrize("stage", ["development", "validation", "confirmation"])
@pytest.mark.parametrize("horizon", [24, 72, 168])
def test_support_gates_at_and_below_boundary(stage: str, horizon: int) -> None:
    minimum = SUPPORT_GATES[stage][horizon]
    assert support_gate(stage, horizon, minimum) is None
    assert support_gate(stage, horizon, minimum - 1) == "INSUFFICIENT_SUPPORT"


def test_holm_uses_family_size_12_and_canonical_ties() -> None:
    keys = [candidate.key for candidate in candidate_inventory()[:3]]
    adjusted = holm_adjust({keys[1]: 0.01, keys[0]: 0.01, keys[2]: 0.02})
    assert list(adjusted)[:2] == [keys[0], keys[1]]
    assert adjusted[keys[0]] == pytest.approx(0.12)
    with pytest.raises(Campaign51Error, match="MULTIPLICITY_FAMILY_FAILURE"):
        holm_adjust({keys[0]: 0.01}, family_size=3)


def test_development_classification_boundary() -> None:
    assert classify_development(True, 0.05) == "DISCOVERY_SUPPORTED"
    assert classify_development(True, 0.0500001) == "DISCOVERY_NOT_SUPPORTED"
    assert classify_development(False, None) == "UNRANKABLE"


def test_validation_requires_eligibility_sign_p_and_ratio() -> None:
    assert classify_validation("DISCOVERY_SUPPORTED", True, 1.0, 0.25, 0.10) == "VALIDATION_SUPPORTED"
    assert classify_validation("DISCOVERY_SUPPORTED", True, 1.0, 4.0, 0.10) == "VALIDATION_SUPPORTED"
    assert classify_validation("DISCOVERY_SUPPORTED", True, 1.0, -1.0, 0.01) == "VALIDATION_NOT_SUPPORTED"
    assert classify_validation("DISCOVERY_SUPPORTED", True, 1.0, 0.249, 0.01) == "VALIDATION_NOT_SUPPORTED"
    assert classify_validation("DISCOVERY_SUPPORTED", True, 1.0, 4.001, 0.01) == "VALIDATION_NOT_SUPPORTED"
    assert classify_validation("DISCOVERY_NOT_SUPPORTED", True, 1.0, 1.0, 0.01) == "VALIDATION_NOT_ELIGIBLE"


def test_sign_and_ratio_helpers() -> None:
    assert same_nonzero_sign(-1.0, -2.0)
    assert not same_nonzero_sign(0.0, 1.0)
    assert compatible_ratio(2.0, 0.5)
    assert compatible_ratio(2.0, 8.0)
    assert not compatible_ratio(2.0, 0.49)


def test_canonical_serialization_is_deterministic_and_strict() -> None:
    left = canonical_json_bytes({"b": 2, "a": 1})
    right = canonical_json_bytes({"a": 1, "b": 2})
    assert left == right == b'{"a":1,"b":2}\n'
    assert json.loads(left) == {"a": 1, "b": 2}
    csv_bytes = canonical_csv_bytes(("a", "b"), ({"b": 2, "a": 1},))
    assert csv_bytes == b"a,b\n1,2\n"


def test_confirmation_is_not_exposed_as_an_execution_function() -> None:
    import research.campaign51_conditional_directional as module

    assert not hasattr(module, "run_confirmation")
    assert not hasattr(module, "execute_development_validation")
