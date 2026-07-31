from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.campaign50_equity_breadth import (
    BREADTH_MEMBERS,
    TARGETS,
    Campaign50Error,
    candidate_inventory,
    canonical_json_bytes,
    load_close_series,
)
from scripts.reconcile_campaign50_equity_sessions import (
    EXPECTED_SHA256,
    build_reconciliation,
)


def build_preflight(data_root: Path) -> dict[str, object]:
    reconciliation = build_reconciliation(data_root)
    if reconciliation["target_calendar_session_count"] != 2010:
        raise Campaign50Error("SOURCE_ORDER_FAILURE: unexpected target calendar")
    if reconciliation["all_source_common_session_count"] != 2010:
        raise Campaign50Error("SOURCE_ORDER_FAILURE: incomplete common calendar")

    holdout_rejection: dict[str, str] = {}
    for symbol in (*TARGETS, *BREADTH_MEMBERS):
        filename = f"{symbol}_1D.csv"
        try:
            load_close_series(
                data_root / filename,
                expected_sha256=EXPECTED_SHA256[filename],
            )
        except Campaign50Error as exc:
            message = str(exc)
            if not message.startswith("HOLDOUT_ACCESS_VIOLATION:"):
                raise
            holdout_rejection[filename] = "PASS"
        else:
            raise Campaign50Error(
                f"HOLDOUT_ACCESS_VIOLATION: discovery loader accepted full source {filename}"
            )

    inventory = candidate_inventory()
    if len(inventory) != 24 or len({candidate.key for candidate in inventory}) != 24:
        raise Campaign50Error("SOURCE_SCHEMA_FAILURE: candidate inventory mismatch")

    return {
        "preflight_type": "campaign50_source_only_implementation",
        "status": "PASS",
        "predictors_generated": False,
        "outcomes_generated": False,
        "coefficients_generated": False,
        "holdout_loaded_into_analytical_structures": False,
        "target_calendar_session_count": 2010,
        "all_source_common_session_count": 2010,
        "candidate_count": 24,
        "discovery_cutoff": "2024-12-31",
        "confirmation_enabled": False,
        "holdout_rejection": holdout_rejection,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Campaign 50 source-only implementation preflight. This command "
            "does not construct predictors, outcomes, coefficients, or shortlist results."
        )
    )
    parser.add_argument("--data-root", default="data")
    parser.add_argument(
        "--output",
        default="artifacts/campaign50_implementation_preflight.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_preflight(Path(args.data_root))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json_bytes(result))
    print(
        json.dumps(
            {
                "candidate_count": result["candidate_count"],
                "confirmation_enabled": False,
                "outcomes_generated": False,
                "output": output.as_posix(),
                "predictors_generated": False,
                "status": result["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
