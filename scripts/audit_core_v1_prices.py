#!/usr/bin/env python
"""Audit Core v1 paper prices, position math, and state freshness.

This script is intentionally independent of the dashboard. It compares the prices
stored in runtime state against fresh external quotes and verifies basic position
math:

- qty * current_price == market value
- cost_basis / qty == average entry
- market value - cost_basis == unrealized P&L

It exits non-zero when price freshness, price drift, or accounting checks fail.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ASSETS = {
    "SPY_1D_equity": "SPY",
    "QQQ_1D_equity": "QQQ",
    "GLD_1D_gold": "GLD",
    "BTC_4H_trend": "BTC",
    "ETH_1H_trend": "ETH",
    "ETH_4H_trend": "ETH",
}

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{params}"
COINBASE_TICKER = "https://api.exchange.coinbase.com/products/{product}/ticker"


def fetch_json(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "IteraDynamics-CoreV1-Audit/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def yahoo_quote(symbol: str) -> dict[str, Any]:
    params = urllib.parse.urlencode({"range": "5d", "interval": "1d", "includePrePost": "false"})
    data = fetch_json(YAHOO_CHART.format(symbol=symbol, params=params))
    result = data["chart"]["result"][0]
    meta = result.get("meta", {})
    ts = result.get("timestamp", [])[-1]
    quote = result["indicators"]["quote"][0]
    close = next((x for x in reversed(quote.get("close", [])) if x is not None), None)
    regular = meta.get("regularMarketPrice")
    price = float(regular if regular is not None else close)
    return {
        "source": "yahoo_chart",
        "symbol": symbol,
        "price": price,
        "timestamp": datetime.fromtimestamp(ts, tz=UTC).isoformat() if ts else None,
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName"),
    }


def coinbase_quote(asset: str) -> dict[str, Any]:
    product = f"{asset}-USD"
    data = fetch_json(COINBASE_TICKER.format(product=product))
    return {
        "source": "coinbase_ticker",
        "symbol": asset,
        "price": float(data["price"]),
        "timestamp": data.get("time"),
        "currency": "USD",
        "exchange": "Coinbase",
    }


def fresh_quote(asset: str) -> dict[str, Any]:
    if asset in {"BTC", "ETH"}:
        return coinbase_quote(asset)
    return yahoo_quote(asset)


def pct_diff(a: float, b: float) -> float:
    if b == 0:
        return math.inf
    return (a - b) / b


def age_hours(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return (datetime.now(UTC) - parsed.astimezone(UTC)).total_seconds() / 3600.0
    except Exception:
        return None


def audit(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    state_path = Path(args.state_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    sleeves = state.get("sleeves", {})
    telemetry = state.get("sleeve_telemetry", {})
    rows: list[dict[str, Any]] = []
    failures: list[str] = []

    for sleeve, asset in ASSETS.items():
        s = sleeves.get(sleeve, {})
        t = telemetry.get(sleeve, {})
        quote = fresh_quote(asset)
        state_price = float(s.get("last_price") or 0.0)
        fresh_price = float(quote["price"])
        diff = pct_diff(state_price, fresh_price)
        qty = float(t.get("qty") or s.get("qty") or 0.0)
        cost_basis = float(t.get("cost_basis") or s.get("cost_basis") or 0.0)
        avg_entry = float(t.get("avg_entry") or s.get("avg_entry") or 0.0)
        stored_position_value = float(t.get("position_value") or 0.0)
        stored_unrealized = float(t.get("unrealized_pnl") or 0.0)
        recomputed_position_value = qty * state_price
        recomputed_unrealized = recomputed_position_value - cost_basis if abs(qty) > 1e-12 else 0.0
        recomputed_avg_entry = cost_basis / qty if abs(qty) > 1e-12 and cost_basis else 0.0
        bar_age = age_hours(s.get("last_timestamp"))
        price_ok = abs(diff) <= args.max_price_diff
        position_value_ok = abs(stored_position_value - recomputed_position_value) <= args.dollar_tolerance
        unrealized_ok = abs(stored_unrealized - recomputed_unrealized) <= args.dollar_tolerance
        avg_entry_ok = abs(avg_entry - recomputed_avg_entry) <= args.price_tolerance

        if asset in {"SPY", "QQQ", "GLD"} and bar_age is not None and bar_age > args.max_etf_bar_age_hours:
            failures.append(f"{sleeve}: stale bar age {bar_age:.1f}h")
        if not price_ok:
            failures.append(f"{sleeve}: state price {state_price:.4f} differs from fresh {fresh_price:.4f} by {diff:.2%}")
        if not position_value_ok:
            failures.append(f"{sleeve}: stored market value does not equal qty * state price")
        if not unrealized_ok:
            failures.append(f"{sleeve}: stored unrealized P&L does not reconcile")
        if not avg_entry_ok:
            failures.append(f"{sleeve}: avg entry does not equal cost basis / qty")

        rows.append({
            "sleeve": sleeve,
            "asset": asset,
            "state_price": state_price,
            "fresh_price": fresh_price,
            "price_diff_pct": diff,
            "bar_timestamp": s.get("last_timestamp"),
            "bar_age_hours": bar_age,
            "qty": qty,
            "cost_basis": cost_basis,
            "avg_entry": avg_entry,
            "recomputed_avg_entry": recomputed_avg_entry,
            "stored_position_value": stored_position_value,
            "recomputed_position_value": recomputed_position_value,
            "stored_unrealized_pnl": stored_unrealized,
            "recomputed_unrealized_pnl": recomputed_unrealized,
            "quote": quote,
            "price_ok": price_ok,
            "position_value_ok": position_value_ok,
            "unrealized_ok": unrealized_ok,
            "avg_entry_ok": avg_entry_ok,
        })

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "state_path": str(state_path),
        "ok": not failures,
        "failures": failures,
        "rows": rows,
    }
    return (0 if not failures else 2), report


def main() -> None:
    p = argparse.ArgumentParser(description="Audit Core v1 paper state against fresh external prices")
    p.add_argument("--state-path", default=os.getenv("CORE_V1_STATE_PATH", "/opt/itera/runtime/core_v1/state.json"))
    p.add_argument("--max-price-diff", type=float, default=float(os.getenv("CORE_V1_AUDIT_MAX_PRICE_DIFF", "0.01")))
    p.add_argument("--max-etf-bar-age-hours", type=float, default=float(os.getenv("CORE_V1_MAX_ETF_BAR_AGE_HOURS", "96")))
    p.add_argument("--dollar-tolerance", type=float, default=0.05)
    p.add_argument("--price-tolerance", type=float, default=0.0001)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    code, report = audit(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "PASS" if report["ok"] else "FAIL"
        print(f"Core v1 audit: {status} @ {report['timestamp']}")
        for row in report["rows"]:
            print(
                f"{row['sleeve']}: state={row['state_price']:.4f} fresh={row['fresh_price']:.4f} "
                f"diff={row['price_diff_pct']:.2%} bar_age={row['bar_age_hours']}h "
                f"qty={row['qty']:.6f} basis={row['cost_basis']:.2f} avg={row['avg_entry']:.4f}"
            )
        for failure in report["failures"]:
            print(f"FAIL: {failure}", file=sys.stderr)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
