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
    _oos_probabilities_unshifted,
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


def _unshifted_predictions(
    source: pd.DataFrame,
    asset: str,
    candidate: str,
    args: argparse.Namespace,
) -> pd.DataFrame:
    """Pre-shift pipeline output, indexed by the bar that produced each value."""
    raw = _oos_probabilities_unshifted(
        source,
        asset,
        candidate,
        args.oos_start,
        args.oos_end,
        args.jump_z,
        args.absolute_jump,
        args.risk_quantile,
    ).copy()
    raw.index.name = "source_bar_close"
    return raw


def verify_shift_provenance(
    served: pd.DataFrame,
    unshifted: pd.DataFrame,
) -> tuple[pd.Series, int]:
    """Prove each served probability came from a strictly earlier source bar.

    ``unshifted`` is indexed by the bar whose own features produced each value;
    ``served`` is what the strategy consumes. For every served row at bar ``T``
    the value must equal the unshifted value at the immediately preceding row.
    A removed, doubled, reversed, or misaligned shift fails this comparison, as
    does any series whose values do not originate from the model pipeline at all.

    Returns the per-row source-bar timestamps (NaT where provenance failed) and
    the failure count.
    """
    expected = unshifted["probability"].shift(1)
    expected_source = pd.Series(unshifted.index, index=unshifted.index).shift(1)

    aligned_expected = expected.reindex(served.index)
    aligned_source = expected_source.reindex(served.index)

    served_values = served["probability"].astype(float).to_numpy()
    expected_values = aligned_expected.astype(float).to_numpy()
    matches = np.isclose(served_values, expected_values, rtol=0.0, atol=1e-12, equal_nan=False)

    source_bars = pd.Series(
        np.where(matches, aligned_source.to_numpy(), np.datetime64("NaT")),
        index=served.index,
    )
    return source_bars, int((~matches).sum())


def _audit_prediction_frame(
    frame: pd.DataFrame,
    asset: str,
    candidate: str,
    bar_delta: pd.Timedelta,
    unshifted: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    out = frame.reset_index().copy()
    out["asset"] = asset
    out["candidate"] = candidate

    # Source bars are established by provenance against the pre-shift pipeline
    # output, never derived from the action timestamp. Deriving both sides of a
    # timing comparison from the same value makes the comparison vacuous.
    source_bars, provenance_failures = verify_shift_provenance(frame, unshifted)
    out["source_bar_close"] = source_bars.to_numpy()
    out["pnl_interval_start"] = out["action_bar_end"] - bar_delta
    out["pnl_interval_end"] = out["action_bar_end"]
    out["provenance_verified"] = out["source_bar_close"].notna()
    out["probability_available_before_pnl"] = (
        out["provenance_verified"] & (out["source_bar_close"] <= out["pnl_interval_start"])
    )
    out["strictly_no_same_bar_source"] = (
        out["provenance_verified"] & (out["source_bar_close"] < out["action_bar_end"])
    )
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
        "shift_provenance_failures": provenance_failures,
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
            "shift_provenance_failures",
            "availability_failures",
            "same_bar_source_failures",
            "nonfinite_probability_rows",
            "nonfinite_threshold_rows",
        )
    ) else "FAIL"
    return out, checks


def lookahead_canary(unshifted: pd.DataFrame) -> dict[str, Any]:
    """Prove the detector can fail, by running it against known lookahead.

    A forward-shifted series serves bar ``T`` a probability computed from a
    later bar. The audit's own provenance check must reject it. An audit that
    never demonstrates a detected failure is not evidence.
    """
    leaked = unshifted.copy()
    leaked["probability"] = leaked["probability"].shift(-1)
    leaked["train_threshold"] = leaked["train_threshold"].shift(-1)
    leaked = leaked.dropna(subset=["probability", "train_threshold"])
    _, failures = verify_shift_provenance(leaked, unshifted)
    return {
        "rows_tested": int(len(leaked)),
        "detected_failures": failures,
        "status": "PASS" if failures > 0 else "FAIL",
    }


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
    canary_rows: list[dict[str, Any]] = []

    for asset, source in (("BTC", btc), ("ETH", eth)):
        for candidate in LOCKED_MODELS:
            print(f"Auditing timing: {asset} {candidate}")
            pred = _candidate_predictions(source, asset, candidate, args)
            unshifted = _unshifted_predictions(source, asset, candidate, args)
            predictions[(asset, candidate)] = pred
            details, checks = _audit_prediction_frame(
                pred, asset, candidate, bar_delta, unshifted
            )
            audit_frames.append(details)
            check_rows.append(checks)

            canary = lookahead_canary(unshifted)
            canary.update({"asset": asset, "candidate": candidate})
            canary_rows.append(canary)

    event_frames: list[pd.DataFrame] = []
    overlay_checks: list[dict[str, Any]] = []
    for asset in ("BTC", "ETH"):
        flags = _aligned_scale(matrix, predictions, asset)
        active = flags.loc[flags["overlay_active"]].copy()
        active.index.name = "action_bar_end"
        active = active.reset_index()
        active["asset"] = asset
        # Source bars come from the verified per-candidate provenance map, not
        # from arithmetic on the action timestamp.
        verified_sources = pd.concat(
            [
                frame.loc[frame["asset"] == asset, ["action_bar_end", "source_bar_close"]]
                for frame in audit_frames
            ]
        )
        source_by_action = (
            verified_sources.dropna(subset=["source_bar_close"])
            .groupby("action_bar_end")["source_bar_close"]
            .max()
        )
        active["source_bar_close"] = active["action_bar_end"].map(source_by_action)
        active["pnl_interval_start"] = active["action_bar_end"] - bar_delta
        active["pnl_interval_end"] = active["action_bar_end"]
        active["provenance_verified"] = active["source_bar_close"].notna()
        active["timing_valid"] = (
            active["provenance_verified"]
            & (active["source_bar_close"] <= active["pnl_interval_start"])
            & (active["source_bar_close"] < active["pnl_interval_end"])
        )
        event_frames.append(active)
        overlay_checks.append(
            {
                "asset": asset,
                "active_rows": int(len(active)),
                "unverified_source_rows": int((~active["provenance_verified"]).sum()),
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

    canary_summary = pd.DataFrame(canary_rows)
    canary_summary.to_csv(run_dir / "jump_risk_lookahead_canary.csv", index=False)

    # The canary must FAIL on injected lookahead. If the detector cannot detect,
    # the whole audit is void regardless of what the other checks report.
    canary_pass = bool((canary_summary["status"] == "PASS").all())
    structural_pass = (
        bool((checks["status"] == "PASS").all())
        and bool((overlay_summary["status"] == "PASS").all())
        and canary_pass
    )
    report = {
        "audit": "jump_risk_timing_audit_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "STRUCTURAL_PASS_RUNTIME_CADENCE_PENDING" if structural_pass else "FAIL",
        "expected_bar_hours": args.expected_bar_hours,
        "structural_checks_passed": structural_pass,
        "lookahead_canary_passed": canary_pass,
        "lookahead_canary": canary_rows,
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
