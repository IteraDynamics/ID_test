"""Campaign #53 source feasibility probe — read-only, no data acquisition.

Establishes empirically what perpetual funding history is actually obtainable
*from this operator's location*, before any acquisition design is frozen.

The 2026-08-11 first run established that venue accessibility is itself a
binding constraint: Binance returned HTTP 451 and Bybit HTTP 403 from a US
address. Those are jurisdictional blocks, not faults. Campaign #53 must
therefore be designed around venues that are actually reachable, and the
probe covers a wider venue set for that reason.

For each venue and asset the probe reports: whether the endpoint responds,
the true settlement cadence, how far back history genuinely reaches (by
walking backwards until the series is exhausted), and whether the series is
monotonic and free of duplicates.

Small samples only. Writes nothing to `data/`, computes no predictor or
outcome, uses public market-data endpoints exclusively -- no key, no auth, no
trading scope. Bulk acquisition requires a separate board transition.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

USER_AGENT = "itera-research-feasibility-probe/2.0"
TIMEOUT_SECONDS = 20
MAX_DEPTH_PAGES = 60  # bounded backward walk; raised after 12 proved insufficient to exhaust Deribit/Hyperliquid


def http(url: str, payload: dict[str, Any] | None = None) -> tuple[int, Any, str | None]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"User-Agent": USER_AGENT}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        reason = str(exc.reason)
        if exc.code == 451:
            reason += " (jurisdictional block)"
        elif exc.code == 403:
            reason += " (forbidden — often a jurisdictional block)"
        return exc.code, None, f"HTTP {exc.code}: {reason}"
    except Exception as exc:  # noqa: BLE001 — a probe reports, never raises
        return 0, None, f"{type(exc).__name__}: {exc}"


# Each adapter returns (points, status, error) where points is [(ts_ms, rate)].
# `before_ms` requests rows strictly older than that timestamp, for depth walking.


def okx(symbol: str, before_ms: int | None, limit: int) -> tuple[list, int, str | None]:
    url = f"https://www.okx.com/api/v5/public/funding-rate-history?instId={symbol}&limit={limit}"
    if before_ms is not None:
        url += f"&after={before_ms}"  # OKX: 'after' = records EARLIER than this ts
    status, payload, error = http(url)
    if payload is None:
        return [], status, error
    rows = payload.get("data", []) or []
    return [(int(r["fundingTime"]), float(r["fundingRate"])) for r in rows], status, error


def binance(symbol: str, before_ms: int | None, limit: int) -> tuple[list, int, str | None]:
    url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit={limit}"
    if before_ms is not None:
        url += f"&endTime={before_ms}"
    status, payload, error = http(url)
    if payload is None:
        return [], status, error
    return [(int(r["fundingTime"]), float(r["fundingRate"])) for r in payload], status, error


def bybit(symbol: str, before_ms: int | None, limit: int) -> tuple[list, int, str | None]:
    url = f"https://api.bybit.com/v5/market/funding/history?category=linear&symbol={symbol}&limit={limit}"
    if before_ms is not None:
        url += f"&endTime={before_ms}"
    status, payload, error = http(url)
    if payload is None:
        return [], status, error
    rows = (payload.get("result") or {}).get("list", []) or []
    return [(int(r["fundingRateTimestamp"]), float(r["fundingRate"])) for r in rows], status, error


def deribit(symbol: str, before_ms: int | None, limit: int) -> tuple[list, int, str | None]:
    end = before_ms if before_ms is not None else int(time.time() * 1000)
    start = end - limit * 8 * 3_600_000
    url = (
        "https://www.deribit.com/api/v2/public/get_funding_rate_history"
        f"?instrument_name={symbol}&start_timestamp={start}&end_timestamp={end}"
    )
    status, payload, error = http(url)
    if payload is None:
        return [], status, error
    rows = payload.get("result", []) or []
    return [(int(r["timestamp"]), float(r["interest_8h"])) for r in rows], status, error


def hyperliquid(symbol: str, before_ms: int | None, limit: int) -> tuple[list, int, str | None]:
    end = before_ms if before_ms is not None else int(time.time() * 1000)
    start = end - limit * 3_600_000  # hyperliquid funds hourly
    status, payload, error = http(
        "https://api.hyperliquid.xyz/info",
        {"type": "fundingHistory", "coin": symbol, "startTime": start, "endTime": end},
    )
    if payload is None:
        return [], status, error
    return [(int(r["time"]), float(r["fundingRate"])) for r in payload], status, error


def coinbase_intx(symbol: str, before_ms: int | None, limit: int) -> tuple[list, int, str | None]:
    """Coinbase International Exchange perpetual funding.

    INTX is where Coinbase lists perpetuals. Market data may be publicly
    readable even where trading access is jurisdictionally restricted --
    which is precisely the distinction the tradeability question below turns
    on. Reachable data does not imply a tradeable instrument.
    """
    url = f"https://api.international.coinbase.com/api/v1/instruments/{symbol}/funding?result_limit={limit}"
    if before_ms is not None:
        url += f"&time_to={datetime.fromtimestamp(before_ms / 1000, tz=timezone.utc).isoformat().replace('+00:00', 'Z')}"
    status, payload, error = http(url)
    if payload is None:
        return [], status, error
    rows = payload.get("results", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return [], status, f"unexpected payload shape: {type(rows).__name__}"
    points = []
    for r in rows:
        try:
            stamp = datetime.fromisoformat(str(r["event_time"]).replace("Z", "+00:00"))
            points.append((int(stamp.timestamp() * 1000), float(r["funding_rate"])))
        except (KeyError, ValueError, TypeError):
            continue
    return points, status, error


def dydx(symbol: str, before_ms: int | None, limit: int) -> tuple[list, int, str | None]:
    url = f"https://indexer.dydx.trade/v4/historicalFunding/{symbol}?limit={limit}"
    if before_ms is not None:
        stamp = (
            datetime.fromtimestamp(before_ms / 1000, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
        url += f"&effectiveBeforeOrAt={stamp}"
    status, payload, error = http(url)
    if payload is None:
        return [], status, error
    rows = payload.get("historicalFunding", []) or []
    points = []
    for r in rows:
        stamp = datetime.fromisoformat(str(r["effectiveAt"]).replace("Z", "+00:00"))
        points.append((int(stamp.timestamp() * 1000), float(r["rate"])))
    return points, status, error


# `rate_period_hours` is the period the quoted rate APPLIES TO, which is not
# always the sampling cadence. Deribit publishes an 8-hour rate sampled hourly;
# annualising it on the 1h sampling interval overstates by 8x.
VENUES: dict[str, dict[str, Any]] = {
    "okx": {"fn": okx, "rate_period_hours": 8, "symbols": {"BTC": "BTC-USDT-SWAP", "ETH": "ETH-USDT-SWAP"}},
    "binance": {"fn": binance, "rate_period_hours": 8, "symbols": {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}},
    "bybit": {"fn": bybit, "rate_period_hours": 8, "symbols": {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}},
    "deribit": {"fn": deribit, "rate_period_hours": 8, "symbols": {"BTC": "BTC-PERPETUAL", "ETH": "ETH-PERPETUAL"}},
    "hyperliquid": {"fn": hyperliquid, "rate_period_hours": 1, "symbols": {"BTC": "BTC", "ETH": "ETH"}},
    "dydx": {"fn": dydx, "rate_period_hours": 1, "symbols": {"BTC": "BTC-USD", "ETH": "ETH-USD"}},
    "coinbase_intx": {
        "fn": coinbase_intx,
        "rate_period_hours": 1,
        "symbols": {"BTC": "BTC-PERP", "ETH": "ETH-PERP"},
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Probe public perpetual funding sources for Campaign #53 feasibility.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--venues", nargs="*", default=sorted(VENUES))
    p.add_argument("--assets", nargs="*", default=["BTC", "ETH"])
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--depth-pages", type=int, default=MAX_DEPTH_PAGES)
    p.add_argument("--out-dir", default="artifacts/campaign53_source_probe")
    p.add_argument("--pause", type=float, default=0.4)
    return p.parse_args(argv)


def characterise(points: list[tuple[int, float]], rate_period_hours: float = 8.0) -> dict[str, Any]:
    if not points:
        return {"rows": 0}
    ordered = sorted(set(points))
    stamps = [p[0] for p in ordered]
    rates = [p[1] for p in ordered]
    deltas = [(b - a) / 3_600_000 for a, b in zip(stamps, stamps[1:])]

    cadence = None
    if deltas:
        counts: dict[float, int] = {}
        for d in deltas:
            counts[round(d, 3)] = counts.get(round(d, 3), 0) + 1
        cadence = max(counts, key=counts.get)

    irregular = sum(1 for d in deltas if cadence and abs(d - cadence) > 0.01)
    mean_rate = sum(rates) / len(rates)
    return {
        "rows": len(ordered),
        "first_utc": datetime.fromtimestamp(stamps[0] / 1000, tz=timezone.utc).isoformat(),
        "last_utc": datetime.fromtimestamp(stamps[-1] / 1000, tz=timezone.utc).isoformat(),
        "modal_cadence_hours": cadence,
        "irregular_intervals": irregular,
        "duplicate_timestamps": len(points) - len(set(points)),
        "monotonic_unique": len(set(stamps)) == len(stamps),
        "funding_rate_mean": mean_rate,
        "funding_rate_min": min(rates),
        "funding_rate_max": max(rates),
        "rate_period_hours": rate_period_hours,
        "annualised_mean_pct": round(mean_rate * (8760.0 / rate_period_hours) * 100, 3),
    }


def probe(name: str, fn: Callable, symbol: str, limit: int, pages: int, pause: float, rate_period_hours: float) -> dict[str, Any]:
    """Fetch the recent window, then walk backwards until the series is exhausted."""
    points, status, error = fn(symbol, None, limit)
    entry: dict[str, Any] = {"symbol": symbol, "http_status": status, "error": error}
    if not points:
        entry["recent"] = {"rows": 0}
        return entry

    entry["recent"] = characterise(points, rate_period_hours)
    collected = list(points)
    oldest = min(p[0] for p in points)
    pages_walked = 0

    for _ in range(max(0, pages)):
        time.sleep(pause)
        older, status, error = fn(symbol, oldest, limit)
        new = [p for p in older if p[0] < oldest]
        if not new:
            entry["depth_exhausted"] = True
            break
        collected.extend(new)
        oldest = min(p[0] for p in new)
        pages_walked += 1
    else:
        entry["depth_exhausted"] = False

    entry["depth_pages_walked"] = pages_walked
    entry["depth"] = characterise(collected, rate_period_hours)
    return entry


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    findings: dict[str, Any] = {
        "probe": "campaign53_source_feasibility_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "data_acquired": False,
        "note": "Venue reachability is location-dependent; re-run from any host intended for acquisition.",
        "venues": {},
    }

    for name in args.venues:
        spec = VENUES.get(name)
        if spec is None:
            print(f"Unknown venue: {name}")
            continue
        print(f"Probing {name} ...")
        findings["venues"][name] = {}
        for asset in args.assets:
            symbol = spec["symbols"].get(asset)
            if symbol is None:
                findings["venues"][name][asset] = {"status": "SYMBOL_NOT_MAPPED"}
                continue
            findings["venues"][name][asset] = probe(
                name, spec["fn"], symbol, args.limit, args.depth_pages, args.pause,
                spec["rate_period_hours"],
            )
            time.sleep(args.pause)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "source_probe_findings.json"
    path.write_text(json.dumps(findings, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("\n" + "=" * 96)
    header = (
        f"{'venue':<12}{'asset':<6}{'HTTP':>6}{'cadence':>9}{'rows':>7}"
        f"{'earliest reached':>22}{'exhausted':>11}{'ann.%':>9}"
    )
    print(header)
    print("-" * len(header))
    for venue, assets in findings["venues"].items():
        for asset, entry in sorted(assets.items()):
            depth = entry.get("depth", entry.get("recent", {}))
            status = entry.get("http_status", "-")
            if entry.get("error") and not depth.get("rows"):
                print(f"{venue:<12}{asset:<6}{str(status):>6}{'-':>9}{'-':>7}{str(entry['error'])[:22]:>22}{'-':>11}{'-':>9}")
                continue
            print(
                f"{venue:<12}{asset:<6}{str(status):>6}"
                f"{str(depth.get('modal_cadence_hours','-')):>9}{depth.get('rows',0):>7}"
                f"{str(depth.get('first_utc','-'))[:19]:>22}"
                f"{str(entry.get('depth_exhausted','-')):>11}"
                f"{str(depth.get('annualised_mean_pct','-')):>9}"
            )
    print("=" * 96)
    print(f"\nFindings: {path}")
    print("Read-only probe. No data acquired; bulk acquisition needs a board transition.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
