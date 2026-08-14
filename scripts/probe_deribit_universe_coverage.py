"""Does Deribit have deep funding history for the full 10-name CDE universe?

Campaign #53's chosen path forward (2026-08-14): run FDR discovery on Deribit's
longer funding history, confirm only on CDE's ~13-month native data. That only
fully works if Deribit actually lists, and has deep history for, the same 10
names resolved as the CDE primary universe (BTC, ETH, XRP, SOL, HYPE, XLM,
LINK, DOGE, ADA, DOT) -- known depth so far is BTC/ETH only, via
`probe_funding_data_sources.py`'s hardcoded symbol map. This checks the rest.

Guessing Deribit's perpetual naming convention for the smaller names (e.g.
whether it's SOL_USDC-PERPETUAL, SOL-PERPETUAL, or something else) risks a
wrong guess reading identically to "not listed" -- a silent false negative.
Instead this queries Deribit's own public instrument listing per currency
first, to find the real name if one exists, then reuses
probe_funding_data_sources.py's existing, already-validated deribit() walker
and characterise() function against it rather than re-implementing that logic.

Public, unauthenticated endpoints only. Read-only: writes findings to
`artifacts/`, nothing to `data/`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.probe_funding_data_sources import characterise, deribit, probe  # noqa: E402

USER_AGENT = "itera-research-feasibility-probe/2.6"
TIMEOUT_SECONDS = 20

# The 10-name CDE primary universe resolved 2026-08-13. BTC/ETH already
# confirmed deep on Deribit; included here for a complete, one-shot report.
TARGET_ASSETS = ["BTC", "ETH", "XRP", "SOL", "HYPE", "XLM", "LINK", "DOGE", "ADA", "DOT"]


def http(url: str) -> tuple[int, Any, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 — a probe reports, never raises
        return 0, None, f"{type(exc).__name__}: {exc}"


def find_perpetual_instrument(currency: str) -> tuple[str | None, int, str | None]:
    """Query Deribit's own instrument listing for a real perpetual name, if any."""
    url = f"https://www.deribit.com/api/v2/public/get_instruments?currency={currency}&kind=future&expired=false"
    status, payload, error = http(url)
    if not isinstance(payload, dict):
        return None, status, error
    for row in payload.get("result", []) or []:
        name = row.get("instrument_name", "")
        if "PERPETUAL" in name.upper():
            return name, status, error
    return None, status, error


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assets", nargs="*", default=TARGET_ASSETS)
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--depth-pages", type=int, default=60)
    p.add_argument("--pause", type=float, default=0.4)
    p.add_argument("--out-dir", default="artifacts/campaign53_source_probe")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    findings: dict[str, Any] = {"probe": "deribit_universe_coverage_v1", "assets": {}}

    header = f"{'asset':<8}{'instrument':<24}{'listed':>8}{'first_utc':>26}{'rows':>8}{'depth_exhausted':>16}"
    print(header)
    print("-" * len(header))

    for asset in args.assets:
        instrument, status, error = find_perpetual_instrument(asset)
        time.sleep(args.pause)

        if instrument is None:
            findings["assets"][asset] = {"listed": False, "http_status": status, "error": error}
            print(f"{asset:<8}{'-- not listed --':<24}{'NO':>8}")
            continue

        entry = probe("deribit", deribit, instrument, args.limit, args.depth_pages, args.pause, rate_period_hours=8)
        entry["listed"] = True
        findings["assets"][asset] = entry
        depth = entry.get("depth", {})
        first_utc = depth.get("first_utc", "-")
        rows = depth.get("rows", 0)
        exhausted = entry.get("depth_exhausted", "?")
        print(f"{asset:<8}{instrument:<24}{'YES':>8}{str(first_utc):>26}{rows:>8}{str(exhausted):>16}")
        time.sleep(args.pause)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "deribit_universe_coverage_findings.json"
    out_path.write_text(json.dumps(findings, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(f"\nFindings: {out_path}")

    listed = [a for a, e in findings["assets"].items() if e.get("listed")]
    not_listed = [a for a in args.assets if a not in listed]
    print(f"\n{len(listed)} of {len(args.assets)} listed on Deribit: {listed}")
    if not_listed:
        print(f"Not listed / no perpetual found: {not_listed}")
        print(
            "For these, option 3 (Deribit discovery / CDE confirmation) doesn't apply -- "
            "they'd need option 1's broader-universe treatment, a shorter CDE-native-only "
            "design, or exclusion, decided per name rather than assumed for the whole universe."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
