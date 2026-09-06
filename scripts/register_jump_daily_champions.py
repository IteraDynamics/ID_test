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
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

from research.research_engine.registry import ChampionRecord, ChampionRegistry


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Register audited daily Jump Risk candidates in the Research Engine champion registry. "
            "Only rows explicitly present in the audited-best scorecard are considered."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--run-dir", required=True, help="Completed daily_asset_generalization run directory")
    p.add_argument("--registry-dir", default="artifacts/research_engine_v1/registry")
    p.add_argument("--status", choices=["CANDIDATE", "CHAMPION"], default="CANDIDATE")
    p.add_argument(
        "--include-validity",
        default="WARN,VALID",
        help="Comma-separated audit validity states eligible for registration",
    )
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def _clean(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _pick(row: pd.Series, *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row.index and not pd.isna(row[name]):
            return _clean(row[name])
    return default


def _candidate_id(row: pd.Series) -> str:
    return (
        f"{str(row['asset']).lower()}__{row['lane']}__h{int(row['horizon_bars'])}__"
        f"{row['model']}__{row['feature_set']}__z{float(row['jump_z']):g}__"
        f"abs{float(row['absolute_jump']):g}"
    ).replace(".", "p")


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir)
    scorecard_path = run_dir / "daily_generalization_audited_best_by_asset_lane.csv"
    audit_report_path = run_dir / "daily_generalization_audit_report.json"
    manifest_path = run_dir / "manifest.json"

    if not scorecard_path.exists():
        raise FileNotFoundError(f"Missing audited scorecard: {scorecard_path}")

    scorecard = pd.read_csv(scorecard_path)
    if scorecard.empty:
        raise RuntimeError("Audited scorecard is empty; nothing can be registered")

    eligible = {part.strip().upper() for part in args.include_validity.split(",") if part.strip()}
    if not eligible:
        raise ValueError("--include-validity cannot be empty")

    audit_report = json.loads(audit_report_path.read_text(encoding="utf-8")) if audit_report_path.exists() else {}
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    registry = ChampionRegistry(args.registry_dir)

    registered: list[str] = []
    skipped: list[str] = []
    for _, row in scorecard.iterrows():
        validity = str(_pick(row, "validity", "validity_status", default="UNKNOWN")).upper()
        candidate_id = _candidate_id(row)
        if validity not in eligible:
            skipped.append(f"{candidate_id}: validity={validity}")
            continue

        metrics = {
            key: _pick(row, key)
            for key in (
                "events",
                "event_rate",
                "roc_auc",
                "average_precision",
                "brier",
                "top5_n",
                "top5_events",
                "top5_event_rate",
                "top5_lift",
                "avg_year_auc",
                "min_year_auc",
                "avg_year_ap",
                "min_year_ap",
                "passed_years",
            )
            if key in row.index
        }
        validation = {
            "validity": validity,
            "stability_grade": _pick(row, "stability_grade", "grade"),
            "audit_reasons": _pick(row, "audit_reasons", "reasons", default=""),
            "audit_policy": audit_report.get("policy") or audit_report.get("thresholds") or {},
            "daily_native": True,
            "hourly_transfer_comparison": False,
        }
        record = ChampionRecord(
            experiment_id="jump-risk-daily-asset-generalization-v0",
            candidate_id=candidate_id,
            status=args.status,
            asset=str(row["asset"]).upper(),
            timeframe="1d",
            target=str(row["target"]),
            model=str(row["model"]),
            feature_set=str(row["feature_set"]),
            horizon_bars=int(row["horizon_bars"]),
            parameters={
                "lane": str(row["lane"]),
                "jump_z": float(row["jump_z"]),
                "absolute_jump": float(row["absolute_jump"]),
                "vol_window": source_manifest.get("config", {}).get("vol_window", 20),
                "fast_window": source_manifest.get("config", {}).get("fast_window", 10),
                "slow_window": source_manifest.get("config", {}).get("slow_window", 60),
                "test_start_year": source_manifest.get("config", {}).get("test_start_year", 2020),
            },
            metrics=metrics,
            validation=validation,
            source_artifacts={
                "run_dir": str(run_dir),
                "audited_scorecard": str(scorecard_path),
                "audit_report": str(audit_report_path),
                "experiment_manifest": str(manifest_path),
            },
            hypothesis=(
                "Daily market-state features contain out-of-sample information about the probability "
                "of a future discontinuity over an asset-appropriate horizon."
            ),
            notes=[
                "Registered from the audited-best scorecard; not selected from the unaudited headline table.",
                "WARN candidates remain research candidates and are not approved for live portfolio action.",
            ],
        )

        if args.dry_run:
            print(json.dumps(record.canonical_payload(), indent=2, default=str))
        else:
            registered.append(str(registry.register(record)))

    print("Research Engine champion registration complete")
    print(f"Source run: {run_dir}")
    print(f"Eligible validity states: {sorted(eligible)}")
    print(f"Registered: {len(registered)} | skipped: {len(skipped)} | dry_run={args.dry_run}")
    for path in registered:
        print(f"- {path}")
    for reason in skipped:
        print(f"- skipped {reason}")
    if not args.dry_run:
        print(f"Registry index: {registry.index_path}")


if __name__ == "__main__":
    main()
