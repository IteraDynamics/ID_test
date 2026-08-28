"""Does CDE expose historical funding-rate data through ANY endpoint -- broader search.

`probe_cde_history_depth.py` (2026-08-14) tried four guessed historical-funding-endpoint
patterns against the public, unauthenticated `/market/` prefix and got HTTP 404 on all four. Its
own stated criterion was explicit: if that happened *and* no candle history existed before
`new_at`, "Section 3 should not freeze until the temporal architecture is reconsidered." Both
conditions were true. Campaign #53's specification was frozen anyway on 2026-08-20, treating
"CDE's contracts are ~13 months old" (confirmed via candles) as equivalent to "CDE's funding
RATE history is retrievable for that same 13 months" (never actually confirmed) -- two different
claims that got conflated. This probe exists to actually resolve the second one before any
acquisition work assumes it.

Three things this script does that the earlier probe didn't:

1. A much broader set of public, unauthenticated path guesses (more REST naming conventions),
   under both the `/market/` prefix (public, read-only mirror) and the bare `/brokerage/` prefix
   (normally requires auth for Advanced Trade -- but an unauthenticated request against it still
   tells us something: a 401 means the endpoint plausibly EXISTS and just needs credentials, a
   404 means it plausibly doesn't exist at all under that path. That distinction is real
   information even without completing authentication).
2. Two clearly-labeled, speculative alternate-domain guesses for CDE specifically (it is a
   CFTC-regulated futures exchange; regulated futures exchanges often publish public historical/
   settlement data separately from their trading API, and CDE could plausibly do the same on a
   different subdomain). These are genuinely guesses, not documented facts -- reported as HTTP
   status only, same as everything else here.
3. Explicit next steps for the operator to check directly, which this sandboxed, unauthenticated,
   network-restricted environment cannot do: (a) the Coinbase Developer Platform's own API
   reference, reachable from the operator's own browser but not from here; (b) whether CDE
   publishes bulk historical/settlement data files on its public site, which regulated futures
   exchanges often do as a transparency practice, and which would not be discoverable by guessing
   REST paths at all; (c) whether an authenticated request (using the operator's now-approved
   derivatives account) reaches a historical funding endpoint that an unauthenticated one cannot
   even see the shape of.

A clean sweep of 404s here does not prove no such endpoint exists -- same honest framing as the
original probe. It narrows the search meaningfully and separates "genuinely no path found" from
"needs the operator's own account or a manual check this environment cannot perform."

Public, unauthenticated /market/ and /brokerage/ endpoints only, plus two speculative domain
guesses. Read-only: writes findings to `artifacts/`, nothing to `data/`, never sends credentials.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

MARKET_BASE = "https://api.coinbase.com/api/v3/brokerage/market"
BROKERAGE_BASE = "https://api.coinbase.com/api/v3/brokerage"
USER_AGENT = "itera-research-feasibility-probe/2.6"
TIMEOUT_SECONDS = 25

# Broader than the original four -- more REST naming conventions, plural/singular variants,
# a couple of query-parameter-based guesses on the already-known-working candles endpoint.
PATH_SUFFIXES = [
    "funding",
    "fundings",
    "funding-rate",
    "funding-rates",
    "funding_rate",
    "funding_rates",
    "funding-rate-history",
    "funding_rate_history",
    "funding-history",
    "funding_history",
    "historicalfunding",
    "historical-funding",
    "historical_funding",
    "rates",
    "rates/history",
]

# Genuinely speculative -- CDE is a CFTC-regulated futures exchange, and regulated futures
# exchanges commonly publish historical/settlement data separately from their trading API as a
# transparency practice. No documentation confirms these exist; reported as plain HTTP status.
SPECULATIVE_DOMAIN_GUESSES = [
    "https://data.coinbase.com/derivatives/funding",
    "https://www.coinbase.com/derivatives/api/funding-history",
]


def http(url: str) -> tuple[int, Any, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            body = ""
        return exc.code, body, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 -- a probe reports, never raises
        return 0, None, f"{type(exc).__name__}: {exc}"


def classify(status: int) -> str:
    if status == 200:
        return "REACHABLE -- inspect payload, this is the interesting case"
    if status == 401 or status == 403:
        return "AUTH-GATED -- plausibly exists, needs the operator's own authenticated account"
    if status == 404:
        return "not found under this path"
    if status == 0:
        return "request failed (network/DNS) -- not evidence either way"
    return f"unexpected status"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--product-id", action="append", default=None,
                   help="Repeatable. Default: BIP-20DEC30-CDE and ETP-20DEC30-CDE.")
    p.add_argument("--out-dir", default="artifacts/campaign53_source_probe")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    product_ids = args.product_id or ["BIP-20DEC30-CDE", "ETP-20DEC30-CDE"]

    findings: dict[str, Any] = {
        "probe": "cde_funding_history_endpoint_broad_v1",
        "public_market_prefix": {},
        "bare_brokerage_prefix": {},
        "speculative_domains": {},
    }

    print("=== Broad path search, public /market/ prefix (unauthenticated) ===\n")
    for product_id in product_ids:
        for suffix in PATH_SUFFIXES:
            url = f"{MARKET_BASE}/products/{product_id}/{suffix}"
            status, _, error = http(url)
            key = f"{product_id}:{suffix}"
            findings["public_market_prefix"][key] = {"url": url, "http_status": status, "error": error}
            note = classify(status)
            if status in (200, 401, 403):
                print(f"  {key}: HTTP {status} -- {note}  [{url}]")
    print("  (404s and failures suppressed from output above for readability -- full detail in the JSON)")

    print("\n=== Same paths, bare /brokerage/ prefix (normally auth-required; unauthenticated here) ===\n")
    print("A 401/403 here is real signal -- it means the path plausibly exists once you're authenticated.\n")
    for product_id in product_ids:
        for suffix in PATH_SUFFIXES:
            url = f"{BROKERAGE_BASE}/products/{product_id}/{suffix}"
            status, _, error = http(url)
            key = f"{product_id}:{suffix}"
            findings["bare_brokerage_prefix"][key] = {"url": url, "http_status": status, "error": error}
            note = classify(status)
            if status in (200, 401, 403):
                print(f"  {key}: HTTP {status} -- {note}  [{url}]")
    print("  (404s and failures suppressed from output above for readability -- full detail in the JSON)")

    print("\n=== Speculative alternate domains (genuinely guessed, not documented) ===\n")
    for url in SPECULATIVE_DOMAIN_GUESSES:
        status, _, error = http(url)
        findings["speculative_domains"][url] = {"http_status": status, "error": error}
        print(f"  {url}: HTTP {status} -- {classify(status)}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cde_funding_history_endpoint_broad_findings.json"
    out_path.write_text(json.dumps(findings, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    any_200 = any(v["http_status"] == 200 for v in {**findings["public_market_prefix"], **findings["bare_brokerage_prefix"]}.values())
    any_auth_gated = any(v["http_status"] in (401, 403) for v in {**findings["public_market_prefix"], **findings["bare_brokerage_prefix"]}.values())

    print(f"\nFindings: {out_path}")
    print("\n=== Verdict ===")
    if any_200:
        print("At least one path returned HTTP 200 -- inspect the payload in the JSON output directly, "
              "this may be the endpoint.")
    elif any_auth_gated:
        print("No path reachable unauthenticated, but at least one returned 401/403 rather than 404 -- "
              "worth trying again with the operator's own authenticated API credentials before "
              "concluding no historical funding endpoint exists.")
    else:
        print("Clean sweep of 404s / unreachable, same as the original four-pattern probe, now across "
              "a much broader guess set. This still does not prove no endpoint exists, but the case for "
              "one being reachable by guessing REST paths is now weak. Two things this environment "
              "genuinely cannot do and the operator should check directly:")
        print("  1. The Coinbase Developer Platform's own API reference (docs.cdp.coinbase.com), reachable "
              "from a normal browser but not from this sandboxed session.")
        print("  2. Whether CDE publishes bulk historical/settlement data files on its public site -- "
              "common practice for CFTC-regulated futures exchanges, and would not show up as a REST "
              "endpoint guess at all.")
        print("If neither turns up a source, the honest fallback is: CDE confirmation data starts "
              "accumulating from whenever polling begins, not backfilled -- a real, if narrower, "
              "constraint on Campaign 53's confirmation stage that its frozen Section 3 does not "
              "currently account for.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
