"""Unit tests — Layer 3 PortfolioAllocator.

Verifies:
- Entry approved under normal conditions.
- Exit approved when holding.
- Entry blocked by drawdown governor halt.
- Entry blocked by exposure cap.
- HOLD returned when delta is below rebalance threshold.
- All-exit triggers SELL decision.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyIntent
from runtime.argus.allocators.portfolio_allocator import PortfolioAllocator, AllocationDecision
from runtime.argus.governors.drawdown_governor import DrawdownGovernor
from runtime.argus.governors.exposure_governor import ExposureGovernor


def make_intent(
    action: Action = Action.ENTER_LONG,
    confidence: float = 0.75,
    exposure: float = 0.70,
    strategy_id: str = "test",
) -> StrategyIntent:
    return StrategyIntent(
        action=action,
        confidence=confidence,
        desired_exposure_frac=exposure,
        horizon_hours=24,
        reason="test",
        strategy_id=strategy_id,
    )


def make_allocator(
    halt_threshold: float = 0.20,
    max_exposure: float = 1.0,
    rebalance_threshold: float = 0.02,
) -> PortfolioAllocator:
    return PortfolioAllocator(
        drawdown_governor=DrawdownGovernor(halt_threshold=halt_threshold, recovery_threshold=0.05),
        exposure_governor=ExposureGovernor(
            max_portfolio_exposure=max_exposure,
            max_strategy_exposure=max_exposure,
            min_trade_notional=10.0,
        ),
        rebalance_threshold=rebalance_threshold,
    )


NAV = 100_000.0


class TestPortfolioAllocator:
    def test_entry_approved(self):
        alloc = make_allocator()
        alloc.dd_gov.update(NAV)
        decision = alloc.allocate(
            intents=[(make_intent(action=Action.ENTER_LONG, exposure=0.70), 1.0)],
            current_nav=NAV,
            current_exposure=0.0,
            regime=RegimeLabel.TREND_UP,
        )
        assert decision.approved
        assert decision.action == "BUY"
        assert 0.0 < decision.target_exposure <= 1.0

    def test_exit_approved_when_holding(self):
        alloc = make_allocator()
        alloc.dd_gov.update(NAV)
        decision = alloc.allocate(
            intents=[(make_intent(action=Action.EXIT_LONG, exposure=0.0), 1.0)],
            current_nav=NAV,
            current_exposure=0.5,
            regime=RegimeLabel.TREND_DOWN,
        )
        assert decision.action == "SELL"
        assert decision.target_exposure == 0.0

    def test_hold_when_below_rebalance_threshold(self):
        alloc = make_allocator(rebalance_threshold=0.10)
        alloc.dd_gov.update(NAV)
        # Desired = 0.65, current = 0.60, delta = 0.05 < 0.10 threshold
        decision = alloc.allocate(
            intents=[(make_intent(action=Action.ENTER_LONG, exposure=0.65), 1.0)],
            current_nav=NAV,
            current_exposure=0.60,
            regime=RegimeLabel.TREND_UP,
        )
        assert decision.action == "HOLD"
        assert not decision.approved

    def test_entry_blocked_when_drawdown_halted(self):
        alloc = make_allocator(halt_threshold=0.15)
        alloc.dd_gov.update(NAV)
        alloc.dd_gov.update(NAV * 0.80)  # 20% DD → halt
        decision = alloc.allocate(
            intents=[(make_intent(action=Action.ENTER_LONG, exposure=0.70), 1.0)],
            current_nav=NAV * 0.80,
            current_exposure=0.0,
            regime=RegimeLabel.TREND_UP,
        )
        assert not decision.approved
        assert decision.action == "HOLD"

    def test_exposure_capped(self):
        alloc = make_allocator(max_exposure=0.50)
        alloc.dd_gov.update(NAV)
        decision = alloc.allocate(
            intents=[(make_intent(action=Action.ENTER_LONG, exposure=0.90), 1.0)],
            current_nav=NAV,
            current_exposure=0.0,
            regime=RegimeLabel.TREND_UP,
        )
        assert decision.target_exposure <= 0.50

    def test_all_sleeves_exiting_triggers_sell(self):
        alloc = make_allocator()
        alloc.dd_gov.update(NAV)
        intents = [
            (make_intent(action=Action.EXIT_LONG, exposure=0.0, strategy_id="s1"), 0.5),
            (make_intent(action=Action.EXIT_LONG, exposure=0.0, strategy_id="s2"), 0.5),
        ]
        decision = alloc.allocate(
            intents=intents,
            current_nav=NAV,
            current_exposure=0.5,
            regime=RegimeLabel.TREND_DOWN,
        )
        assert decision.action == "SELL"
        assert decision.target_exposure == 0.0

    def test_no_intents_returns_hold(self):
        alloc = make_allocator()
        decision = alloc.allocate(
            intents=[],
            current_nav=NAV,
            current_exposure=0.5,
            regime=RegimeLabel.RANGE,
        )
        assert decision.action == "HOLD"

    def test_blended_exposure_in_decision(self):
        alloc = make_allocator()
        alloc.dd_gov.update(NAV)
        intents = [
            (make_intent(action=Action.ENTER_LONG, exposure=0.8, strategy_id="s1"), 0.5),
            (make_intent(action=Action.ENTER_LONG, exposure=0.6, strategy_id="s2"), 0.5),
        ]
        decision = alloc.allocate(
            intents=intents,
            current_nav=NAV,
            current_exposure=0.0,
            regime=RegimeLabel.TREND_UP,
        )
        # Blended = 0.8 * 0.5 + 0.6 * 0.5 = 0.7
        assert abs(decision.blended_exposure - 0.70) < 0.01
