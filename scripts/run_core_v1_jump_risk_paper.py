#!/usr/bin/env python
"""Isolated Core v1 + Jump Risk paper candidate.

The candidate always runs the canonical Core v1 paper cycle against isolated
state and log paths. Jump Risk can be evaluated only through explicitly injected
probability inputs during local engineering. Its result is observation-only:
no order, fill, target exposure, NAV, or Core state mutation is permitted.

Production defaults intentionally target the DigitalOcean Linux runtime. Local
engineering must override them with temporary or repository-local paths. Path
validation is host-independent so Windows tests can still protect Linux paths.

The command-line flag remains fail-closed until a frozen scoring adapter,
deterministic replay, and runtime cadence gate exist. This prevents accidental
activation on the server before the complete input pipeline is approved.
"""

from __future__ import annotations

# Preserve direct-file execution; package imports use normal discovery.
if __package__ in (None, ""):
    try:
        from _checkout_bootstrap import bootstrap as _bootstrap_checkout
    except ModuleNotFoundError as _bootstrap_error:
        if _bootstrap_error.name != "_checkout_bootstrap":
            raise
        from scripts._checkout_bootstrap import bootstrap as _bootstrap_checkout
    _bootstrap_checkout(__file__)


import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent

from runtime.core_v1.jump_risk_overlay import (  # noqa: E402
    ProbabilityInput,
    decide_asset_scale,
)
from scripts.run_core_v1_paper_live import (  # noqa: E402
    STATE_VERSION,
    append_jsonl,
    run_cycle as run_legacy_core_cycle,
    utc_now,
)

INSTANCE_ID = "core_v1_jump_risk"
CANDIDATE_STATE_VERSION = "core_v1_jump_risk_shadow_runtime_v1"

PRODUCTION_CANDIDATE_PATHS = {
    "state_path": "/opt/itera/runtime/core_v1_jump_risk/state.json",
    "signals_log": "/opt/itera/logs/core_v1_jump_risk/signals.jsonl",
    "fills_log": "/opt/itera/logs/core_v1_jump_risk/fills.jsonl",
    "market_data_log": "/opt/itera/logs/core_v1_jump_risk/market_data.jsonl",
}

PROTECTED_LEGACY_PATHS = frozenset(
    {
        "/opt/itera/runtime/core_v1/state.json",
        "/opt/itera/logs/core_v1_signals.jsonl",
        "/opt/itera/logs/core_v1_fills.jsonl",
        "/opt/itera/logs/core_v1_market_data.jsonl",
    }
)

ProbabilityMap = Mapping[str, ProbabilityInput]
InjectedInputs = Mapping[str, ProbabilityMap | None]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Isolated Core v1 + Jump Risk paper candidate (shadow evaluation only)"
    )
    p.add_argument("--capital", type=float, default=float(os.getenv("CORE_V1_JR_CAPITAL", "100000")))
    p.add_argument("--poll", type=int, default=int(os.getenv("CORE_V1_JR_POLL_SECONDS", "3600")))
    p.add_argument("--max-cycles", type=int, default=None)
    p.add_argument(
        "--state-path",
        default=os.getenv("CORE_V1_JR_STATE_PATH", PRODUCTION_CANDIDATE_PATHS["state_path"]),
    )
    p.add_argument(
        "--signals-log",
        default=os.getenv("CORE_V1_JR_SIGNALS_LOG", PRODUCTION_CANDIDATE_PATHS["signals_log"]),
    )
    p.add_argument(
        "--fills-log",
        default=os.getenv("CORE_V1_JR_FILLS_LOG", PRODUCTION_CANDIDATE_PATHS["fills_log"]),
    )
    p.add_argument(
        "--market-data-log",
        default=os.getenv("CORE_V1_JR_MARKET_DATA_LOG", PRODUCTION_CANDIDATE_PATHS["market_data_log"]),
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
        help="Reserved for injected local shadow evaluation; CLI activation remains blocked.",
    )
    return p.parse_args(argv)


def _portable_path_key(value: str | os.PathLike[str]) -> str:
    """Normalize configured paths without applying host filesystem semantics."""
    raw = os.fspath(value).strip().replace("\\", "/")
    while "//" in raw:
        raw = raw.replace("//", "/")
    if len(raw) > 1:
        raw = raw.rstrip("/")
    return raw.casefold()


def validate_args(args: argparse.Namespace, *, injected_shadow_inputs: bool = False) -> None:
    if args.jump_risk_enabled and not injected_shadow_inputs:
        raise RuntimeError(
            "Jump Risk activation is not yet allowed without explicit injected shadow inputs. "
            "Complete the frozen scoring adapter, deterministic replay, and runtime cadence gates first."
        )

    protected = {_portable_path_key(path) for path in PROTECTED_LEGACY_PATHS}
    candidate_paths = {
        _portable_path_key(args.state_path),
        _portable_path_key(args.signals_log),
        _portable_path_key(args.fills_log),
        _portable_path_key(args.market_data_log),
    }
    overlap = sorted(protected & candidate_paths)
    if overlap:
        raise RuntimeError(f"Candidate runner path overlaps legacy Core v1: {overlap}")

    if len(candidate_paths) != 4:
        raise RuntimeError("Candidate state and log paths must be distinct")


def _replace_last_jsonl_record(path: Path, record: dict) -> None:
    """Replace the just-written candidate event while preserving prior JSONL rows."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    encoded = json.dumps(record, default=str, sort_keys=True)
    if lines:
        lines[-1] = encoded
    else:
        lines.append(encoded)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _decorate_shadow_event(
    event: dict,
    *,
    jump_risk_inputs: InjectedInputs,
    decision_at: datetime,
) -> dict:
    decorated_signals: list[dict] = []
    decisions: list[dict] = []

    for signal in event["signals"]:
        row = dict(signal)
        asset = str(row.get("asset", "")).upper()
        core_target = float(row.get("target_exposure", 0.0) or 0.0)

        if asset in {"BTC", "ETH"}:
            decision = decide_asset_scale(
                asset=asset,
                probabilities=jump_risk_inputs.get(asset),
                core_aligned=core_target > 0.0,
                decision_at=decision_at,
                enabled=True,
                paper_mode=True,
            )
            shadow = {
                **decision.to_dict(),
                "core_target_exposure": core_target,
                "shadow_scaled_target_exposure": min(1.0, core_target * decision.scale),
                "orders_mutated": False,
                "state_mutated": False,
                "nav_mutated": False,
            }
            row["jump_risk_shadow"] = shadow
            decisions.append({"sleeve": row.get("sleeve"), **shadow})

        decorated_signals.append(row)

    return {
        **event,
        "signals": decorated_signals,
        "candidate_instance": INSTANCE_ID,
        "candidate_state_version": CANDIDATE_STATE_VERSION,
        "legacy_engine_state_version": STATE_VERSION,
        "jump_risk_enabled": True,
        "jump_risk_mode": "INJECTED_SHADOW_ONLY",
        "jump_risk_decisions": decisions,
        "jump_risk_orders_mutated": False,
        "jump_risk_state_mutated": False,
        "jump_risk_nav_mutated": False,
    }


def run_cycle(
    args: argparse.Namespace,
    *,
    jump_risk_inputs: InjectedInputs | None = None,
    decision_at: datetime | None = None,
) -> dict:
    """Run canonical Core and optionally attach injected shadow decisions.

    With the feature disabled, this remains a thin delegation and preserves the
    byte-for-byte parity gate. With injected inputs enabled, Core executes first
    without any overlay influence; decisions are then attached to the candidate
    event and candidate signals log for observation and testing.
    """
    injected = args.jump_risk_enabled and jump_risk_inputs is not None
    validate_args(args, injected_shadow_inputs=injected)
    event = run_legacy_core_cycle(args)

    if not injected:
        return {
            **event,
            "candidate_instance": INSTANCE_ID,
            "candidate_state_version": CANDIDATE_STATE_VERSION,
            "legacy_engine_state_version": STATE_VERSION,
            "jump_risk_enabled": False,
            "jump_risk_mode": "PARITY_BASELINE_ONLY",
        }

    decorated = _decorate_shadow_event(
        event,
        jump_risk_inputs=jump_risk_inputs,
        decision_at=decision_at or utc_now(),
    )
    _replace_last_jsonl_record(Path(args.signals_log), decorated)
    return decorated


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
