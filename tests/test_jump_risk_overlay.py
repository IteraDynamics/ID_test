from __future__ import annotations

from datetime import UTC, datetime, timedelta

from runtime.core_v1.jump_risk_overlay import (
    BASE_SCALE,
    BOOST_SCALE,
    ProbabilityInput,
    config_fingerprint,
    decide_asset_scale,
)


def _inputs(now: datetime, medium: float = 0.96, extended: float = 0.20):
    return {
        "medium_up": ProbabilityInput(
            probability=medium,
            threshold=0.95,
            source_bar_ts=now - timedelta(hours=1),
            computed_at=now - timedelta(minutes=2),
        ),
        "extended_up": ProbabilityInput(
            probability=extended,
            threshold=0.95,
            source_bar_ts=now - timedelta(hours=1),
            computed_at=now - timedelta(minutes=2),
        ),
    }


def test_disabled_by_default_fails_closed() -> None:
    now = datetime(2026, 7, 16, 18, tzinfo=UTC)
    result = decide_asset_scale(asset="BTC", probabilities=_inputs(now), core_aligned=True, decision_at=now)
    assert result.scale == BASE_SCALE
    assert result.reason_code == "FEATURE_DISABLED"
    assert result.boosted is False


def test_active_medium_up_boosts_when_core_aligned() -> None:
    now = datetime(2026, 7, 16, 18, tzinfo=UTC)
    result = decide_asset_scale(
        asset="BTC", probabilities=_inputs(now), core_aligned=True, decision_at=now, enabled=True
    )
    assert result.scale == BOOST_SCALE
    assert result.boosted is True
    assert result.reason_code == "ALIGNED_UPSIDE_ACTIVE"
    assert result.medium_up_active is True


def test_either_locked_up_model_can_activate() -> None:
    now = datetime(2026, 7, 16, 18, tzinfo=UTC)
    result = decide_asset_scale(
        asset="ETH",
        probabilities=_inputs(now, medium=0.20, extended=0.97),
        core_aligned=True,
        decision_at=now,
        enabled=True,
    )
    assert result.scale == BOOST_SCALE
    assert result.extended_up_active is True


def test_below_threshold_remains_baseline() -> None:
    now = datetime(2026, 7, 16, 18, tzinfo=UTC)
    result = decide_asset_scale(
        asset="ETH",
        probabilities=_inputs(now, medium=0.50, extended=0.70),
        core_aligned=True,
        decision_at=now,
        enabled=True,
    )
    assert result.scale == BASE_SCALE
    assert result.reason_code == "BELOW_THRESHOLD"


def test_overlay_cannot_create_direction() -> None:
    now = datetime(2026, 7, 16, 18, tzinfo=UTC)
    result = decide_asset_scale(
        asset="BTC", probabilities=_inputs(now), core_aligned=False, decision_at=now, enabled=True
    )
    assert result.scale == BASE_SCALE
    assert result.reason_code == "CORE_NOT_ALIGNED"


def test_non_paper_mode_is_blocked() -> None:
    now = datetime(2026, 7, 16, 18, tzinfo=UTC)
    result = decide_asset_scale(
        asset="BTC",
        probabilities=_inputs(now),
        core_aligned=True,
        decision_at=now,
        enabled=True,
        paper_mode=False,
    )
    assert result.scale == BASE_SCALE
    assert result.reason_code == "PAPER_ONLY_GUARD"


def test_missing_and_stale_inputs_fail_closed() -> None:
    now = datetime(2026, 7, 16, 18, tzinfo=UTC)
    missing = decide_asset_scale(
        asset="BTC", probabilities=None, core_aligned=True, decision_at=now, enabled=True
    )
    assert missing.reason_code == "MISSING_INPUTS"

    stale_inputs = _inputs(now)
    stale_inputs["medium_up"] = ProbabilityInput(
        probability=0.99,
        threshold=0.95,
        source_bar_ts=now - timedelta(hours=5),
        computed_at=now - timedelta(hours=4),
    )
    stale = decide_asset_scale(
        asset="BTC", probabilities=stale_inputs, core_aligned=True, decision_at=now, enabled=True
    )
    assert stale.scale == BASE_SCALE
    assert stale.reason_code == "STALE_INPUTS"


def test_invalid_timestamp_order_fails_closed() -> None:
    now = datetime(2026, 7, 16, 18, tzinfo=UTC)
    bad = _inputs(now)
    bad["medium_up"] = ProbabilityInput(
        probability=0.99,
        threshold=0.95,
        source_bar_ts=now,
        computed_at=now - timedelta(minutes=1),
    )
    result = decide_asset_scale(
        asset="BTC", probabilities=bad, core_aligned=True, decision_at=now, enabled=True
    )
    assert result.scale == BASE_SCALE
    assert result.reason_code == "INVALID_TIMESTAMP_ORDER"


def test_config_fingerprint_is_stable() -> None:
    first = config_fingerprint()
    second = config_fingerprint()
    assert first == second
    assert len(first) == 64
