"""Campaign #53 source feasibility probe — read-only, no data acquisition.

Establishes empirically what perpetual funding, open-interest and basis history
is actually obtainable, before any acquisition design is frozen. Answers the
questions the Campaign #53 charter's feasibility section requires:

  - which venues respond, and on what endpoint shape;
  - how far back funding history actually goes per venue and symbol;
  - the true settlement cadence (nominally 8h, but venue- and era-dependent);
  - whether the series has gaps, duplicates, or non-monotonic timestamps;
  - whether open interest carries usable history or is snapshot-only.

This probe fetches only small samples -- enough to characterise coverage. It
does not build a dataset, does not write to `data/`, and does not compute any
predictor or outcome. Bulk acquisition requires a separate board transition
per the Campaign #53 charter.

Public market-data endpoints only. No API key, no authentication, no trading
scope, no account access.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

USER_AGENT = "itera-research-feasibility-probe/1.0"
TIMEOUT_SECONDS = 20

# Public funding-history endpoints. Response shapes differ per venue; the probe
# normalises to (timestamp_ms, funding_rate) via the extractor for each.
VENUES: dict[str, dict[str, Any]] = {
    "binance": {
        "funding_url": "https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit={limit}",
        "funding_url_paged": "https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&startTime={start_ms}&limit={limit}",
        "oi_url": "https://fapi.binance.com/futures/data/openInterestHist?symbol={symbol}&period=1h&limit=10",
        "symbols": {"BTC": "BTCUSDT", "ETH": "ETHUSDT"},
        "funding_extract": lambda rows: [
            (int(r["fundingTime"]), float(r["fundingRate"])) for r in rows
        ],
    },
    "bybit": {
        "funding_url": "https://api.bybit.com/v5/market/funding/history?category=linear&symbol={symbol}&limit={limit}",
        "funding_url_paged": "https://api.bybit.com/v5/market/funding/history?category=linear&symbol={symbol}&startTime={start_ms}&limit={limit}",
        "oi_url": "https://api.bybit.com/v5/market/open-interest?category=linear&symbol={symbol}&intervalTime=1h&limit=10",
        "symbols": {"BTC": "BTCUSDT", "ETH": "ETHUSDT"},
        "funding_extract": lambda payload: [
            (int(r["fundingRateTimestamp"]), float(r["fundingRate"]))
            for r in payload["result"]["list"]
        ],
    },
    "okx": {
        "funding_url": "https://www.okx.com/api/v5/public/funding-rate-history?instId={symbol}&limit={limit}",
        "funding_url_paged": "https://www.okx.com/api/v5/public/funding-rate-history?instId={symbol}&after={start_ms}&limit={limit}",
        "oi_url": "https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId={symbol}",
        "symbols": {"BTC": "BTC-USDT-SWAP", "ETH": "ETH-USDT-SWAP"},
        "funding_extract": lambda payload: [
            (int(r["fundingTime"]), float(r["fundingRate"])) for r in payload["data"]
        ],
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Probe public perpetual funding/OI sources for Campaign #53 feasibility.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--venues", nargs="*", default=sorted(VENUES))
    p.add_argument("--assets", nargs="*", default=["BTC", "ETH"])
    p.add_argument("--limit", type=int, default=200, help="Rows per sample request.")
    p.add_argument("--out-dir", default="artifacts/campaign53_source_probe")
    p.add_argument("--pause", type=float, default=0.4, help="Seconds between requests.")
    return p.parse_args(argv)


def fetch(url: str) -> tuple[int, Any, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, f"HTTPError: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 - probe reports, never raises
        return 0, None, f"{type(exc).__name__}: {exc}"


def characterise(points: list[tuple[int, float]]) -> dict[str, Any]:
    """Describe cadence, ordering and gaps of a funding series sample."""
    if not points:
        return {"rows": 0}
    ordered = sorted(points)
    stamps = [p[0] for p in ordered]
    rates = [p[1] for p in ordered]
    deltas = [(b - a) / 3_600_000 for a, b in zip(stamps, stamps[1:])]
    duplicates = len(stamps) - len(set(stamps))

    cadence_hours = None
    if deltas:
        counts: dict[float, int] = {}
        for d in deltas:
            key = round(d, 3)
            counts[key] = counts.get(key, 0) + 1
        cadence_hours = max(counts, key=counts.get)

    irregular = (
        sum(1 for d in deltas if cadence_hours and abs(d - cadence_hours) > 0.01) if deltas else 0
    )
    return {
        "rows": len(ordered),
        "first_utc": datetime.fromtimestamp(stamps[0] / 1000, tz=timezone.utc).isoformat(),
        "last_utc": datetime.fromtimestamp(stamps[-1] / 1000, tz=timezone.utc).isoformat(),
        "modal_cadence_hours": cadence_hours,
        "irregular_intervals": irregular,
        "duplicate_timestamps": duplicates,
        "monotonic": stamps == sorted(stamps) and duplicates == 0,
        "funding_rate_min": min(rates),
        "funding_rate_max": max(rates),
        "funding_rate_mean": sum(rates) / len(rates),
        "annualised_mean_pct_at_modal_cadence": (
            round(sum(rates) / len(rates) * (24 / cadence_hours) * 365 * 100, 3)
            if cadence_hours
            else None
        ),
    }


def probe_venue(name: str, spec: dict[str, Any], assets: list[str], limit: int, pause: float) -> dict[str, Any]:
    result: dict[str, Any] = {"venue": name, "assets": {}}
    for asset in assets:
        symbol = spec["symbols"].get(asset)
        if symbol is None:
            result["assets"][asset] = {"status": "SYMBOL_NOT_MAPPED"}
            continue

        entry: dict[str, Any] = {"symbol": symbol}

        url = spec["funding_url"].format(symbol=symbol, limit=limit)
        status, payload, error = fetch(url)
        entry["funding_recent"] = {"http_status": status, "error": error}
        if payload is not None:
            try:
                points = spec["funding_extract"](payload)
                entry["funding_recent"].update(characterise(points))
            except Exception as exc:  # noqa: BLE001
                entry["funding_recent"]["parse_error"] = f"{type(exc).__name__}: {exc}"
        time.sleep(pause)

        # How far back does history reach? Ask from an early date and see what returns.
        early_ms = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        url = spec["funding_url_paged"].format(symbol=symbol, start_ms=early_ms, limit=limit)
        status, payload, error = fetch(url)
        entry["funding_from_2020"] = {"http_status": status, "error": error}
        if payload is not None:
            try:
                points = spec["funding_extract"](payload)
                entry["funding_from_2020"].update(characterise(points))
            except Exception as exc:  # noqa: BLE001
                entry["funding_from_2020"]["parse_error"] = f"{type(exc).__name__}: {exc}"
        time.sleep(pause)

        url = spec["oi_url"].format(symbol=symbol)
        status, payload, error = fetch(url)
        entry["open_interest"] = {
            "http_status": status,
            "error": error,
            "sample_present": payload is not None,
        }
        time.sleep(pause)

        result["assets"][asset] = entry
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    findings = {
        "probe": "campaign53_source_feasibility_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "data_acquired": False,
        "venues": [],
    }

    for name in args.venues:
        spec = VENUES.get(name)
        if spec is None:
            print(f"Unknown venue: {name}")
            continue
        print(f"Probing {name} ...")
        findings["venues"].append(probe_venue(name, spec, args.assets, args.limit, args.pause))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "source_probe_findings.json"
    path.write_text(json.dumps(findings, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("\n" + "=" * 84)
    header = f"{'venue':<10}{'asset':<6}{'recent':>8}{'cadence':>9}{'earliest available':>28}{'mono':>6}"
    print(header)
    print("-" * len(header))
    for venue in findings["venues"]:
        for asset, entry in sorted(venue.get("assets", {}).items()):
            recent = entry.get("funding_recent", {})
            early = entry.get("funding_from_2020", {})
            status = recent.get("http_status", "-")
            cadence = recent.get("modal_cadence_hours", "-")
            earliest = early.get("first_utc", early.get("error", "-"))
            mono = recent.get("monotonic", "-")
            print(f"{venue['venue']:<10}{asset:<6}{str(status):>8}{str(cadence):>9}{str(earliest)[:28]:>28}{str(mono):>6}")
    print("=" * 84)
    print(f"\nFindings: {path}")
    print("Read-only probe. No data acquired; bulk acquisition needs a board transition.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
