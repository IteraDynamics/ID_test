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

  T1 source bar close      market_data.bar_timestamp + this bar's own timeframe duration
  T2 data observed         market_data.timestamp   (runtime's own data_age_hours)
  T5 portfolio decision    signals.timestamp
  T6 executable order      fills.timestamp

T3 (model inference) and T4 (signal availability) are not separately logged because
Jump Risk has never run live. They are bounded above by T5 and are reported as such
rather than invented.

Two corrections versus the first version of this script (2026-08-20 review):

1. `market_data.bar_timestamp` is a bar's *start* label, not its close --
   `scripts/run_core_v1_paper_live.py`'s own `drop_incomplete_bars` docstring is explicit
   that "a bar labeled T covers [T, T+bar_duration)". The original version of this script
   subtracted `bar_timestamp` directly, which measured "time since bar started" and silently
   overstated every reported lag by exactly that bar's own duration (confirmed against a real
   paper export: the discrepancy between the old and corrected ETH_1H_trend medians was exactly
   1.00h, matching its 1-hour bar precisely -- not a coincidence).
2. A sleeve running on a longer timeframe than the poll interval re-logs its current,
   unchanged bar on every intervening cycle (correctly -- there is nothing new to report).
   Averaging bar-close-to-observed age across *all* rows, as the original version did, mixes
   genuine fresh pickups with these growing-stale re-logs and inflates the aggregate for any
   sleeve coarser than the poll cadence. This version reports both: the all-decisions aggregate
   (relevant to "how stale is the input this decision actually used") and a fresh-pickup-only
   aggregate, restricted to the first cycle each bar was ever observed (relevant to "how fast
   does the runtime react once new information exists" -- the question this audit exists to
   answer, per the research assumption quoted above).

Both corrections were found by reviewing a real 808-cycle export and are demonstrated by the
regression tests in tests/test_paper_runtime_cadence_audit.py, including a synthetic-fixture
canary that fails under the old (reverted) computation and passes under this one.

This correction affects three governance documents that cite this script's output
(`docs/ITERA_RESEARCH_PROCESS_AMENDMENTS.md`, `docs/engineering/CORE_V1_JUMP_RISK_PAPER_CHARTER.md`,
`docs/research/CANDIDATE_HORIZON_FEASIBILITY_SWEEP.md`, all citing the 2026-08-10 run). Those
citations have not been updated by this change -- doing so requires re-running this corrected
script against the real paper export and is a separate, deliberate step, not a byproduct of
fixing the measurement tool.

Observation-only. Reads logs; changes nothing.
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
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent

# The overlay fails closed to 1.00x when inputs exceed this age.
from runtime.core_v1.jump_risk_overlay import MAX_INPUT_AGE_SECONDS

# Jump Risk scores BTC and ETH on hourly bars.
JUMP_RISK_ASSETS = ("BTC", "ETH")
RESEARCH_ASSUMPTION_HOURS = 1.0

# Mirrors scripts/run_core_v1_paper_live.py's own TIMEFRAME_DURATION. Duplicated rather than
# imported so this audit stays dependency-light (no pandas) and observation-only; kept in sync
# by tests/test_paper_runtime_cadence_audit.py's cross-check against the live runtime's copy.
TIMEFRAME_DURATION = {"1H": timedelta(hours=1), "4H": timedelta(hours=4), "1D": timedelta(days=1)}


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
    per_sleeve_first_pickup: dict[str, list[float]] = {}
    per_asset_bar_to_decision: dict[str, list[float]] = {}
    per_asset_first_pickup_to_decision: dict[str, list[float]] = {}
    first_seen_bar: set[tuple[str, str]] = set()
    rows: list[dict[str, Any]] = []

    for row in market:
        sleeve = str(row.get("sleeve", "?"))
        asset = str(row.get("asset", "?"))
        timeframe = row.get("timeframe")
        cycle = row.get("cycle")
        bar_start = parse_ts(row.get("bar_timestamp"))
        observed = parse_ts(row.get("timestamp"))
        if bar_start is None or observed is None:
            continue

        duration = TIMEFRAME_DURATION.get(str(timeframe))
        if duration is None:
            raise ValueError(
                f"Unrecognized timeframe {timeframe!r} for sleeve {sleeve!r} (cycle {cycle}) -- "
                "cannot compute this bar's true close without a known duration. Add it to "
                "TIMEFRAME_DURATION rather than silently assuming bar_timestamp is the close."
            )
        bar_close = bar_start + duration

        observe_age = (observed - bar_close).total_seconds() / 3600.0
        per_sleeve.setdefault(sleeve, []).append(observe_age)

        bar_key = (sleeve, bar_start.isoformat())
        is_first_sighting = bar_key not in first_seen_bar
        if is_first_sighting:
            first_seen_bar.add(bar_key)
            per_sleeve_first_pickup.setdefault(sleeve, []).append(observe_age)

        decision = decision_at.get(cycle) if isinstance(cycle, int) else None
        decide_age = (decision - bar_close).total_seconds() / 3600.0 if decision else None
        if decide_age is not None:
            per_asset_bar_to_decision.setdefault(asset, []).append(decide_age)
            if is_first_sighting:
                per_asset_first_pickup_to_decision.setdefault(asset, []).append(decide_age)

        rows.append(
            {
                "cycle": cycle,
                "sleeve": sleeve,
                "asset": asset,
                "timeframe": timeframe,
                "bar_start": bar_start.isoformat(),
                "bar_close": bar_close.isoformat(),
                "observed_at": observed.isoformat(),
                "first_sighting_of_this_bar": is_first_sighting,
                "bar_close_to_observation_hours": round(observe_age, 6),
                "bar_close_to_decision_hours": round(decide_age, 6) if decide_age is not None else None,
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

    def _pct_within(ages: list[float], threshold: float) -> float | None:
        if not ages:
            return None
        return round(100.0 * sum(1 for a in ages if a <= threshold) / len(ages), 2)

    overlay_gate_hours = MAX_INPUT_AGE_SECONDS / 3600.0

    # The decisive test, restricted to the assets Jump Risk actually scores. Reported two ways:
    # "all decisions" (every cycle's decision, including ones re-using an unchanged bar -- the
    # relevant question for "how stale is the input this decision actually used") and
    # "fresh bar only" (restricted to the cycle each bar was first observed -- the relevant
    # question for "how fast does the runtime react once new information exists", which is what
    # the research assumption quoted at the top of this file is actually about).
    verdict_rows: dict[str, Any] = {}
    for asset in JUMP_RISK_ASSETS:
        ages_all = per_asset_bar_to_decision.get(asset, [])
        ages_fresh = per_asset_first_pickup_to_decision.get(asset, [])
        if not ages_all:
            verdict_rows[asset] = {"observations": 0, "verdict": "NO_DATA"}
            continue
        verdict_rows[asset] = {
            "observations_all_decisions": len(ages_all),
            "observations_fresh_bar_only": len(ages_fresh),
            "bar_close_to_decision_hours_all_decisions": summarize(ages_all),
            "bar_close_to_decision_hours_fresh_bar_only": summarize(ages_fresh),
            "within_research_assumption_pct_all_decisions": _pct_within(ages_all, assumption_hours),
            "within_research_assumption_pct_fresh_bar_only": _pct_within(ages_fresh, assumption_hours),
            "within_overlay_freshness_gate_pct_all_decisions": _pct_within(ages_all, overlay_gate_hours),
            "within_overlay_freshness_gate_pct_fresh_bar_only": _pct_within(ages_fresh, overlay_gate_hours),
        }

    return {
        "audit": "paper_runtime_cadence_audit_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "paper_export_dir": str(export_dir).replace("\\", "/"),
        "research_assumption_hours": assumption_hours,
        "overlay_freshness_gate_hours": overlay_gate_hours,
        "cycles_observed": len(decision_at),
        "market_data_rows": len(rows),
        "timestamps_measured": {
            "T1_source_bar_close": "market_data.bar_timestamp + this bar's timeframe duration",
            "T2_data_observed": "market_data.timestamp",
            "T5_portfolio_decision": "signals.timestamp",
            "T6_executable_order": "fills.timestamp",
            "T3_model_inference": "NOT LOGGED (Jump Risk has never run live; bounded above by T5)",
            "T4_signal_availability": "NOT LOGGED (bounded above by T5)",
        },
        "bar_close_to_observation_hours_by_sleeve_all_decisions": {
            sleeve: summarize(values) for sleeve, values in sorted(per_sleeve.items())
        },
        "bar_close_to_observation_hours_by_sleeve_fresh_bar_only": {
            sleeve: summarize(values) for sleeve, values in sorted(per_sleeve_first_pickup.items())
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

    print("Bar close -> data observed, by sleeve, ALL DECISIONS (hours):")
    print("  (includes cycles that re-log an unchanged bar while nothing new has closed yet)")
    for sleeve, stats in report["bar_close_to_observation_hours_by_sleeve_all_decisions"].items():
        print(
            f"  {sleeve:<16} n={stats['count']:<5} median={stats['median']:<9} "
            f"p95={stats['p95']:<9} max={stats['max']}"
        )

    print("\nBar close -> data observed, by sleeve, FRESH BAR ONLY (hours):")
    print("  (first cycle each bar was ever observed -- true reaction speed to new information)")
    for sleeve, stats in report["bar_close_to_observation_hours_by_sleeve_fresh_bar_only"].items():
        print(
            f"  {sleeve:<16} n={stats['count']:<5} median={stats['median']:<9} "
            f"p95={stats['p95']:<9} max={stats['max']}"
        )

    internal = report["internal_observe_to_decision_seconds"]
    print(f"\nObserve -> decision (seconds): median={internal['median']} max={internal['max']}")

    print("\nJUMP RISK VERDICT (BTC/ETH bar close -> portfolio decision):")
    for asset, verdict in report["jump_risk_verdict"].items():
        if verdict.get("observations_all_decisions", 0) == 0:
            print(f"  {asset}: NO DATA")
            continue
        all_stats = verdict["bar_close_to_decision_hours_all_decisions"]
        fresh_stats = verdict["bar_close_to_decision_hours_fresh_bar_only"]
        print(
            f"  {asset} [all decisions]:   median={all_stats['median']}h  "
            f"p95={all_stats['p95']}h  max={all_stats['max']}h"
        )
        print(
            f"       within research assumption ({args.assumption_hours}h): "
            f"{verdict['within_research_assumption_pct_all_decisions']}%   "
            f"within overlay freshness gate: {verdict['within_overlay_freshness_gate_pct_all_decisions']}%"
        )
        print(
            f"  {asset} [fresh bar only]:  median={fresh_stats['median']}h  "
            f"p95={fresh_stats['p95']}h  max={fresh_stats['max']}h"
        )
        print(
            f"       within research assumption ({args.assumption_hours}h): "
            f"{verdict['within_research_assumption_pct_fresh_bar_only']}%   "
            f"within overlay freshness gate: {verdict['within_overlay_freshness_gate_pct_fresh_bar_only']}%"
        )

    print(f"\nArtifacts: {out_dir}")
    print("Note: this measures Core v1's live cadence as a proxy. It does not include")
    print("Jump Risk model-inference time, which has never run live.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
