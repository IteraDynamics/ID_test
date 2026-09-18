"""Offline-only RRE Core v1 exposure-increase deferral adapter.

Pure intervention logic. It does not execute trades, calculate P&L, modify Core,
or fit/tune the frozen instability model.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from research.harness.campaign52_target_replay import TargetRecord
from research.strategies.contracts import Action

ELIGIBLE_SLEEVES = frozenset({"BTC_4H_trend", "ETH_1H_trend", "ETH_4H_trend"})
FROZEN_MODEL_HORIZON_DAYS = 7
FROZEN_QUANTILE = 0.80


class RREEntryDeferralError(ValueError):
    """Fail-closed specification violation."""


@dataclass(frozen=True)
class InstabilityScore:
    timestamp: pd.Timestamp
    probability: float | None
    training_cutoff: pd.Timestamp
    model_horizon_days: int = FROZEN_MODEL_HORIZON_DAYS


@dataclass(frozen=True)
class DeferralDecision:
    timestamp: pd.Timestamp
    fold: str
    sleeve: str
    core_label: str
    canonical_action: str
    pre_decision_exposure: float
    canonical_target: float
    instability_probability: float | None
    training_q80: float | None
    intervention_eligible: bool
    deferred: bool
    experimental_target: float
    reason_code: str


def training_q80(probabilities: Iterable[float]) -> float:
    """Frozen q80 cutoff from finite matured training predictions only."""
    values = np.asarray(list(probabilities), dtype=float)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise RREEntryDeferralError("TRAINING_SCORE_SET_INVALID")
    if np.any((values < 0.0) | (values > 1.0)):
        raise RREEntryDeferralError("TRAINING_SCORE_OUT_OF_RANGE")
    return float(np.quantile(values, FROZEN_QUANTILE, method="linear"))


def _finite_exposure(value: float, code: str) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise RREEntryDeferralError(code)
    return value


def decide_deferral(
    *,
    record: TargetRecord,
    pre_decision_exposure: float,
    core_label: str,
    score: InstabilityScore | None,
    q80: float | None,
) -> DeferralDecision:
    """Apply the frozen veto to one canonical target.

    Invalid/unavailable RRE information fails closed to canonical Core behavior.
    Structural violations in target/exposure semantics raise fail-closed errors.
    """
    ts = pd.Timestamp(record.timestamp)
    pre = _finite_exposure(pre_decision_exposure, "PRE_EXPOSURE_NONFINITE")
    canonical = _finite_exposure(record.signed_target_exposure, "CANONICAL_TARGET_NONFINITE")
    try:
        action = Action(record.action)
    except ValueError as exc:
        raise RREEntryDeferralError(f"CANONICAL_ACTION_INVALID:{record.action}") from exc

    eligible_sleeve = record.sleeve_label in ELIGIBLE_SLEEVES
    exposure_increase = action == Action.ENTER_LONG and canonical > pre
    structurally_eligible = eligible_sleeve and exposure_increase

    probability: float | None = None
    if not structurally_eligible:
        reason = "NON_ELIGIBLE_SLEEVE" if not eligible_sleeve else "NON_INCREASE_ACTION"
        return DeferralDecision(ts, record.fold, record.sleeve_label, str(core_label), record.action,
                                pre, canonical, None, q80, False, False, canonical, reason)

    if score is None or q80 is None:
        return DeferralDecision(ts, record.fold, record.sleeve_label, str(core_label), record.action,
                                pre, canonical, None, q80, True, False, canonical, "RRE_UNAVAILABLE_CANONICAL")

    if pd.Timestamp(score.timestamp) != ts:
        raise RREEntryDeferralError("SCORE_TIMESTAMP_MISMATCH")
    if score.model_horizon_days != FROZEN_MODEL_HORIZON_DAYS:
        raise RREEntryDeferralError("MODEL_HORIZON_DRIFT")
    if pd.Timestamp(score.training_cutoff) > ts:
        raise RREEntryDeferralError("FUTURE_TRAINING_CUTOFF")

    if score.probability is None:
        return DeferralDecision(ts, record.fold, record.sleeve_label, str(core_label), record.action,
                                pre, canonical, None, q80, True, False, canonical, "RRE_UNAVAILABLE_CANONICAL")
    probability = float(score.probability)
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        return DeferralDecision(ts, record.fold, record.sleeve_label, str(core_label), record.action,
                                pre, canonical, probability, q80, True, False, canonical, "RRE_INVALID_CANONICAL")

    cutoff = float(q80)
    if not math.isfinite(cutoff) or not 0.0 <= cutoff <= 1.0:
        return DeferralDecision(ts, record.fold, record.sleeve_label, str(core_label), record.action,
                                pre, canonical, probability, q80, True, False, canonical, "Q80_INVALID_CANONICAL")

    deferred = probability >= cutoff
    experimental = pre if deferred else canonical
    if experimental > canonical + 1e-12:
        raise RREEntryDeferralError("EXPERIMENTAL_TARGET_EXCEEDS_CANONICAL")
    return DeferralDecision(
        ts, record.fold, record.sleeve_label, str(core_label), record.action, pre, canonical,
        probability, cutoff, True, deferred, experimental,
        "DEFER_Q80" if deferred else "ALLOW_BELOW_Q80",
    )


def decisions_to_targets(
    records: Sequence[TargetRecord],
    decisions: Sequence[DeferralDecision],
) -> list[TargetRecord]:
    """Create replay targets without mutating canonical records."""
    if len(records) != len(decisions):
        raise RREEntryDeferralError("DECISION_COUNT_MISMATCH")
    out: list[TargetRecord] = []
    for record, decision in zip(records, decisions, strict=True):
        if pd.Timestamp(record.timestamp) != pd.Timestamp(decision.timestamp):
            raise RREEntryDeferralError("DECISION_TIMESTAMP_MISMATCH")
        if record.fold != decision.fold or record.sleeve_label != decision.sleeve:
            raise RREEntryDeferralError("DECISION_IDENTITY_MISMATCH")
        if decision.experimental_target > record.signed_target_exposure + 1e-12 and record.action == Action.ENTER_LONG.value:
            raise RREEntryDeferralError("EXPERIMENTAL_TARGET_EXCEEDS_CANONICAL")
        out.append(TargetRecord(
            stage=record.stage, fold=record.fold, timestamp=record.timestamp,
            sleeve_label=record.sleeve_label, asset=record.asset,
            native_timeframe=record.native_timeframe, strategy_id=record.strategy_id,
            action=record.action, desired_exposure_frac=record.desired_exposure_frac,
            signed_target_exposure=float(decision.experimental_target),
            sequence_number=record.sequence_number,
        ))
    return out
