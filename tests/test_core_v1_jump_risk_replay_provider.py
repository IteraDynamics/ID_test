from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import hashlib
import json

import pytest

from runtime.core_v1.jump_risk_overlay import decide_asset_scale
from runtime.core_v1.jump_risk_replay_provider import ReplayProbabilityProvider


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _row(ts: datetime, *, active: bool) -> dict:
    source = ts - timedelta(hours=1)
    probability = 0.90 if active else 0.20
    return {
        "decision_at": ts.isoformat(),
        "source_bar_ts": source.isoformat(),
        "medium_up_probability": probability,
        "medium_up_threshold": 0.80,
        "extended_up_probability": 0.30,
        "extended_up_threshold": 0.85,
        "scale": 1.15 if active else 1.0,
        "boosted": active,
        "reason_code": "ALIGNED_UPSIDE_ACTIVE" if active else "BELOW_THRESHOLD",
    }


def _report() -> dict:
    start = datetime(2025, 1, 1, 1, tzinfo=UTC)
    assets = {}
    for asset, active_second in (("BTC", True), ("ETH", False)):
        rows = [_row(start, active=False), _row(start + timedelta(hours=1), active=active_second)]
        assets[asset] = {
            "asset": asset,
            "rows": len(rows),
            "decision_digest": _digest(rows),
            "decisions": rows,
        }
    return {
        "version": "core_v1_jump_risk_replay_v1",
        "replay_digest": "synthetic",
        "overlay_config_fingerprint": "test",
        "assets": assets,
    }


def test_exact_timestamp_lookup_returns_exact_score() -> None:
    provider = ReplayProbabilityProvider(_report())
    at = datetime(2025, 1, 1, 2, tzinfo=UTC)
    lookup = provider.lookup("BTC", at)

    assert lookup.reason_code == "SCORE_FOUND"
    assert lookup.score_decision_at == at
    assert lookup.probabilities is not None
    assert lookup.probabilities["medium_up"].probability == pytest.approx(0.90)


def test_between_bar_lookup_returns_latest_eligible_score() -> None:
    provider = ReplayProbabilityProvider(_report())
    requested = datetime(2025, 1, 1, 2, 30, tzinfo=UTC)
    lookup = provider.lookup("BTC", requested)

    assert lookup.score_decision_at == datetime(2025, 1, 1, 2, tzinfo=UTC)
    assert lookup.score_decision_at <= requested


def test_pre_history_lookup_fails_closed() -> None:
    provider = ReplayProbabilityProvider(_report())
    requested = datetime(2025, 1, 1, 0, 59, tzinfo=UTC)

    assert provider.get("BTC", requested) is None
    assert provider.lookup("BTC", requested).reason_code == "NO_SCORE_AS_OF_TIME"


def test_assets_are_independent() -> None:
    provider = ReplayProbabilityProvider(_report())
    at = datetime(2025, 1, 1, 2, tzinfo=UTC)

    btc = decide_asset_scale(
        asset="BTC",
        probabilities=provider.get("BTC", at),
        core_aligned=True,
        decision_at=at,
        enabled=True,
        paper_mode=True,
    )
    eth = decide_asset_scale(
        asset="ETH",
        probabilities=provider.get("ETH", at),
        core_aligned=True,
        decision_at=at,
        enabled=True,
        paper_mode=True,
    )

    assert btc.boosted is True
    assert eth.boosted is False


def test_stale_asof_score_is_rejected_by_overlay() -> None:
    provider = ReplayProbabilityProvider(_report())
    requested = datetime(2025, 1, 1, 5, 0, 1, tzinfo=UTC)
    decision = decide_asset_scale(
        asset="BTC",
        probabilities=provider.get("BTC", requested),
        core_aligned=True,
        decision_at=requested,
        enabled=True,
        paper_mode=True,
    )

    assert decision.scale == 1.0
    assert decision.reason_code == "STALE_INPUTS"


def test_repeated_lookups_are_deterministic() -> None:
    provider = ReplayProbabilityProvider(_report())
    requested = datetime(2025, 1, 1, 2, 45, tzinfo=UTC)

    assert provider.lookup_digest("BTC", requested) == provider.lookup_digest("BTC", requested)
    assert provider.lookup("BTC", requested).to_dict() == provider.lookup("BTC", requested).to_dict()


def test_digest_tampering_is_rejected() -> None:
    report = deepcopy(_report())
    report["assets"]["BTC"]["decisions"][0]["medium_up_probability"] = 0.99

    with pytest.raises(ValueError, match="digest mismatch"):
        ReplayProbabilityProvider(report)


def test_future_or_duplicate_rows_are_rejected() -> None:
    report = _report()
    report["assets"]["BTC"]["decisions"][1]["decision_at"] = report["assets"]["BTC"]["decisions"][0]["decision_at"]
    report["assets"]["BTC"]["decision_digest"] = _digest(report["assets"]["BTC"]["decisions"])

    with pytest.raises(ValueError, match="unique and increasing"):
        ReplayProbabilityProvider(report)


def test_missing_digest_fails_closed_by_default() -> None:
    """Absent integrity evidence must not read as passing evidence."""
    report = deepcopy(_report())
    del report["assets"]["BTC"]["decision_digest"]
    with pytest.raises(ValueError, match="no decision_digest"):
        ReplayProbabilityProvider(report)


def test_missing_digest_allowed_only_by_explicit_opt_out() -> None:
    report = deepcopy(_report())
    del report["assets"]["BTC"]["decision_digest"]
    provider = ReplayProbabilityProvider(report, require_digests=False)
    assert provider.version == "core_v1_jump_risk_replay_v1"


def test_config_fingerprint_tracks_the_effective_freshness_bound() -> None:
    from runtime.core_v1.jump_risk_overlay import config_fingerprint

    assert config_fingerprint(7200) != config_fingerprint(3600)
