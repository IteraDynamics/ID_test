"""Does Deribit expose historical open interest, needed for Campaign #53's third statistical
candidate (open interest change)?

The funding-rate acquisition (`scripts/fetch_deribit_funding_history.py`) succeeded and confirmed
Deribit's `get_funding_rate_history` endpoint. Open interest is a separate data stream and has
never been probed for this campaign -- §3c's "open interest change" candidate has no confirmed
source yet. This checks Deribit's public API for a genuine historical OI series (not just the
current snapshot every exchange trivially exposes) before assuming one exists.

Public, unauthenticated Deribit endpoints only. Read-only: writes findings to `artifacts/`,
nothing to `data/`.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

USER_AGENT = "itera-research-feasibility-probe/2.9"
TIMEOUT_SECONDS = 25

SYMBOLS = {"BTC": "BTC-PERPETUAL", "ETH": "ETH-PERPETUAL"}


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
    except Exception as exc:  # noqa: BLE001
        return 0, None, f"{type(exc).__name__}: {exc}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-dir", default="artifacts/campaign53_source_probe")
    args = p.parse_args(argv)

    findings: dict[str, Any] = {"probe": "deribit_open_interest_history_v1", "calls": {}}
    now = int(time.time() * 1000)
    start_30d = now - 30 * 24 * 3_600_000

    print("=== Current snapshot (every exchange has this; not evidence of historical access) ===\n")
    for asset, symbol in SYMBOLS.items():
        url = f"https://www.deribit.com/api/v2/public/get_book_summary_by_instrument?instrument_name={symbol}"
        status, payload, error = http(url)
        result = (payload or {}).get("result") if isinstance(payload, dict) else None
        current_oi = result[0].get("open_interest") if isinstance(result, list) and result else None
        findings["calls"][f"{asset}:current_snapshot"] = {"url": url, "http_status": status, "current_open_interest": current_oi, "error": error}
        print(f"{asset}: HTTP {status}, current open_interest={current_oi}" + (f"  ({error})" if error else ""))

    print("\n=== Historical OI candidates (exploratory, patterns not confirmed against docs) ===\n")
    candidate_calls = [
        ("get_historical_volatility", lambda sym: f"https://www.deribit.com/api/v2/public/get_historical_volatility?currency={sym.split('-')[0]}"),
        ("get_open_interest_history", lambda sym: f"https://www.deribit.com/api/v2/public/get_open_interest_history?instrument_name={sym}&start_timestamp={start_30d}&end_timestamp={now}"),
        ("get_open_interest", lambda sym: f"https://www.deribit.com/api/v2/public/get_open_interest?instrument_name={sym}&start_timestamp={start_30d}&end_timestamp={now}"),
        ("get_trade_volumes", lambda sym: f"https://www.deribit.com/api/v2/public/get_trade_volumes?currency={sym.split('-')[0]}"),
    ]
    for asset, symbol in SYMBOLS.items():
        for name, url_fn in candidate_calls:
            url = url_fn(symbol)
            status, payload, error = http(url)
            key = f"{asset}:{name}"
            has_data = isinstance(payload, dict) and payload.get("result") not in (None, [], {})
            findings["calls"][key] = {"url": url, "http_status": status, "error": error, "has_result": has_data}
            print(f"{key}: HTTP {status}" + (f", has_result={has_data}" if status == 200 else "") + (f"  ({error})" if error else ""))
            if status == 200 and has_data:
                print(f"  payload sample: {json.dumps(payload)[:500]}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "deribit_open_interest_history_findings.json"
    out_path.write_text(json.dumps(findings, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    print(f"\nFindings: {out_path}")
    print("\n=== Verdict ===")
    any_historical_hit = any(
        v.get("has_result") and "current_snapshot" not in k
        for k, v in findings["calls"].items()
    )
    if any_historical_hit:
        print("At least one candidate historical-OI call returned real data -- inspect the payload "
              "and build acquisition around whichever one it was.")
    else:
        print("No historical OI endpoint found among these guesses. Only the current snapshot is "
              "confirmed. If true, open interest change can't be a candidate against multi-year "
              "history the way funding level and funding persistence can -- it could still be "
              "logged live-forward (same pattern as the CDE funding logger), but that's a much "
              "slower path to a usable series than what we have for funding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
