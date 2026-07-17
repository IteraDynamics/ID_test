from __future__ import annotations

import copy
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import scripts.run_core_v1_jump_risk_paper as candidate
import scripts.run_core_v1_paper_live as legacy
from runtime.core_v1.jump_risk_overlay import BOOST_SCALE, ProbabilityInput
from scripts.run_core_v1_jump_risk_parity import FIXED_NOW, frozen_market_snapshot


def _args(root: Path, *, enabled: bool) -> object:
    argv = [
        "--capital", "100000",
        "--max-cycles", "1",
        "--state-path", str(root / "state.json"),
        "--signals-log", str(root / "signals.jsonl"),
        "--fills-log", str(root / "fills.jsonl"),
        "--market-data-log", str(root / "market_data.jsonl"),
        "--data-dir", str(root / "unused_data"),
    ]
    if enabled:
        argv.append("--jump-risk-enabled")
    return candidate.parse_args(argv)


def _probabilities(probability: float = 0.99):
    return {
        "medium_up": ProbabilityInput(
            probability=probability,
            threshold=0.95,
            source_bar_ts=FIXED_NOW - timedelta(hours=1),
            computed_at=FIXED_NOW - timedelta(minutes=2),
        ),
        "extended_up": ProbabilityInput(
            probability=0.20,
            threshold=0.95,
            source_bar_ts=FIXED_NOW - timedelta(hours=1),
            computed_at=FIXED_NOW - timedelta(minutes=2),
        ),
    }


def _run(args, *, inputs=None):
    snapshot, provenance = frozen_market_snapshot()

    def loader(_args):
        return copy.deepcopy(snapshot), copy.deepcopy(provenance)

    with patch.object(legacy, "load_market_data", side_effect=loader), patch.object(
        legacy, "utc_now", return_value=FIXED_NOW
    ):
        return candidate.run_cycle(
            args,
            jump_risk_inputs=inputs,
            decision_at=FIXED_NOW,
        )


def test_shadow_decoration_reports_active_boost_without_mutation_flags() -> None:
    event = {
        "signals": [
            {"sleeve": "btc_test", "asset": "BTC", "target_exposure": 0.50},
            {"sleeve": "spy_test", "asset": "SPY", "target_exposure": 1.00},
        ]
    }
    decorated = candidate._decorate_shadow_event(
        event,
        jump_risk_inputs={"BTC": _probabilities()},
        decision_at=FIXED_NOW,
    )

    shadow = decorated["signals"][0]["jump_risk_shadow"]
    assert shadow["scale"] == BOOST_SCALE
    assert shadow["shadow_scaled_target_exposure"] == 0.575
    assert shadow["orders_mutated"] is False
    assert shadow["state_mutated"] is False
    assert shadow["nav_mutated"] is False
    assert "jump_risk_shadow" not in decorated["signals"][1]


def test_missing_inputs_fail_closed_in_shadow_metadata() -> None:
    event = {"signals": [{"sleeve": "eth_test", "asset": "ETH", "target_exposure": 0.50}]}
    decorated = candidate._decorate_shadow_event(
        event,
        jump_risk_inputs={"ETH": None},
        decision_at=FIXED_NOW,
    )

    shadow = decorated["signals"][0]["jump_risk_shadow"]
    assert shadow["scale"] == 1.0
    assert shadow["reason_code"] == "MISSING_INPUTS"
    assert shadow["shadow_scaled_target_exposure"] == 0.50


def test_injected_shadow_cycle_does_not_change_core_state_fills_or_nav(tmp_path: Path) -> None:
    baseline_root = tmp_path / "baseline"
    shadow_root = tmp_path / "shadow"
    baseline = _run(_args(baseline_root, enabled=False))
    shadow = _run(
        _args(shadow_root, enabled=True),
        inputs={"BTC": _probabilities(), "ETH": _probabilities()},
    )

    assert shadow["jump_risk_mode"] == "INJECTED_SHADOW_ONLY"
    assert shadow["jump_risk_orders_mutated"] is False
    assert shadow["jump_risk_state_mutated"] is False
    assert shadow["jump_risk_nav_mutated"] is False
    assert shadow["total_nav"] == baseline["total_nav"]
    assert shadow["fills"] == baseline["fills"]
    assert (shadow_root / "state.json").read_bytes() == (baseline_root / "state.json").read_bytes()
    assert (shadow_root / "fills.jsonl").read_bytes() == (baseline_root / "fills.jsonl").read_bytes()
    assert shadow["jump_risk_decisions"]


def test_candidate_signals_log_persists_shadow_metadata(tmp_path: Path) -> None:
    root = tmp_path / "candidate"
    event = _run(
        _args(root, enabled=True),
        inputs={"BTC": _probabilities(), "ETH": _probabilities(0.50)},
    )

    rows = (root / "signals.jsonl").read_text(encoding="utf-8").splitlines()
    persisted = json.loads(rows[-1])
    assert persisted["jump_risk_mode"] == "INJECTED_SHADOW_ONLY"
    assert persisted["jump_risk_decisions"] == json.loads(json.dumps(event["jump_risk_decisions"], default=str))
