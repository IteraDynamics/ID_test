#!/usr/bin/env python
"""Isolated Core v1 + Jump Risk paper-runner shell.

Phase-1 engineering objective:
- run a second paper instance without touching legacy Core v1 state or logs,
- execute the exact legacy Core cycle while Jump Risk remains disabled,
- establish a clean parity baseline before model scoring or overlay scaling is wired.

This script intentionally refuses ``--jump-risk-enabled`` until the frozen
scoring adapter and replay/parity gates are implemented. That prevents the
candidate instance from drifting ahead of the engineering acceptance sequence.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_core_v1_paper_live import (  # noqa: E402
    STATE_VERSION,
    append_jsonl,
    run_cycle as run_legacy_core_cycle,
    utc_now,
)

INSTANCE_ID = "core_v1_jump_risk"
CANDIDATE_STATE_VERSION = "core_v1_jump_risk_paper_shell_v1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Isolated Core v1 + Jump Risk paper candidate (Jump Risk disabled during parity phase)"
    )
    p.add_argument("--capital", type=float, default=float(os.getenv("CORE_V1_JR_CAPITAL", "100000")))
    p.add_argument("--poll", type=int, default=int(os.getenv("CORE_V1_JR_POLL_SECONDS", "3600")))
    p.add_argument("--max-cycles", type=int, default=None)
    p.add_argument(
        "--state-path",
        default=os.getenv("CORE_V1_JR_STATE_PATH", "/opt/itera/runtime/core_v1_jump_risk/state.json"),
    )
    p.add_argument(
        "--signals-log",
        default=os.getenv("CORE_V1_JR_SIGNALS_LOG", "/opt/itera/logs/core_v1_jump_risk/signals.jsonl"),
    )
    p.add_argument(
        "--fills-log",
        default=os.getenv("CORE_V1_JR_FILLS_LOG", "/opt/itera/logs/core_v1_jump_risk/fills.jsonl"),
    )
    p.add_argument(
        "--market-data-log",
        default=os.getenv("CORE_V1_JR_MARKET_DATA_LOG", "/opt/itera/logs/core_v1_jump_risk/market_data.jsonl"),
    )
    p.add_argument("--data-dir", default=os.getenv("DATA_DIR", "data"))
    p.add_argument("--crypto-days", type=int, default=int(os.getenv("CORE_V1_CRYPTO_DAYS", "420")))
    p.add_argument("--etf-days", type=int, default=int(os.getenv("CORE_V1_ETF_DAYS", "520")))
    p.add_argument("--fee", type=float, default=float(os.getenv("FEE_RATE", "0.0006")))
    p.add_argument("--equity-fee", type=float, default=float(os.getenv("EQUITY_FEE_RATE", "0.0001")))
    p.add_argument(
        "--crypto-slippage-bps",
        type=float,
        default=float(os.getenv("CORE_V1_CRYPTO_SLIPPAGE_BPS", "3.0")),
    )
    p.add_argument(
        "--equity-slippage-bps",
        type=float,
        default=float(os.getenv("CORE_V1_EQUITY_SLIPPAGE_BPS", "0.5")),
    )
    p.add_argument(
        "--rebalance-threshold",
        type=float,
        default=float(os.getenv("REBALANCE_THRESHOLD", "0.02")),
    )
    p.add_argument(
        "--max-etf-bar-age-hours",
        type=float,
        default=float(os.getenv("CORE_V1_MAX_ETF_BAR_AGE_HOURS", "96")),
    )
    p.add_argument(
        "--max-crypto-bar-age-hours",
        type=float,
        default=float(os.getenv("CORE_V1_MAX_CRYPTO_BAR_AGE_HOURS", "6")),
    )
    p.add_argument("--allow-stale-local-fallback", action="store_true")
    p.add_argument(
        "--jump-risk-enabled",
        action="store_true",
        help="Reserved for the later frozen-overlay phase; currently rejected fail-closed.",
    )
    return p.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    if args.jump_risk_enabled:
        raise RuntimeError(
            "Jump Risk activation is not yet allowed. Complete scoring adapter, deterministic replay, "
            "baseline parity, and runtime cadence gates first."
        )

    legacy_defaults = {
        "/opt/itera/runtime/core_v1/state.json",
        "/opt/itera/logs/core_v1_signals.jsonl",
        "/opt/itera/logs/core_v1_fills.jsonl",
        "/opt/itera/logs/core_v1_market_data.jsonl",
    }
    candidate_paths = {
        str(Path(args.state_path)),
        str(Path(args.signals_log)),
        str(Path(args.fills_log)),
        str(Path(args.market_data_log)),
    }
    overlap = sorted(legacy_defaults & candidate_paths)
    if overlap:
        raise RuntimeError(f"Candidate runner path overlaps legacy Core v1: {overlap}")

    if len(candidate_paths) != 4:
        raise RuntimeError("Candidate state and log paths must be distinct")


def run_cycle(args: argparse.Namespace) -> dict:
    """Run the exact legacy Core cycle against isolated candidate paths.

    During parity phase this is deliberately a thin delegation. Any mismatch
    therefore points to state initialization, market-data timing, or environment,
    not duplicated strategy logic.
    """
    validate_args(args)
    event = run_legacy_core_cycle(args)
    return {
        **event,
        "candidate_instance": INSTANCE_ID,
        "candidate_state_version": CANDIDATE_STATE_VERSION,
        "legacy_engine_state_version": STATE_VERSION,
        "jump_risk_enabled": False,
        "jump_risk_mode": "PARITY_BASELINE_ONLY",
    }


def main() -> None:
    args = parse_args()
    validate_args(args)
    cycles = 0

    while True:
        try:
            event = run_cycle(args)
            print(
                f"{event['timestamp']} Core v1 + Jump Risk candidate "
                f"cycle={event['cycle']} NAV=${event['total_nav']:,.2f} "
                f"DD={event['drawdown_frac']:.2%} today={event['today_pnl']:+,.2f} "
                f"fills={len(event['fills'])} mode={event['jump_risk_mode']}",
                flush=True,
            )
        except Exception as exc:
            err = {
                "timestamp": utc_now().isoformat(),
                "error": str(exc),
                "version": CANDIDATE_STATE_VERSION,
                "instance": INSTANCE_ID,
            }
            error_path = Path(args.signals_log).with_name("errors.jsonl")
            append_jsonl(error_path, err)
            print(f"ERROR Core v1 + Jump Risk candidate cycle failed: {exc}", file=sys.stderr, flush=True)
            raise

        cycles += 1
        if args.max_cycles is not None and cycles >= args.max_cycles:
            break
        time.sleep(args.poll)


if __name__ == "__main__":
    main()
