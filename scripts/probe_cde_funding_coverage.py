"""Check funding_rate coverage across the full liquid CDE perpetual-style set.

`probe_cde_product_detail.py` found that `future_product_details.funding_rate`
is populated for BTC PERP and ETH PERP, even though the bulk `/market/products`
list's `perpetual_details.funding_rate` field -- the one the original feasibility
probe read -- is empty for all 99 CDE products. That was a probe reading the
wrong nested path, not genuinely absent data.

This re-derives the liquid perpetual-style CDE universe fresh (same query as
`probe_coinbase_derivatives_universe.py`, so it doesn't depend on a possibly
stale saved findings file) and checks the correct field,
`future_product_details.funding_rate`, for every liquid instrument -- so the
"funding is available" finding is established across the cross-section a
campaign would actually use, not inferred from two examples.

Public, unauthenticated /market/ endpoint. Read-only: writes findings to
`artifacts/`, nothing to `data/`.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = "https://api.coinbase.com/api/v3/brokerage/market"
USER_AGENT = "itera-research-feasibility-probe/2.3"
TIMEOUT_SECONDS = 25
PERPETUAL_STYLE_YEAR = 2029


def http(url: str) -> tuple[int, Any, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 — a probe reports, never raises
        return 0, None, f"{type(exc).__name__}: {exc}"


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--min-volume", type=float, default=1_000_000.0)
    p.add_argument("--out-dir", default="artifacts/campaign53_source_probe")
    return p.parse_args(argv)


def expiry_year(product_id: str) -> int | None:
    parts = product_id.split("-")
    if len(parts) < 2 or len(parts[1]) < 2 or not parts[1][-2:].isdigit():
        return None
    return 2000 + int(parts[1][-2:])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    status, payload, error = http(f"{BASE}/products?product_type=FUTURE&contract_expiry_type=EXPIRING")
    if not isinstance(payload, dict):
        print(f"Universe fetch failed: HTTP {status} ({error})")
        return 1
    products = payload.get("products", [])
    cde = [p for p in products if isinstance(p, dict)
           and str((p.get("future_product_details") or {}).get("venue", "")).lower() == "cde"]

    def volume(p: dict) -> float:
        v = to_float(p.get("approximate_quote_24h_volume"))
        return v if v is not None else 0.0

    liquid_perp_style = sorted(
        (p for p in cde
         if (expiry_year(str(p.get("product_id", ""))) or 0) >= PERPETUAL_STYLE_YEAR
         and volume(p) >= args.min_volume),
        key=lambda p: -volume(p),
    )

    print(f"CDE perpetual-style products above ${args.min_volume:,.0f}/day: {len(liquid_perp_style)}\n")

    rows = []
    header = f"{'product_id':<20}{'24h vol':>16}{'funding_rate':>14}{'funding_interval':>18}{'index_price':>14}"
    print(header)
    print("-" * len(header))
    for p in liquid_perp_style:
        product_id = str(p.get("product_id"))
        status, detail, error = http(f"{BASE}/products/{product_id}")
        fpd = (detail or {}).get("future_product_details") or {} if isinstance(detail, dict) else {}
        rate = fpd.get("funding_rate")
        interval = fpd.get("funding_interval")
        index_price = fpd.get("index_price")
        rows.append({
            "product_id": product_id, "http_status": status, "error": error,
            "funding_rate": rate, "funding_interval": interval, "index_price": index_price,
        })
        rate_text = rate if rate not in (None, "") else "MISSING"
        print(f"{product_id:<20}{volume(p):>16,.0f}{str(rate_text):>14}{str(interval or '-'):>18}{str(index_price or '-'):>14}")

    covered = sum(1 for r in rows if r["funding_rate"] not in (None, ""))
    print(f"\n{covered} of {len(rows)} liquid perpetual-style CDE products publish "
          f"future_product_details.funding_rate.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cde_funding_coverage_findings.json"
    out_path.write_text(json.dumps({
        "probe": "cde_funding_coverage_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "liquid_perpetual_style_count": len(rows),
        "funding_rate_covered_count": covered,
        "products": rows,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Findings: {out_path}")

    if covered == len(rows):
        print("\nFull coverage. The Amendment 5 funding-accrual gap is closed for this "
              "cross-section: native, same-venue, per-instrument funding is directly "
              "observable, and funding carry is viable as originally scoped -- no proxy, "
              "no assumed-cost fallback needed.")
    elif covered > 0:
        print(f"\nPartial coverage ({covered}/{len(rows)}). A funding-carry design would "
              "need to either restrict its cross-section to covered instruments or treat "
              "the gap for the rest under one of the previously recorded fallback options.")
    else:
        print("\nNo coverage despite the BTC/ETH confirmation -- unexpected; re-check the "
              "field path before concluding anything.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
