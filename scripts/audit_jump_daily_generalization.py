from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit an existing Jump Risk daily asset-generalization run for sparse labels, "
            "degenerate yearly folds, undefined metrics, and misleading best-row selection."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--run-dir", required=True, help="Completed daily_asset_generalization run directory")
    parser.add_argument("--min-events", type=int, default=20, help="Minimum aggregate out-of-sample events")
    parser.add_argument("--min-top5-events", type=int, default=3, help="Minimum observed events in the top-5%% bucket")
    parser.add_argument("--min-passed-years", type=int, default=3, help="Minimum walk-forward PASS folds")
    parser.add_argument("--min-metric-years", type=int, default=2, help="Minimum years with defined AUC and AP")
    parser.add_argument(
        "--min-year-events",
        type=int,
        default=2,
        help="Minimum test events for a yearly fold to count toward stable yearly metrics",
    )
    return parser.parse_args()


def _finite(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _atomic_json(path: Path, payload: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temp.replace(path)


def _load_results(run_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    results_dir = run_dir / "results"
    if not results_dir.exists():
        raise FileNotFoundError(f"Missing results directory: {results_dir}")
    loaded: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(results_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or "spec" not in payload or "run" not in payload:
            continue
        loaded.append((path, payload))
    if not loaded:
        raise RuntimeError(f"No usable result JSON files found under {results_dir}")
    return loaded


def _top_lift(aggregate: dict[str, Any], quantile: float) -> tuple[float | None, float | None, int | None]:
    diagnostics = aggregate.get("diagnostics") or {}
    for row in diagnostics.get("lift_at_top_quantiles", []):
        if abs(float(row.get("top_quantile", -1.0)) - quantile) < 1e-9:
            return row.get("event_rate"), row.get("lift_vs_unconditional"), row.get("n")
    return None, None, None


def _audit_one(
    path: Path,
    payload: dict[str, Any],
    *,
    min_events: int,
    min_top5_events: int,
    min_passed_years: int,
    min_metric_years: int,
    min_year_events: int,
) -> dict[str, Any]:
    spec = payload["spec"]
    run = payload["run"]
    aggregate = run.get("aggregate") or {}
    folds = run.get("folds") or []

    events = int(aggregate.get("events") or 0)
    rows = int(aggregate.get("rows") or 0)
    event_rate = aggregate.get("event_rate")
    roc_auc = aggregate.get("roc_auc")
    average_precision = aggregate.get("average_precision")
    brier = aggregate.get("brier")
    top5_rate, top5_lift, top5_n = _top_lift(aggregate, 0.05)
    top5_n_int = int(top5_n or 0)
    top5_events = int(round(float(top5_rate) * top5_n_int)) if _finite(top5_rate) else 0

    passed = [fold for fold in folds if fold.get("status") == "PASS"]
    skipped = [fold for fold in folds if fold.get("status") != "PASS"]
    one_class = [
        fold
        for fold in passed
        if int(fold.get("test_events") or 0) == 0
        or int(fold.get("test_events") or 0) == int(fold.get("test_rows") or 0)
    ]
    metric_folds = [
        fold
        for fold in passed
        if int(fold.get("test_events") or 0) >= min_year_events
        and _finite(fold.get("roc_auc"))
        and _finite(fold.get("average_precision"))
    ]

    yearly_auc = [float(fold["roc_auc"]) for fold in metric_folds]
    yearly_ap = [float(fold["average_precision"]) for fold in metric_folds]
    yearly_event_rates = [float(fold["test_event_rate"]) for fold in metric_folds if _finite(fold.get("test_event_rate"))]

    invalid_reasons: list[str] = []
    warning_reasons: list[str] = []

    if aggregate.get("status") != "PASS":
        invalid_reasons.append(f"aggregate_status={aggregate.get('status')!r}")
    if rows <= 0:
        invalid_reasons.append("no_oos_rows")
    if events < min_events:
        invalid_reasons.append(f"aggregate_events<{min_events}")
    if not _finite(roc_auc):
        invalid_reasons.append("undefined_auc")
    if not _finite(average_precision):
        invalid_reasons.append("undefined_average_precision")
    if not _finite(top5_lift) or not _finite(top5_rate):
        invalid_reasons.append("undefined_top5_metrics")
    if top5_n_int <= 0:
        invalid_reasons.append("empty_top5_bucket")
    if top5_events < min_top5_events:
        invalid_reasons.append(f"top5_events<{min_top5_events}")
    if len(passed) < min_passed_years:
        invalid_reasons.append(f"passed_years<{min_passed_years}")
    if len(metric_folds) < min_metric_years:
        invalid_reasons.append(f"metric_years<{min_metric_years}")

    if one_class:
        warning_reasons.append(f"one_class_years={len(one_class)}")
    if skipped:
        warning_reasons.append(f"skipped_years={len(skipped)}")
    if _finite(roc_auc) and float(roc_auc) >= 0.80 and top5_events == 0:
        invalid_reasons.append("high_auc_with_zero_top5_events")
    if _finite(top5_lift) and float(top5_lift) >= 4.0 and top5_events < 5:
        warning_reasons.append("high_lift_supported_by_fewer_than_5_top5_events")
    if yearly_auc and min(yearly_auc) < 0.45:
        warning_reasons.append("at_least_one_metric_year_auc_below_0.45")

    validity = "INVALID" if invalid_reasons else ("WARN" if warning_reasons else "VALID")
    stability_grade = "F"
    if validity != "INVALID":
        min_auc = min(yearly_auc) if yearly_auc else float("nan")
        avg_auc = float(np.mean(yearly_auc)) if yearly_auc else float("nan")
        if len(metric_folds) >= 4 and min_auc >= 0.55 and avg_auc >= 0.60 and top5_events >= 5:
            stability_grade = "A"
        elif len(metric_folds) >= 3 and min_auc >= 0.50 and avg_auc >= 0.57 and top5_events >= 3:
            stability_grade = "B"
        else:
            stability_grade = "C"

    return {
        **spec,
        "validity": validity,
        "stability_grade": stability_grade,
        "invalid_reasons": ";".join(invalid_reasons),
        "warning_reasons": ";".join(warning_reasons),
        "result_json": str(path),
        "rows": rows,
        "events": events,
        "event_rate": event_rate,
        "roc_auc": roc_auc,
        "average_precision": average_precision,
        "brier": brier,
        "top5_n": top5_n_int,
        "top5_events": top5_events,
        "top5_event_rate": top5_rate,
        "top5_lift": top5_lift,
        "total_years": len(folds),
        "passed_years": len(passed),
        "skipped_years": len(skipped),
        "one_class_years": len(one_class),
        "metric_years": len(metric_folds),
        "avg_year_auc": float(np.mean(yearly_auc)) if yearly_auc else None,
        "min_year_auc": float(np.min(yearly_auc)) if yearly_auc else None,
        "avg_year_ap": float(np.mean(yearly_ap)) if yearly_ap else None,
        "min_year_ap": float(np.min(yearly_ap)) if yearly_ap else None,
        "min_year_event_rate": float(np.min(yearly_event_rates)) if yearly_event_rates else None,
        "max_year_event_rate": float(np.max(yearly_event_rates)) if yearly_event_rates else None,
    }


def _rank_valid(frame: pd.DataFrame) -> pd.DataFrame:
    valid = frame[frame["validity"].isin(["VALID", "WARN"])].copy()
    if valid.empty:
        return valid
    grade_rank = {"A": 0, "B": 1, "C": 2, "F": 3}
    valid["_grade_rank"] = valid["stability_grade"].map(grade_rank).fillna(9)
    valid = valid.sort_values(
        ["_grade_rank", "top5_lift", "roc_auc", "events"],
        ascending=[True, False, False, False],
        na_position="last",
    )
    return valid.drop(columns=["_grade_rank"])


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory does not exist: {run_dir}")

    rows = [
        _audit_one(
            path,
            payload,
            min_events=args.min_events,
            min_top5_events=args.min_top5_events,
            min_passed_years=args.min_passed_years,
            min_metric_years=args.min_metric_years,
            min_year_events=args.min_year_events,
        )
        for path, payload in _load_results(run_dir)
    ]
    audit = pd.DataFrame(rows)
    ranked = _rank_valid(audit)
    rejected = audit[audit["validity"] == "INVALID"].copy()
    best = (
        ranked.groupby(["asset", "lane"], as_index=False).head(1)
        if not ranked.empty
        else pd.DataFrame(columns=audit.columns)
    )

    audit_path = run_dir / "daily_generalization_audit_all.csv"
    scorecard_path = run_dir / "daily_generalization_valid_scorecard.csv"
    best_path = run_dir / "daily_generalization_audited_best_by_asset_lane.csv"
    rejected_path = run_dir / "daily_generalization_rejected.csv"
    report_path = run_dir / "daily_generalization_audit_report.json"

    audit.sort_values(["asset", "lane", "horizon_bars", "jump_z", "absolute_jump"]).to_csv(audit_path, index=False)
    ranked.to_csv(scorecard_path, index=False)
    best.sort_values(["asset", "lane"]).to_csv(best_path, index=False)
    rejected.sort_values(["asset", "lane", "horizon_bars", "jump_z", "absolute_jump"]).to_csv(rejected_path, index=False)

    counts = audit["validity"].value_counts().to_dict()
    report = {
        "experiment": "jump_risk_daily_generalization_validity_audit_v1",
        "source_run_dir": str(run_dir),
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "thresholds": {
            "min_events": args.min_events,
            "min_top5_events": args.min_top5_events,
            "min_passed_years": args.min_passed_years,
            "min_metric_years": args.min_metric_years,
            "min_year_events": args.min_year_events,
        },
        "counts": {str(key): int(value) for key, value in counts.items()},
        "outputs": {
            "all": str(audit_path),
            "valid_scorecard": str(scorecard_path),
            "audited_best_by_asset_lane": str(best_path),
            "rejected": str(rejected_path),
        },
    }
    _atomic_json(report_path, report)

    print("Jump Risk daily generalization validity audit complete")
    print(f"Source run: {run_dir}")
    print(f"Configurations audited: {len(audit)}")
    print("Validity counts: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    print()
    print("Audited best by asset/lane:")
    if best.empty:
        print("- No configuration passed the validity gates.")
    else:
        for _, row in best.sort_values(["asset", "lane"]).iterrows():
            print(
                f"- asset={row['asset']:<3} lane={row['lane']:<14} validity={row['validity']:<5} "
                f"grade={row['stability_grade']} h={int(row['horizon_bars']):<3} z={row['jump_z']:g} "
                f"abs={row['absolute_jump']:g} events={int(row['events']):<3} top5_events={int(row['top5_events']):<2} "
                f"auc={float(row['roc_auc']):.4f} lift={float(row['top5_lift']):.2f}x"
            )
    print()
    print("Reference files:")
    print(f"- {audit_path}")
    print(f"- {scorecard_path}")
    print(f"- {best_path}")
    print(f"- {rejected_path}")
    print(f"- {report_path}")


if __name__ == "__main__":
    main()
