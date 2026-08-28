"""Which liquid CDE perpetual-style names have a liquid matched dated contract?

Campaign #53's frozen specification needs to choose between two carry-trade
constructions:

- **perp-vs-dated, both on CDE** -- satisfies Amendment 5 (research source =
  execution venue) by construction, no custody or cross-venue assumption, but
  only available for underlyings where a same-root dated contract also trades
  liquidly on CDE. The feasibility finding confirmed 5 such pairs (BTC, ETH,
  XRP, SOL, DOGE) from a partial check.
- **perp-vs-spot, spot off-CDE** -- covers the full 19-name liquid perpetual-
  style cross-section, but the spot leg trades on Coinbase's regular exchange,
  a different venue from CDE even though it's the same company. That is a
  custody/basis assumption to defend, not a free pass under Amendment 5.

This checks, for every liquid (>min-volume) CDE perpetual-style product, the
full liquid dated CDE universe for a same-root match, giving the exact count
available for the cleaner construction before the specification commits to
either one.

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
USER_AGENT = "itera-research-feasibility-probe/2.4"
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
    p.add_argument("--min-volume-perp", type=float, default=1_000_000.0)
    p.add_argument("--min-volume-dated", type=float, default=100_000.0,
                   help="Lower bar for the dated leg — it only needs to be tradeable, "
                        "not independently liquid at the perp's scale.")
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
    products = [p for p in payload.get("products", []) if isinstance(p, dict)]
    cde = [p for p in products
           if str((p.get("future_product_details") or {}).get("venue", "")).lower() == "cde"]

    def volume(p: dict) -> float:
        v = to_float(p.get("approximate_quote_24h_volume"))
        return v if v is not None else 0.0

    def root(p: dict) -> str:
        return str((p.get("future_product_details") or {}).get("contract_root_unit", ""))

    liquid_perp = sorted(
        (p for p in cde
         if (expiry_year(str(p.get("product_id", ""))) or 0) >= PERPETUAL_STYLE_YEAR
         and volume(p) >= args.min_volume_perp),
        key=lambda p: -volume(p),
    )
    dated = [p for p in cde
             if (expiry_year(str(p.get("product_id", ""))) or 0) < PERPETUAL_STYLE_YEAR]
    tradeable_dated = [p for p in dated if volume(p) >= args.min_volume_dated]

    dated_by_root: dict[str, list[dict]] = {}
    for p in tradeable_dated:
        dated_by_root.setdefault(root(p), []).append(p)

    print(f"Liquid CDE perpetual-style products (>${args.min_volume_perp:,.0f}/day): {len(liquid_perp)}")
    print(f"Tradeable CDE dated futures (>${args.min_volume_dated:,.0f}/day): {len(tradeable_dated)}\n")

    header = f"{'perp product_id':<20}{'root':>6}{'perp vol':>14}{'matched dated':<20}{'dated vol':>14}"
    print(header)
    print("-" * len(header))
    rows = []
    matched = 0
    for p in liquid_perp:
        r = root(p)
        candidates = sorted(dated_by_root.get(r, []), key=lambda d: -volume(d))
        best = candidates[0] if candidates else None
        if best:
            matched += 1
        rows.append({
            "perp_product_id": p.get("product_id"), "root": r, "perp_volume": volume(p),
            "matched_dated_product_id": best.get("product_id") if best else None,
            "matched_dated_volume": volume(best) if best else None,
        })
        print(
            f"{str(p.get('product_id')):<20}{r:>6}{volume(p):>14,.0f}"
            f"{(str(best.get('product_id')) if best else '-- none --'):<20}"
            f"{(f'{volume(best):,.0f}' if best else ''):>14}"
        )

    print(f"\n{matched} of {len(liquid_perp)} liquid perpetual-style names have a tradeable "
          f"same-root dated contract on CDE.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cde_matched_pairs_findings.json"
    out_path.write_text(json.dumps({
        "probe": "cde_matched_pairs_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "liquid_perp_count": len(liquid_perp),
        "matched_count": matched,
        "rows": rows,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Findings: {out_path}")

    if matched == len(liquid_perp):
        print("\nFull match. The perp-vs-dated, both-on-CDE construction covers the entire "
              "liquid cross-section -- no custody/cross-venue assumption needed anywhere.")
    else:
        print(f"\nPartial match. A perp-vs-dated design covers {matched} names cleanly; the "
              f"remaining {len(liquid_perp) - matched} would need perp-vs-spot (off-CDE leg) "
              "or exclusion from the cross-section.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
