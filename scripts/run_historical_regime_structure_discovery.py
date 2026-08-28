"""CLI for deterministic Campaign #47 regime-structure discovery."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.ml.validation.historical_regime_structure_discovery import (  # noqa: E402
    SourcePaths,
    generate,
    preflight,
)


def default_paths(repo_root: Path) -> SourcePaths:
    source_root = repo_root / "artifacts" / "full_historical_regime_state_sequence"
    return SourcePaths(
        manifest=source_root / "btc_hourly_regime_state_manifest.json",
        states=source_root / "btc_hourly_regime_state_sequence.csv",
        runs=source_root / "btc_hourly_regime_state_runs.csv",
        transitions=source_root / "btc_hourly_regime_transitions.csv",
        btc=repo_root / "data" / "btcusd_3600s_2018-01-01_to_2025-12-31.csv",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/historical_regime_structure"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = default_paths(REPO_ROOT)
    if args.preflight_only:
        payload = preflight(paths)
    else:
        output = args.output
        if not output.is_absolute():
            output = REPO_ROOT / output
        payload = generate(paths, output)
    print(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
