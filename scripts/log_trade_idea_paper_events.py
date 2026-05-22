#!/usr/bin/env python
"""Event logger for the trade idea radar paper ledger.

Reads artifacts/trade_idea_radar/paper_ledger.csv, snapshots the ledger, compares
it against the prior ledger snapshot, and appends material lifecycle events to
paper_ledger_events.csv.

This is a companion to update_trade_idea_paper_ledger.py. It does not modify the
ledger or any runtime/broker code.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PENDING_STATUS = "pending"
OPEN_STATUS = "open"
CLOSED_STATUSES = {"target_hit", "stop_hit", "expired", "manual_closed", "cancelled"}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def _trade_key(row: pd.Series | dict[str, Any]) -> str:
    value = row.get("trade_id")
    if value is not None and str(value) and str(value).lower() != "nan":
        return str(value)
    value = row.get("trade_key")
    if value is not None and str(value) and str(value).lower() != "nan":
        return str(value)
    return "|".join([
        str(row.get("ticker", "")),
        str(row.get("setup", "")),
        str(row.get("trigger", "")),
        str(row.get("stop", "")),
        str(row.get("target", "")),
    ])


def _latest_snapshot(snapshot_dir: Path) -> Path | None:
    files = sorted(snapshot_dir.glob("paper_ledger_*.csv"))
    return files[-1] if files else None


def _event_type(prev: dict[str, Any] | None, cur: dict[str, Any]) -> str | None:
    cur_status = str(cur.get("status", ""))
    if prev is None:
        if cur_status == PENDING_STATUS:
            return "new_pending"
        if cur_status == OPEN_STATUS:
            return "new_open"
        if cur_status in CLOSED_STATUSES:
            return f"new_{cur_status}"
        return "new_row"

    prev_status = str(prev.get("status", ""))
    if prev_status == PENDING_STATUS and cur_status == OPEN_STATUS:
        return "activated"
    if prev_status in {PENDING_STATUS, OPEN_STATUS} and cur_status in CLOSED_STATUSES:
        return cur_status
    if prev_status != cur_status:
        return "status_changed"
    return None


def _event_row(run_id: str, run_date: str, event_type: str, cur: dict[str, Any], prev: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_date": run_date,
        "event_type": event_type,
        "ticker": cur.get("ticker"),
        "trade_id": cur.get("trade_id"),
        "trade_key": cur.get("trade_key"),
        "bucket": cur.get("bucket"),
        "trade_type": cur.get("trade_type"),
        "setup": cur.get("setup"),
        "priority": cur.get("priority"),
        "score": cur.get("score"),
        "previous_status": None if prev is None else prev.get("status"),
        "status": cur.get("status"),
        "last_date": cur.get("last_date"),
        "last_price": cur.get("last_price"),
        "trigger": cur.get("trigger"),
        "entry_date": cur.get("entry_date"),
        "entry_price": cur.get("entry_price"),
        "exit_date": cur.get("exit_date"),
        "exit_price": cur.get("exit_price"),
        "exit_reason": cur.get("exit_reason"),
        "realized_pnl": cur.get("realized_pnl"),
        "realized_return_pct": cur.get("realized_return_pct"),
        "unrealized_pnl": cur.get("unrealized_pnl"),
        "unrealized_return_pct": cur.get("unrealized_return_pct"),
        "days_pending": cur.get("days_pending"),
        "days_open": cur.get("days_open"),
    }


def _print_events(events: list[dict[str, Any]], previous_snapshot: Path | None, current_snapshot: Path) -> None:
    print("=" * 156)
    print("  TRADE IDEA RADAR — PAPER LEDGER EVENTS")
    print("=" * 156)
    if previous_snapshot is None:
        print("  No previous paper-ledger snapshot found. Current ledger saved as baseline.")
    else:
        print(f"  Compared against: {previous_snapshot}")
    print(f"  Current snapshot: {current_snapshot}")
    print("-" * 156)
    if not events:
        print("  No material paper-ledger lifecycle events.")
        print("=" * 156)
        return
    print(f"  {'#':>3} {'Event':<14} {'Ticker':<8} {'Prev':<12} {'Status':<12} {'Setup':<27} {'Pri':<3} {'Score':>7} {'Last':>10} {'Entry':>10} {'Exit':>10} {'Ret%':>8}")
    for i, e in enumerate(events, start=1):
        def fmt(x: Any) -> str:
            if x is None or str(x).lower() == "nan" or str(x) == "":
                return ""
            return str(x)
        print(
            f"  {i:>3} {fmt(e.get('event_type')):<14} {fmt(e.get('ticker')):<8} {fmt(e.get('previous_status')):<12} "
            f"{fmt(e.get('status')):<12} {fmt(e.get('setup')):<27} {fmt(e.get('priority')):<3} "
            f"{float(e.get('score') or 0.0):>7.1f} {fmt(e.get('last_price')):>10} {fmt(e.get('entry_price')):>10} "
            f"{fmt(e.get('exit_price')):>10} {fmt(e.get('realized_return_pct')):>8}"
        )
    print("=" * 156)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Log lifecycle events from the trade idea paper ledger")
    p.add_argument("--radar-dir", default="artifacts/trade_idea_radar")
    p.add_argument("--ledger-file", default=None)
    p.add_argument("--events-file", default=None)
    p.add_argument("--snapshot-id", default=None)
    p.add_argument("--run-date", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    radar_dir = Path(args.radar_dir)
    ledger_path = Path(args.ledger_file) if args.ledger_file else radar_dir / "paper_ledger.csv"
    events_path = Path(args.events_file) if args.events_file else radar_dir / "paper_ledger_events.csv"
    snapshot_dir = radar_dir / "paper_ledger_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    ledger = _read_csv(ledger_path)
    if ledger.empty:
        raise SystemExit(f"No ledger rows found at {ledger_path}")

    previous_snapshot = _latest_snapshot(snapshot_dir)
    previous = _read_csv(previous_snapshot) if previous_snapshot is not None else pd.DataFrame()
    prev_by_key = {_trade_key(row): row.to_dict() for _, row in previous.iterrows()} if not previous.empty else {}

    run_id = args.snapshot_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_date = args.run_date or datetime.now().date().isoformat()
    current_snapshot = snapshot_dir / f"paper_ledger_{run_id}.csv"
    ledger.to_csv(current_snapshot, index=False)
    (radar_dir / "latest_paper_ledger_snapshot_path.txt").write_text(str(current_snapshot), encoding="utf-8")

    events: list[dict[str, Any]] = []
    if previous_snapshot is not None:
        for _, row in ledger.iterrows():
            cur = row.to_dict()
            prev = prev_by_key.get(_trade_key(cur))
            event_type = _event_type(prev, cur)
            if event_type is not None:
                events.append(_event_row(run_id, run_date, event_type, cur, prev))

    if events:
        existing = _read_csv(events_path)
        combined = pd.concat([existing, pd.DataFrame(events)], ignore_index=True) if not existing.empty else pd.DataFrame(events)
        combined.to_csv(events_path, index=False)
    elif not events_path.exists():
        pd.DataFrame(columns=[
            "run_id", "run_date", "event_type", "ticker", "trade_id", "trade_key", "bucket", "trade_type",
            "setup", "priority", "score", "previous_status", "status", "last_date", "last_price", "trigger",
            "entry_date", "entry_price", "exit_date", "exit_price", "exit_reason", "realized_pnl",
            "realized_return_pct", "unrealized_pnl", "unrealized_return_pct", "days_pending", "days_open",
        ]).to_csv(events_path, index=False)

    _print_events(events, previous_snapshot, current_snapshot)
    print(f"  Ledger file : {ledger_path}")
    print(f"  Events file : {events_path}")
    print("  Verdict     : PAPER ONLY; lifecycle event logging only.\n")


if __name__ == "__main__":
    main()
