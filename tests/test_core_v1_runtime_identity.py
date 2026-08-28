"""Runtime-side of dashboard-redesign Phase 0 item 1.

The paper runtime records which git branch / commit / host produced a state,
for the dashboard's provenance strip. This must NOT go inside ``state.json``
(that file is byte-for-byte compared by the replay / parity gates) — it is a
sidecar, ``core_v1_runtime_identity.json``.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

import scripts.run_core_v1_paper_live as legacy
from scripts.run_core_v1_jump_risk_parity import FIXED_NOW, _args, frozen_market_snapshot


def _run_cycle(root: Path):
    snapshot, provenance = frozen_market_snapshot()

    def loader(_args):
        return copy.deepcopy(snapshot), copy.deepcopy(provenance)

    with patch.object(legacy, "load_market_data", side_effect=loader), patch.object(
        legacy, "utc_now", return_value=FIXED_NOW
    ):
        legacy.run_cycle(_args(root, is_candidate=False))
    return root / "legacy"


def test_runtime_identity_is_a_sidecar_not_a_state_field(tmp_path):
    out = _run_cycle(tmp_path)

    state = json.loads((out / "state.json").read_text())
    assert "runtime_identity" not in state, "identity must not pollute the replay-compared state.json"

    sidecar = out / "core_v1_runtime_identity.json"
    assert sidecar.exists()
    identity = json.loads(sidecar.read_text())
    assert identity["git_branch"]
    assert identity["git_commit_short"]
    assert identity["hostname"]
    assert identity["runtime_entrypoint"] == "scripts/run_core_v1_paper_live.py"
    assert identity["state_path"].endswith("state.json")
    assert identity["recorded_at"] == FIXED_NOW.isoformat()


def test_state_json_is_byte_identical_across_runs_at_different_paths(tmp_path):
    """The canary: two cycles run under different directories must still
    produce identical state.json bytes — proving the identity sidecar (whose
    contents DO vary by path) never leaks into it."""
    a = _run_cycle(tmp_path / "a")
    b = _run_cycle(tmp_path / "b")
    assert (a / "state.json").read_bytes() == (b / "state.json").read_bytes()
    # ...and the sidecars legitimately differ (different resolved state_path)
    assert (a / "core_v1_runtime_identity.json").read_bytes() != (b / "core_v1_runtime_identity.json").read_bytes()
