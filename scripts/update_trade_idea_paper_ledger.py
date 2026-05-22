#!/usr/bin/env python
"""Paper trade ledger for the trade idea radar.

Reads the latest trade_tickets.csv from artifacts/trade_idea_radar, creates
pending paper orders from watchlist tickets, opens active paper trades, updates
open trades using the latest local close data, cancels stale/invalid pending
orders, and marks open trades as target_hit, stop_hit, expired, or still open.

Research/paper only. No runtime, broker, or live execution code is modified.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from scripts.scan_trade_ideas import CRYPTO_FILE_MAP
from scripts.run_state_confirmed_risk_off_sweep import _load_close


PENDING_STATUS = "pending"
OPEN_STATUS = "open"
CANCELLED_STATUS = "cancelled"
CLOSED_STATUSES = {"target_hit", "stop_hit", "expired", "manual_closed", CANCELLED_STATUS}
ACTIVE_STATUSES = {PENDING_STATUS, OPEN_STATUS}


def _data_path(data_dir: Path, ticker: str) -> Path:
    return data_dir / CRYPTO_FILE_MAP[ticker] if ticker in CRYPTO_FILE_MAP else data_dir / f"{ticker}_1D.csv"


def _load_close_for_ticker(data_dir: Path, ticker: str, start: str, end: str) -> pd.Series | None:
    path = _data_path(data_dir, ticker)
    if not path.exists():
        return None
    try:
        return _load_close(str(path), ticker, start, end).dropna()
    except Exception as exc:  # pragma: no cover - ledger should keep going.
        print(f"WARN: failed to load close data for {ticker}: {exc}", file=sys.stderr)
        return None


def _last_close(data_dir: Path, ticker: str, start: str, end: str) -> tuple[str | None, float | None]:
    close = _load_close_for_ticker(data_dir, ticker, start, end)
    if close is None or close.empty:
        return None, None
    return close.index[-1].date().isoformat(), float(close.iloc[-1])


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def _ticket_status(row: pd.Series) -> str:
    return str(row.get("status", ""))


def _eligible_ticket(row: pd.Series, args: argparse.Namespace) -> bool:
    if str(row.get("direction", "LONG")) != "LONG":
        return False
    status = _ticket_status(row)
    if status != "active" and not args.open_watchlist:
        return False
    priority = str(row.get("priority", ""))
    if priority not in set(args.open_priorities):
        return False
    try:
        score = float(row.get("score", 0.0))
    except (TypeError, ValueError):
        return False
    return score >= args.min_score


def _trade_key(row: pd.Series | dict[str, Any]) -> str:
    return "|".join([
        str(row.get("ticker", "")),
        str(row.get("setup", "")),
        str(row.get("trigger", "")),
        str(row.get("stop", "")),
        str(row.get("target", "")),
    ])


def _existing_active_keys(ledger: pd.DataFrame) -> set[str]:
    if ledger.empty or "status" not in ledger.columns:
        return set()
    active_rows = ledger[ledger["status"].astype(str).isin(ACTIVE_STATUSES)]
    return set(active_rows.get("trade_key", pd.Series(dtype=str)).astype(str))


def _tickets_by_key(tickets: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if tickets.empty:
        return {}
    return {_trade_key(row): row.to_dict() for _, row in tickets.iterrows()}


def _base_trade_from_ticket(row: pd.Series, run_date: str, data_dir: Path, start: str, end: str, default_notional: float) -> dict[str, Any]:
    ticker = str(row.get("ticker"))
    close_date, close_px = _last_close(data_dir, ticker, start, end)
    last_price = close_px if close_px is not None else float(row.get("close"))
    trigger = float(row.get("trigger"))
    stop = float(row.get("stop"))
    target = float(row.get("target"))
    horizon_days = int(float(row.get("horizon_days", 20)))
    ticket_status = _ticket_status(row)
    should_open_now = ticket_status == "active" or last_price >= trigger
    entry_price: float | str = last_price if should_open_now else ""
    qty: float | str = (default_notional / last_price) if should_open_now and last_price > 0 else ""
    status = OPEN_STATUS if should_open_now else PENDING_STATUS
    return {
        "trade_id": f"{ticker}_{row.get('setup')}_{run_date}_{abs(hash(_trade_key(row))) % 1_000_000}",
        "trade_key": _trade_key(row),
        "ticker": ticker,
        "direction": "LONG",
        "bucket": row.get("bucket"),
        "trade_type": row.get("trade_type"),
        "setup": row.get("setup"),
        "priority": row.get("priority"),
        "score": row.get("score"),
        "ticket_status_at_creation": ticket_status,
        "created_at_run": run_date,
        "pending_since": "" if should_open_now else (close_date or run_date),
        "trigger": trigger,
        "entry_date": close_date if should_open_now else "",
        "opened_at_run": run_date if should_open_now else "",
        "entry_price": entry_price,
        "last_date": close_date or run_date,
        "last_price": last_price,
        "stop": stop,
        "target": target,
        "notional": default_notional,
        "qty": qty,
        "horizon_days": horizon_days,
        "days_pending": 0,
        "days_open": 0,
        "status": status,
        "exit_date": "",
        "exit_price": "",
        "exit_reason": "",
        "unrealized_pnl": 0.0 if should_open_now else "",
        "unrealized_return_pct": 0.0 if should_open_now else "",
        "realized_pnl": "",
        "realized_return_pct": "",
        "cancel_date": "",
        "cancel_reason": "",
        "why": row.get("why"),
        "invalidation": row.get("invalidation"),
    }


def _activate_pending(out: dict[str, Any], close_date: str, last_px: float, run_date: str) -> dict[str, Any]:
    notional = float(out.get("notional", 0.0))
    qty = notional / last_px if last_px > 0 else 0.0
    out.update({
        "status": OPEN_STATUS,
        "entry_date": close_date,
        "opened_at_run": run_date,
        "entry_price": last_px,
        "qty": qty,
        "days_open": 0,
        "unrealized_pnl": 0.0,
        "unrealized_return_pct": 0.0,
    })
    return out


def _cancel_pending(out: dict[str, Any], cancel_date: str, reason: str) -> dict[str, Any]:
    out.update({
        "status": CANCELLED_STATUS,
        "cancel_date": cancel_date,
        "cancel_reason": reason,
        "exit_date": cancel_date,
        "exit_reason": reason,
        "unrealized_pnl": "",
        "unrealized_return_pct": "",
    })
    return out


def _pending_cancel_reason(out: dict[str, Any], ticket: dict[str, Any] | None, args: argparse.Namespace) -> str | None:
    if not args.cancel_stale_pending:
        return None
    if ticket is None:
        return "ticket_missing_from_radar"

    priority = str(ticket.get("priority", ""))
    if priority not in set(args.open_priorities):
        return f"priority_below_gate:{priority}"

    try:
        score = float(ticket.get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    if score < args.min_score:
        return f"score_below_gate:{score:.1f}"

    try:
        distance = abs(float(ticket.get("distance_to_trigger_pct", 0.0)))
    except (TypeError, ValueError):
        distance = 0.0
    if distance > args.cancel_pending_if_distance_gt_pct:
        return f"too_far_from_trigger:{distance:.2f}%"

    try:
        days_pending = int(float(out.get("days_pending", 0)))
    except (TypeError, ValueError):
        days_pending = 0
    if days_pending > args.cancel_pending_after_days:
        return f"pending_age_exceeded:{days_pending}d"

    return None


def _update_trade(
    row: pd.Series,
    data_dir: Path,
    start: str,
    end: str,
    run_date: str,
    tickets_by_key: dict[str, dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    out = row.to_dict()
    status = str(out.get("status"))
    if status not in ACTIVE_STATUSES:
        return out

    ticker = str(out.get("ticker"))
    close_date, last_px = _last_close(data_dir, ticker, start, end)
    if close_date is None or last_px is None:
        return out
    out["last_date"] = close_date
    out["last_price"] = last_px

    if status == PENDING_STATUS:
        pending_since = out.get("pending_since") or out.get("created_at_run") or close_date
        out["days_pending"] = max(0, int((pd.Timestamp(close_date) - pd.Timestamp(pending_since)).days))
        trigger = float(out.get("trigger"))
        if last_px >= trigger:
            return _activate_pending(out, close_date, last_px, run_date)
        reason = _pending_cancel_reason(out, tickets_by_key.get(str(out.get("trade_key"))), args)
        if reason:
            return _cancel_pending(out, close_date, reason)
        return out

    entry_price = float(out.get("entry_price"))
    stop = float(out.get("stop"))
    target = float(out.get("target"))
    qty = float(out.get("qty"))
    entry_date = pd.Timestamp(out.get("entry_date"))
    last_date = pd.Timestamp(close_date)
    days_open = max(0, int((last_date - entry_date).days))
    pnl = (last_px - entry_price) * qty
    ret_pct = (last_px / entry_price - 1.0) * 100.0 if entry_price > 0 else 0.0

    final_status = OPEN_STATUS
    exit_reason = ""
    exit_price: float | str = ""
    exit_date: str = ""
    realized_pnl: float | str = ""
    realized_return_pct: float | str = ""

    if last_px <= stop:
        final_status = "stop_hit"
        exit_reason = "close_at_or_below_stop"
        exit_price = last_px
        exit_date = close_date
        realized_pnl = pnl
        realized_return_pct = ret_pct
    elif last_px >= target:
        final_status = "target_hit"
        exit_reason = "close_at_or_above_target"
        exit_price = last_px
        exit_date = close_date
        realized_pnl = pnl
        realized_return_pct = ret_pct
    elif days_open >= int(float(out.get("horizon_days", 20))):
        final_status = "expired"
        exit_reason = "horizon_elapsed"
        exit_price = last_px
        exit_date = close_date
        realized_pnl = pnl
        realized_return_pct = ret_pct

    out.update({
        "days_open": days_open,
        "status": final_status,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "unrealized_pnl": pnl if final_status == OPEN_STATUS else "",
        "unrealized_return_pct": ret_pct if final_status == OPEN_STATUS else "",
        "realized_pnl": realized_pnl,
        "realized_return_pct": realized_return_pct,
    })
    return out


def _summarize(ledger: pd.DataFrame) -> dict[str, Any]:
    if ledger.empty:
        return {"total_trades": 0, "pending_trades": 0, "open_trades": 0, "closed_trades": 0, "cancelled_trades": 0}
    status = ledger.get("status", pd.Series(dtype=str)).astype(str)
    pending = ledger[status == PENDING_STATUS]
    open_trades = ledger[status == OPEN_STATUS]
    cancelled = ledger[status == CANCELLED_STATUS]
    closed = ledger[status.isin(CLOSED_STATUSES)]
    summary: dict[str, Any] = {
        "total_trades": int(len(ledger)),
        "pending_trades": int(len(pending)),
        "open_trades": int(len(open_trades)),
        "closed_trades": int(len(closed)),
        "cancelled_trades": int(len(cancelled)),
    }
    realized = ledger[status.isin({"target_hit", "stop_hit", "expired", "manual_closed"})]
    if not realized.empty and "realized_return_pct" in realized.columns:
        rets = pd.to_numeric(realized["realized_return_pct"], errors="coerce").dropna()
        pnl = pd.to_numeric(realized["realized_pnl"], errors="coerce").dropna()
        if not rets.empty:
            summary.update({
                "win_rate_pct": float((rets > 0).mean() * 100.0),
                "avg_realized_return_pct": float(rets.mean()),
                "median_realized_return_pct": float(rets.median()),
            })
        if not pnl.empty:
            summary["total_realized_pnl"] = float(pnl.sum())
    if not open_trades.empty and "unrealized_pnl" in open_trades.columns:
        upnl = pd.to_numeric(open_trades["unrealized_pnl"], errors="coerce").dropna()
        if not upnl.empty:
            summary["open_unrealized_pnl"] = float(upnl.sum())
    return summary


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _display_price(value: Any) -> str:
    try:
        if value == "" or pd.isna(value):
            return "pending"
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "pending"


def _display_return(value: Any, status: str) -> str:
    if status in {PENDING_STATUS, CANCELLED_STATUS}:
        return "n/a"
    try:
        if value == "" or pd.isna(value):
            return "n/a"
        v = float(value)
        if math.isnan(v):
            return "n/a"
        return f"{v:.2f}%"
    except (TypeError, ValueError):
        return "n/a"


def _trigger_distance_pct(row: pd.Series) -> str:
    last = _safe_float(row.get("last_price"))
    trigger = _safe_float(row.get("trigger"))
    if last <= 0 or trigger <= 0:
        return "n/a"
    return f"{(trigger / last - 1.0) * 100.0:.2f}%"


def _print_ledger(ledger: pd.DataFrame, summary: dict[str, Any], limit: int) -> None:
    print("=" * 184)
    print("  TRADE IDEA RADAR — PAPER LEDGER")
    print("=" * 184)
    print(
        f"  Total={summary.get('total_trades', 0)}  Pending={summary.get('pending_trades', 0)}  "
        f"Open={summary.get('open_trades', 0)}  Closed={summary.get('closed_trades', 0)}  Cancelled={summary.get('cancelled_trades', 0)}  "
        f"RealizedPnL={summary.get('total_realized_pnl', 0.0):,.2f}  OpenUPnL={summary.get('open_unrealized_pnl', 0.0):,.2f}"
    )
    if ledger.empty:
        print("  No paper trades in ledger.")
        print("=" * 184)
        return
    status_order = {OPEN_STATUS: 0, PENDING_STATUS: 1, "target_hit": 2, "stop_hit": 3, "expired": 4, CANCELLED_STATUS: 5}
    view = ledger.copy()
    view["_status_order"] = view["status"].map(status_order).fillna(9)
    view = view.sort_values(["_status_order", "score"], ascending=[True, False]).head(limit)
    print("-" * 184)
    print(f"  {'Ticker':<8} {'Status':<12} {'Setup':<27} {'Pri':<3} {'Score':>7} {'Entry':>10} {'Last':>10} {'Trigger':>10} {'TrigDist':>9} {'Stop':>10} {'Target':>10} {'Days':>5} {'Ret%':>8} {'Reason':<24}")
    for _, r in view.iterrows():
        status = str(r.get("status"))
        ret = r.get("unrealized_return_pct") if status == OPEN_STATUS else r.get("realized_return_pct")
        ret_s = _display_return(ret, status)
        days = r.get("days_open") if status == OPEN_STATUS else r.get("days_pending")
        reason = str(r.get("cancel_reason") or r.get("exit_reason") or "")
        if reason.lower() == "nan":
            reason = ""
        print(
            f"  {str(r.get('ticker')):<8} {status:<12} {str(r.get('setup')):<27} {str(r.get('priority')):<3} "
            f"{_safe_float(r.get('score')):>7.1f} {_display_price(r.get('entry_price')):>10} {_safe_float(r.get('last_price')):>10.2f} "
            f"{_safe_float(r.get('trigger')):>10.2f} {_trigger_distance_pct(r):>9} {_safe_float(r.get('stop')):>10.2f} {_safe_float(r.get('target')):>10.2f} {int(_safe_float(days)):>5} {ret_s:>8} {reason:<24}"
        )
    print("=" * 184)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Update paper ledger for trade idea radar tickets")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--radar-dir", default="artifacts/trade_idea_radar")
    p.add_argument("--tickets-file", default=None)
    p.add_argument("--ledger-file", default=None)
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--run-date", default=None)
    p.add_argument("--default-notional", type=float, default=10_000.0)
    p.add_argument("--open-priorities", nargs="+", default=["A", "B"])
    p.add_argument("--min-score", type=float, default=80.0)
    p.add_argument("--open-watchlist", action="store_true", help="Create pending paper orders for non-active watchlist tickets if priority/score gates pass")
    p.add_argument("--max-new-trades", type=int, default=10)
    p.add_argument("--print-limit", type=int, default=30)
    p.add_argument("--cancel-stale-pending", action="store_true", default=True, help="Cancel pending orders when radar support weakens or ages out")
    p.add_argument("--no-cancel-stale-pending", dest="cancel_stale_pending", action="store_false")
    p.add_argument("--cancel-pending-after-days", type=int, default=10)
    p.add_argument("--cancel-pending-if-distance-gt-pct", type=float, default=3.0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    radar_dir = Path(args.radar_dir)
    tickets_path = Path(args.tickets_file) if args.tickets_file else radar_dir / "trade_tickets.csv"
    ledger_path = Path(args.ledger_file) if args.ledger_file else radar_dir / "paper_ledger.csv"
    run_date = args.run_date or datetime.now().date().isoformat()

    tickets = _read_csv(tickets_path)
    ledger = _read_csv(ledger_path)
    current_tickets_by_key = _tickets_by_key(tickets)

    updated_rows = []
    if not ledger.empty:
        for _, row in ledger.iterrows():
            updated_rows.append(_update_trade(row, Path(args.data_dir), args.start, args.end, run_date, current_tickets_by_key, args))
    ledger = pd.DataFrame(updated_rows) if updated_rows else pd.DataFrame()

    active_keys = _existing_active_keys(ledger)
    new_rows: list[dict[str, Any]] = []
    if not tickets.empty:
        for _, row in tickets.iterrows():
            if len(new_rows) >= args.max_new_trades:
                break
            if not _eligible_ticket(row, args):
                continue
            key = _trade_key(row)
            if key in active_keys:
                continue
            new_rows.append(_base_trade_from_ticket(row, run_date, Path(args.data_dir), args.start, args.end, args.default_notional))
            active_keys.add(key)

    if new_rows:
        ledger = pd.concat([ledger, pd.DataFrame(new_rows)], ignore_index=True) if not ledger.empty else pd.DataFrame(new_rows)

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(ledger_path, index=False)
    summary = _summarize(ledger)
    (radar_dir / "paper_ledger_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _print_ledger(ledger, summary, args.print_limit)
    print(f"  Tickets file : {tickets_path}")
    print(f"  Ledger file  : {ledger_path}")
    print(f"  New rows     : {len(new_rows)}")
    print("  Verdict      : PAPER ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
