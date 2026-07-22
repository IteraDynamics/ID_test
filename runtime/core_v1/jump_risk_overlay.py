from __future__ import annotations

"""Deterministic, paper-only Jump Risk aligned-upside decision layer.

This module deliberately does not load data, train models, place orders, mutate
Core state, or calculate NAV. It converts already-computed frozen Jump Risk
probabilities plus canonical Core alignment into a fail-closed shadow scale.

The research-approved mapping is:
- medium-up OR extended-up probability at/above its active train-derived threshold,
- canonical Core direction aligned positively,
- all inputs fresh and structurally valid,
- output 1.15x; otherwise 1.00x.

It is suitable for local replay and later observation-only runtime wiring.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
import math
from typing import Any, Mapping

BASE_SCALE = 1.00
BOOST_SCALE = 1.15
RISK_QUANTILE = 0.95
MAX_INPUT_AGE_SECONDS = 2 * 60 * 60
SUPPORTED_ASSETS = frozenset({"BTC", "ETH"})
MODEL_NAMES = ("medium_up", "extended_up")


@dataclass(frozen=True)
class ProbabilityInput:
    probability: float
    threshold: float
    source_bar_ts: datetime
    computed_at: datetime


@dataclass(frozen=True)
class OverlayDecision:
    asset: str
    scale: float
    boosted: bool
    reason_code: str
    decision_at: datetime
    core_aligned: bool
    medium_up_active: bool
    extended_up_active: bool
    freshest_source_bar_ts: datetime | None
    stalest_input_age_seconds: float | None
    config_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _finite_probability(value: float) -> bool:
    return math.isfinite(value) and 0.0 <= value <= 1.0


def config_payload() -> dict[str, Any]:
    return {
        "mapping": "btc_eth_aligned_upside",
        "base_scale": BASE_SCALE,
        "boost_scale": BOOST_SCALE,
        "risk_quantile": RISK_QUANTILE,
        "models": list(MODEL_NAMES),
        "max_input_age_seconds": MAX_INPUT_AGE_SECONDS,
        "paper_only": True,
        "standalone_direction_prohibited": True,
    }


def config_fingerprint() -> str:
    payload = json.dumps(config_payload(), sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def _base_decision(
    *,
    asset: str,
    reason_code: str,
    decision_at: datetime,
    core_aligned: bool,
    medium_active: bool = False,
    extended_active: bool = False,
    freshest_source_bar_ts: datetime | None = None,
    stalest_input_age_seconds: float | None = None,
) -> OverlayDecision:
    return OverlayDecision(
        asset=asset,
        scale=BASE_SCALE,
        boosted=False,
        reason_code=reason_code,
        decision_at=decision_at,
        core_aligned=core_aligned,
        medium_up_active=medium_active,
        extended_up_active=extended_active,
        freshest_source_bar_ts=freshest_source_bar_ts,
        stalest_input_age_seconds=stalest_input_age_seconds,
        config_fingerprint=config_fingerprint(),
    )


def decide_asset_scale(
    *,
    asset: str,
    probabilities: Mapping[str, ProbabilityInput] | None,
    core_aligned: bool,
    decision_at: datetime | None = None,
    enabled: bool = False,
    paper_mode: bool = True,
    max_input_age_seconds: int = MAX_INPUT_AGE_SECONDS,
) -> OverlayDecision:
    """Return 1.00x or 1.15x without side effects.

    Fail-closed order is intentional and stable. The overlay cannot create a
    direction: ``core_aligned`` must already be true. ``enabled`` defaults to
    false so importing or wiring this module cannot alter behavior by accident.
    """

    now = _as_utc(decision_at or datetime.now(UTC))
    normalized_asset = str(asset).upper().strip()

    if normalized_asset not in SUPPORTED_ASSETS:
        return _base_decision(
            asset=normalized_asset,
            reason_code="UNSUPPORTED_ASSET",
            decision_at=now,
            core_aligned=core_aligned,
        )
    if not paper_mode:
        return _base_decision(
            asset=normalized_asset,
            reason_code="PAPER_ONLY_GUARD",
            decision_at=now,
            core_aligned=core_aligned,
        )
    if not enabled:
        return _base_decision(
            asset=normalized_asset,
            reason_code="FEATURE_DISABLED",
            decision_at=now,
            core_aligned=core_aligned,
        )
    if not core_aligned:
        return _base_decision(
            asset=normalized_asset,
            reason_code="CORE_NOT_ALIGNED",
            decision_at=now,
            core_aligned=False,
        )
    if probabilities is None:
        return _base_decision(
            asset=normalized_asset,
            reason_code="MISSING_INPUTS",
            decision_at=now,
            core_aligned=True,
        )

    missing = [name for name in MODEL_NAMES if name not in probabilities]
    if missing:
        return _base_decision(
            asset=normalized_asset,
            reason_code="MISSING_INPUTS",
            decision_at=now,
            core_aligned=True,
        )

    normalized: dict[str, ProbabilityInput] = {}
    ages: list[float] = []
    source_times: list[datetime] = []
    for name in MODEL_NAMES:
        item = probabilities[name]
        source_ts = _as_utc(item.source_bar_ts)
        computed_at = _as_utc(item.computed_at)
        normalized[name] = ProbabilityInput(
            probability=float(item.probability),
            threshold=float(item.threshold),
            source_bar_ts=source_ts,
            computed_at=computed_at,
        )
        if not _finite_probability(normalized[name].probability):
            return _base_decision(
                asset=normalized_asset,
                reason_code="INVALID_PROBABILITY",
                decision_at=now,
                core_aligned=True,
            )
        if not _finite_probability(normalized[name].threshold):
            return _base_decision(
                asset=normalized_asset,
                reason_code="INVALID_THRESHOLD",
                decision_at=now,
                core_aligned=True,
            )
        if computed_at > now or source_ts > computed_at:
            return _base_decision(
                asset=normalized_asset,
                reason_code="INVALID_TIMESTAMP_ORDER",
                decision_at=now,
                core_aligned=True,
            )
        age = (now - computed_at).total_seconds()
        ages.append(age)
        source_times.append(source_ts)

    stalest_age = max(ages)
    freshest_source = max(source_times)
    medium_active = normalized["medium_up"].probability >= normalized["medium_up"].threshold
    extended_active = normalized["extended_up"].probability >= normalized["extended_up"].threshold

    if stalest_age > float(max_input_age_seconds):
        return _base_decision(
            asset=normalized_asset,
            reason_code="STALE_INPUTS",
            decision_at=now,
            core_aligned=True,
            medium_active=medium_active,
            extended_active=extended_active,
            freshest_source_bar_ts=freshest_source,
            stalest_input_age_seconds=stalest_age,
        )

    active = medium_active or extended_active
    return OverlayDecision(
        asset=normalized_asset,
        scale=BOOST_SCALE if active else BASE_SCALE,
        boosted=active,
        reason_code="ALIGNED_UPSIDE_ACTIVE" if active else "BELOW_THRESHOLD",
        decision_at=now,
        core_aligned=True,
        medium_up_active=medium_active,
        extended_up_active=extended_active,
        freshest_source_bar_ts=freshest_source,
        stalest_input_age_seconds=stalest_age,
        config_fingerprint=config_fingerprint(),
    )
