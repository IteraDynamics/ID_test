"""Unit tests — Layer 3 Governors.

Verifies:
- DrawdownGovernor halts on threshold breach.
- DrawdownGovernor unhalts on recovery.
- DrawdownGovernor never blocks sells.
- ExposureGovernor caps exposure correctly.
- ExposureGovernor blocks entry at UNKNOWN regime.
- ExposureGovernor blocks low-confidence intents.
- ExposureGovernor checks minimum notional.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyIntent
from runtime.argus.governors.drawdown_governor import DrawdownGovernor
from runtime.argus.governors.exposure_governor import ExposureGovernor


def make_intent(
    action: Action = Action.ENTER_LONG,
    confidence: float = 0.75,
    desired_exposure: float = 0.80,
    strategy_id: str = "test",
) -> StrategyIntent:
    return StrategyIntent(
        action=action,
        confidence=confidence,
        desired_exposure_frac=desired_exposure,
        horizon_hours=24,
        reason="test",
        strategy_id=strategy_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DrawdownGovernor
# ─────────────────────────────────────────────────────────────────────────────

class TestDrawdownGovernor:
    def test_initially_not_halted(self):
        gov = DrawdownGovernor(halt_threshold=0.20, recovery_threshold=0.10)
        gov.update(100_000)
        assert gov.is_buy_allowed()

    def test_halts_on_threshold_breach(self):
        gov = DrawdownGovernor(halt_threshold=0.20, recovery_threshold=0.10)
        gov.update(100_000)   # sets HWM
        gov.update(79_000)    # 21% drawdown — should halt
        assert not gov.is_buy_allowed()

    def test_sells_always_allowed(self):
        gov = DrawdownGovernor(halt_threshold=0.20, recovery_threshold=0.10)
        gov.update(100_000)
        gov.update(50_000)    # deep drawdown
        assert gov.is_sell_allowed()

    def test_unhalts_on_recovery(self):
        gov = DrawdownGovernor(halt_threshold=0.20, recovery_threshold=0.09)
        gov.update(100_000)
        gov.update(79_000)    # halted at 21% DD
        assert not gov.is_buy_allowed()
        gov.update(92_000)    # recovered to 8% DD — below recovery threshold
        assert gov.is_buy_allowed()

    def test_does_not_unhalt_partially(self):
        gov = DrawdownGovernor(halt_threshold=0.20, recovery_threshold=0.10)
        gov.update(100_000)
        gov.update(79_000)    # halted
        gov.update(88_000)    # 12% DD — still above recovery threshold of 10%
        assert not gov.is_buy_allowed()

    def test_hwm_updates_on_new_high(self):
        gov = DrawdownGovernor(halt_threshold=0.20, recovery_threshold=0.10)
        gov.update(100_000)
        gov.update(120_000)   # new high
        gov.update(97_000)    # 19% DD from new HWM — NOT halted
        assert gov.is_buy_allowed()

    def test_state_dict_and_load(self):
        gov = DrawdownGovernor(halt_threshold=0.20, recovery_threshold=0.10)
        gov.update(100_000)
        gov.update(79_000)
        state = gov.state_dict()
        assert state["is_halted"] is True
        assert state["high_water_mark"] == 100_000.0

        gov2 = DrawdownGovernor()
        gov2.load_state(state)
        assert gov2._is_halted is True

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            DrawdownGovernor(halt_threshold=0.0)

    def test_recovery_must_be_leq_halt(self):
        with pytest.raises(ValueError):
            DrawdownGovernor(halt_threshold=0.10, recovery_threshold=0.20)


# ─────────────────────────────────────────────────────────────────────────────
# ExposureGovernor
# ─────────────────────────────────────────────────────────────────────────────

class TestExposureGovernor:
    def setup_method(self):
        self.gov = ExposureGovernor(
            max_portfolio_exposure=0.80,
            max_strategy_exposure=0.70,
            min_trade_notional=50.0,
        )
        self.nav = 100_000.0

    def test_entry_approved(self):
        intent = make_intent(confidence=0.75, desired_exposure=0.60)
        ok, capped, reason = self.gov.check_entry(
            intent=intent,
            current_nav=self.nav,
            current_exposure=0.0,
            regime=RegimeLabel.TREND_UP,
            drawdown_governor_allows=True,
        )
        assert ok
        assert capped <= 0.70  # capped by max_strategy_exposure

    def test_entry_capped_by_max_exposure(self):
        intent = make_intent(confidence=0.75, desired_exposure=0.95)
        ok, capped, _ = self.gov.check_entry(
            intent=intent,
            current_nav=self.nav,
            current_exposure=0.0,
            regime=RegimeLabel.TREND_UP,
            drawdown_governor_allows=True,
        )
        assert ok
        assert capped <= 0.70

    def test_entry_blocked_by_drawdown_governor(self):
        intent = make_intent(confidence=0.75, desired_exposure=0.60)
        ok, _, reason = self.gov.check_entry(
            intent=intent,
            current_nav=self.nav,
            current_exposure=0.0,
            regime=RegimeLabel.TREND_UP,
            drawdown_governor_allows=False,  # halted
        )
        assert not ok
        assert "halt" in reason.lower() or "blocked" in reason.lower()

    def test_entry_blocked_on_unknown_regime_no_position(self):
        intent = make_intent(confidence=0.75, desired_exposure=0.60)
        ok, _, reason = self.gov.check_entry(
            intent=intent,
            current_nav=self.nav,
            current_exposure=0.0,
            regime=RegimeLabel.UNKNOWN,
            drawdown_governor_allows=True,
        )
        assert not ok
        assert "UNKNOWN" in reason

    def test_entry_blocked_on_low_confidence(self):
        intent = make_intent(confidence=0.25, desired_exposure=0.60)
        ok, _, reason = self.gov.check_entry(
            intent=intent,
            current_nav=self.nav,
            current_exposure=0.0,
            regime=RegimeLabel.TREND_UP,
            drawdown_governor_allows=True,
        )
        assert not ok

    def test_entry_blocked_on_notional_too_small(self):
        # nav=$1000, flat, desired=0.001 → delta_notional = 0.001 * 1000 = $1 < $50 min
        intent = make_intent(confidence=0.75, desired_exposure=0.001)
        ok, _, reason = self.gov.check_entry(
            intent=intent,
            current_nav=1000.0,
            current_exposure=0.0,   # flat → delta_notional = $1 < $50
            regime=RegimeLabel.TREND_UP,
            drawdown_governor_allows=True,
        )
        assert not ok
        assert "notional" in reason.lower()

    def test_exit_approved(self):
        intent = make_intent(action=Action.EXIT_LONG)
        ok, reason = self.gov.check_exit(
            intent=intent,
            current_exposure=0.5,
            current_nav=self.nav,
        )
        assert ok

    def test_exit_blocked_when_flat(self):
        intent = make_intent(action=Action.EXIT_LONG)
        ok, reason = self.gov.check_exit(
            intent=intent,
            current_exposure=0.0,
            current_nav=self.nav,
        )
        assert not ok
