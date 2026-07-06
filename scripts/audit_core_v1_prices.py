#!/usr/bin/env python
"""Independently verify Core v1 paper runtime state and position math.

This script is intentionally independent of the dashboard and of the live
runtime's own market-data cache. It re-fetches market data from source and
reconstructs the latest completed strategy bar for each sleeve, then checks
that the runtime's stored price for that bar matches what actually happened
in the market — not what the market is doing *right now*.

That distinction matters. The live runtime only acts on completed bars
(1H/4H/1D depending on the sleeve), so its stored price is always a snapshot
of a closed bar. Comparing that snapshot to a continuously-updating live
quote produces false failures purely from ordinary price movement between
bar close and audit time — that is not a runtime defect.

This script therefore separates two different concepts:

- Bar verification (pass/fail): does the runtime's stored price for sleeve X
  match the close of the bar it says it used, per independently-fetched
  market data? A mismatch here means the runtime read the wrong price or
  the wrong bar — a real integrity problem.
- Live drift (informational only): how far has the market moved since that
  bar closed? This is operationally useful context, but normal market
  movement can never fail the audit.

It also verifies basic position math:

- qty * strategy bar price == market value
- cost_basis / qty == average entry
- market value - cost_basis == unrealized P&L

It exits non-zero when bar verification, staleness, or accounting checks
fail. Live drift never affects the exit code or the `ok` field.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from pandas.tseries.holiday import (
    AbstractHolidayCalendar,
    GoodFriday,
    Holiday,
    USLaborDay,
    USMartinLutherKingJr,
    USMemorialDay,
    USPresidentsDay,
    USThanksgivingDay,
    nearest_workday,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from research.harness.resampler import resample_ohlcv
from runtime.core_v1.allocation import SELECTED_CORE_V1_SLEEVES

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{params}"
COINBASE_TICKER = "https://api.exchange.coinbase.com/products/{product}/ticker"
COINBASE_CANDLES = "https://api.exchange.coinbase.com/products/{product}/candles"


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
    """Current live quote — informational only, never used for pass/fail."""
    if asset in {"BTC", "ETH"}:
        return coinbase_quote(asset)
    return yahoo_quote(asset)


TIMEFRAME_DURATION = {"1H": timedelta(hours=1), "4H": timedelta(hours=4), "1D": timedelta(days=1)}


def drop_incomplete_bars(df: pd.DataFrame, bar_duration: timedelta, now: datetime) -> pd.DataFrame:
    """Drop any bar whose window has not fully closed as of `now`.

    Mirrors the same rule the live runtime applies when loading market data —
    a bar labeled T covers [T, T+bar_duration) and is only a fixed, immutable
    observation once now >= T+bar_duration. Without this, the audit's own
    independent fetch could pick up the same still-forming candle the
    runtime is being checked against, comparing two different snapshots of
    a price that is still changing — a false failure, not a real mismatch.
    """
    if df.empty:
        return df
    now_naive = now.replace(tzinfo=None) if now.tzinfo is not None else now
    return df[df.index + bar_duration <= now_naive]


def fetch_coinbase_hourly(product: str, days: float) -> pd.DataFrame:
    """Independently fetch recent hourly Coinbase candles.

    Deliberately duplicated (not imported) from the live runtime's fetch
    logic — this script re-derives market data on its own rather than
    trusting the same code path it is verifying. Only fully-closed hourly
    candles are returned (see drop_incomplete_bars).
    """
    now = datetime.now(UTC)
    end = now.replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    rows: list[list[float]] = []
    chunk_start = start
    max_hours = 300

    while chunk_start < end:
        chunk_end = min(chunk_start + timedelta(hours=max_hours), end)
        params = urllib.parse.urlencode(
            {
                "granularity": 3600,
                "start": chunk_start.isoformat().replace("+00:00", "Z"),
                "end": chunk_end.isoformat().replace("+00:00", "Z"),
            }
        )
        url = f"{COINBASE_CANDLES.format(product=product)}?{params}"
        data = fetch_json(url)
        if isinstance(data, list):
            rows.extend(data)
        time.sleep(0.12)
        chunk_start = chunk_end

    if not rows:
        raise RuntimeError(f"no independent Coinbase candles returned for {product}")

    df = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert(None)
    df = df.drop(columns=["time"]).drop_duplicates("timestamp").set_index("timestamp").sort_index()
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    return drop_incomplete_bars(df, timedelta(hours=1), now)


def fetch_daily_bars(symbol: str, days: float) -> pd.DataFrame:
    """Independently fetch recent daily bars (equities/gold).

    Only fully-closed daily candles are returned (see drop_incomplete_bars).
    Yahoo's intraday response includes a mutable "today" row that keeps
    changing until market close; without filtering it out, this independent
    verification would be comparing the runtime's live snapshot against its
    own, differently-timed live snapshot of the same still-forming candle —
    a false failure, not a real price mismatch.
    """
    params = urllib.parse.urlencode({"range": f"{max(int(days), 5)}d", "interval": "1d", "includePrePost": "false"})
    data = fetch_json(YAHOO_CHART.format(symbol=symbol, params=params))
    result = data["chart"]["result"][0]
    timestamps = result.get("timestamp", [])
    quote = result["indicators"]["quote"][0]
    if not timestamps:
        raise RuntimeError(f"no independent daily data returned for {symbol}")

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(None).normalize(),
        "open": quote.get("open", []),
        "high": quote.get("high", []),
        "low": quote.get("low", []),
        "close": quote.get("close", []),
        "volume": quote.get("volume", []),
    })
    df = df.dropna(subset=["open", "high", "low", "close"]).drop_duplicates("timestamp")
    df = df.set_index("timestamp").sort_index()[["open", "high", "low", "close", "volume"]].astype(float)
    return drop_incomplete_bars(df, TIMEFRAME_DURATION["1D"], datetime.now(UTC))


def reconstruct_bar(asset: str, timeframe: str, target_ts: pd.Timestamp, crypto_days: float, etf_days: float) -> tuple[float, pd.Timestamp]:
    """Independently rebuild the completed bar the runtime should have used.

    Uses the same resampling rule (research.harness.resampler.resample_ohlcv)
    the live runtime applies, but fetches its own market data from scratch.
    """
    if asset in {"BTC", "ETH"}:
        df = fetch_coinbase_hourly(f"{asset}-USD", days=crypto_days)
        if timeframe == "4H":
            df = resample_ohlcv(df, "4h")
            # Same defense-in-depth as the runtime: a resampled trailing 4H
            # bin can still be partially formed even when its hourly inputs
            # are all individually complete.
            df = drop_incomplete_bars(df, TIMEFRAME_DURATION["4H"], datetime.now(UTC))
    else:
        df = fetch_daily_bars(asset, days=etf_days)

    if df.empty:
        raise RuntimeError(f"independently fetched {asset} data is empty")
    eligible = df.index[df.index <= target_ts]
    if len(eligible) == 0:
        raise RuntimeError(f"no independently-verified bar at or before {target_ts} for {asset} (lookback window too short?)")
    bar_ts = eligible[-1]
    return float(df.loc[bar_ts, "close"]), bar_ts


def pct_diff(a: float, b: float) -> float:
    if b == 0:
        return math.inf
    return (a - b) / b


def parse_naive_ts(value: str | None) -> pd.Timestamp | None:
    if not value:
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    if ts.tzinfo is not None:
        ts = ts.tz_convert(None)
    return ts


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


class _NYSEHolidayCalendar(AbstractHolidayCalendar):
    """Approximate NYSE trading holiday calendar.

    Deliberately duplicated from the live runtime's own copy of this same
    calendar (scripts/run_core_v1_paper_live.py) rather than imported —
    this script re-derives its notion of market freshness independently,
    same as it re-derives market data independently, so a bug in one
    doesn't silently pass unnoticed in the other.
    """

    rules = [
        Holiday("New Year's Day", month=1, day=1, observance=nearest_workday),
        USMartinLutherKingJr,
        USPresidentsDay,
        GoodFriday,
        USMemorialDay,
        Holiday("Juneteenth", month=6, day=19, start_date="2022-01-01", observance=nearest_workday),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday("Christmas Day", month=12, day=25, observance=nearest_workday),
    ]


_NYSE_CALENDAR = _NYSEHolidayCalendar()
_NYSE_ET = ZoneInfo("America/New_York")


def _is_nyse_trading_day(date: pd.Timestamp) -> bool:
    if date.weekday() >= 5:
        return False
    holidays = _NYSE_CALENDAR.holidays(start=date - pd.Timedelta(days=1), end=date + pd.Timedelta(days=1))
    return date.normalize() not in holidays


def _previous_nyse_trading_day(date: pd.Timestamp) -> pd.Timestamp:
    d = date.normalize() - pd.Timedelta(days=1)
    while not _is_nyse_trading_day(d):
        d -= pd.Timedelta(days=1)
    return d


def expected_completed_daily_bar_date(now_utc: datetime) -> pd.Timestamp:
    """The most recent trading day whose regular session should be fully closed by `now_utc`."""
    now_et = now_utc.astimezone(_NYSE_ET)
    today_et = pd.Timestamp(now_et.date())
    market_close_et = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    if _is_nyse_trading_day(today_et) and now_et >= market_close_et:
        return today_et
    return _previous_nyse_trading_day(today_et)


def daily_etf_freshness_status(last_bar_ts: pd.Timestamp, now_utc: datetime) -> tuple[str, str]:
    """Classify a daily ETF/gold bar as PASS / WAITING / FAIL.

    Market-aware, unlike a naive elapsed-hours check: only FAIL if a newer
    completed session should exist by now and doesn't. Mirrors the runtime's
    own daily_etf_freshness_status (scripts/run_core_v1_paper_live.py).
    """
    last_bar_date = pd.Timestamp(last_bar_ts).normalize()
    now_et = now_utc.astimezone(_NYSE_ET)
    today_et = pd.Timestamp(now_et.date())
    expected_date = expected_completed_daily_bar_date(now_utc)

    if last_bar_date < expected_date:
        return "FAIL", f"newer completed bar expected by now (expected>={expected_date.date()}, last={last_bar_date.date()})"
    if last_bar_date == today_et:
        return "PASS", f"latest completed bar is today's closed session (last={last_bar_date.date()})"
    return "WAITING", f"market session in progress or closed; no newer completed bar expected yet (last={last_bar_date.date()}, expected={expected_date.date()})"


def audit(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    state_path = Path(args.state_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    sleeves = state.get("sleeves", {})
    telemetry = state.get("sleeve_telemetry", {})
    rows: list[dict[str, Any]] = []
    failures: list[str] = []

    for sleeve_meta in SELECTED_CORE_V1_SLEEVES:
        label = sleeve_meta.label
        asset = sleeve_meta.asset
        timeframe = sleeve_meta.timeframe
        s = sleeves.get(label, {})
        t = telemetry.get(label, {})

        strategy_bar_price = float(s.get("last_price") or 0.0)
        strategy_bar_ts = parse_naive_ts(s.get("last_timestamp"))
        bar_age = age_hours(s.get("last_timestamp"))
        bar_duration = TIMEFRAME_DURATION.get(timeframe)
        bar_completed: bool | None = None
        if strategy_bar_ts is not None and bar_duration is not None:
            bar_completed = bool(datetime.now(UTC).replace(tzinfo=None) >= (strategy_bar_ts + bar_duration))

        verified_bar_price: float | None = None
        verified_bar_ts: pd.Timestamp | None = None
        bar_error: str | None = None
        if strategy_bar_ts is None:
            bar_error = "no stored bar timestamp to verify"
        else:
            try:
                verified_bar_price, verified_bar_ts = reconstruct_bar(
                    asset, timeframe, strategy_bar_ts, args.crypto_lookback_days, args.etf_lookback_days
                )
            except Exception as e:
                bar_error = str(e)

        if bar_error is not None:
            bar_price_ok = False
            bar_price_diff = None
        else:
            bar_price_diff = pct_diff(strategy_bar_price, verified_bar_price)
            bar_price_ok = abs(bar_price_diff) <= args.max_bar_price_diff

        live_price: float | None = None
        live_drift_pct: float | None = None
        live_error: str | None = None
        try:
            quote = fresh_quote(asset)
            live_price = float(quote["price"])
            reference_price = verified_bar_price if verified_bar_price is not None else strategy_bar_price
            live_drift_pct = pct_diff(live_price, reference_price) if reference_price else None
        except Exception as e:
            live_error = str(e)

        qty = float(t.get("qty") or s.get("qty") or 0.0)
        cost_basis = float(t.get("cost_basis") or s.get("cost_basis") or 0.0)
        avg_entry = float(t.get("avg_entry") or s.get("avg_entry") or 0.0)
        stored_position_value = float(t.get("position_value") or 0.0)
        stored_unrealized = float(t.get("unrealized_pnl") or 0.0)
        recomputed_position_value = qty * strategy_bar_price
        recomputed_unrealized = recomputed_position_value - cost_basis if abs(qty) > 1e-12 else 0.0
        recomputed_avg_entry = cost_basis / qty if abs(qty) > 1e-12 and cost_basis else 0.0
        position_value_ok = abs(stored_position_value - recomputed_position_value) <= args.dollar_tolerance
        unrealized_ok = abs(stored_unrealized - recomputed_unrealized) <= args.dollar_tolerance
        avg_entry_ok = abs(avg_entry - recomputed_avg_entry) <= args.price_tolerance

        # Daily ETF/gold bars: a naive "age > threshold" check produces false
        # failures across any weekend/holiday gap wider than the fixed
        # threshold (e.g. a holiday Friday plus a weekend). Use the same
        # market-calendar-aware PASS/WAITING/FAIL semantics as the runtime's
        # own validate_market_freshness — only FAIL if a newer completed
        # session should exist by now and doesn't.
        freshness_status: str | None = None
        freshness_detail: str | None = None
        if asset in {"SPY", "QQQ", "GLD"} and strategy_bar_ts is not None:
            freshness_status, freshness_detail = daily_etf_freshness_status(strategy_bar_ts, datetime.now(UTC))
            if freshness_status == "FAIL":
                failures.append(f"{label}: {freshness_detail}")

        if bar_completed is False and timeframe in ("1H", "4H"):
            # Wall-clock "bar_start + duration <= now" is only a valid
            # completeness test for continuously-trading crypto. Daily
            # equity/gold bars are midnight-normalized and depend on market
            # session hours, not naive 24h arithmetic — bar_completed is
            # still reported for them below, just never used to fail here.
            failures.append(
                f"{label}: stored bar {strategy_bar_ts} for timeframe {timeframe} had not closed as of "
                "audit time — runtime may be using an in-progress candle"
            )
        if bar_error is not None:
            failures.append(f"{label}: could not independently verify bar — {bar_error}")
        elif not bar_price_ok:
            failures.append(
                f"{label}: stored bar price {strategy_bar_price:.4f} for {strategy_bar_ts} does not match "
                f"independently verified price {verified_bar_price:.4f} ({bar_price_diff:.2%})"
            )
        if not position_value_ok:
            failures.append(f"{label}: stored market value does not equal qty * strategy bar price")
        if not unrealized_ok:
            failures.append(f"{label}: stored unrealized P&L does not reconcile")
        if not avg_entry_ok:
            failures.append(f"{label}: avg entry does not equal cost basis / qty")

        rows.append({
            "sleeve": label,
            "asset": asset,
            "timeframe": timeframe,
            "strategy_bar_timestamp": str(strategy_bar_ts) if strategy_bar_ts is not None else None,
            "strategy_bar_price": strategy_bar_price,
            "verified_bar_timestamp": str(verified_bar_ts) if verified_bar_ts is not None else None,
            "verified_bar_price": verified_bar_price,
            "bar_price_diff_pct": bar_price_diff,
            "bar_price_ok": bar_price_ok,
            "bar_completed": bar_completed,
            "bar_verification_error": bar_error,
            "live_price": live_price,
            "live_drift_pct": live_drift_pct,
            "live_quote_error": live_error,
            "bar_age_hours": bar_age,
            "freshness_status": freshness_status,
            "freshness_detail": freshness_detail,
            "qty": qty,
            "cost_basis": cost_basis,
            "avg_entry": avg_entry,
            "recomputed_avg_entry": recomputed_avg_entry,
            "stored_position_value": stored_position_value,
            "recomputed_position_value": recomputed_position_value,
            "stored_unrealized_pnl": stored_unrealized,
            "recomputed_unrealized_pnl": recomputed_unrealized,
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


def write_report_atomic(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    tmp.replace(path)


def main() -> None:
    p = argparse.ArgumentParser(description="Independently verify Core v1 paper runtime state against re-fetched market data")
    p.add_argument("--state-path", default=os.getenv("CORE_V1_STATE_PATH", "/opt/itera/runtime/core_v1/state.json"))
    p.add_argument("--max-bar-price-diff", type=float, default=float(os.getenv("CORE_V1_AUDIT_MAX_BAR_PRICE_DIFF", "0.001")))
    p.add_argument("--max-etf-bar-age-hours", type=float, default=float(os.getenv("CORE_V1_MAX_ETF_BAR_AGE_HOURS", "96")))
    p.add_argument("--dollar-tolerance", type=float, default=0.05)
    p.add_argument("--price-tolerance", type=float, default=0.0001)
    p.add_argument("--crypto-lookback-days", type=float, default=float(os.getenv("CORE_V1_AUDIT_CRYPTO_LOOKBACK_DAYS", "5")))
    p.add_argument("--etf-lookback-days", type=float, default=float(os.getenv("CORE_V1_AUDIT_ETF_LOOKBACK_DAYS", "15")))
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--output",
        default=os.getenv("CORE_V1_AUDIT_REPORT_PATH"),
        help="Optional path to persist the JSON audit report (e.g. for dashboard consumption). Unset by default.",
    )
    args = p.parse_args()
    code, report = audit(args)
    if args.output:
        write_report_atomic(Path(args.output), report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "PASS" if report["ok"] else "FAIL"
        print(f"Core v1 audit: {status} @ {report['timestamp']}")
        for row in report["rows"]:
            drift = f"{row['live_drift_pct']:.2%}" if row["live_drift_pct"] is not None else "n/a"
            bar_diff = f"{row['bar_price_diff_pct']:.4%}" if row["bar_price_diff_pct"] is not None else "n/a"
            freshness = f" freshness={row['freshness_status']}" if row.get("freshness_status") is not None else ""
            print(
                f"{row['sleeve']}: bar={row['strategy_bar_price']:.4f} verified={row['verified_bar_price']} "
                f"bar_diff={bar_diff} live_drift={drift} bar_age={row['bar_age_hours']}h{freshness} "
                f"qty={row['qty']:.6f} basis={row['cost_basis']:.2f} avg={row['avg_entry']:.4f}"
            )
        for failure in report["failures"]:
            print(f"FAIL: {failure}", file=sys.stderr)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
