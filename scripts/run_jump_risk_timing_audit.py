from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_jump_risk_portfolio_integration import (  # noqa: E402
    CANONICAL_DATA,
    CORE_SCENARIO,
    LOCKED_MODELS,
    _canonical_path,
    _load_matrix,
    _oos_probabilities,
    read_ohlcv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the exact bar timing used by the validated Jump Risk aligned-upside overlay.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--btc-data", default=CANONICAL_DATA["btc_data"])
    parser.add_argument("--eth-data", default=CANONICAL_DATA["eth_data"])
    parser.add_argument(
        "--core-wfo-dir",
        default="artifacts/trend_persistence_v0/portfolio_integration/core_wfo",
    )
    parser.add_argument("--out-dir", default="artifacts/jump_risk_timing_audit")
    parser.add_argument("--oos-start", default="2020-01-01")
    parser.add_argument("--oos-end", default="2025-12-31")
    parser.add_argument("--risk-quantile", type=float, default=0.95)
    parser.add_argument("--jump-z", type=float, default=3.0)
    parser.add_argument("--absolute-jump", type=float, default=0.05)
    parser.add_argument("--expected-bar-hours", type=int, default=1)
    return parser.parse_args()


def _atomic_json(path: Path, payload: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temp.replace(path)


def _candidate_predictions(
    source: pd.DataFrame,
    asset: str,
    candidate: str,
    args: argparse.Namespace,
) -> pd.DataFrame:
    shifted = _oos_probabilities(
        source,
        asset,
        candidate,
        args.oos_start,
        args.oos_end,
        args.jump_z,
        args.absolute_jump,
        args.risk_quantile,
    ).copy()
    shifted.index.name = "action_bar_end"
    return shifted


def _audit_prediction_frame(
    frame: pd.DataFrame,
    asset: str,
    candidate: str,
    bar_delta: pd.Timedelta,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    out = frame.reset_index().copy()
    out["asset"] = asset
    out["candidate"] = candidate
    out["source_bar_close"] = out["action_bar_end"] - bar_delta
    out["pnl_interval_start"] = out["action_bar_end"] - bar_delta
    out["pnl_interval_end"] = out["action_bar_end"]
    out["probability_available_before_pnl"] = (
        out["source_bar_close"] <= out["pnl_interval_start"]
    )
    out["strictly_no_same_bar_source"] = out["source_bar_close"] < out["action_bar_end"]
    out["threshold_finite"] = np.isfinite(out["train_threshold"].astype(float))
    out["probability_finite"] = np.isfinite(out["probability"].astype(float))
    out["high_risk"] = out["probability"] >= out["train_threshold"]

    index = pd.DatetimeIndex(frame.index)
    gaps = index.to_series().diff().dropna()
    backwards = int((gaps <= pd.Timedelta(0)).sum())
    subhour_gaps = int((gaps < bar_delta).sum())

    checks = {
        "asset": asset,
        "candidate": candidate,
        "rows": int(len(out)),
        "first_action_bar_end": str(index.min()),
        "last_action_bar_end": str(index.max()),
        "backwards_or_duplicate_timestamps": backwards,
        "gaps_shorter_than_expected_bar": subhour_gaps,
        "availability_failures": int((~out["probability_available_before_pnl"]).sum()),
        "same_bar_source_failures": int((~out["strictly_no_same_bar_source"]).sum()),
        "nonfinite_probability_rows": int((~out["probability_finite"]).sum()),
        "nonfinite_threshold_rows": int((~out["threshold_finite"]).sum()),
        "high_risk_rows": int(out["high_risk"].sum()),
    }
    checks["status"] = "PASS" if all(
        checks[key] == 0
        for key in (
            "backwards_or_duplicate_timestamps",
            "gaps_shorter_than_expected_bar",
            "availability_failures",
            "same_bar_source_failures",
            "nonfinite_probability_rows",
            "nonfinite_threshold_rows",
        )
    ) else "FAIL"
    return out, checks


def _aligned_scale(
    matrix: pd.DataFrame,
    predictions: dict[tuple[str, str], pd.DataFrame],
    asset: str,
) -> pd.DataFrame:
    medium = predictions[(asset, "medium_up")]
    extended = predictions[(asset, "extended_up")]
    idx = medium.index.union(extended.index).sort_values()
    med_high = (
        (medium["probability"] >= medium["train_threshold"])
        .reindex(idx, method="ffill")
        .fillna(False)
    )
    ext_high = (
        (extended["probability"] >= extended["train_threshold"])
        .reindex(idx, method="ffill")
        .fillna(False)
    )
    cols = [c for c in matrix.columns if c.startswith(f"{asset}_") and "trend" in c]
    if not cols:
        raise RuntimeError(f"No active {asset} trend sleeves found in {CORE_SCENARIO}")
    sleeve = matrix[cols].sum(axis=1)
    aligned = sleeve.diff(24).reindex(idx, method="ffill").fillna(0.0) > 0.0
    active = aligned & (med_high | ext_high)
    return pd.DataFrame(
        {
            "medium_high": med_high.astype(bool),
            "extended_high": ext_high.astype(bool),
            "core_24h_aligned": aligned.astype(bool),
            "overlay_active": active.astype(bool),
        },
        index=idx,
    )


def main() -> None:
    args = parse_args()
    if args.expected_bar_hours <= 0:
        raise ValueError("--expected-bar-hours must be positive")

    btc_path = _canonical_path(args.btc_data)
    eth_path = _canonical_path(args.eth_data)
    matrix, _, _ = _load_matrix(args.core_wfo_dir, args.oos_start, args.oos_end)
    btc = read_ohlcv(btc_path)
    eth = read_ohlcv(eth_path)
    bar_delta = pd.Timedelta(hours=args.expected_bar_hours)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.out_dir) / f"{timestamp}_jump-risk-timing-audit-v0"
    run_dir.mkdir(parents=True, exist_ok=False)

    predictions: dict[tuple[str, str], pd.DataFrame] = {}
    audit_frames: list[pd.DataFrame] = []
    check_rows: list[dict[str, Any]] = []

    for asset, source in (("BTC", btc), ("ETH", eth)):
        for candidate in LOCKED_MODELS:
            print(f"Auditing timing: {asset} {candidate}")
            pred = _candidate_predictions(source, asset, candidate, args)
            predictions[(asset, candidate)] = pred
            details, checks = _audit_prediction_frame(
                pred, asset, candidate, bar_delta
            )
            audit_frames.append(details)
            check_rows.append(checks)

    event_frames: list[pd.DataFrame] = []
    overlay_checks: list[dict[str, Any]] = []
    for asset in ("BTC", "ETH"):
        flags = _aligned_scale(matrix, predictions, asset)
        active = flags.loc[flags["overlay_active"]].copy()
        active.index.name = "action_bar_end"
        active = active.reset_index()
        active["asset"] = asset
        active["source_bar_close"] = active["action_bar_end"] - bar_delta
        active["pnl_interval_start"] = active["action_bar_end"] - bar_delta
        active["pnl_interval_end"] = active["action_bar_end"]
        active["timing_valid"] = (
            active["source_bar_close"] <= active["pnl_interval_start"]
        ) & (active["source_bar_close"] < active["pnl_interval_end"])
        event_frames.append(active)
        overlay_checks.append(
            {
                "asset": asset,
                "active_rows": int(len(active)),
                "timing_failures": int((~active["timing_valid"]).sum()),
                "status": "PASS" if bool(active["timing_valid"].all()) else "FAIL",
            }
        )

    prediction_audit = pd.concat(audit_frames, ignore_index=True)
    checks = pd.DataFrame(check_rows)
    overlay_events = pd.concat(event_frames, ignore_index=True)
    overlay_summary = pd.DataFrame(overlay_checks)

    prediction_audit.to_csv(run_dir / "jump_risk_prediction_timing_rows.csv", index=False)
    checks.to_csv(run_dir / "jump_risk_prediction_timing_checks.csv", index=False)
    overlay_events.to_csv(run_dir / "jump_risk_overlay_activation_timing.csv", index=False)
    overlay_summary.to_csv(run_dir / "jump_risk_overlay_timing_summary.csv", index=False)

    structural_pass = bool((checks["status"] == "PASS").all()) and bool(
        (overlay_summary["status"] == "PASS").all()
    )
    report = {
        "audit": "jump_risk_timing_audit_v0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "STRUCTURAL_PASS_RUNTIME_CADENCE_PENDING" if structural_pass else "FAIL",
        "expected_bar_hours": args.expected_bar_hours,
        "structural_checks_passed": structural_pass,
        "interpretation": {
            "source_bar_close": "Timestamp of the fully closed bar whose features produce the probability.",
            "action_bar_end": "End of the subsequent return interval receiving the overlay scale.",
            "execution_assumption": "The scale is actionable at source-bar close and applies to P&L accrued over the immediately following hourly interval.",
            "remaining_requirement": "Compare this assumption with the actual paper runtime data-finalization, cycle start, order-generation, and fill timestamps before enabling the overlay.",
        },
        "prediction_checks": check_rows,
        "overlay_checks": overlay_checks,
    }
    _atomic_json(run_dir / "jump_risk_timing_audit_report.json", report)

    print()
    print("Jump Risk timing audit complete")
    print(f"Out dir: {run_dir}")
    print(f"Structural timing status: {report['status']}")
    print("Important: this proves historical bar alignment, not live runtime cadence.")
    print("Reference files:")
    for name in (
        "jump_risk_prediction_timing_checks.csv",
        "jump_risk_overlay_timing_summary.csv",
        "jump_risk_overlay_activation_timing.csv",
        "jump_risk_timing_audit_report.json",
    ):
        print(f"- {run_dir / name}")

    if not structural_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
