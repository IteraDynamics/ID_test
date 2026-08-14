"""Does real CDE history reach back further than the product's `new_at` field?

Campaign #53's adversarial review flagged an unverified, load-bearing assumption:
`probe_cde_product_detail.py`'s earlier output showed `new_at = '2025-07-18T13:00:00Z'`
for both BIP-20DEC30-CDE (BTC PERP) and ETP-20DEC30-CDE (ETH PERP). If that means
"this product did not exist before this date," the campaign has at most ~13 months
of history -- nowhere near the multi-year development/validation/holdout split the
frozen Charter's "why the historical record can test it" section assumes, and that
assumption has never been checked against CDE specifically since the pivot from
generic multi-venue funding history to CDE as the execution venue.

This settles it empirically rather than by guessing what `new_at` documents:
query the product's own public candle endpoint for a window starting well before
that date. If candles exist earlier, `new_at` does not mean "no trading before
this" (it plausibly marks something else -- a UI "new" badge, a re-listing, a
schema change) and the history-depth concern is resolved. If candles do not exist
earlier, the concern is confirmed and the campaign's temporal architecture needs
rethinking before Section 3 can freeze.

Separately, and honestly exploratory since no documentation was reachable to
confirm the correct endpoint shape: tries a small number of plausible historical-
funding-rate endpoint patterns and reports what each returns. A 404 across all of
them does not prove no such endpoint exists, only that these specific guesses
don't hit it -- report the raw results rather than a confident conclusion either
way.

Public, unauthenticated /market/ endpoints only. Read-only: writes findings to
`artifacts/`, nothing to `data/`.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE = "https://api.coinbase.com/api/v3/brokerage/market"
USER_AGENT = "itera-research-feasibility-probe/2.5"
TIMEOUT_SECONDS = 25


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
    except Exception as exc:  # noqa: BLE001 — a probe reports, never raises
        return 0, None, f"{type(exc).__name__}: {exc}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--product-id", action="append", default=None,
                   help="Repeatable. Default: BIP-20DEC30-CDE and ETP-20DEC30-CDE.")
    p.add_argument("--probe-start", default="2023-01-01",
                   help="How far before new_at to probe for candle history.")
    p.add_argument("--out-dir", default="artifacts/campaign53_source_probe")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    product_ids = args.product_id or ["BIP-20DEC30-CDE", "ETP-20DEC30-CDE"]
    probe_start = datetime.fromisoformat(args.probe_start).replace(tzinfo=timezone.utc)

    findings: dict[str, Any] = {"probe": "cde_history_depth_v1", "products": {}, "funding_history_attempts": {}}

    print("=== Candle history depth (does data exist before new_at?) ===\n")
    for product_id in product_ids:
        # Advanced Trade candles endpoint, documented and already known to work
        # for spot/index products; testing it here against a CDE futures product.
        end = probe_start + timedelta(days=10)
        url = (f"{BASE}/products/{product_id}/candles"
               f"?start={int(probe_start.timestamp())}&end={int(end.timestamp())}"
               f"&granularity=ONE_DAY")
        status, payload, error = http(url)
        candles = (payload or {}).get("candles", []) if isinstance(payload, dict) else []
        findings["products"][product_id] = {
            "http_status": status, "error": error,
            "probe_window_start": probe_start.isoformat(),
            "candles_found": len(candles),
        }
        print(f"{product_id}: HTTP {status}, {len(candles)} candles in "
              f"{probe_start.date()}..{end.date()}" + (f"  ({error})" if error else ""))
        if candles:
            print(f"  -> Real trading data exists before new_at (2025-07-18). "
                  f"new_at does NOT mean 'no history before this'.")
        elif status == 200:
            print(f"  -> Endpoint reachable, zero candles in this window. Consistent with "
                  f"new_at marking genuine product inception -- try a window closer to "
                  f"new_at to confirm precisely where history starts.")

    print("\n=== Historical funding endpoint (exploratory, patterns not confirmed against docs) ===\n")
    candidate_patterns = [
        "{base}/products/{pid}/funding",
        "{base}/products/{pid}/funding-rate-history",
        "{base}/products/{pid}/historicalfunding",
        "{base}/products/{pid}/funding_rate_history",
    ]
    for product_id in product_ids:
        for pattern in candidate_patterns:
            url = pattern.format(base=BASE, pid=product_id)
            status, payload, error = http(url)
            key = f"{product_id}:{pattern.split('/')[-1]}"
            findings["funding_history_attempts"][key] = {"url": url, "http_status": status, "error": error}
            print(f"{key}: HTTP {status}" + (f"  ({error})" if error else "  -- reachable, inspect payload"))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cde_history_depth_findings.json"
    out_path.write_text(json.dumps(findings, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(f"\nFindings: {out_path}")
    print(
        "\nIf candle history exists before new_at: that concern is resolved, and this probe's "
        "job is done regardless of the funding-history patterns above.\n"
        "If no candle history exists before new_at, and none of the funding-history patterns "
        "return real data: both open items in Campaign 53's adversarial review are confirmed, "
        "not just suspected, and Section 3 should not freeze until the temporal architecture "
        "is reconsidered against however much history genuinely exists."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
