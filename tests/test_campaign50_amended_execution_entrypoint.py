from __future__ import annotations

import json

from scripts.run_campaign50_development_validation_amended import (
    FRESH_EXECUTION_GO_COMMIT,
    SUPPORT_GATE_AMENDMENT_COMMIT,
    _amend_governance_metadata,
)


def test_amended_entrypoint_records_fresh_go_and_support_amendment() -> None:
    artifacts = {
        "campaign50_preflight.json": b'{"execution_go_commit_sha":"old"}\n',
        "campaign50_stage_manifest.json": b'{"execution_go_commit_sha":"old"}\n',
    }
    amended = _amend_governance_metadata(artifacts)
    for name in artifacts:
        payload = json.loads(amended[name].decode("utf-8"))
        assert payload["execution_go_commit_sha"] == FRESH_EXECUTION_GO_COMMIT
        assert payload["support_gate_amendment_commit_sha"] == SUPPORT_GATE_AMENDMENT_COMMIT
        assert payload["support_gate_amendment_applied"] is True
        assert payload["amended_development_minimum_total_support"] == {
            "5": 180,
            "20": 50,
            "60": 16,
        }
