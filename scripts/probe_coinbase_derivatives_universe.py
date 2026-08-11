"""Enumerate the Coinbase derivatives universe and check funding availability.

Campaign #53 feasibility, two open questions:

1. **Universe breadth.** A cross-sectional funding study needs to know exactly
   how many perpetual instruments are tradable, their contract specifications,
   and their liquidity -- not a partial list read off a phone screen. The
   cross-section's width directly determines the campaign's statistical power.

2. **The CDE-vs-INTX gap.** The earlier probe measured Coinbase *International*
   Exchange funding. The operator would trade Coinbase *Derivatives* Exchange.
   Amendment 5 requires the research source and execution venue be reconciled.
   This probe reports whether Coinbase publishes current and historical funding
   for the instruments actually tradable.

Public market-data endpoints only -- the `/market/` prefix on Advanced Trade
requires no authentication. No key, no account access, no trading scope.
Read-only: writes findings to `artifacts/`, nothing to `data/`.
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
USER_AGENT = "itera-research-feasibility-probe/2.1"
TIMEOUT_SECONDS = 25


def http(url: str) -> tuple[int, Any, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 — a probe reports, never raises
        return 0, None, f"{type(exc).__name__}: {exc}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Enumerate Coinbase derivatives products and funding availability.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--out-dir", default="artifacts/campaign53_source_probe")
    p.add_argument("--min-volume", type=float, default=1_000_000.0,
                   help="Liquidity floor used only for the summary count, not a spec decision.")
    return p.parse_args(argv)


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarise(product: dict[str, Any]) -> dict[str, Any]:
    """Pull the fields a cross-sectional design actually needs."""
    fcm = product.get("fcm_trading_session_details") or {}
    future = product.get("future_product_details") or {}
    perp = future.get("perpetual_details") or {}

    volume = to_float(product.get("approximate_quote_24h_volume"))
    if volume is None:
        vol_24h = to_float(product.get("volume_24h"))
        price = to_float(product.get("price"))
        volume = vol_24h * price if (vol_24h is not None and price is not None) else None

    return {
        "product_id": product.get("product_id"),
        "display_name": product.get("display_name"),
        "status": product.get("status"),
        "trading_disabled": product.get("trading_disabled"),
        "price": to_float(product.get("price")),
        "quote_volume_24h": volume,
        "contract_size": future.get("contract_size") or product.get("base_increment"),
        "contract_expiry_type": future.get("contract_expiry_type"),
        "expiry": future.get("contract_expiry"),
        "venue": future.get("venue"),
        "funding_rate": to_float(perp.get("funding_rate")),
        "funding_time": perp.get("funding_time"),
        "open_interest": to_float(perp.get("open_interest")),
        "max_leverage": perp.get("max_leverage"),
        "session_open": fcm.get("is_session_open"),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    findings: dict[str, Any] = {
        "probe": "coinbase_derivatives_universe_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "data_acquired": False,
        "queries": {},
    }

    queries = {
        "perpetual": f"{BASE}/products?product_type=FUTURE&contract_expiry_type=PERPETUAL",
        "expiring": f"{BASE}/products?product_type=FUTURE&contract_expiry_type=EXPIRING",
        "future_all": f"{BASE}/products?product_type=FUTURE",
    }

    universes: dict[str, list[dict[str, Any]]] = {}
    for label, url in queries.items():
        status, payload, error = http(url)
        entry: dict[str, Any] = {"http_status": status, "error": error, "url": url}
        rows: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            products = payload.get("products", [])
            if isinstance(products, list):
                rows = [summarise(p) for p in products if isinstance(p, dict)]
        entry["count"] = len(rows)
        universes[label] = rows
        findings["queries"][label] = entry
        print(f"{label:<12} HTTP {status}  products: {len(rows)}" + (f"  ({error})" if error else ""))

    perps = universes.get("perpetual") or []
    if not perps:
        # Some deployments do not honour the expiry-type filter; derive it instead.
        perps = [p for p in (universes.get("future_all") or [])
                 if str(p.get("contract_expiry_type", "")).upper() == "PERPETUAL"
                 or "PERP" in str(p.get("product_id", "")).upper()]
        if perps:
            print(f"\n(perpetuals derived from the unfiltered future list: {len(perps)})")

    findings["perpetuals"] = perps
    findings["expiring"] = universes.get("expiring") or []

    with_funding = [p for p in perps if p.get("funding_rate") is not None]
    tradable = [p for p in perps if not p.get("trading_disabled")]
    liquid = [p for p in tradable
              if (p.get("quote_volume_24h") or 0) >= args.min_volume]

    findings["summary"] = {
        "perpetual_products": len(perps),
        "tradable": len(tradable),
        f"tradable_above_{int(args.min_volume):,}_quote_volume": len(liquid),
        "publishing_current_funding": len(with_funding),
        "expiring_futures": len(findings["expiring"]),
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "coinbase_universe_findings.json"
    path.write_text(json.dumps(findings, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if perps:
        print("\n" + "=" * 94)
        header = (
            f"{'product_id':<22}{'contract':>12}{'price':>12}"
            f"{'24h quote vol':>16}{'funding':>11}{'OI':>12}"
        )
        print(header)
        print("-" * len(header))
        for p in sorted(perps, key=lambda r: -(r.get("quote_volume_24h") or 0)):
            price = p.get("price")
            vol = p.get("quote_volume_24h")
            fund = p.get("funding_rate")
            oi = p.get("open_interest")
            price_text = f"{price:,.4f}" if price else "-"
            vol_text = f"{vol:,.0f}" if vol else "-"
            fund_text = f"{fund:.6f}" if fund is not None else "-"
            oi_text = f"{oi:,.0f}" if oi else "-"
            print(
                f"{str(p.get('product_id'))[:22]:<22}"
                f"{str(p.get('contract_size'))[:12]:>12}"
                f"{price_text:>12}{vol_text:>16}{fund_text:>11}{oi_text:>12}"
            )
        print("=" * 94)

    print("\nSummary:")
    for key, value in findings["summary"].items():
        print(f"  {key}: {value}")
    print(f"\nFindings: {path}")
    print("\nNote: current funding is a snapshot. Historical funding series availability")
    print("is a separate question and is not established by this probe.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
