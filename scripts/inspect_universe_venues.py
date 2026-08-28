"""Break the saved universe findings down by venue — CDE vs INTX."""
import json, sys, collections
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1
            else "artifacts/campaign53_source_probe/coinbase_universe_findings.json")
data = json.loads(path.read_text(encoding="utf-8"))

for bucket in ("perpetuals", "expiring"):
    rows = data.get(bucket) or []
    print(f"\n=== {bucket}: {len(rows)} products ===")
    venues = collections.Counter(str(r.get("venue")) for r in rows)
    suffix = collections.Counter(str(r.get("product_id","")).split("-")[-1] for r in rows)
    print("  venue field   :", dict(venues))
    print("  id suffix     :", dict(suffix))
    liquid = [r for r in rows if (r.get("quote_volume_24h") or 0) >= 1_000_000]
    print(f"  >= $1M vol    : {len(liquid)}")
    for r in rows[:3]:
        print(f"    sample: {r.get('product_id')} venue={r.get('venue')} "
              f"contract={r.get('contract_size')} expiry_type={r.get('contract_expiry_type')}")
