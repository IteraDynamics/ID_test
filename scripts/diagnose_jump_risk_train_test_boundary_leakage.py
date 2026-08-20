"""Quantify the severity of Jump Risk's known, deliberately-uncorrected train/test leakage.

`docs/engineering/CORE_V1_JUMP_RISK_PAPER_CHARTER.md`'s "Found and deliberately NOT corrected"
section records this as a real, unresolved gap: in `_oos_probabilities`, training rows within
`horizon_bars` of a year boundary carry labels that extend into the test year (up to 120 hours
for the extended-up model), and correcting it "would change every Jump Risk probability and
threshold" -- a governed decision, not a silent fix.

This script does not fix it or take a position on whether it matters enough to act on. It
measures two things a governed decision would want to know, neither of which requires refitting
any model or touching the frozen research path:

1. **How many rows actually leak, as a fraction of each fold's training set.** The label window
   (`research/jump_risk_engine/lab.py`'s `_future_window_stat`) is purely positional -- a
   `.shift(-1)` then a `horizon`-bar rolling window, with no calendar-date logic at all. That
   means the leaking rows in any fold are *exactly* `train.tail(horizon_bars)`, provably from
   the code, independent of what the real data contains.
2. **Whether those specific rows look different from the rest of the training set** --
   comparing the leaking tail's positive-label rate against the clean remainder's. A leakage
   mechanism that happens to touch rows with a similar label rate to the rest of training is a
   smaller practical concern than one where the tail is disproportionately event-heavy (which
   would mean the model is being handed a preview of exactly the kind of event it will soon be
   asked to predict in the test year). This is a descriptive comparison, not a formal hypothesis
   test -- with folds this few, a p-value would invite more confidence than the sample supports.

Uses `_build_frame`, `LOCKED_MODELS`, `JumpRiskConfig`, and `FEATURE_SETS` unchanged. No model
is fit -- this only inspects the label column, so it runs fast and cannot itself introduce any
new leakage or touch any frozen result.

Observation-only. No runtime, strategy, order, NAV, model, or production change.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_jump_risk_portfolio_integration import (  # noqa: E402
    CANONICAL_DATA,
    FEATURE_SETS,
    LOCKED_MODELS,
    _build_frame,
    _canonical_path,
    read_ohlcv,
)
from research.jump_risk_engine.lab import JumpRiskConfig  # noqa: E402


def boundary_leakage_rows(
    frame: pd.DataFrame, label_col: str, year: int, horizon_bars: int, min_train_rows: int
) -> dict[str, Any] | None:
    """One fold's leakage measurement, or None if the fold doesn't have enough training data
    to have been used at all (mirrors _oos_probabilities_unshifted's own skip condition)."""
    train = frame[frame.index.year < year]
    if len(train) < min_train_rows:
        return None
    if len(train) <= horizon_bars:
        # Every training row is within the leaking tail -- degenerate fold, report as such
        # rather than silently producing a fraction over 1.0 or an empty "clean" comparison.
        leaking = train
        clean = train.iloc[0:0]
    else:
        leaking = train.tail(horizon_bars)
        clean = train.iloc[: len(train) - horizon_bars]

    leaking_rate = float(leaking[label_col].mean()) if len(leaking) else None
    clean_rate = float(clean[label_col].mean()) if len(clean) else None
    return {
        "test_year": year,
        "train_rows": int(len(train)),
        "leaking_rows": int(len(leaking)),
        "leaking_fraction": round(len(leaking) / len(train), 6),
        "leaking_positive_rate": round(leaking_rate, 6) if leaking_rate is not None else None,
        "clean_positive_rate": round(clean_rate, 6) if clean_rate is not None else None,
        "positive_rate_delta": (
            round(leaking_rate - clean_rate, 6) if leaking_rate is not None and clean_rate is not None else None
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Quantify Jump Risk's known train/test boundary leakage -- measurement only.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--btc-data", default=CANONICAL_DATA["btc_data"])
    p.add_argument("--eth-data", default=CANONICAL_DATA["eth_data"])
    p.add_argument("--oos-start", default="2020-01-01")
    p.add_argument("--oos-end", default="2025-12-31")
    p.add_argument("--out-dir", default="artifacts/jump_risk_boundary_leakage_diagnosis")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sources = {"BTC": read_ohlcv(_canonical_path(args.btc_data)), "ETH": read_ohlcv(_canonical_path(args.eth_data))}
    start_year = pd.Timestamp(args.oos_start).year
    end_year = pd.Timestamp(args.oos_end).year

    rows: list[dict[str, Any]] = []
    for asset, ohlcv in sources.items():
        for candidate_name, spec in LOCKED_MODELS.items():
            cfg = JumpRiskConfig(
                asset=asset,
                horizon_bars=int(spec["horizon_bars"]),
                vol_window=96,
                fast_window=24,
                slow_window=240,
                min_train_rows=500,
                min_train_events=20,
                test_start_year=start_year,
            )
            frame = _build_frame(ohlcv, cfg)
            label_col = f"jump_{spec['target']}"
            if label_col not in frame.columns:
                raise RuntimeError(f"{label_col!r} missing from built frame for {asset} {candidate_name}")

            for year in range(start_year, end_year + 1):
                measured = boundary_leakage_rows(frame, label_col, year, cfg.horizon_bars, cfg.min_train_rows)
                if measured is None:
                    continue
                rows.append({"asset": asset, "candidate": candidate_name, "horizon_bars": cfg.horizon_bars, **measured})

    if not rows:
        raise SystemExit("No folds produced a measurement -- check --oos-start/--oos-end against the data range.")

    frame_out = pd.DataFrame(rows)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frame_out.to_csv(out_dir / "boundary_leakage_by_fold.csv", index=False)

    summary = {
        "diagnosis": "jump_risk_train_test_boundary_leakage_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "folds_measured": len(rows),
        "leaking_fraction": {
            "min": round(float(frame_out["leaking_fraction"].min()), 6),
            "median": round(float(frame_out["leaking_fraction"].median()), 6),
            "max": round(float(frame_out["leaking_fraction"].max()), 6),
        },
        "positive_rate_delta": {
            "min": round(float(frame_out["positive_rate_delta"].dropna().min()), 6) if frame_out["positive_rate_delta"].notna().any() else None,
            "median": round(float(frame_out["positive_rate_delta"].dropna().median()), 6) if frame_out["positive_rate_delta"].notna().any() else None,
            "max": round(float(frame_out["positive_rate_delta"].dropna().max()), 6) if frame_out["positive_rate_delta"].notna().any() else None,
        },
        "rows": rows,
    }
    (out_dir / "boundary_leakage_report.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"{'asset':<6}{'candidate':<14}{'year':>6}{'train_n':>9}{'leak_n':>8}{'leak_%':>8}{'leak_pos%':>11}{'clean_pos%':>12}{'delta':>9}")
    for row in rows:
        leak_pos = f"{row['leaking_positive_rate']*100:.2f}" if row["leaking_positive_rate"] is not None else "n/a"
        clean_pos = f"{row['clean_positive_rate']*100:.2f}" if row["clean_positive_rate"] is not None else "n/a"
        delta = f"{row['positive_rate_delta']*100:+.2f}" if row["positive_rate_delta"] is not None else "n/a"
        print(
            f"{row['asset']:<6}{row['candidate']:<14}{row['test_year']:>6}{row['train_rows']:>9}"
            f"{row['leaking_rows']:>8}{row['leaking_fraction']*100:>7.2f}%{leak_pos:>11}{clean_pos:>12}{delta:>9}"
        )

    print(f"\nLeaking fraction of training set: min={summary['leaking_fraction']['min']*100:.2f}%  "
          f"median={summary['leaking_fraction']['median']*100:.2f}%  max={summary['leaking_fraction']['max']*100:.2f}%")
    if summary["positive_rate_delta"]["median"] is not None:
        print(f"Positive-rate delta (leaking tail vs clean remainder): "
              f"min={summary['positive_rate_delta']['min']*100:+.2f}pp  "
              f"median={summary['positive_rate_delta']['median']*100:+.2f}pp  "
              f"max={summary['positive_rate_delta']['max']*100:+.2f}pp")
    print(f"\nArtifacts: {out_dir}")
    print("\nThis measures severity only. It does not fix the leakage or decide whether it")
    print("matters enough to act on -- that remains the governed decision the charter names.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
