#!/usr/bin/env python
"""Deterministic historical replay gate for the frozen Jump Risk overlay.

This command rebuilds the locked medium-up and extended-up out-of-sample
probabilities from canonical BTC/ETH hourly bars, converts them into the
paper-only overlay contract, and writes a deterministic audit report.

It does not place orders, mutate Core state, or calculate candidate NAV.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from runtime.core_v1.jump_risk_overlay import ProbabilityInput, config_fingerprint, decide_asset_scale  # noqa: E402
from scripts.run_jump_risk_portfolio_integration import (  # noqa: E402
    CANONICAL_DATA,
    _oos_probabilities,
    read_ohlcv,
)

ASSETS = ("BTC", "ETH")
MODEL_NAMES = ("medium_up", "extended_up")
REPLAY_VERSION = "core_v1_jump_risk_replay_v1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Replay frozen Jump Risk probabilities against historical bars")
    p.add_argument("--btc-data", default=CANONICAL_DATA["btc_data"])
    p.add_argument("--eth-data", default=CANONICAL_DATA["eth_data"])
    p.add_argument("--oos-start", default="2020-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--risk-quantile", type=float, default=0.95)
    p.add_argument("--jump-z", type=float, default=3.0)
    p.add_argument("--absolute-jump", type=float, default=0.05)
    p.add_argument("--out", default="artifacts/jump_risk_portfolio_v0/core_v1_jump_risk_replay.json")
    return p.parse_args(argv)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _as_utc(ts: pd.Timestamp | datetime) -> datetime:
    value = pd.Timestamp(ts)
    if value.tzinfo is None:
        value = value.tz_localize(UTC)
    else:
        value = value.tz_convert(UTC)
    return value.to_pydatetime()


def _score_asset(
    *,
    asset: str,
    ohlcv: pd.DataFrame,
    oos_start: str,
    oos_end: str,
    jump_z: float,
    absolute_jump: float,
    risk_quantile: float,
    scorer: Callable[..., pd.DataFrame] = _oos_probabilities,
) -> pd.DataFrame:
    frames: dict[str, pd.DataFrame] = {}
    for model_name in MODEL_NAMES:
        scored = scorer(
            ohlcv,
            asset,
            model_name,
            oos_start,
            oos_end,
            jump_z,
            absolute_jump,
            risk_quantile,
        )[["probability", "train_threshold"]].copy()
        scored.columns = [f"{model_name}_probability", f"{model_name}_threshold"]
        frames[model_name] = scored
    merged = frames["medium_up"].join(frames["extended_up"], how="inner").dropna().sort_index()
    if merged.empty:
        raise RuntimeError(f"No overlapping frozen probabilities for {asset}")
    if not merged.index.is_monotonic_increasing or merged.index.has_duplicates:
        raise RuntimeError(f"Non-canonical replay index for {asset}")
    return merged


def replay_asset(asset: str, scored: pd.DataFrame) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    boosts = 0

    for ts, row in scored.iterrows():
        decision_at = _as_utc(ts)
        source_bar_ts = decision_at - timedelta(hours=1)
        inputs = {
            model_name: ProbabilityInput(
                probability=float(row[f"{model_name}_probability"]),
                threshold=float(row[f"{model_name}_threshold"]),
                source_bar_ts=source_bar_ts,
                computed_at=decision_at,
            )
            for model_name in MODEL_NAMES
        }
        decision = decide_asset_scale(
            asset=asset,
            probabilities=inputs,
            core_aligned=True,
            decision_at=decision_at,
            enabled=True,
            paper_mode=True,
        )
        if decision.decision_at < max(item.computed_at for item in inputs.values()):
            raise RuntimeError(f"Future-computed input detected for {asset} at {decision_at.isoformat()}")
        if any(item.source_bar_ts >= decision.decision_at for item in inputs.values()):
            raise RuntimeError(f"Non-historical source bar detected for {asset} at {decision_at.isoformat()}")

        reasons[decision.reason_code] += 1
        boosts += int(decision.boosted)
        rows.append(
            {
                "decision_at": decision_at.isoformat(),
                "source_bar_ts": source_bar_ts.isoformat(),
                "medium_up_probability": inputs["medium_up"].probability,
                "medium_up_threshold": inputs["medium_up"].threshold,
                "extended_up_probability": inputs["extended_up"].probability,
                "extended_up_threshold": inputs["extended_up"].threshold,
                "scale": decision.scale,
                "boosted": decision.boosted,
                "reason_code": decision.reason_code,
            }
        )

    digest = _sha256_bytes(_canonical_json(rows))
    return {
        "asset": asset,
        "rows": len(rows),
        "first_decision_at": rows[0]["decision_at"],
        "last_decision_at": rows[-1]["decision_at"],
        "boost_count": boosts,
        "boost_fraction": boosts / len(rows),
        "reason_counts": dict(sorted(reasons.items())),
        "decision_digest": digest,
        "decisions": rows,
    }


def build_replay_report(args: argparse.Namespace) -> dict[str, Any]:
    data_paths = {"BTC": Path(args.btc_data), "ETH": Path(args.eth_data)}
    reports: dict[str, Any] = {}
    for asset in ASSETS:
        path = data_paths[asset]
        if not path.exists():
            raise FileNotFoundError(f"Missing canonical input: {path}")
        ohlcv = read_ohlcv(path)
        scored = _score_asset(
            asset=asset,
            ohlcv=ohlcv,
            oos_start=args.oos_start,
            oos_end=args.oos_end,
            jump_z=args.jump_z,
            absolute_jump=args.absolute_jump,
            risk_quantile=args.risk_quantile,
        )
        reports[asset] = replay_asset(asset, scored)

    summary = {
        asset: {key: value for key, value in report.items() if key != "decisions"}
        for asset, report in reports.items()
    }
    report = {
        "version": REPLAY_VERSION,
        "overlay_config_fingerprint": config_fingerprint(),
        "parameters": {
            "oos_start": args.oos_start,
            "oos_end": args.oos_end,
            "risk_quantile": args.risk_quantile,
            "jump_z": args.jump_z,
            "absolute_jump": args.absolute_jump,
        },
        "guards": {
            "orders_mutated": False,
            "state_mutated": False,
            "nav_mutated": False,
            "future_bar_leakage_detected": False,
        },
        "assets": reports,
        "summary": summary,
    }
    report["replay_digest"] = _sha256_bytes(_canonical_json({"parameters": report["parameters"], "assets": summary}))
    return report


def main() -> None:
    args = parse_args()
    report = build_replay_report(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": "PASS", "out": str(out), "replay_digest": report["replay_digest"], "summary": report["summary"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
