from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_core_v1_jump_risk_paper import (
    PRODUCTION_CANDIDATE_PATHS,
    parse_args,
    validate_args,
)


def test_production_defaults_target_isolated_server_paths() -> None:
    args = parse_args([])

    assert args.state_path == PRODUCTION_CANDIDATE_PATHS["state_path"]
    assert args.signals_log == PRODUCTION_CANDIDATE_PATHS["signals_log"]
    assert args.fills_log == PRODUCTION_CANDIDATE_PATHS["fills_log"]
    assert args.market_data_log == PRODUCTION_CANDIDATE_PATHS["market_data_log"]
    assert args.jump_risk_enabled is False
    validate_args(args)


def test_local_overrides_validate_with_temporary_paths(tmp_path: Path) -> None:
    root = tmp_path / "core_v1_jump_risk"
    args = parse_args(
        [
            "--state-path",
            str(root / "state.json"),
            "--signals-log",
            str(root / "signals.jsonl"),
            "--fills-log",
            str(root / "fills.jsonl"),
            "--market-data-log",
            str(root / "market_data.jsonl"),
        ]
    )

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
def test_legacy_path_overlap_is_rejected_on_any_host(flag: str, legacy_path: str) -> None:
    args = parse_args([flag, legacy_path])

    with pytest.raises(RuntimeError, match="overlaps legacy Core v1"):
        validate_args(args)


@pytest.mark.parametrize(
    "flag,legacy_path",
    [
        ("--state-path", r"\opt\itera\runtime\core_v1\state.json"),
        ("--signals-log", r"\opt\itera\logs\core_v1_signals.jsonl"),
        ("--fills-log", r"\opt\itera\logs\core_v1_fills.jsonl"),
        ("--market-data-log", r"\opt\itera\logs\core_v1_market_data.jsonl"),
    ],
)
def test_windows_rendering_of_legacy_path_is_also_rejected(flag: str, legacy_path: str) -> None:
    args = parse_args([flag, legacy_path])

    with pytest.raises(RuntimeError, match="overlaps legacy Core v1"):
        validate_args(args)


def test_candidate_paths_must_be_distinct(tmp_path: Path) -> None:
    shared = str(tmp_path / "shared.jsonl")
    args = parse_args(["--signals-log", shared, "--fills-log", shared])

    with pytest.raises(RuntimeError, match="must be distinct"):
        validate_args(args)
