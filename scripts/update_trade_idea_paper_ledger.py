#!/usr/bin/env python
"""Paper trade ledger for the trade idea radar.

Reads the latest trade_tickets.csv from artifacts/trade_idea_radar, opens paper
trades from selected active/high-priority tickets, updates open trades using the
latest local close data, and marks trades as target_hit, stop_hit, expired, or
still open.

Research/paper only. No runtime, broker, or live execution code is modified.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from scripts.scan_trade_ideas import CRYPTO_FILE_MAP
from scripts.run_state_confirmed_risk_off_sweep import _load_close


OPEN_STATUS = "open"
CLOSED_STATUSES = {"target_hit", "stop_hit", "expired", "manual_closed"}


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


def _eligible_ticket(row: pd.Series, args: argparse.Namespace) -> bool:
    if str(row.get("direction", "LONG")) != "LONG":
        return False
    if str(row.get("status", "")) != "active" and not args.open_watchlist:
        return False
    priority = str(row.get("priority", ""))
    if priority not in set(args.open_priorities):
        return False
    try:
        score = float(row.get("score", 0.0))
    except (TypeError, ValueError):
        return False
    return score >= args.min_score


def _trade_key(row: pd.Series) -> str:
    return "|".join([
        str(row.get("ticker", "")),
        str(row.get("setup", "")),
        str(row.get("trigger", "")),
        str(row.get("stop", "")),
        str(row.get("target", "")),
    ])


def _existing_open_keys(ledger: pd.DataFrame) -> set[str]:
    if ledger.empty or "status" not in ledger.columns:
        return set()
    open_rows = ledger[ledger["status"] == OPEN_STATUS]
    return set(open_rows.get("trade_key", pd.Series(dtype=str)).astype(str))


def _new_trade_from_ticket(row: pd.Series, run_date: str, data_dir: Path, start: str, end: str, default_notional: float) -> dict[str, Any]:
    ticker = str(row.get("ticker"))
    close_date, close_px = _last_close(data_dir, ticker, start, end)
    entry_price = close_px if close_px is not None else float(row.get("close"))
    stop = float(row.get("stop"))
    target = float(row.get("target"))
    notional = default_notional
    qty = notional / entry_price if entry_price > 0 else 0.0
    horizon_days = int(float(row.get("horizon_days", 20)))
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
        "entry_date": close_date or run_date,
        "opened_at_run": run_date,
        "entry_price": entry_price,
        "last_date": close_date or run_date,
        "last_price": entry_price,
        "stop": stop,
        "target": target,
        "notional": notional,
        "qty": qty,
        "horizon_days": horizon_days,
        "days_open": 0,
        "status": OPEN_STATUS,
        "exit_date": "",
        "exit_price": "",
        "exit_reason": "",
        "unrealized_pnl": 0.0,
        "unrealized_return_pct": 0.0,
        "realized_pnl": "",
        "realized_return_pct": "",
        "why": row.get("why"),
        "invalidation": row.get("invalidation"),
    }


def _update_trade(row: pd.Series, data_dir: Path, start: str, end: str) -> dict[str, Any]:
    out = row.to_dict()
    if str(out.get("status")) != OPEN_STATUS:
        return out
    ticker = str(out.get("ticker"))
    close_date, last_px = _last_close(data_dir, ticker, start, end)
    if close_date is None or last_px is None:
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

    status = OPEN_STATUS
    exit_reason = ""
    exit_price: float | str = ""
    exit_date: str = ""
    realized_pnl: float | str = ""
    realized_return_pct: float | str = ""

    if last_px <= stop:
        status = "stop_hit"
        exit_reason = "close_at_or_below_stop"
        exit_price = last_px
        exit_date = close_date
        realized_pnl = pnl
        realized_return_pct = ret_pct
    elif last_px >= target:
        status = "target_hit"
        exit_reason = "close_at_or_above_target"
        exit_price = last_px
        exit_date = close_date
        realized_pnl = pnl
        realized_return_pct = ret_pct
    elif days_open >= int(float(out.get("horizon_days", 20))):
        status = "expired"
        exit_reason = "horizon_elapsed"
        exit_price = last_px
        exit_date = close_date
        realized_pnl = pnl
        realized_return_pct = ret_pct

    out.update({
        "last_date": close_date,
        "last_price": last_px,
        "days_open": days_open,
        "status": status,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "unrealized_pnl": pnl if status == OPEN_STATUS else "",
        "unrealized_return_pct": ret_pct if status == OPEN_STATUS else "",
        "realized_pnl": realized_pnl,
        "realized_return_pct": realized_return_pct,
    })
    return out


def _summarize(ledger: pd.DataFrame) -> dict[str, Any]:
    if ledger.empty:
        return {"total_trades": 0, "open_trades": 0, "closed_trades": 0}
    status = ledger.get("status", pd.Series(dtype=str)).astype(str)
    closed = ledger[status.isin(CLOSED_STATUSES)]
    open_trades = ledger[status == OPEN_STATUS]
    summary: dict[str, Any] = {
        "total_trades": int(len(ledger)),
        "open_trades": int(len(open_trades)),
        "closed_trades": int(len(closed)),
    }
    if not closed.empty and "realized_return_pct" in closed.columns:
        rets = pd.to_numeric(closed["realized_return_pct"], errors="coerce").dropna()
        pnl = pd.to_numeric(closed["realized_pnl"], errors="coerce").dropna()
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


def _print_ledger(ledger: pd.DataFrame, summary: dict[str, Any], limit: int) -> None:
    print("=" * 150)
    print("  TRADE IDEA RADAR — PAPER LEDGER")
    print("=" * 150)
    print(
        f"  Total={summary.get('total_trades', 0)}  Open={summary.get('open_trades', 0)}  Closed={summary.get('closed_trades', 0)}  "
        f"RealizedPnL={summary.get('total_realized_pnl', 0.0):,.2f}  OpenUPnL={summary.get('open_unrealized_pnl', 0.0):,.2f}"
    )
    if ledger.empty:
        print("  No paper trades in ledger.")
        print("=" * 150)
        return
    view = ledger.sort_values(["status", "score"], ascending=[True, False]).head(limit)
    print("-" * 150)
    print(f"  {'Ticker':<8} {'Status':<12} {'Setup':<27} {'Pri':<3} {'Score':>7} {'Entry':>10} {'Last':>10} {'Stop':>10} {'Target':>10} {'Days':>5} {'Ret%':>8}")
    for _, r in view.iterrows():
        ret = r.get("unrealized_return_pct") if str(r.get("status")) == OPEN_STATUS else r.get("realized_return_pct")
        try:
            ret_s = f"{float(ret):.2f}%"
        except (TypeError, ValueError):
            ret_s = "n/a"
        print(
            f"  {str(r.get('ticker')):<8} {str(r.get('status')):<12} {str(r.get('setup')):<27} {str(r.get('priority')):<3} "
            f"{float(r.get('score')):>7.1f} {float(r.get('entry_price')):>10.2f} {float(r.get('last_price')):>10.2f} "
            f"{float(r.get('stop')):>10.2f} {float(r.get('target')):>10.2f} {int(float(r.get('days_open'))):>5} {ret_s:>8}"
        )
    print("=" * 150)


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
    p.add_argument("--open-watchlist", action="store_true", help="Also open non-active watchlist tickets if priority/score gates pass")
    p.add_argument("--max-new-trades", type=int, default=10)
    p.add_argument("--print-limit", type=int, default=30)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    radar_dir = Path(args.radar_dir)
    tickets_path = Path(args.tickets_file) if args.tickets_file else radar_dir / "trade_tickets.csv"
    ledger_path = Path(args.ledger_file) if args.ledger_file else radar_dir / "paper_ledger.csv"
    run_date = args.run_date or datetime.now().date().isoformat()

    tickets = _read_csv(tickets_path)
    ledger = _read_csv(ledger_path)

    updated_rows = []
    if not ledger.empty:
        for _, row in ledger.iterrows():
            updated_rows.append(_update_trade(row, Path(args.data_dir), args.start, args.end))
    ledger = pd.DataFrame(updated_rows) if updated_rows else pd.DataFrame()

    open_keys = _existing_open_keys(ledger)
    new_rows: list[dict[str, Any]] = []
    if not tickets.empty:
        for _, row in tickets.iterrows():
            if len(new_rows) >= args.max_new_trades:
                break
            if not _eligible_ticket(row, args):
                continue
            key = _trade_key(row)
            if key in open_keys:
                continue
            new_rows.append(_new_trade_from_ticket(row, run_date, Path(args.data_dir), args.start, args.end, args.default_notional))

    if new_rows:
        ledger = pd.concat([ledger, pd.DataFrame(new_rows)], ignore_index=True) if not ledger.empty else pd.DataFrame(new_rows)

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(ledger_path, index=False)
    summary = _summarize(ledger)
    (radar_dir / "paper_ledger_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _print_ledger(ledger, summary, args.print_limit)
    print(f"  Tickets file : {tickets_path}")
    print(f"  Ledger file  : {ledger_path}")
    print(f"  New trades   : {len(new_rows)}")
    print("  Verdict      : PAPER ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
