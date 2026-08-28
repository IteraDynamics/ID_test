"""Campaign #53 structural family (basis): first real look at the perp-vs-dated spread.

§3c defines the basis candidate as (perp price - matched leg price) / matched leg price, and
§3d/§4 note two parameters this specification deliberately left unset because they need real
data this environment doesn't have: the mark-to-market risk tolerance threshold (§3b) and the
roll-timing N (§3a-ii). Neither can be set from reasoning alone -- they need to see how the
actual spread behaves.

This is the first step toward that, not the final answer. It does NOT assume field names for
"the perp leg's price" and "the dated leg's price" -- those haven't been confirmed for this
specific pair of product types in this repo yet (probe_cde_product_detail.py's own
`funding_like_keys` search list shows the schema wasn't fully known when that was written
either). Instead: it discovers the current BTC/ETH perp-style/dated matched pair (same logic as
probe_cde_matched_pairs.py, restricted to the two roots this specification is frozen to), dumps
each leg's FULL product detail payload so the real schema is visible, and prints a best-effort
basis calculation clearly labeled as unverified pending that inspection -- not asserted as
correct.

Public, unauthenticated /market/ endpoint. Read-only: writes findings to `artifacts/`, nothing
to `data/`. This is a probe, not the live basis logger -- building that comes after this
confirms the real field names.
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
USER_AGENT = "itera-research-feasibility-probe/2.5"
TIMEOUT_SECONDS = 25
PERPETUAL_STYLE_YEAR = 2029
ROOTS = ("BTC", "ETH")  # the only roots this specification (§3c) is frozen to. Confirmed
                        # 2026-08-25 against real CDE data that contract_root_unit holds the
                        # plain ticker, not the product-ID prefix (BIP/ETP) -- the original guess.


def http(url: str) -> tuple[int, Any, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 -- a probe reports, never raises
        return 0, None, f"{type(exc).__name__}: {exc}"


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def expiry_year(product_id: str) -> int | None:
    parts = product_id.split("-")
    if len(parts) < 2 or len(parts[1]) < 2 or not parts[1][-2:].isdigit():
        return None
    return 2000 + int(parts[1][-2:])


def volume(p: dict) -> float:
    v = to_float(p.get("approximate_quote_24h_volume"))
    return v if v is not None else 0.0


def root(p: dict) -> str:
    return str((p.get("future_product_details") or {}).get("contract_root_unit", ""))


def dated_ladder(cde_products: list[dict], target_root: str) -> list[dict]:
    """Every dated (non-perpetual-style) contract for one root, sorted nearest-expiry first --
    not just the highest-volume one. "Highest volume" is the right criterion for confirming a
    matched pair exists at all, but the wrong one for picking a fresh-entry trading candidate:
    near-expiry contracts are often the most liquid precisely because everyone is closing or
    rolling out of them, not because they're a good new position to open."""
    same_root = [p for p in cde_products
                 if root(p) == target_root and (expiry_year(str(p.get("product_id", ""))) or 0) < PERPETUAL_STYLE_YEAR]
    return sorted(same_root, key=lambda p: (p.get("future_product_details") or {}).get("contract_expiry", ""))


def find_current_pair(cde_products: list[dict], target_root: str) -> tuple[dict | None, dict | None]:
    """Highest-volume perp-style and highest-volume dated product for one root, right now."""
    same_root = [p for p in cde_products if root(p) == target_root]
    perp_candidates = sorted(
        (p for p in same_root if (expiry_year(str(p.get("product_id", ""))) or 0) >= PERPETUAL_STYLE_YEAR),
        key=lambda p: -volume(p),
    )
    dated_candidates = sorted(
        (p for p in same_root if (expiry_year(str(p.get("product_id", ""))) or 0) < PERPETUAL_STYLE_YEAR),
        key=lambda p: -volume(p),
    )
    perp = perp_candidates[0] if perp_candidates else None
    dated = dated_candidates[0] if dated_candidates else None
    return perp, dated


def best_effort_price(detail: dict) -> tuple[float | None, str | None]:
    """Tries plausible field names in a reasoned priority order; returns (value, field_used)
    so the caller can see exactly which field the number came from, not just trust it blindly."""
    fpd = detail.get("future_product_details") or {}
    for field, source in (
        ("mark_price", fpd),
        ("price", detail),
        ("index_price", fpd),
    ):
        val = to_float(source.get(field))
        if val is not None:
            return val, field
    return None, None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--out-dir", default="artifacts/campaign53_source_probe")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    status, payload, error = http(f"{BASE}/products?product_type=FUTURE&contract_expiry_type=EXPIRING")
    if not isinstance(payload, dict):
        print(f"Universe fetch failed: HTTP {status} ({error})")
        return 1
    products = [p for p in payload.get("products", []) if isinstance(p, dict)]
    cde = [p for p in products
           if str((p.get("future_product_details") or {}).get("venue", "")).lower() == "cde"]

    distinct_roots = sorted({root(p) for p in cde})
    print(f"Universe fetch: HTTP {status}, {len(products)} total products, {len(cde)} CDE products.")
    print(f"Distinct contract_root_unit values seen among CDE products: {distinct_roots}")
    if not distinct_roots:
        print("No CDE products found at all -- the venue filter, product_type, or "
              "contract_expiry_type query params may no longer match the live API. "
              "Dumping the first 3 raw products for inspection:")
        for p in products[:3]:
            print(json.dumps(p, indent=2, sort_keys=True))
    elif not any(r in distinct_roots for r in ROOTS):
        print(f"None of the assumed roots {ROOTS} appear in the real data -- ROOTS was a guess, "
              f"not confirmed. Use the real values printed above instead.")

    results: dict[str, Any] = {}
    for r in ROOTS:
        ladder = dated_ladder(cde, r)
        print(f"\n=== {r} dated-contract ladder (nearest expiry first) ===")
        if not ladder:
            print("  (none)")
        for p in ladder:
            fpd = p.get("future_product_details") or {}
            days_to_expiry = None
            tte_ms = to_float(fpd.get("time_to_expiry_ms"))
            if tte_ms is not None:
                days_to_expiry = tte_ms / 1000 / 86400
            print(f"  {str(p.get('product_id')):<18} expiry={fpd.get('contract_expiry','')!s:<24}"
                  f"days_to_expiry={days_to_expiry if days_to_expiry is not None else '?':<8}"
                  f"vol_24h=${volume(p):,.0f}")

        perp, dated = find_current_pair(cde, r)
        print(f"\n=== {r} ===")
        if not perp or not dated:
            print(f"  No current matched pair found (perp={'yes' if perp else 'NONE'}, "
                  f"dated={'yes' if dated else 'NONE'}) -- cannot compute basis right now.")
            results[r] = {"perp_product_id": None, "dated_product_id": None, "basis": None}
            continue

        perp_id = str(perp.get("product_id"))
        dated_id = str(dated.get("product_id"))
        print(f"  perp-style leg:  {perp_id}")
        print(f"  dated leg:       {dated_id}")

        perp_status, perp_detail, perp_err = http(f"{BASE}/products/{perp_id}")
        dated_status, dated_detail, dated_err = http(f"{BASE}/products/{dated_id}")

        print(f"\n  --- {perp_id} full product detail (HTTP {perp_status}) ---")
        print(json.dumps(perp_detail, indent=2, sort_keys=True) if isinstance(perp_detail, dict)
              else f"  fetch failed: {perp_err}")
        print(f"\n  --- {dated_id} full product detail (HTTP {dated_status}) ---")
        print(json.dumps(dated_detail, indent=2, sort_keys=True) if isinstance(dated_detail, dict)
              else f"  fetch failed: {dated_err}")

        perp_price, perp_field = (None, None)
        dated_price, dated_field = (None, None)
        if isinstance(perp_detail, dict):
            perp_price, perp_field = best_effort_price(perp_detail)
        if isinstance(dated_detail, dict):
            dated_price, dated_field = best_effort_price(dated_detail)

        basis = None
        if perp_price is not None and dated_price is not None and dated_price != 0:
            basis = (perp_price - dated_price) / dated_price

        print(f"\n  BEST-EFFORT (unverified -- confirm against the dumps above):")
        print(f"    perp price:  {perp_price} (field: {perp_field})")
        print(f"    dated price: {dated_price} (field: {dated_field})")
        print(f"    basis = (perp - dated) / dated = {basis}")

        results[r] = {
            "perp_product_id": perp_id,
            "dated_product_id": dated_id,
            "perp_price": perp_price,
            "perp_price_field": perp_field,
            "dated_price": dated_price,
            "dated_price_field": dated_field,
            "basis_best_effort": basis,
        }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"cde_basis_snapshot_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps({
        "probe": "cde_basis_snapshot_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "caveat": "basis_best_effort uses a reasoned field-name priority order, not a confirmed "
                  "schema -- verify against the printed full payload dumps before trusting it.",
        "results": results,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nFindings: {out_path}")
    print("\nNext step: inspect the full payload dumps above for the real price field names, "
          "confirm best_effort_price picked the right one, then build the live basis logger.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
