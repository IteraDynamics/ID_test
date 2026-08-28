"""Verify the real CDE historical funding-rate endpoint before building acquisition around it.

The operator found the actual OpenAPI spec (docs.cdp.coinbase.com), which this sandboxed,
egress-blocked environment could not reach or discover by guessing. Key facts from that spec,
none of them assumed:

- Base URL is a DIFFERENT domain entirely: https://api.exchange.fairx.net (FairX was the
  CFTC-regulated exchange Coinbase acquired to become CDE) -- not api.coinbase.com, which is why
  every guess against that domain in the earlier probes was structurally unable to find it.
- Path: GET /rest/funding-rate, query params `symbol` (required) and `trading_session_date`
  (optional, YYYY-MM-DD, defaults to today).
- The operation-level `security: []` in the spec overrides the global auth requirement -- this
  specific endpoint may not need authentication at all, unlike the rest of the API. Worth
  confirming empirically rather than assuming the override is meaningful in practice.
- Symbol format is NOT the Advanced Trade product ID (`BIP-20DEC30-CDE`). The spec's own example,
  "BIPZ30", is standard futures month-code notation: Z = December, 30 = 2030 -- matching our
  already-confirmed product's 20DEC30 expiry exactly. Derived, not found in the spec: BTC ->
  BIPZ30, ETH -> ETPZ30 (same BIP/ETP root prefixes already confirmed via the Advanced Trade
  product IDs). This probe exists partly to confirm that derivation is actually correct.
- The endpoint returns data for ONE trading_session_date per call, not a range -- a real
  acquisition script needs to iterate day by day, not fetch in one shot.

This probe makes a small number of calls (both symbols, a couple of sample dates -- today and a
date near the product's confirmed ~2025-07-18 inception) to answer four questions before any
acquisition script gets built: does it work unauthenticated, is the derived symbol format
correct, how far back does trading_session_date actually go, and what does a real response
look like.

Public GET requests only (no auth attempted first, per the spec's own override). Read-only:
writes findings to `artifacts/`, nothing to `data/`.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE = "https://api.exchange.fairx.net/rest/funding-rate"
USER_AGENT = "itera-research-feasibility-probe/2.7"
TIMEOUT_SECONDS = 25

SYMBOLS = {"BTC": "BIPZ30", "ETH": "ETPZ30"}


def http(url: str) -> tuple[int, Any, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
            try:
                return response.status, json.loads(body), None
            except json.JSONDecodeError:
                return response.status, body, "response was not valid JSON"
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            body = ""
        return exc.code, body, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 -- a probe reports, never raises
        return 0, None, f"{type(exc).__name__}: {exc}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--probe-dates",
        nargs="*",
        default=None,
        help="YYYY-MM-DD dates to sample. Default: today, 30 days ago, and near the product's "
             "confirmed 2025-07-18 inception.",
    )
    p.add_argument("--out-dir", default="artifacts/campaign53_source_probe")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    today = datetime.now(timezone.utc).date()
    probe_dates = args.probe_dates or [
        today.isoformat(),
        (today - timedelta(days=30)).isoformat(),
        "2025-07-20",  # two days after confirmed product inception
        "2025-07-15",  # before confirmed inception -- expect empty/error, a useful boundary check
    ]

    findings: dict[str, Any] = {"probe": "cde_funding_rate_endpoint_v1", "calls": {}}

    print("=== No-date call (defaults to today per the spec) ===\n")
    for asset, symbol in SYMBOLS.items():
        url = f"{BASE}?{urllib.parse.urlencode({'symbol': symbol})}"
        status, payload, error = http(url)
        key = f"{asset}:{symbol}:no_date"
        findings["calls"][key] = {"url": url, "http_status": status, "error": error, "payload": payload}
        n = len(payload) if isinstance(payload, list) else None
        print(f"{key}: HTTP {status}" + (f", {n} records" if n is not None else "") + (f"  ({error})" if error else ""))
        if isinstance(payload, list) and payload:
            print(f"  sample record: {json.dumps(payload[0])}")

    print("\n=== Explicit trading_session_date calls ===\n")
    for asset, symbol in SYMBOLS.items():
        for date_str in probe_dates:
            url = f"{BASE}?{urllib.parse.urlencode({'symbol': symbol, 'trading_session_date': date_str})}"
            status, payload, error = http(url)
            key = f"{asset}:{symbol}:{date_str}"
            findings["calls"][key] = {"url": url, "http_status": status, "error": error, "payload": payload}
            n = len(payload) if isinstance(payload, list) else None
            print(f"{key}: HTTP {status}" + (f", {n} records" if n is not None else "") + (f"  ({error})" if error else ""))
            if isinstance(payload, list) and payload:
                print(f"  sample record: {json.dumps(payload[0])}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cde_funding_rate_endpoint_probe_findings.json"
    out_path.write_text(json.dumps(findings, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    any_200_with_data = any(
        v["http_status"] == 200 and isinstance(v["payload"], list) and len(v["payload"]) > 0
        for v in findings["calls"].values()
    )
    any_401 = any(v["http_status"] in (401, 403) for v in findings["calls"].values())

    print(f"\nFindings: {out_path}")
    print("\n=== Verdict ===")
    if any_200_with_data:
        print("At least one call returned real records unauthenticated. The endpoint is real, the "
              "derived symbol format works, and no auth is required for this specific operation, "
              "matching the spec's own security override. Next step: build the real day-by-day "
              "acquisition script.")
    elif any_401:
        print("Got 401/403 despite the spec's security override -- the override may not be honored "
              "in practice, or something else is gating this. Try again with an authenticated "
              "request (CB-ACCESS-KEY/SIGN/TIMESTAMP/PASSPHRASE, per the spec's auth scheme) before "
              "concluding anything.")
    else:
        print("No records came back on any date, including 2025-07-20 (two days after confirmed "
              "product inception). Either the symbol format is wrong (check the sample record if "
              "any call returned HTTP 200 with an empty list vs. a real error), or "
              "trading_session_date needs a different format/timezone than assumed. Inspect the "
              "raw JSON output before building anything further.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
