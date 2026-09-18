"""Offline strategy wrapper for the frozen RRE entry/add-on deferral experiment."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from research.rre_entry_deferral import ELIGIBLE_SLEEVES
from research.strategies.contracts import Action, StrategyIntent


@dataclass
class RREDeferralStrategy:
    canonical_strategy: Any
    sleeve_label: str
    score_series: pd.Series
    q80: float
    audit: list[dict] = field(default_factory=list)

    @property
    def STRATEGY_ID(self) -> str:
        return getattr(self.canonical_strategy, "STRATEGY_ID", "unknown")

    def generate_intent(self, df: pd.DataFrame, ctx: Any, closed_only: bool = True) -> StrategyIntent:
        intent = self.canonical_strategy.generate_intent(df, ctx, closed_only=closed_only)
        ts = pd.Timestamp(df.index[-1])
        current = float(ctx.current_exposure_frac)
        requested = float(intent.desired_exposure_frac)
        eligible = (
            self.sleeve_label in ELIGIBLE_SLEEVES
            and intent.action == Action.ENTER_LONG
            and requested > current
        )
        p = None
        if eligible and len(self.score_series):
            loc = self.score_series.index.searchsorted(ts, side="right") - 1
            if loc >= 0:
                value = self.score_series.iloc[loc]
                if pd.notna(value):
                    p = float(value)
        deferred = bool(eligible and p is not None and p >= self.q80)
        if eligible:
            self.audit.append({
                "timestamp": ts,
                "sleeve": self.sleeve_label,
                "core_label": getattr(ctx.regime, "value", str(ctx.regime)),
                "canonical_action": intent.action.value,
                "pre_decision_exposure": current,
                "canonical_requested_target": requested,
                "instability_probability": p,
                "training_q80": float(self.q80),
                "intervention_eligible": True,
                "deferred": deferred,
                "experimental_target": current if deferred else requested,
                "reason_code": "DEFER_Q80" if deferred else ("ALLOW_BELOW_Q80" if p is not None else "RRE_UNAVAILABLE_CANONICAL"),
            })
        if not deferred:
            return intent
        # HOLD exactly preserves the experimental arm's current exposure. No pending state.
        return StrategyIntent(
            action=Action.HOLD,
            desired_exposure_frac=current,
            confidence=intent.confidence,
            horizon_hours=intent.horizon_hours,
            reason=f"rre_defer_q80:{intent.reason}",
            strategy_id=intent.strategy_id,
            meta={**intent.meta, "rre_deferred": True, "canonical_action": intent.action.value},
        )
