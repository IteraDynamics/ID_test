"""Unit tests for the Fund v2 DefensiveExposureGovernor."""

from __future__ import annotations

import math

from runtime.argus.governors.defensive_exposure_governor import (
    DefensiveExposureGovernor,
)


def test_defensive_governor_triggers_and_recovers_with_hysteresis() -> None:
    """Governor should activate after confirmed drawdown and release after recovery."""
    gov = DefensiveExposureGovernor(
        lookback_bars=50,
        dd_trigger=0.20,
        dd_release=0.12,
        trend_ema_span=20,
        risk_off_scale=0.75,
        confirm_bars=3,
        release_confirm_bars=3,
        min_warmup_bars=10,
    )

    prices: list[float] = []
    prices += [100.0 + i for i in range(60)]          # stable uptrend / warmup
    prices += [160.0 - 4.0 * i for i in range(12)]    # drawdown through trigger
    prices += [112.0 for _ in range(12)]              # confirmed risk-off
    prices += [112.0 + 3.0 * i for i in range(30)]    # recovery / release

    scales: list[float] = []
    active_flags: list[bool] = []
    transitions: list[str] = []

    for i, price in enumerate(prices):
        decision = gov.update(price, price, timestamp=f"bar-{i}")
        scales.append(decision.exposure_scale)
        active_flags.append(decision.active)
        transitions.append(str(decision.meta.get("transition")))

    assert min(scales) == 0.75
    assert any(active_flags), "Governor never entered risk-off mode"
    assert scales[-1] == 1.0
    assert active_flags[-1] is False
    assert "activated" in transitions
    assert "released" in transitions

    scale_flips = sum(1 for prev, cur in zip(scales, scales[1:]) if abs(prev - cur) > 1e-9)
    assert scale_flips == 2, "Expected one activation and one release"


def test_defensive_governor_apply_scale_never_adds_risk() -> None:
    gov = DefensiveExposureGovernor(
        lookback_bars=20,
        dd_trigger=0.20,
        dd_release=0.12,
        trend_ema_span=10,
        risk_off_scale=0.75,
        confirm_bars=1,
        release_confirm_bars=1,
        min_warmup_bars=5,
    )

    for i, price in enumerate([100, 101, 102, 103, 104, 70, 69, 68]):
        decision = gov.update(float(price), float(price), timestamp=i)

    assert decision.active is True
    assert math.isclose(gov.apply_scale(0.80), 0.60)
    assert gov.apply_scale(0.0) == 0.0
    assert gov.apply_scale(1.5) <= 1.0


def test_defensive_governor_state_round_trip_preserves_mode() -> None:
    gov = DefensiveExposureGovernor(
        lookback_bars=20,
        dd_trigger=0.20,
        dd_release=0.12,
        trend_ema_span=10,
        risk_off_scale=0.75,
        confirm_bars=1,
        release_confirm_bars=2,
        min_warmup_bars=5,
    )

    for i, price in enumerate([100, 101, 102, 103, 104, 70, 69, 68]):
        gov.update(float(price), float(price), timestamp=f"bar-{i}")

    assert gov.is_active is True
    state = gov.state_dict()

    restored = DefensiveExposureGovernor(
        lookback_bars=20,
        dd_trigger=0.20,
        dd_release=0.12,
        trend_ema_span=10,
        risk_off_scale=0.75,
        confirm_bars=1,
        release_confirm_bars=2,
        min_warmup_bars=5,
    )
    restored.load_state(state)

    assert restored.is_active is True
    assert restored.current_scale == 0.75
    assert restored.apply_scale(1.0) == 0.75

    decision = restored.update(105.0, 105.0, timestamp="recovery-1")
    assert decision.exposure_scale in (0.75, 1.0)
    assert "exposure_scale" in decision.meta
