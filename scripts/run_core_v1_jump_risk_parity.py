#!/usr/bin/env python
"""Deterministic local parity gate for legacy Core v1 and the candidate shell.

This harness never contacts live data providers and never uses production paths.
It generates one frozen synthetic market snapshot, fixes runtime time, executes the
legacy runner and the Jump Risk candidate shell independently, then compares the
underlying Core event, state, and append-only logs byte-for-byte.

Jump Risk remains disabled. A PASS proves that the isolated candidate shell adds
no behavioral drift before scoring or overlay integration begins.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import scripts.run_core_v1_paper_live as legacy  # noqa: E402
import scripts.run_core_v1_jump_risk_paper as candidate  # noqa: E402

FIXED_NOW = datetime(2025, 12, 31, 12, 0, 0, tzinfo=UTC)
CANDIDATE_ONLY_KEYS = {
    "candidate_instance",
    "candidate_state_version",
    "legacy_engine_state_version",
    "jump_risk_enabled",
    "jump_risk_mode",
}


def _ohlcv(index: pd.DatetimeIndex, start: float, drift: float, amplitude: float) -> pd.DataFrame:
    closes = [start + drift * i + amplitude * math.sin(i / 37.0) for i in range(len(index))]
    opens = [closes[0], *closes[:-1]]
    highs = [max(o, c) * 1.002 for o, c in zip(opens, closes, strict=True)]
    lows = [min(o, c) * 0.998 for o, c in zip(opens, closes, strict=True)]
    volumes = [1000.0 + float(i % 97) for i in range(len(index))]
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=index,
    )


def frozen_market_snapshot() -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, object]]]:
    hourly_index = pd.date_range(end="2025-12-31 10:00:00", periods=9000, freq="1h")
    daily_index = pd.date_range(end="2025-12-30", periods=600, freq="1D")
    data = {
        "BTC": _ohlcv(hourly_index, 30000.0, 4.0, 450.0),
        "ETH": _ohlcv(hourly_index, 1800.0, 0.25, 45.0),
        "SPY": _ohlcv(daily_index, 350.0, 0.22, 4.0),
        "QQQ": _ohlcv(daily_index, 280.0, 0.28, 5.0),
        "GLD": _ohlcv(daily_index, 170.0, 0.08, 2.0),
        "BIL": _ohlcv(daily_index, 91.0, 0.002, 0.03),
    }
    provenance = {asset: {"source": "deterministic_parity_fixture", "fallback": False} for asset in data}
    return data, provenance


def _args(root: Path, *, is_candidate: bool) -> argparse.Namespace:
    prefix = "candidate" if is_candidate else "legacy"
    argv = [
        "--capital", "100000",
        "--max-cycles", "1",
        "--state-path", str(root / prefix / "state.json"),
        "--signals-log", str(root / prefix / "signals.jsonl"),
        "--fills-log", str(root / prefix / "fills.jsonl"),
        "--market-data-log", str(root / prefix / "market_data.jsonl"),
        "--data-dir", str(root / "unused_data"),
    ]
    if is_candidate:
        return candidate.parse_args(argv)

    # The legacy CLI predates injectable argv support and reads sys.argv
    # directly. Patch it only while constructing the deterministic local
    # Namespace; no process-level arguments leak into or out of the harness.
    with patch.object(sys, "argv", ["run_core_v1_paper_live.py", *argv]):
        return legacy.parse_args()


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes() if path.exists() else b""


def _core_candidate_event(event: dict) -> dict:
    return {key: value for key, value in event.items() if key not in CANDIDATE_ONLY_KEYS}


def run_parity_gate(work_root: Path) -> dict[str, object]:
    snapshot, provenance = frozen_market_snapshot()

    def loader(_args: argparse.Namespace):
        return copy.deepcopy(snapshot), copy.deepcopy(provenance)

    legacy_args = _args(work_root, is_candidate=False)
    candidate_args = _args(work_root, is_candidate=True)

    with patch.object(legacy, "load_market_data", side_effect=loader), patch.object(
        legacy, "utc_now", return_value=FIXED_NOW
    ):
        legacy_event = legacy.run_cycle(legacy_args)
        candidate_event = candidate.run_cycle(candidate_args)

    checks = {
        "event": legacy_event == _core_candidate_event(candidate_event),
        "state": _read_bytes(Path(legacy_args.state_path)) == _read_bytes(Path(candidate_args.state_path)),
        "signals_log": _read_bytes(Path(legacy_args.signals_log)) == _read_bytes(Path(candidate_args.signals_log)),
        "fills_log": _read_bytes(Path(legacy_args.fills_log)) == _read_bytes(Path(candidate_args.fills_log)),
        "market_data_log": _read_bytes(Path(legacy_args.market_data_log))
        == _read_bytes(Path(candidate_args.market_data_log)),
    }
    passed = all(checks.values())
    result = {
        "status": "PASS" if passed else "FAIL",
        "fixed_now": FIXED_NOW.isoformat(),
        "checks": checks,
        "legacy_nav": legacy_event["total_nav"],
        "candidate_nav": candidate_event["total_nav"],
        "legacy_fills": len(legacy_event["fills"]),
        "candidate_fills": len(candidate_event["fills"]),
        "jump_risk_enabled": candidate_event["jump_risk_enabled"],
        "jump_risk_mode": candidate_event["jump_risk_mode"],
    }
    if not passed:
        raise RuntimeError("Core v1 candidate parity gate failed: " + json.dumps(result, sort_keys=True))
    return result


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="itera_core_v1_parity_") as temp_dir:
        result = run_parity_gate(Path(temp_dir))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
