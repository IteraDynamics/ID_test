"""Portfolio allocator — combines per-sleeve intents into a governed target exposure.

Allocation flow:
    1. Receive a list of (StrategyIntent, weight) pairs.
    2. Compute weighted-blend desired exposure.
    3. Evaluate against ExposureGovernor rules.
    4. Return an AllocationDecision with the final approved target.

The allocator does not interact with any broker.  It outputs a target
exposure fraction which the orchestrator then executes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyIntent
from runtime.argus.governors.drawdown_governor import DrawdownGovernor
from runtime.argus.governors.exposure_governor import ExposureGovernor

log = logging.getLogger(__name__)


@dataclass
class AllocationDecision:
    """Output of a single allocator cycle.

    Attributes
    ----------
    target_exposure : float
        Final approved exposure fraction [0, 1] to execute.
    action : str
        "BUY", "SELL", or "HOLD" — the net portfolio action.
    reason : str
        Composite reason string from all sleeves and governors.
    sleeve_exposures : dict
        Per-sleeve desired exposures before blending.
    blended_exposure : float
        Weighted blend before governor caps.
    approved : bool
        Whether the change was approved (False = hold current state).
    meta : dict
        Audit metadata.
    """

    target_exposure: float
    action: str
    reason: str
    sleeve_exposures: dict[str, float] = field(default_factory=dict)
    blended_exposure: float = 0.0
    approved: bool = True
    meta: dict[str, Any] = field(default_factory=dict)


class PortfolioAllocator:
    """Combines strategy intents into a governed allocation decision.

    Parameters
    ----------
    drawdown_governor : DrawdownGovernor
    exposure_governor : ExposureGovernor
    rebalance_threshold : float
        Minimum exposure change that triggers a trade decision.
    """

    def __init__(
        self,
        drawdown_governor: DrawdownGovernor,
        exposure_governor: ExposureGovernor,
        rebalance_threshold: float = 0.02,
    ) -> None:
        self.dd_gov = drawdown_governor
        self.exp_gov = exposure_governor
        self.rebalance_threshold = rebalance_threshold

    def allocate(
        self,
        intents: list[tuple[StrategyIntent, float]],  # (intent, weight)
        current_nav: float,
        current_exposure: float,
        regime: RegimeLabel,
    ) -> AllocationDecision:
        """Compute the final allocation decision.

        Parameters
        ----------
        intents :
            List of (StrategyIntent, weight) tuples.  Weights are normalised.
        current_nav :
            Current portfolio NAV in USD.
        current_exposure :
            Current portfolio exposure fraction [0, 1].
        regime :
            Current regime label.

        Returns
        -------
        AllocationDecision
        """
        if not intents:
            return AllocationDecision(
                target_exposure=current_exposure,
                action="HOLD",
                reason="No intents provided",
                approved=False,
            )

        # ── Normalise weights ─────────────────────────────────────────
        total_w = sum(w for _, w in intents)
        if total_w <= 0:
            total_w = 1.0
        norm_weights = [w / total_w for _, w in intents]

        # ── Compute per-sleeve desired exposures (unscaled) ──────────
        sleeve_exposures: dict[str, float] = {}
        for (intent, _), nw in zip(intents, norm_weights):
            if intent.action in (Action.EXIT_LONG, Action.FLAT):
                desired = 0.0
            elif intent.action == Action.HOLD:
                desired = current_exposure
            else:
                desired = intent.desired_exposure_frac
            sleeve_exposures[intent.strategy_id] = round(desired, 5)

        # ── Blended exposure: weighted sum of unscaled sleeve exposures
        blended = sum(
            exp * nw
            for exp, nw in zip(sleeve_exposures.values(), norm_weights)
        )

        # ── Any sleeve calling exit? → de-risk ────────────────────────
        any_exit = any(
            intent.action in (Action.EXIT_LONG, Action.FLAT)
            for intent, _ in intents
        )

        # If all sleeves exit, go flat
        all_exit = all(
            intent.action in (Action.EXIT_LONG, Action.FLAT)
            for intent, _ in intents
        )

        if all_exit:
            # Check sell is worthwhile
            sell_ok, sell_reason = self.exp_gov.check_exit(
                intents[0][0], current_exposure, current_nav
            )
            return AllocationDecision(
                target_exposure=0.0,
                action="SELL",
                reason=f"All sleeves exiting. {sell_reason}",
                sleeve_exposures=sleeve_exposures,
                blended_exposure=0.0,
                approved=sell_ok,
                meta={"all_exit": True},
            )

        # ── Check if change is large enough to bother ─────────────────
        delta = blended - current_exposure
        if abs(delta) < self.rebalance_threshold:
            return AllocationDecision(
                target_exposure=current_exposure,
                action="HOLD",
                reason=f"Change {delta:.4f} below rebalance threshold {self.rebalance_threshold}",
                sleeve_exposures=sleeve_exposures,
                blended_exposure=blended,
                approved=False,
                meta={"delta": delta},
            )

        if delta > 0:
            # BUY path — check all governors
            entry_ok, capped_exp, gov_reason = self.exp_gov.check_entry(
                intent=_dominant_intent(intents),
                current_nav=current_nav,
                current_exposure=current_exposure,
                regime=regime,
                drawdown_governor_allows=self.dd_gov.is_buy_allowed(),
            )
            if not entry_ok:
                return AllocationDecision(
                    target_exposure=current_exposure,
                    action="HOLD",
                    reason=f"Entry blocked by governor: {gov_reason}",
                    sleeve_exposures=sleeve_exposures,
                    blended_exposure=blended,
                    approved=False,
                    meta={"governor_reason": gov_reason},
                )
            return AllocationDecision(
                target_exposure=capped_exp,
                action="BUY",
                reason=f"Entry approved. {gov_reason}",
                sleeve_exposures=sleeve_exposures,
                blended_exposure=blended,
                approved=True,
                meta={"governor_reason": gov_reason},
            )

        else:
            # SELL path
            sell_ok, sell_reason = self.exp_gov.check_exit(
                _dominant_intent(intents), current_exposure, current_nav
            )
            return AllocationDecision(
                target_exposure=blended if sell_ok else current_exposure,
                action="SELL" if sell_ok else "HOLD",
                reason=sell_reason,
                sleeve_exposures=sleeve_exposures,
                blended_exposure=blended,
                approved=sell_ok,
            )


def _dominant_intent(intents: list[tuple[StrategyIntent, float]]) -> StrategyIntent:
    """Return the highest-weight intent for governor checks."""
    return max(intents, key=lambda x: x[1])[0]
