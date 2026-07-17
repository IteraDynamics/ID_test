from __future__ import annotations

from pathlib import Path

from scripts.run_core_v1_jump_risk_parity import run_parity_gate


def test_candidate_shell_matches_legacy_core_byte_for_byte(tmp_path: Path) -> None:
    result = run_parity_gate(tmp_path)

    assert result["status"] == "PASS"
    assert result["checks"] == {
        "event": True,
        "state": True,
        "signals_log": True,
        "fills_log": True,
        "market_data_log": True,
    }
    assert result["legacy_nav"] == result["candidate_nav"]
    assert result["legacy_fills"] == result["candidate_fills"]
    assert result["jump_risk_enabled"] is False
    assert result["jump_risk_mode"] == "PARITY_BASELINE_ONLY"
