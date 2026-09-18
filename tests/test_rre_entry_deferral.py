from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from research.harness.campaign52_target_replay import TargetRecord
from research.rre_entry_deferral import (
    ELIGIBLE_SLEEVES,
    FROZEN_MODEL_HORIZON_DAYS,
    DeferralDecision,
    InstabilityScore,
    RREEntryDeferralError,
    decide_deferral,
    decisions_to_targets,
    training_q80,
)
from research.strategies.contracts import Action


def rec(*, sleeve="BTC_4H_trend", action=Action.ENTER_LONG, target=.9, seq=0):
    return TargetRecord(
        stage="development", fold="2024", timestamp=pd.Timestamp("2024-06-01T00:00:00Z"),
        sleeve_label=sleeve, asset="BTC" if sleeve.startswith("BTC") else "ETH",
        native_timeframe="4H", strategy_id="trend_following_v11", action=action.value,
        desired_exposure_frac=max(0.0, target), signed_target_exposure=target,
        sequence_number=seq,
    )


def score(p=.9, *, ts="2024-06-01T00:00:00Z", cutoff="2024-01-01T00:00:00Z", horizon=7):
    return InstabilityScore(pd.Timestamp(ts), p, pd.Timestamp(cutoff), horizon)


def test_frozen_eligible_sleeves_exclude_btc1h_and_hedges():
    assert ELIGIBLE_SLEEVES == {"BTC_4H_trend", "ETH_1H_trend", "ETH_4H_trend"}
    assert "BTC_1H_trend" not in ELIGIBLE_SLEEVES
    assert "BTC_1H_hedge" not in ELIGIBLE_SLEEVES
    assert "ETH_1H_hedge" not in ELIGIBLE_SLEEVES


def test_training_q80_is_deterministic_and_outcome_free():
    values = [0.1, 0.2, 0.3, 0.4, 0.5]
    assert training_q80(values) == pytest.approx(0.42)
    assert training_q80(reversed(values)) == pytest.approx(0.42)


def test_training_q80_rejects_empty_nonfinite_and_out_of_range():
    for values in ([], [0.1, float("nan")], [-0.1, 0.2], [0.2, 1.1]):
        with pytest.raises(RREEntryDeferralError):
            training_q80(values)


def test_high_instability_defers_only_to_current_exposure():
    d = decide_deferral(record=rec(target=.9), pre_decision_exposure=.4,
                        core_label="TREND_UP", score=score(.81), q80=.80)
    assert d.intervention_eligible
    assert d.deferred
    assert d.experimental_target == pytest.approx(.4)
    assert d.reason_code == "DEFER_Q80"


def test_equal_to_q80_defers_by_frozen_greater_equal_rule():
    d = decide_deferral(record=rec(target=.7), pre_decision_exposure=.2,
                        core_label="TREND_UP", score=score(.8), q80=.8)
    assert d.deferred


def test_below_q80_leaves_canonical_target_exactly():
    d = decide_deferral(record=rec(target=.9), pre_decision_exposure=.4,
                        core_label="TREND_UP", score=score(.79), q80=.80)
    assert not d.deferred
    assert d.experimental_target == pytest.approx(.9)


@pytest.mark.parametrize("action,target,pre", [
    (Action.HOLD, .4, .4),
    (Action.EXIT_LONG, 0.0, .4),
    (Action.FLAT, 0.0, .4),
    (Action.ENTER_LONG, .3, .4),
])
def test_non_increase_actions_are_never_modified(action, target, pre):
    d = decide_deferral(record=rec(action=action, target=target), pre_decision_exposure=pre,
                        core_label="TREND_DOWN", score=score(.99), q80=.5)
    assert not d.deferred
    assert d.experimental_target == pytest.approx(target)
    assert d.reason_code == "NON_INCREASE_ACTION"


def test_noneligible_sleeve_is_never_modified():
    d = decide_deferral(record=rec(sleeve="SPY_1D_equity", target=.9),
                        pre_decision_exposure=.1, core_label="TREND_UP",
                        score=score(.99), q80=.5)
    assert not d.intervention_eligible
    assert d.experimental_target == pytest.approx(.9)
    assert d.reason_code == "NON_ELIGIBLE_SLEEVE"


@pytest.mark.parametrize("bad_score,bad_q80", [
    (None, .8),
    (score(None), .8),
    (score(float("nan")), .8),
    (score(1.1), .8),
    (score(.9), None),
    (score(.9), float("nan")),
    (score(.9), 1.1),
])
def test_missing_or_invalid_rre_fails_closed_to_canonical(bad_score, bad_q80):
    d = decide_deferral(record=rec(target=.9), pre_decision_exposure=.2,
                        core_label="TREND_UP", score=bad_score, q80=bad_q80)
    assert not d.deferred
    assert d.experimental_target == pytest.approx(.9)


def test_future_training_cutoff_fails_closed_by_exception():
    with pytest.raises(RREEntryDeferralError, match="FUTURE_TRAINING_CUTOFF"):
        decide_deferral(record=rec(), pre_decision_exposure=.2, core_label="TREND_UP",
                        score=score(.9, cutoff="2024-06-02T00:00:00Z"), q80=.8)


def test_wrong_horizon_and_timestamp_fail_closed_by_exception():
    with pytest.raises(RREEntryDeferralError, match="MODEL_HORIZON_DRIFT"):
        decide_deferral(record=rec(), pre_decision_exposure=.2, core_label="TREND_UP",
                        score=score(.9, horizon=3), q80=.8)
    with pytest.raises(RREEntryDeferralError, match="SCORE_TIMESTAMP_MISMATCH"):
        decide_deferral(record=rec(), pre_decision_exposure=.2, core_label="TREND_UP",
                        score=score(.9, ts="2024-06-01T04:00:00Z"), q80=.8)


def test_target_conversion_preserves_identity_and_does_not_mutate_input():
    r = rec(target=.9)
    d = decide_deferral(record=r, pre_decision_exposure=.4, core_label="TREND_UP",
                        score=score(.9), q80=.8)
    out = decisions_to_targets([r], [d])
    assert r.signed_target_exposure == .9
    assert out[0].signed_target_exposure == pytest.approx(.4)
    assert replace(out[0], signed_target_exposure=r.signed_target_exposure) == r


def test_target_conversion_is_deterministic():
    r = rec(target=.9)
    d = decide_deferral(record=r, pre_decision_exposure=.4, core_label="TREND_UP",
                        score=score(.9), q80=.8)
    assert decisions_to_targets([r], [d]) == decisions_to_targets([r], [d])


def test_frozen_horizon_is_seven_days():
    assert FROZEN_MODEL_HORIZON_DAYS == 7
