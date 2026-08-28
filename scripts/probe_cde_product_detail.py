"""Check the CDE single-product detail endpoint for a funding field — read-only.

`probe_coinbase_derivatives_universe.py` queried only the bulk `/market/products`
list, which returned `funding_rate: null` for all 99 CDE products (Campaign #53
feasibility finding, section 8b). Bulk list endpoints sometimes omit fields the
single-product detail endpoint carries. This checks the detail endpoint directly,
for named liquid perpetual-style CDE products, and prints every field returned
rather than a pre-selected subset -- so a field this operator hasn't thought to
look for isn't silently dropped.

Public, unauthenticated `/market/` endpoint. Read-only: writes findings to
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
USER_AGENT = "itera-research-feasibility-probe/2.2"
TIMEOUT_SECONDS = 25

# Named from the Campaign #53 feasibility finding: the two most liquid CDE
# perpetual-style products (contract sizes match the Coinbase app's "BTC PERP" /
# "ETH PERP" exactly).
DEFAULT_PRODUCT_IDS = ["BIP-20DEC30-CDE", "ETP-20DEC30-CDE"]


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
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--product-id", action="append", default=None,
                   help="Repeatable. Default: the two liquid CDE perpetual-style products.")
    p.add_argument("--out-dir", default="artifacts/campaign53_source_probe")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    product_ids = args.product_id or DEFAULT_PRODUCT_IDS

    findings: dict[str, Any] = {
        "probe": "cde_product_detail_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "products": {},
    }

    funding_like_keys = {"funding", "financing", "carry", "rate", "index_price", "mark_price"}

    for product_id in product_ids:
        status, payload, error = http(f"{BASE}/products/{product_id}")
        findings["products"][product_id] = {"http_status": status, "error": error, "payload": payload}
        print(f"{product_id}: HTTP {status}" + (f"  ({error})" if error else ""))
        if not isinstance(payload, dict):
            continue

        def walk(obj: Any, prefix: str = "") -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    path = f"{prefix}.{k}" if prefix else k
                    if isinstance(v, (dict, list)):
                        walk(v, path)
                    else:
                        hit = any(fk in k.lower() for fk in funding_like_keys)
                        marker = "  <-- funding-like key" if hit else ""
                        print(f"    {path} = {v!r}{marker}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj[:3]):
                    walk(item, f"{prefix}[{i}]")

        walk(payload)
        print()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "cde_product_detail_findings.json"
    path.write_text(json.dumps(findings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Findings: {path}")
    print(
        "\nIf no field above is marked funding-like, the single-product detail endpoint "
        "does not expose CDE funding either, and the public unauthenticated API is fully "
        "exhausted as a source -- the only remaining route to option 1 is this operator's "
        "own Coinbase Derivatives account statements (financing/carry line items), which "
        "no probe can read."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
