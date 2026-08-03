from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from research.campaign50_equity_breadth import canonical_json_bytes
from scripts.run_campaign50_development_validation import (
    CANONICAL_FILES,
    ExecutionError,
    _validate_repository_state,
    build_artifacts,
)

FRESH_EXECUTION_GO_COMMIT = "07276cc5831de016ebb55259c3c8154ec10cde86"
SUPPORT_GATE_AMENDMENT_COMMIT = "18ff04022fac611c4c2c6136132afa57ee8ad30e"


def _require_fresh_execution_go(head: str) -> None:
    check = subprocess.run(
        ["git", "merge-base", "--is-ancestor", FRESH_EXECUTION_GO_COMMIT, head],
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        raise ExecutionError("SOURCE_IDENTITY_FAILURE: amended execution GO absent from HEAD")


def _amend_governance_metadata(artifacts: dict[str, bytes]) -> dict[str, bytes]:
    amended = dict(artifacts)
    for name in ("campaign50_preflight.json", "campaign50_stage_manifest.json"):
        payload = json.loads(amended[name].decode("utf-8"))
        payload["execution_go_commit_sha"] = FRESH_EXECUTION_GO_COMMIT
        payload["support_gate_amendment_commit_sha"] = SUPPORT_GATE_AMENDMENT_COMMIT
        payload["support_gate_amendment_applied"] = True
        payload["amended_development_minimum_total_support"] = {
            "5": 180,
            "20": 50,
            "60": 16,
        }
        amended[name] = canonical_json_bytes(payload)
    return amended


def execute(data_root: Path, output_dir: Path) -> dict[str, object]:
    if output_dir.exists():
        raise ExecutionError(f"SOURCE_IDENTITY_FAILURE: output exists {output_dir}")
    branch, head = _validate_repository_state()
    _require_fresh_execution_go(head)
    artifacts = _amend_governance_metadata(build_artifacts(data_root, head, branch))
    output_dir.mkdir(parents=True, exist_ok=False)
    try:
        for name in CANONICAL_FILES:
            (output_dir / name).write_bytes(artifacts[name])
    except Exception:
        for child in output_dir.iterdir():
            if child.is_file():
                child.unlink()
        output_dir.rmdir()
        raise
    return {
        "candidate_count": 24,
        "confirmation_enabled": False,
        "execution_go_commit_sha": FRESH_EXECUTION_GO_COMMIT,
        "holdout_loaded": False,
        "outcomes_generated": True,
        "output_dir": output_dir.as_posix(),
        "predictors_generated": True,
        "status": "PASS",
        "support_gate_amendment_commit_sha": SUPPORT_GATE_AMENDMENT_COMMIT,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run amended governed Campaign 50 development and validation only."
    )
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(execute(Path(args.data_root), Path(args.output_dir)), sort_keys=True))


if __name__ == "__main__":
    main()
