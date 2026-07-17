from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_core_v1_jump_risk_paper import parse_args, validate_args


def test_candidate_defaults_are_isolated_from_legacy() -> None:
    args = parse_args([])

    assert args.state_path == "/opt/itera/runtime/core_v1_jump_risk/state.json"
    assert args.signals_log == "/opt/itera/logs/core_v1_jump_risk/signals.jsonl"
    assert args.fills_log == "/opt/itera/logs/core_v1_jump_risk/fills.jsonl"
    assert args.market_data_log == "/opt/itera/logs/core_v1_jump_risk/market_data.jsonl"
    assert args.jump_risk_enabled is False
    validate_args(args)


def test_jump_risk_activation_is_rejected_during_parity_phase() -> None:
    args = parse_args(["--jump-risk-enabled"])

    with pytest.raises(RuntimeError, match="activation is not yet allowed"):
        validate_args(args)


@pytest.mark.parametrize(
    "flag,legacy_path",
    [
        ("--state-path", "/opt/itera/runtime/core_v1/state.json"),
        ("--signals-log", "/opt/itera/logs/core_v1_signals.jsonl"),
        ("--fills-log", "/opt/itera/logs/core_v1_fills.jsonl"),
        ("--market-data-log", "/opt/itera/logs/core_v1_market_data.jsonl"),
    ],
)
def test_legacy_path_overlap_is_rejected(flag: str, legacy_path: str) -> None:
    args = parse_args([flag, legacy_path])

    with pytest.raises(RuntimeError, match="overlaps legacy Core v1"):
        validate_args(args)


def test_candidate_paths_must_be_distinct(tmp_path: Path) -> None:
    shared = str(tmp_path / "shared.jsonl")
    args = parse_args(["--signals-log", shared, "--fills-log", shared])

    with pytest.raises(RuntimeError, match="must be distinct"):
        validate_args(args)
