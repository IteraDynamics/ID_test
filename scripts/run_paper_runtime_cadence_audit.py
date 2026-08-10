"""Measure the live paper runtime's decision cadence against the Jump Risk research assumption.

The Jump Risk promotion decision (docs/research/PROMOTION_DECISION_JUMP_RISK_V0.md)
records that the candidate's benefit "decays sharply after the first implementation
bar" and blocks paper activation until the runtime can reproduce the research timing
without using information unavailable at the decision point.

The research assumption is explicit in the timing audit report:

    "The scale is actionable at source-bar close and applies to P&L accrued over
     the immediately following hourly interval."

So the operative question is: how long after a source bar closes does this runtime
actually decide and act? This script answers that from logs the runtime already
writes -- no runtime change, no new instrumentation, no waiting.

Measured from an existing paper export:

  T1 source bar close      market_data.bar_timestamp
  T2 data observed         market_data.timestamp   (runtime's own data_age_hours)
  T5 portfolio decision    signals.timestamp
  T6 executable order      fills.timestamp

T3 (model inference) and T4 (signal availability) are not separately logged because
Jump Risk has never run live. They are bounded above by T5 and are reported as such
rather than invented.

Observation-only. Reads logs; changes nothing.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# The overlay fails closed to 1.00x when inputs exceed this age.
from runtime.core_v1.jump_risk_overlay import MAX_INPUT_AGE_SECONDS

# Jump Risk scores BTC and ETH on hourly bars.
JUMP_RISK_ASSETS = ("BTC", "ETH")
RESEARCH_ASSUMPTION_HOURS = 1.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Measure live paper runtime cadence against the Jump Risk timing assumption.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--paper-export", required=True)
    p.add_argument("--out-dir", default="artifacts/paper_runtime_cadence_audit")
    p.add_argument(
        "--assumption-hours",
        type=float,
        default=RESEARCH_ASSUMPTION_HOURS,
        help="Maximum bar-close-to-decision age under which the research timing holds.",
    )
    return p.parse_args(argv)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def parse_ts(raw: Any) -> datetime | None:
    """Parse both tz-aware ISO stamps and naive bar timestamps (treated as UTC)."""
    if not raw:
        return None
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def summarize(values: Iterable[float]) -> dict[str, float | int | None]:
    data = sorted(v for v in values if v is not None)
    if not data:
        return {"count": 0, "median": None, "p90": None, "p95": None, "max": None, "min": None}

    def pct(fraction: float) -> float:
        if len(data) == 1:
            return data[0]
        index = min(len(data) - 1, int(round(fraction * (len(data) - 1))))
        return data[index]

    return {
        "count": len(data),
        "min": round(data[0], 4),
        "median": round(statistics.median(data), 4),
        "p90": round(pct(0.90), 4),
        "p95": round(pct(0.95), 4),
        "max": round(data[-1], 4),
    }


def build_report(export_dir: Path, assumption_hours: float) -> dict[str, Any]:
    market = read_jsonl(export_dir / "market_data.jsonl")
    signals = read_jsonl(export_dir / "signals.jsonl")
    fills = read_jsonl(export_dir / "fills.jsonl")
    if not market:
        raise SystemExit(f"No market_data.jsonl rows in {export_dir}")
    if not signals:
        raise SystemExit(f"No signals.jsonl rows in {export_dir}")

    decision_at: dict[int, datetime] = {}
    for event in signals:
        cycle = event.get("cycle")
        stamp = parse_ts(event.get("timestamp"))
        if isinstance(cycle, int) and stamp is not None:
            decision_at[cycle] = stamp

    per_sleeve: dict[str, list[float]] = {}
    per_asset_bar_to_decision: dict[str, list[float]] = {}
    rows: list[dict[str, Any]] = []

    for row in market:
        sleeve = str(row.get("sleeve", "?"))
        asset = str(row.get("asset", "?"))
        cycle = row.get("cycle")
        bar_ts = parse_ts(row.get("bar_timestamp"))
        observed = parse_ts(row.get("timestamp"))
        if bar_ts is None or observed is None:
            continue

        observe_age = (observed - bar_ts).total_seconds() / 3600.0
        per_sleeve.setdefault(sleeve, []).append(observe_age)

        decision = decision_at.get(cycle) if isinstance(cycle, int) else None
        decide_age = (decision - bar_ts).total_seconds() / 3600.0 if decision else None
        if decide_age is not None:
            per_asset_bar_to_decision.setdefault(asset, []).append(decide_age)

        rows.append(
            {
                "cycle": cycle,
                "sleeve": sleeve,
                "asset": asset,
                "timeframe": row.get("timeframe"),
                "bar_timestamp": bar_ts.isoformat(),
                "observed_at": observed.isoformat(),
                "bar_to_observation_hours": round(observe_age, 6),
                "bar_to_decision_hours": round(decide_age, 6) if decide_age is not None else None,
                "runtime_reported_data_age_hours": row.get("data_age_hours"),
            }
        )

    # Internal latency: how long from observing data to recording the decision.
    internal: list[float] = []
    for row in rows:
        observed = parse_ts(row["observed_at"])
        cycle = row["cycle"]
        decision = decision_at.get(cycle) if isinstance(cycle, int) else None
        if observed is not None and decision is not None:
            internal.append((decision - observed).total_seconds())

    fill_lag: list[float] = []
    for fill in fills:
        stamp = parse_ts(fill.get("timestamp"))
        if stamp is None:
            continue
        nearest = min(
            (abs((stamp - d).total_seconds()) for d in decision_at.values()),
            default=None,
        )
        if nearest is not None:
            fill_lag.append(nearest)

    # The decisive test, restricted to the assets Jump Risk actually scores.
    verdict_rows: dict[str, Any] = {}
    for asset in JUMP_RISK_ASSETS:
        ages = per_asset_bar_to_decision.get(asset, [])
        if not ages:
            verdict_rows[asset] = {"observations": 0, "verdict": "NO_DATA"}
            continue
        within = sum(1 for a in ages if a <= assumption_hours)
        within_overlay_gate = sum(1 for a in ages if a <= MAX_INPUT_AGE_SECONDS / 3600.0)
        verdict_rows[asset] = {
            "observations": len(ages),
            "bar_to_decision_hours": summarize(ages),
            "within_research_assumption_pct": round(100.0 * within / len(ages), 2),
            "within_overlay_freshness_gate_pct": round(100.0 * within_overlay_gate / len(ages), 2),
        }

    return {
        "audit": "paper_runtime_cadence_audit_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "paper_export_dir": str(export_dir).replace("\\", "/"),
        "research_assumption_hours": assumption_hours,
        "overlay_freshness_gate_hours": MAX_INPUT_AGE_SECONDS / 3600.0,
        "cycles_observed": len(decision_at),
        "market_data_rows": len(rows),
        "timestamps_measured": {
            "T1_source_bar_close": "market_data.bar_timestamp",
            "T2_data_observed": "market_data.timestamp",
            "T5_portfolio_decision": "signals.timestamp",
            "T6_executable_order": "fills.timestamp",
            "T3_model_inference": "NOT LOGGED (Jump Risk has never run live; bounded above by T5)",
            "T4_signal_availability": "NOT LOGGED (bounded above by T5)",
        },
        "bar_to_observation_hours_by_sleeve": {
            sleeve: summarize(values) for sleeve, values in sorted(per_sleeve.items())
        },
        "internal_observe_to_decision_seconds": summarize(internal),
        "fill_to_decision_seconds": summarize(fill_lag),
        "jump_risk_verdict": verdict_rows,
    }, rows


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report, rows = build_report(Path(args.paper_export), args.assumption_hours)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "cadence_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    import csv as csv_module

    with (out_dir / "cadence_rows.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv_module.DictWriter(
            handle, fieldnames=list(rows[0].keys()), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Cycles observed: {report['cycles_observed']}")
    print(f"Research assumption: decision within {args.assumption_hours}h of bar close")
    print(f"Overlay freshness gate: {report['overlay_freshness_gate_hours']}h\n")

    print("Bar close -> data observed, by sleeve (hours):")
    for sleeve, stats in report["bar_to_observation_hours_by_sleeve"].items():
        print(
            f"  {sleeve:<16} n={stats['count']:<5} median={stats['median']:<9} "
            f"p95={stats['p95']:<9} max={stats['max']}"
        )

    internal = report["internal_observe_to_decision_seconds"]
    print(f"\nObserve -> decision (seconds): median={internal['median']} max={internal['max']}")

    print("\nJUMP RISK VERDICT (BTC/ETH bar close -> portfolio decision):")
    for asset, verdict in report["jump_risk_verdict"].items():
        if verdict.get("observations", 0) == 0:
            print(f"  {asset}: NO DATA")
            continue
        stats = verdict["bar_to_decision_hours"]
        print(
            f"  {asset}: median={stats['median']}h  p95={stats['p95']}h  max={stats['max']}h"
        )
        print(
            f"       within research assumption ({args.assumption_hours}h): "
            f"{verdict['within_research_assumption_pct']}%"
        )
        print(
            f"       within overlay freshness gate: "
            f"{verdict['within_overlay_freshness_gate_pct']}%"
        )

    print(f"\nArtifacts: {out_dir}")
    print("Note: this measures Core v1's live cadence as a proxy. It does not include")
    print("Jump Risk model-inference time, which has never run live.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
