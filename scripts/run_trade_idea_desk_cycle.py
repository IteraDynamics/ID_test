#!/usr/bin/env python
"""Run the full trade idea desk cycle.

Convenience wrapper for the daily/paper desk workflow:

1. scan_trade_ideas.py
2. update_trade_idea_paper_ledger.py
3. log_trade_idea_paper_events.py

Research/paper only. No runtime, broker, or live execution code is modified.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _run_step(label: str, cmd: list[str], cwd: Path, continue_on_error: bool) -> int:
    print("\n" + "=" * 180)
    print(f"  DESK CYCLE STEP — {label}")
    print("=" * 180)
    print("  " + " ".join(cmd))
    print("-" * 180)
    proc = subprocess.run(cmd, cwd=str(cwd))
    if proc.returncode != 0:
        print("-" * 180)
        print(f"  STEP FAILED: {label} returned exit code {proc.returncode}")
        if not continue_on_error:
            return proc.returncode
    return proc.returncode


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run full trade idea desk cycle")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--radar-dir", default="artifacts/trade_idea_radar")
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--top-n", type=int, default=15)
    p.add_argument("--per-bucket", type=int, default=8)
    p.add_argument("--default-notional", type=float, default=10_000.0)
    p.add_argument("--open-watchlist", action="store_true", default=True, help="Create pending paper orders for watchlist tickets")
    p.add_argument("--no-open-watchlist", dest="open_watchlist", action="store_false", help="Only open active tickets; do not create pending watchlist orders")
    p.add_argument("--open-priorities", nargs="+", default=["A", "B"])
    p.add_argument("--min-score", type=float, default=80.0)
    p.add_argument("--max-new-trades", type=int, default=10)
    p.add_argument("--print-limit", type=int, default=30)
    p.add_argument("--cancel-stale-pending", action="store_true", default=True, help="Cancel pending orders when radar support weakens or ages out")
    p.add_argument("--no-cancel-stale-pending", dest="cancel_stale_pending", action="store_false")
    p.add_argument("--cancel-pending-after-days", type=int, default=10)
    p.add_argument("--cancel-pending-if-distance-gt-pct", type=float, default=3.0)
    p.add_argument("--snapshot-id", default=None, help="Optional deterministic snapshot id passed to scanner and event logger")
    p.add_argument("--run-date", default=None, help="Optional run date passed to ledger/event logger")
    p.add_argument("--continue-on-error", action="store_true")
    p.add_argument("--skip-scan", action="store_true")
    p.add_argument("--skip-ledger", action="store_true")
    p.add_argument("--skip-events", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    root = _repo_root()
    py = sys.executable
    failures: list[tuple[str, int]] = []

    if not args.skip_scan:
        scan_cmd = [
            py,
            "scripts/scan_trade_ideas.py",
            "--data-dir", args.data_dir,
            "--start", args.start,
            "--end", args.end,
            "--top-n", str(args.top_n),
            "--per-bucket", str(args.per_bucket),
            "--out-dir", args.radar_dir,
        ]
        if args.snapshot_id:
            scan_cmd.extend(["--snapshot-id", args.snapshot_id])
        rc = _run_step("SCAN TRADE IDEAS", scan_cmd, root, args.continue_on_error)
        if rc != 0:
            failures.append(("scan", rc))
            if not args.continue_on_error:
                raise SystemExit(rc)

    if not args.skip_ledger:
        ledger_cmd = [
            py,
            "scripts/update_trade_idea_paper_ledger.py",
            "--data-dir", args.data_dir,
            "--radar-dir", args.radar_dir,
            "--start", args.start,
            "--end", args.end,
            "--default-notional", str(args.default_notional),
            "--min-score", str(args.min_score),
            "--max-new-trades", str(args.max_new_trades),
            "--print-limit", str(args.print_limit),
            "--cancel-pending-after-days", str(args.cancel_pending_after_days),
            "--cancel-pending-if-distance-gt-pct", str(args.cancel_pending_if_distance_gt_pct),
            "--open-priorities",
            *args.open_priorities,
        ]
        if args.open_watchlist:
            ledger_cmd.append("--open-watchlist")
        if args.cancel_stale_pending:
            ledger_cmd.append("--cancel-stale-pending")
        else:
            ledger_cmd.append("--no-cancel-stale-pending")
        if args.run_date:
            ledger_cmd.extend(["--run-date", args.run_date])
        rc = _run_step("UPDATE PAPER LEDGER", ledger_cmd, root, args.continue_on_error)
        if rc != 0:
            failures.append(("ledger", rc))
            if not args.continue_on_error:
                raise SystemExit(rc)

    if not args.skip_events:
        events_cmd = [
            py,
            "scripts/log_trade_idea_paper_events.py",
            "--radar-dir", args.radar_dir,
        ]
        if args.snapshot_id:
            events_cmd.extend(["--snapshot-id", args.snapshot_id])
        if args.run_date:
            events_cmd.extend(["--run-date", args.run_date])
        rc = _run_step("LOG PAPER EVENTS", events_cmd, root, args.continue_on_error)
        if rc != 0:
            failures.append(("events", rc))
            if not args.continue_on_error:
                raise SystemExit(rc)

    print("\n" + "=" * 180)
    print("  TRADE IDEA DESK CYCLE COMPLETE")
    print("=" * 180)
    if failures:
        print("  Failures:")
        for label, rc in failures:
            print(f"  - {label}: exit code {rc}")
        raise SystemExit(failures[0][1])
    print("  All enabled steps completed successfully.")
    print(f"  Radar dir: {args.radar_dir}")
    print("  Verdict : PAPER ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
