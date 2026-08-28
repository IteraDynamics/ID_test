from __future__ import annotations

from datetime import date, timedelta

from scripts.run_campaign50_development_validation import (
    DEVELOPMENT,
    VALIDATION,
    _classify_stages,
    stage_anchor_indices,
)


def test_stage_anchors_keep_forward_window_inside_development() -> None:
    sessions = [date(2018, 1, 2) + timedelta(days=i) for i in range(2200)]
    anchors = stage_anchor_indices(
        sessions,
        start=DEVELOPMENT[0],
        end=DEVELOPMENT[1],
        horizon=60,
    )
    assert anchors
    assert all(sessions[index + 60] <= DEVELOPMENT[1] for index in anchors)
    assert all(right - left == 60 for left, right in zip(anchors, anchors[1:]))


def test_stage_anchors_keep_forward_window_inside_validation() -> None:
    sessions = [date(2018, 1, 2) + timedelta(days=i) for i in range(2600)]
    anchors = stage_anchor_indices(
        sessions,
        start=VALIDATION[0],
        end=VALIDATION[1],
        horizon=20,
    )
    assert anchors
    assert all(VALIDATION[0] <= sessions[index] <= VALIDATION[1] for index in anchors)
    assert all(sessions[index + 20] <= VALIDATION[1] for index in anchors)


def _row(key: str, *, status: str, beta1: float, holm_p: float, sign: bool = True) -> dict[str, object]:
    predictor, target, horizon_text = key.split("__")
    return {
        "candidate_key": key,
        "predictor": predictor,
        "target": target,
        "horizon": int(horizon_text.rsplit("_", 1)[1]),
        "expected_sign": 1,
        "status": status,
        "rankable": True,
        "n": 100,
        "event_n": None,
        "non_event_n": None,
        "beta0": 0.0,
        "beta1": beta1,
        "se_beta1": 0.1,
        "t_stat": beta1 / 0.1,
        "raw_p": holm_p / 24,
        "holm_p": holm_p,
        "ci_low": beta1 - 0.2,
        "ci_high": beta1 + 0.2,
        "sign_matches": sign,
        "development_compatibility_matches": None,
    }


def test_shortlist_requires_discovery_validation_and_compatibility() -> None:
    key = "breadth50__SPY__fwd_return_20"
    development = [_row(key, status="", beta1=1.0, holm_p=0.01)]
    validation = [_row(key, status="", beta1=0.5, holm_p=0.05)]
    development, validation, shortlist = _classify_stages(development, validation)
    assert development[0]["status"] == "DISCOVERY_SUPPORTED"
    assert validation[0]["status"] == "VALIDATION_SUPPORTED"
    assert len(shortlist) == 1
    assert shortlist[0]["confirmation_authorized"] is False


def test_validation_is_not_eligible_without_discovery_support() -> None:
    key = "breadth50__QQQ__fwd_return_5"
    development = [_row(key, status="", beta1=1.0, holm_p=0.20)]
    validation = [_row(key, status="", beta1=1.0, holm_p=0.01)]
    development, validation, shortlist = _classify_stages(development, validation)
    assert development[0]["status"] == "DISCOVERY_NOT_SUPPORTED"
    assert validation[0]["status"] == "VALIDATION_NOT_ELIGIBLE"
    assert shortlist == []
