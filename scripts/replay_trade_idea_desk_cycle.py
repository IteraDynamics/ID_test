#!/usr/bin/env python
"""Historical replay for the trade idea desk cycle.

This replays the same radar -> pending/open trade -> lifecycle idea over a
historical window using only data available up to each replay date.

Mechanics are intentionally conservative with daily close data:

1. Existing pending/open trades are updated using the current close.
2. The radar is scanned using data through the current close.
3. New orders are created after that close and are not eligible to fill until a
   later bar.
4. Pending orders activate when a later close is at/above trigger.
5. Open trades close on close-based stop, target, or horizon expiry.
6. Stale pending orders cancel when radar support weakens, distance widens, or
   age exceeds the configured pending limit.

Research/paper only. No runtime, broker, or live execution code is modified.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from scripts.scan_trade_ideas import DEFAULT_UNIVERSE, _load_universe, scan_all


PENDING_STATUS = "pending"
OPEN_STATUS = "open"
CANCELLED_STATUS = "cancelled"
TARGET_STATUS = "target_hit"
STOP_STATUS = "stop_hit"
EXPIRED_STATUS = "expired"
CLOSED_STATUSES = {TARGET_STATUS, STOP_STATUS, EXPIRED_STATUS, CANCELLED_STATUS}
REALIZED_STATUSES = {TARGET_STATUS, STOP_STATUS, EXPIRED_STATUS}


def _quiet_load_universe(data_dir: Path, tickers: list[str], start: str, end: str, show_warnings: bool) -> dict[str, pd.Series]:
    if show_warnings:
        return _load_universe(data_dir, tickers, start, end)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return _load_universe(data_dir, tickers, start, end)


def _trade_key(row: dict[str, Any]) -> str:
    return "|".join([
        str(row.get("ticker", "")),
        str(row.get("setup", "")),
        str(row.get("trigger", "")),
        str(row.get("stop", "")),
        str(row.get("target", "")),
    ])


def _close_on(prices: dict[str, pd.Series], ticker: str, dt: pd.Timestamp) -> float | None:
    s = prices.get(ticker)
    if s is None or dt not in s.index:
        return None
    value = s.loc[dt]
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _tickets_by_key(tickets: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_trade_key(row): row for row in tickets}


def _eligible_ticket(row: dict[str, Any], args: argparse.Namespace) -> bool:
    if str(row.get("direction", "LONG")) != "LONG":
        return False
    if str(row.get("priority", "")) not in set(args.open_priorities):
        return False
    try:
        score = float(row.get("score", 0.0))
    except (TypeError, ValueError):
        return False
    if score < args.min_score:
        return False
    if str(row.get("status", "")) == "active":
        return True
    return bool(args.open_watchlist)


def _new_pending_order(row: dict[str, Any], dt: pd.Timestamp, last_price: float, args: argparse.Namespace) -> dict[str, Any]:
    key = _trade_key(row)
    trade_id = f"{row.get('ticker')}_{row.get('setup')}_{dt.date().isoformat()}_{abs(hash(key)) % 1_000_000}"
    return {
        "trade_id": trade_id,
        "trade_key": key,
        "ticker": row.get("ticker"),
        "direction": row.get("direction", "LONG"),
        "bucket": row.get("bucket"),
        "trade_type": row.get("trade_type"),
        "setup": row.get("setup"),
        "priority": row.get("priority"),
        "score": float(row.get("score", 0.0)),
        "ticket_status_at_creation": row.get("status"),
        "created_date": dt.date().isoformat(),
        "pending_since": dt.date().isoformat(),
        "eligible_after": dt.date().isoformat(),
        "trigger": float(row.get("trigger")),
        "entry_date": "",
        "entry_price": "",
        "last_date": dt.date().isoformat(),
        "last_price": last_price,
        "stop": float(row.get("stop")),
        "target": float(row.get("target")),
        "notional": float(args.default_notional),
        "qty": "",
        "horizon_days": int(float(row.get("horizon_days", args.default_horizon_days))),
        "days_pending": 0,
        "days_open": 0,
        "status": PENDING_STATUS,
        "exit_date": "",
        "exit_price": "",
        "exit_reason": "",
        "cancel_date": "",
        "cancel_reason": "",
        "realized_pnl": "",
        "realized_return_pct": "",
        "unrealized_pnl": "",
        "unrealized_return_pct": "",
        "why": row.get("why"),
        "invalidation": row.get("invalidation"),
    }


def _activate(order: dict[str, Any], dt: pd.Timestamp, price: float) -> None:
    qty = float(order["notional"]) / price if price > 0 else 0.0
    order.update({
        "status": OPEN_STATUS,
        "entry_date": dt.date().isoformat(),
        "entry_price": price,
        "last_date": dt.date().isoformat(),
        "last_price": price,
        "qty": qty,
        "days_open": 0,
        "unrealized_pnl": 0.0,
        "unrealized_return_pct": 0.0,
    })


def _close_order(order: dict[str, Any], dt: pd.Timestamp, price: float, status: str, reason: str) -> None:
    entry = float(order.get("entry_price") or 0.0)
    qty = float(order.get("qty") or 0.0)
    pnl = (price - entry) * qty
    ret = (price / entry - 1.0) * 100.0 if entry > 0 else 0.0
    order.update({
        "status": status,
        "last_date": dt.date().isoformat(),
        "last_price": price,
        "exit_date": dt.date().isoformat(),
        "exit_price": price,
        "exit_reason": reason,
        "realized_pnl": pnl,
        "realized_return_pct": ret,
        "unrealized_pnl": "",
        "unrealized_return_pct": "",
    })


def _cancel_order(order: dict[str, Any], dt: pd.Timestamp, price: float | None, reason: str) -> None:
    order.update({
        "status": CANCELLED_STATUS,
        "last_date": dt.date().isoformat(),
        "last_price": order.get("last_price") if price is None else price,
        "cancel_date": dt.date().isoformat(),
        "cancel_reason": reason,
        "exit_date": dt.date().isoformat(),
        "exit_reason": reason,
        "unrealized_pnl": "",
        "unrealized_return_pct": "",
    })


def _pending_cancel_reason(order: dict[str, Any], ticket: dict[str, Any] | None, dt: pd.Timestamp, args: argparse.Namespace) -> str | None:
    if not args.cancel_stale_pending:
        return None
    if ticket is None:
        return "ticket_missing_from_radar"
    if str(ticket.get("priority", "")) not in set(args.open_priorities):
        return f"priority_below_gate:{ticket.get('priority')}"
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
    pending_since = pd.Timestamp(order.get("pending_since"))
    days_pending = max(0, int((dt - pending_since).days))
    if days_pending > args.cancel_pending_after_days:
        return f"pending_age_exceeded:{days_pending}d"
    return None


def _update_existing_orders(
    orders: list[dict[str, Any]],
    prices: dict[str, pd.Series],
    dt: pd.Timestamp,
    current_tickets: dict[str, dict[str, Any]],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for order in orders:
        status = str(order.get("status"))
        if status not in {PENDING_STATUS, OPEN_STATUS}:
            continue
        ticker = str(order.get("ticker"))
        price = _close_on(prices, ticker, dt)
        if price is None:
            continue
        order["last_date"] = dt.date().isoformat()
        order["last_price"] = price

        if status == PENDING_STATUS:
            pending_since = pd.Timestamp(order.get("pending_since"))
            order["days_pending"] = max(0, int((dt - pending_since).days))
            if dt > pd.Timestamp(order.get("eligible_after")) and price >= float(order.get("trigger")):
                _activate(order, dt, price)
                events.append({"date": dt.date().isoformat(), "event": "activated", "ticker": ticker, "trade_id": order.get("trade_id"), "price": price})
                continue
            reason = _pending_cancel_reason(order, current_tickets.get(str(order.get("trade_key"))), dt, args)
            if reason:
                _cancel_order(order, dt, price, reason)
                events.append({"date": dt.date().isoformat(), "event": CANCELLED_STATUS, "ticker": ticker, "trade_id": order.get("trade_id"), "price": price, "reason": reason})
            continue

        entry_date = pd.Timestamp(order.get("entry_date"))
        order["days_open"] = max(0, int((dt - entry_date).days))
        entry = float(order.get("entry_price"))
        qty = float(order.get("qty"))
        pnl = (price - entry) * qty
        ret = (price / entry - 1.0) * 100.0 if entry > 0 else 0.0
        order["unrealized_pnl"] = pnl
        order["unrealized_return_pct"] = ret

        if price <= float(order.get("stop")):
            _close_order(order, dt, price, STOP_STATUS, "close_at_or_below_stop")
            events.append({"date": dt.date().isoformat(), "event": STOP_STATUS, "ticker": ticker, "trade_id": order.get("trade_id"), "price": price, "realized_pnl": order.get("realized_pnl")})
        elif price >= float(order.get("target")):
            _close_order(order, dt, price, TARGET_STATUS, "close_at_or_above_target")
            events.append({"date": dt.date().isoformat(), "event": TARGET_STATUS, "ticker": ticker, "trade_id": order.get("trade_id"), "price": price, "realized_pnl": order.get("realized_pnl")})
        elif int(order.get("days_open", 0)) >= int(order.get("horizon_days", args.default_horizon_days)):
            _close_order(order, dt, price, EXPIRED_STATUS, "horizon_elapsed")
            events.append({"date": dt.date().isoformat(), "event": EXPIRED_STATUS, "ticker": ticker, "trade_id": order.get("trade_id"), "price": price, "realized_pnl": order.get("realized_pnl")})
    return events


def _create_new_orders(
    orders: list[dict[str, Any]],
    tickets: list[dict[str, Any]],
    prices: dict[str, pd.Series],
    dt: pd.Timestamp,
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    active_keys = {str(o.get("trade_key")) for o in orders if str(o.get("status")) in {PENDING_STATUS, OPEN_STATUS}}
    events: list[dict[str, Any]] = []
    new_count = 0
    for row in tickets:
        if new_count >= args.max_new_trades_per_day:
            break
        if not _eligible_ticket(row, args):
            continue
        key = _trade_key(row)
        if key in active_keys:
            continue
        ticker = str(row.get("ticker"))
        price = _close_on(prices, ticker, dt)
        if price is None:
            continue
        order = _new_pending_order(row, dt, price, args)
        orders.append(order)
        active_keys.add(key)
        new_count += 1
        events.append({"date": dt.date().isoformat(), "event": "new_pending", "ticker": ticker, "trade_id": order.get("trade_id"), "price": price, "trigger": row.get("trigger")})
    return events


def _scan_tickets_for_date(prices: dict[str, pd.Series], dt: pd.Timestamp, args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sliced = {ticker: close.loc[:dt].dropna() for ticker, close in prices.items() if len(close.loc[:dt].dropna()) > 0}
    ideas, raw_ideas = scan_all(sliced, args)
    return [asdict(x) for x in ideas], [asdict(x) for x in raw_ideas]


def _equity_value(args: argparse.Namespace, orders: list[dict[str, Any]]) -> float:
    realized = 0.0
    unrealized = 0.0
    for order in orders:
        if str(order.get("status")) in REALIZED_STATUSES:
            realized += _to_float(order.get("realized_pnl"))
        elif str(order.get("status")) == OPEN_STATUS:
            unrealized += _to_float(order.get("unrealized_pnl"))
    return float(args.capital + realized + unrealized)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _max_drawdown_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    dd = equity / equity.cummax() - 1.0
    return float(dd.min() * 100.0)


def _summarize(orders: list[dict[str, Any]], daily: pd.DataFrame, events: pd.DataFrame, args: argparse.Namespace) -> dict[str, Any]:
    ledger = pd.DataFrame(orders)
    if ledger.empty:
        return {"total_orders": 0}
    status = ledger["status"].astype(str)
    realized = ledger[status.isin(REALIZED_STATUSES)].copy()
    rets = pd.to_numeric(realized.get("realized_return_pct", pd.Series(dtype=float)), errors="coerce").dropna()
    pnl = pd.to_numeric(realized.get("realized_pnl", pd.Series(dtype=float)), errors="coerce").dropna()
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss = float(losses.mean()) if not losses.empty else 0.0
    win_rate = float((rets > 0).mean()) if not rets.empty else 0.0
    expectancy = float(win_rate * avg_win + (1.0 - win_rate) * avg_loss) if not rets.empty else 0.0
    equity = pd.to_numeric(daily.get("equity", pd.Series(dtype=float)), errors="coerce")
    final_equity = float(equity.iloc[-1]) if not equity.empty else args.capital
    total_return_pct = (final_equity / args.capital - 1.0) * 100.0 if args.capital > 0 else 0.0
    by_setup = {}
    if not realized.empty:
        grouped = realized.assign(realized_return_pct=pd.to_numeric(realized["realized_return_pct"], errors="coerce")).groupby("setup")
        for setup, g in grouped:
            rs = g["realized_return_pct"].dropna()
            by_setup[str(setup)] = {
                "trades": int(len(g)),
                "win_rate_pct": float((rs > 0).mean() * 100.0) if not rs.empty else 0.0,
                "avg_return_pct": float(rs.mean()) if not rs.empty else 0.0,
                "expectancy_pct": float(rs.mean()) if not rs.empty else 0.0,
            }
    return {
        "start": args.start,
        "end": args.end,
        "capital": args.capital,
        "default_notional": args.default_notional,
        "total_orders": int(len(ledger)),
        "pending_orders": int((status == PENDING_STATUS).sum()),
        "open_trades": int((status == OPEN_STATUS).sum()),
        "closed_realized_trades": int(status.isin(REALIZED_STATUSES).sum()),
        "cancelled_orders": int((status == CANCELLED_STATUS).sum()),
        "target_hits": int((status == TARGET_STATUS).sum()),
        "stop_hits": int((status == STOP_STATUS).sum()),
        "expired_trades": int((status == EXPIRED_STATUS).sum()),
        "activation_events": int((events.get("event") == "activated").sum()) if not events.empty else 0,
        "win_rate_pct": win_rate * 100.0,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "expectancy_pct_per_realized_trade": expectancy,
        "total_realized_pnl": float(pnl.sum()) if not pnl.empty else 0.0,
        "final_equity": final_equity,
        "total_return_pct_on_capital": total_return_pct,
        "max_drawdown_pct_on_equity": _max_drawdown_pct(equity),
        "events": int(len(events)),
        "by_setup": by_setup,
    }


def _print_summary(summary: dict[str, Any]) -> None:
    print("=" * 156)
    print("  TRADE IDEA DESK CYCLE — HISTORICAL REPLAY")
    print("=" * 156)
    print(f"  Window              : {summary.get('start')} -> {summary.get('end')}")
    print(f"  Total orders        : {summary.get('total_orders', 0)}")
    print(f"  Realized trades     : {summary.get('closed_realized_trades', 0)}")
    print(f"  Open / Pending      : {summary.get('open_trades', 0)} / {summary.get('pending_orders', 0)}")
    print(f"  Cancelled orders    : {summary.get('cancelled_orders', 0)}")
    print(f"  Target / Stop / Exp : {summary.get('target_hits', 0)} / {summary.get('stop_hits', 0)} / {summary.get('expired_trades', 0)}")
    print(f"  Win rate            : {summary.get('win_rate_pct', 0.0):.2f}%")
    print(f"  Avg win / loss      : {summary.get('avg_win_pct', 0.0):.2f}% / {summary.get('avg_loss_pct', 0.0):.2f}%")
    print(f"  Expectancy / trade  : {summary.get('expectancy_pct_per_realized_trade', 0.0):.2f}%")
    print(f"  Realized PnL        : ${summary.get('total_realized_pnl', 0.0):,.2f}")
    print(f"  Final equity        : ${summary.get('final_equity', 0.0):,.2f}")
    print(f"  Return on capital   : {summary.get('total_return_pct_on_capital', 0.0):.2f}%")
    print(f"  Max DD on equity    : {summary.get('max_drawdown_pct_on_equity', 0.0):.2f}%")
    print("=" * 156)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Replay trade idea desk cycle historically")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--tickers", nargs="+", default=DEFAULT_UNIVERSE)
    p.add_argument("--start", default="2019-01-01")
    p.add_argument("--end", default="2025-12-30")
    p.add_argument("--replay-start", default=None, help="Optional later replay start; data before this is still used for lookbacks")
    p.add_argument("--out-dir", default="artifacts/trade_idea_replay")
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--default-notional", type=float, default=10_000.0)
    p.add_argument("--default-horizon-days", type=int, default=20)
    p.add_argument("--open-watchlist", action="store_true", default=True)
    p.add_argument("--no-open-watchlist", dest="open_watchlist", action="store_false")
    p.add_argument("--open-priorities", nargs="+", default=["A", "B"])
    p.add_argument("--min-score", type=float, default=80.0)
    p.add_argument("--max-new-trades-per-day", type=int, default=10)
    p.add_argument("--cancel-stale-pending", action="store_true", default=True)
    p.add_argument("--no-cancel-stale-pending", dest="cancel_stale_pending", action="store_false")
    p.add_argument("--cancel-pending-after-days", type=int, default=10)
    p.add_argument("--cancel-pending-if-distance-gt-pct", type=float, default=3.0)
    p.add_argument("--near-trigger-pct", type=float, default=3.0)
    p.add_argument("--near-reclaim-pct", type=float, default=1.5)
    p.add_argument("--default-stop-pct", type=float, default=0.08)
    p.add_argument("--prefer-tighter-stop", action="store_true", default=True)
    p.add_argument("--vol-window", type=int, default=20)
    p.add_argument("--vol-rank-window", type=int, default=90)
    p.add_argument("--compression-pctile", type=float, default=0.30)
    p.add_argument("--compression-memory", type=int, default=10)
    p.add_argument("--channel-window", type=int, default=20)
    p.add_argument("--breakout-horizon-days", type=int, default=20)
    p.add_argument("--momentum-horizon-days", type=int, default=20)
    p.add_argument("--reclaim-horizon-days", type=int, default=30)
    p.add_argument("--reclaim-lookback-days", type=int, default=30)
    p.add_argument("--show-loader-warnings", action="store_true")
    p.add_argument("--progress-every", type=int, default=250)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    prices = _quiet_load_universe(Path(args.data_dir), args.tickers, args.start, args.end, args.show_loader_warnings)
    if not prices:
        raise SystemExit(f"No data files found in {args.data_dir} for requested tickers")

    common_index = sorted(set().union(*[set(s.index) for s in prices.values()]))
    dates = [pd.Timestamp(x) for x in common_index if pd.Timestamp(args.start) <= pd.Timestamp(x) <= pd.Timestamp(args.end)]
    if args.replay_start:
        dates = [d for d in dates if d >= pd.Timestamp(args.replay_start)]

    orders: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []

    for i, dt in enumerate(dates, start=1):
        tickets, raw = _scan_tickets_for_date(prices, dt, args)
        ticket_map = _tickets_by_key(tickets)
        events.extend(_update_existing_orders(orders, prices, dt, ticket_map, args))
        events.extend(_create_new_orders(orders, tickets, prices, dt, args))
        status_counts = pd.Series([o.get("status") for o in orders]).value_counts().to_dict() if orders else {}
        daily_rows.append({
            "date": dt.date().isoformat(),
            "tickets": len(tickets),
            "raw_signals": len(raw),
            "orders_total": len(orders),
            "pending": int(status_counts.get(PENDING_STATUS, 0)),
            "open": int(status_counts.get(OPEN_STATUS, 0)),
            "cancelled": int(status_counts.get(CANCELLED_STATUS, 0)),
            "target_hit": int(status_counts.get(TARGET_STATUS, 0)),
            "stop_hit": int(status_counts.get(STOP_STATUS, 0)),
            "expired": int(status_counts.get(EXPIRED_STATUS, 0)),
            "equity": _equity_value(args, orders),
        })
        if args.progress_every and i % args.progress_every == 0:
            print(f"Replay progress: {i}/{len(dates)} dates processed through {dt.date().isoformat()}")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ledger = pd.DataFrame(orders)
    daily = pd.DataFrame(daily_rows)
    event_df = pd.DataFrame(events)
    summary = _summarize(orders, daily, event_df, args)

    ledger.to_csv(out / "replay_trades.csv", index=False)
    daily.to_csv(out / "replay_daily.csv", index=False)
    event_df.to_csv(out / "replay_events.csv", index=False)
    (out / "replay_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    _print_summary(summary)
    print(f"  Trades : {out / 'replay_trades.csv'}")
    print(f"  Daily  : {out / 'replay_daily.csv'}")
    print(f"  Events : {out / 'replay_events.csv'}")
    print(f"  Summary: {out / 'replay_summary.json'}")
    print("  Verdict: HISTORICAL PAPER REPLAY ONLY; no broker/runtime execution.\n")


if __name__ == "__main__":
    main()
