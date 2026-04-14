"""Exposure governor — enforces hard caps on portfolio and per-strategy exposure.

Rules enforced:
1. Portfolio gross exposure cannot exceed ``max_portfolio_exposure``.
2. Any single strategy's exposure cannot exceed ``max_strategy_exposure``.
3. Minimum trade notional: orders below threshold are suppressed.
4. If regime is UNKNOWN and we have no position, block new entries (fail-closed).

These rules are applied AFTER governors are consulted and BEFORE broker submission.
"""

from __future__ import annotations

import logging
import os

from research.regimes.contracts import RegimeLabel
from research.strategies.contracts import Action, StrategyIntent

log = logging.getLogger(__name__)

DEFAULT_MAX_PORTFOLIO_EXPOSURE = float(os.getenv("MAX_PORTFOLIO_EXPOSURE_FRAC", "1.0"))
DEFAULT_MAX_STRATEGY_EXPOSURE = float(os.getenv("MAX_SINGLE_STRATEGY_EXPOSURE_FRAC", "1.0"))
DEFAULT_MIN_NOTIONAL = float(os.getenv("MIN_TRADE_NOTIONAL_USD", "50.0"))


class ExposureGovernor:
    """Enforces exposure limits and minimum notional constraints.

    Parameters
    ----------
    max_portfolio_exposure : float
        Hard cap on total portfolio exposure [0, 1].
    max_strategy_exposure : float
        Hard cap on any single strategy exposure [0, 1].
    min_trade_notional : float
        Minimum trade notional in USD.  Orders below this are suppressed.
    """

    def __init__(
        self,
        max_portfolio_exposure: float = DEFAULT_MAX_PORTFOLIO_EXPOSURE,
        max_strategy_exposure: float = DEFAULT_MAX_STRATEGY_EXPOSURE,
        min_trade_notional: float = DEFAULT_MIN_NOTIONAL,
    ) -> None:
        self.max_portfolio_exposure = max_portfolio_exposure
        self.max_strategy_exposure = max_strategy_exposure
        self.min_trade_notional = min_trade_notional

    def check_entry(
        self,
        intent: StrategyIntent,
        current_nav: float,
        current_exposure: float,
        regime: RegimeLabel,
        drawdown_governor_allows: bool,
    ) -> tuple[bool, float, str]:
        """Evaluate an ENTER_LONG intent against all exposure rules.

        Parameters
        ----------
        intent :
            The strategy's intent.
        current_nav :
            Current portfolio NAV in USD.
        current_exposure :
            Current portfolio exposure fraction [0, 1].
        regime :
            Current regime label.
        drawdown_governor_allows :
            Output of DrawdownGovernor.is_buy_allowed().

        Returns
        -------
        (allowed, capped_exposure, reason)
            allowed : bool
            capped_exposure : float — the allowed exposure after caps.
            reason : str — human-readable explanation.
        """
        # ── Fail-closed on uncertain regime ────────────────────────────
        if regime == RegimeLabel.UNKNOWN and current_exposure == 0.0:
            return False, 0.0, "Regime UNKNOWN — blocking new entry (fail-closed)"

        # ── Drawdown halt ───────────────────────────────────────────────
        if not drawdown_governor_allows:
            return False, 0.0, "DrawdownGovernor halt active — new buys blocked"

        # ── Low confidence ──────────────────────────────────────────────
        if intent.confidence < 0.35:
            return False, 0.0, f"Intent confidence too low: {intent.confidence:.2f} < 0.35"

        # ── Cap exposure ────────────────────────────────────────────────
        desired = intent.desired_exposure_frac
        capped = min(desired, self.max_strategy_exposure, self.max_portfolio_exposure)

        # Check if the increase in exposure meets minimum notional
        delta_exposure = max(0.0, capped - current_exposure)
        delta_notional = delta_exposure * current_nav
        if delta_notional < self.min_trade_notional and delta_exposure > 1e-6:
            return (
                False,
                current_exposure,
                f"Delta notional ${delta_notional:.2f} below minimum ${self.min_trade_notional:.2f}",
            )

        if capped < desired:
            log.debug(
                "ExposureGovernor: exposure capped %.4f → %.4f", desired, capped
            )

        return True, capped, f"Exposure approved at {capped:.4f}"

    def check_exit(
        self,
        intent: StrategyIntent,
        current_exposure: float,
        current_nav: float,
    ) -> tuple[bool, str]:
        """Check a SELL / EXIT intent.

        Exits are always allowed unless the position is already flat.

        Returns
        -------
        (allowed, reason)
        """
        if current_exposure <= 1e-6:
            return False, "Already flat — exit not needed"
        notional = current_exposure * current_nav
        if notional < self.min_trade_notional:
            return False, f"Position notional ${notional:.2f} below min ${self.min_trade_notional:.2f}"
        return True, "Exit approved"
