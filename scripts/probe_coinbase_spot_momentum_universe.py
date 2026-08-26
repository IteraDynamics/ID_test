"""Coinbase spot cross-sectional momentum -- universe history-depth probe.

Gate 2 (tradeability) for the cross-sectional crypto momentum idea named the venue: Coinbase's
regular retail spot exchange (not CDE, not INTX -- CDE only has 5 matched perp+dated names, too
narrow for a real cross-section). The operator confirmed real, current spot-tradable access to a
broad universe (2026-08-26 screenshots: 50+ names including majors, mid-caps and long-tail).

What's still unverified: whether that breadth holds up historically. A momentum cross-section
needs CONTEMPORANEOUS history across the basket -- if half the universe only listed 18 months
ago, either the backtest window shrinks to 18 months (weak power) or the basket composition
changes discontinuously over the backtest (survivorship/look-ahead risk in which names were even
listed at a given historical date). This script does not build a strategy or compute momentum --
it only measures how far back real daily price history goes, per product, using the exact
endpoint scripts/fetch_coinbase_hourly_history.py already confirmed works in this repo
(https://api.exchange.coinbase.com/products/{product_id}/candles, public, unauthenticated).

Method: binary search each product's earliest available daily candle between a floor date
(2015-01-01, before which Coinbase itself barely existed) and today. ~12 iterations per product,
each checking a short window (not a single day, to avoid candle-boundary false negatives) for any
returned rows. Cheap (a few dozen requests per product) and read-only -- no order placement, no
authentication, matches this repo's existing probe convention (findings to artifacts/, a report
that never raises).

Candidate list below is the real, current spot-tradable product set from the operator's own
Coinbase app screenshots (2026-08-26) -- not guessed, not asserted from memory. It mixes majors,
established mid-caps and clearly recent-vintage tokens (PENGU, MON, VVV, WIF, BONK) on purpose:
the point of this probe is to find out where the real history cutoff falls across that mix, not
to pre-filter to names likely to look good.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"
GRANULARITY_SECONDS = 86400  # daily -- cheapest resolution sufficient for a history-depth probe
PROBE_WINDOW_DAYS = 5  # check a short window, not a single day, to avoid candle-boundary misses
BISECTION_ITERATIONS = 13  # ~ (today - floor) / 2^13 < 1 day resolution over an 11yr range
# Note: because has_data() checks a PROBE_WINDOW_DAYS-wide window rather than a single day (to
# avoid candle-boundary false negatives), the converged earliest_date is biased up to
# PROBE_WINDOW_DAYS EARLY relative to the true first candle -- i.e. this probe slightly
# OVERSTATES years_of_history, by at most PROBE_WINDOW_DAYS out of however many hundreds/
# thousands of days a product actually has. Immaterial at that magnitude for a discovery-stage
# depth check, but worth knowing before treating any reported date as precise to the day.
FLOOR_DATE = datetime(2015, 1, 1, tzinfo=timezone.utc)  # Coinbase itself barely existed earlier
DEFAULT_SLEEP_SECONDS = 0.20
USER_AGENT = "IteraDynamics-research-probe/1.0"

# Real, current spot-tradable products from the operator's own Coinbase app (2026-08-26
# screenshots) -- majors, established mid-caps, and clearly recent-vintage tokens deliberately
# left in, not pre-filtered.
CANDIDATE_PRODUCTS = [
    "BTC-USD", "ETH-USD", "XRP-USD", "SOL-USD", "ZEC-USD", "DOGE-USD", "SUI-USD", "LINK-USD",
    "ADA-USD", "MDT-USD", "XLM-USD", "NEAR-USD", "AERO-USD", "VVV-USD", "PENGU-USD", "HBAR-USD",
    "TAO-USD", "ONDO-USD", "LTC-USD", "AAVE-USD", "UNI-USD", "AVAX-USD", "PEPE-USD", "DOT-USD",
    "POL-USD", "STX-USD", "WIF-USD", "BCH-USD", "ETC-USD", "FIL-USD", "RENDER-USD", "MON-USD",
    "JASMY-USD", "FET-USD", "ICP-USD", "JTO-USD", "INJ-USD", "MORPHO-USD", "SEI-USD", "BONK-USD",
    "BICO-USD", "CRV-USD", "PAXG-USD", "SHIB-USD", "PLU-USD", "APT-USD", "ALGO-USD", "SQD-USD",
    "TIA-USD", "ATOM-USD", "PENDLE-USD",
]


@dataclass
class ProbeResult:
    product_id: str
    reachable: bool
    earliest_date: str | None = None
    years_of_history: float | None = None
    error: str | None = None
    requests_used: int = 0
    warnings: list[str] = field(default_factory=list)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def has_data(product_id: str, window_start: datetime, timeout: int = 20) -> bool:
    """True if the product has at least one daily candle in [window_start, window_start+N days)."""
    window_end = window_start + timedelta(days=PROBE_WINDOW_DAYS)
    params = urllib.parse.urlencode(
        {"start": iso_z(window_start), "end": iso_z(window_end), "granularity": str(GRANULARITY_SECONDS)}
    )
    url = f"{BASE_URL.format(product_id=product_id)}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return isinstance(payload, list) and len(payload) > 0


def probe_product(product_id: str, sleep_seconds: float, retries: int) -> ProbeResult:
    result = ProbeResult(product_id=product_id, reachable=False)

    def query(window_start: datetime) -> bool:
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                result.requests_used += 1
                return has_data(product_id, window_start)
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    # Product doesn't exist / was never listed under this id -- not a transient error.
                    return False
                last_exc = exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_exc = exc
            time.sleep(sleep_seconds * (attempt + 1))
        raise RuntimeError(str(last_exc))

    try:
        now = datetime.now(timezone.utc)
        # Sanity: confirm the product currently has data at all before bisecting its history.
        if not query(now - timedelta(days=PROBE_WINDOW_DAYS)):
            result.error = "no recent data (product may be delisted or id wrong)"
            return result
        time.sleep(sleep_seconds)

        # Confirm data exists at the floor date's neighborhood -- if so, we can't tell how much
        # further back it goes (Coinbase itself is only ~13yrs old, floor is a reasonable cap for
        # this probe's purpose: distinguishing "long-established" from "recently listed").
        floor_has_data = query(FLOOR_DATE)
        time.sleep(sleep_seconds)

        if floor_has_data:
            result.reachable = True
            result.earliest_date = FLOOR_DATE.date().isoformat()
            result.warnings.append(f"data present at floor {FLOOR_DATE.date()} -- true earliest may be older")
            result.years_of_history = (now - FLOOR_DATE).days / 365.25
            return result

        lo, hi = FLOOR_DATE, now
        for _ in range(BISECTION_ITERATIONS):
            mid = lo + (hi - lo) / 2
            if query(mid):
                hi = mid
            else:
                lo = mid
            time.sleep(sleep_seconds)

        result.reachable = True
        result.earliest_date = hi.date().isoformat()
        result.years_of_history = (now - hi).days / 365.25
        return result
    except Exception as exc:  # noqa: BLE001 -- a probe must never raise, only report
        result.error = f"{type(exc).__name__}: {exc}"
        return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--products", nargs="+", default=CANDIDATE_PRODUCTS)
    p.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--out-dir", default="artifacts")
    p.add_argument("--out-name", default="coinbase_spot_momentum_universe_probe.json")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[ProbeResult] = []
    for i, product_id in enumerate(args.products, 1):
        print(f"[{i}/{len(args.products)}] probing {product_id} ...", flush=True)
        r = probe_product(product_id, args.sleep_seconds, args.retries)
        results.append(r)
        if r.error:
            print(f"  FAILED: {r.error}")
        else:
            print(f"  earliest daily candle: ~{r.earliest_date}  (~{r.years_of_history:.1f}y of history)")
            for w in r.warnings:
                print(f"  note: {w}")

    payload = {
        "generated_at_utc": iso_z(datetime.now(timezone.utc)),
        "endpoint": BASE_URL,
        "method": "binary search for earliest daily candle, bounded at floor date "
                  f"{FLOOR_DATE.date().isoformat()}, {BISECTION_ITERATIONS} iterations",
        "products": [
            {
                "product_id": r.product_id,
                "reachable": r.reachable,
                "earliest_date": r.earliest_date,
                "years_of_history": r.years_of_history,
                "error": r.error,
                "warnings": r.warnings,
                "requests_used": r.requests_used,
            }
            for r in results
        ],
    }
    out_path = out_dir / args.out_name
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    ok = [r for r in results if r.reachable and r.years_of_history is not None]
    failed = [r for r in results if not r.reachable]
    print(f"\n{'='*70}")
    print(f"{len(ok)}/{len(results)} products reachable with history data. {len(failed)} failed.")
    if failed:
        print("Failed / unreachable:", ", ".join(r.product_id for r in failed))
    if ok:
        ok_sorted = sorted(ok, key=lambda r: r.years_of_history, reverse=True)
        for threshold in (5, 3, 2, 1):
            n = sum(1 for r in ok if r.years_of_history >= threshold)
            print(f"  >= {threshold}y of history: {n}/{len(ok)} products")
        print(f"\nLongest history: {ok_sorted[0].product_id} (~{ok_sorted[0].years_of_history:.1f}y)")
        print(f"Shortest history: {ok_sorted[-1].product_id} (~{ok_sorted[-1].years_of_history:.1f}y)")
    print(f"\nWrote {out_path}")
    print("\nThis is a reachability/history-depth probe only -- no momentum signal computed, no")
    print("strategy backtest run. Next step if the universe looks viable: decide a fixed-size")
    print("cross-section (e.g. top-N by history depth and liquidity) and a frozen formation date,")
    print("not a universe that silently grows as more coins clear a history bar over time.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
