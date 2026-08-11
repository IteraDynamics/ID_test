"""Characterise the tradable CDE universe from saved universe findings.

Coinbase Derivatives Exchange lists US-regulated perpetual-style futures as
very-long-dated contracts (e.g. `BIP-20DEC30-CDE`, a December 2030 expiry with
a funding mechanism) alongside genuinely dated futures (`BIT-28AUG26-CDE`).
The Advanced Trade API classifies both as EXPIRING, so a PERPETUAL filter
returns only Coinbase International Exchange products, which are a different
venue.

This separates the CDE universe into perpetual-style and dated cohorts,
reports liquidity, and establishes whether CDE publishes funding for the
perpetual-style contracts -- the open Amendment 5 question.

Read-only: reads the saved findings file, makes no network calls.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

# Contracts expiring this far out are perpetual-style in substance.
PERPETUAL_STYLE_YEAR = 2029


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--findings",
        default="artifacts/campaign53_source_probe/coinbase_universe_findings.json",
    )
    p.add_argument("--min-volume", type=float, default=1_000_000.0)
    return p.parse_args(argv)


def expiry_year(row: dict[str, Any]) -> int | None:
    """CDE ids encode expiry as e.g. 20DEC30 -> 2030."""
    parts = str(row.get("product_id", "")).split("-")
    if len(parts) < 2:
        return None
    token = parts[1]
    if len(token) < 2 or not token[-2:].isdigit():
        return None
    return 2000 + int(token[-2:])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data = json.loads(Path(args.findings).read_text(encoding="utf-8"))
    cde = [r for r in (data.get("expiring") or [])
           if str(r.get("venue", "")).lower() == "cde"]

    perp_style, dated = [], []
    for row in cde:
        year = expiry_year(row)
        (perp_style if (year and year >= PERPETUAL_STYLE_YEAR) else dated).append(row)

    def report(label: str, rows: list[dict[str, Any]]) -> None:
        liquid = sorted(
            (r for r in rows if (r.get("quote_volume_24h") or 0) >= args.min_volume),
            key=lambda r: -(r.get("quote_volume_24h") or 0),
        )
        funded = [r for r in rows if r.get("funding_rate") is not None]
        print(f"\n=== {label}: {len(rows)} products "
              f"({len(liquid)} above ${args.min_volume:,.0f}, "
              f"{len(funded)} publishing funding) ===")
        if not liquid:
            return
        header = f"{'product_id':<24}{'contract':>10}{'price':>13}{'24h quote vol':>16}{'funding':>12}"
        print(header)
        print("-" * len(header))
        for r in liquid:
            price, vol, fund = r.get("price"), r.get("quote_volume_24h"), r.get("funding_rate")
            print(
                f"{str(r.get('product_id'))[:24]:<24}"
                f"{str(r.get('contract_size'))[:10]:>10}"
                f"{(f'{price:,.4f}' if price else '-'):>13}"
                f"{(f'{vol:,.0f}' if vol else '-'):>16}"
                f"{(f'{fund:.8f}' if fund is not None else 'none'):>12}"
            )

    report("CDE perpetual-style (expiry >= 2029)", perp_style)
    report("CDE dated futures", dated)

    print("\n--- expiry distribution across all CDE products ---")
    for year, count in sorted(Counter(expiry_year(r) for r in cde).items(),
                              key=lambda kv: (kv[0] is None, kv[0])):
        print(f"  {year}: {count}")

    funded_total = sum(1 for r in cde if r.get("funding_rate") is not None)
    print(f"\nCDE products publishing a funding_rate field: {funded_total} of {len(cde)}")
    if funded_total == 0:
        print("  -> Funding is NOT exposed for CDE via this endpoint. The Amendment 5 gap")
        print("     stands: a separate CDE funding source must be established, or Deribit")
        print("     justified as a proxy, before any specification freezes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
