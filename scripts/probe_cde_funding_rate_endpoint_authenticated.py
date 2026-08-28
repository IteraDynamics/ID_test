"""Authenticated version of probe_cde_funding_rate_endpoint.py.

The unauthenticated probe got a consistent, real 401 on every call to the actual, spec-confirmed
`GET /rest/funding-rate` endpoint -- not the "everything under this prefix 401s regardless of
path" ambiguity from the earlier broad guess. This is real signal: the endpoint needs auth
despite its OpenAPI spec's operation-level `security: []` override.

The spec's auth scheme is the classic Coinbase Exchange (Pro/GDAX-era) signing scheme, not the
newer JWT-based Coinbase Developer Platform key format:

  CB-ACCESS-KEY:        the API key
  CB-ACCESS-TIMESTAMP:  Unix epoch seconds, as a string
  CB-ACCESS-PASSPHRASE: the passphrase set when the key was created
  CB-ACCESS-SIGN:       base64(HMAC-SHA256(base64_decode(secret), timestamp + method + request_path + body))

That three-part key/secret/passphrase shape means you need an Exchange-style API key
specifically, not a newer CDP/Advanced-Trade-style key (which uses a single key name + EC
private key for JWT signing, no passphrase, and won't work with this signing scheme).

Credentials are read from environment variables and never printed, logged, or written to any
output file this script produces -- only HTTP status and response bodies (funding rate data,
not secrets) get written to artifacts/.

Set before running:
  CDE_API_KEY
  CDE_API_SECRET       (base64-encoded, as issued)
  CDE_API_PASSPHRASE

Public GET requests, now signed. Read-only: writes findings to `artifacts/`, nothing to `data/`.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_HOST = "https://api.exchange.fairx.net"
REQUEST_PATH_BASE = "/rest/funding-rate"
USER_AGENT = "itera-research-feasibility-probe/2.8"
TIMEOUT_SECONDS = 25

SYMBOLS = {"BTC": "BIPZ30", "ETH": "ETPZ30"}


def load_credentials() -> tuple[str, str, str | None]:
    key = os.environ.get("CDE_API_KEY")
    secret = os.environ.get("CDE_API_SECRET")
    passphrase = os.environ.get("CDE_API_PASSPHRASE") or None
    missing = [name for name, val in (("CDE_API_KEY", key), ("CDE_API_SECRET", secret)) if not val]
    if missing:
        print(f"Missing required environment variable(s): {', '.join(missing)}", file=sys.stderr)
        print("Set CDE_API_KEY and CDE_API_SECRET before running. CDE_API_PASSPHRASE is optional --", file=sys.stderr)
        print("omit it if your key was issued as key+secret only, with no passphrase.", file=sys.stderr)
        sys.exit(2)
    if passphrase is None:
        print("CDE_API_PASSPHRASE not set -- proceeding without it (key+secret-only credential).\n", file=sys.stderr)
    return key, secret, passphrase  # type: ignore[return-value]


def sign_request(secret_raw: str, timestamp: str, method: str, request_path: str, body: str) -> tuple[str, str]:
    """Returns (signature, mode) -- mode records whether the secret was interpreted as base64
    or raw bytes, since that's unconfirmed for this key type and worth reporting."""
    try:
        secret_bytes = base64.b64decode(secret_raw, validate=True)
        mode = "base64-decoded"
    except Exception:  # noqa: BLE001 -- not valid base64, fall back rather than crash
        secret_bytes = secret_raw.encode("utf-8")
        mode = "raw-utf8 (secret was not valid base64)"
    message = f"{timestamp}{method}{request_path}{body}".encode("utf-8")
    signature = hmac.new(secret_bytes, message, hashlib.sha256).digest()
    return base64.b64encode(signature).decode("utf-8"), mode


def signed_get(request_path_with_query: str, key: str, secret: str, passphrase: str | None) -> tuple[int, Any, str | None]:
    timestamp = str(int(time.time()))
    signature, secret_mode = sign_request(secret, timestamp, "GET", request_path_with_query, "")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "CB-ACCESS-KEY": key,
        "CB-ACCESS-SIGN": signature,
        "CB-ACCESS-TIMESTAMP": timestamp,
    }
    if passphrase is not None:
        headers["CB-ACCESS-PASSPHRASE"] = passphrase
    url = f"{BASE_HOST}{request_path_with_query}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
            try:
                return response.status, json.loads(body), None
            except json.JSONDecodeError:
                return response.status, body, "response was not valid JSON"
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            body = ""
        return exc.code, body, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 -- a probe reports, never raises
        return 0, None, f"{type(exc).__name__}: {exc}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--probe-dates", nargs="*", default=None)
    p.add_argument("--out-dir", default="artifacts/campaign53_source_probe")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    key, secret, passphrase = load_credentials()

    today = datetime.now(timezone.utc).date()
    probe_dates = args.probe_dates or [
        today.isoformat(),
        (today - timedelta(days=30)).isoformat(),
        "2025-07-20",
        "2025-07-15",
    ]

    _, secret_mode = sign_request(secret, "0", "GET", "/", "")
    print(f"Secret interpreted as: {secret_mode}")
    print(f"Passphrase header: {'included' if passphrase is not None else 'omitted (none provided)'}\n")

    findings: dict[str, Any] = {"probe": "cde_funding_rate_endpoint_authenticated_v1", "secret_mode": secret_mode, "passphrase_included": passphrase is not None, "calls": {}}

    print("=== Authenticated calls ===\n")
    for asset, symbol in SYMBOLS.items():
        for date_str in probe_dates:
            query = urllib.parse.urlencode({"symbol": symbol, "trading_session_date": date_str})
            request_path = f"{REQUEST_PATH_BASE}?{query}"
            status, payload, error = signed_get(request_path, key, secret, passphrase)
            findings_key = f"{asset}:{symbol}:{date_str}"
            findings["calls"][findings_key] = {"request_path": request_path, "http_status": status, "error": error, "payload": payload}
            n = len(payload) if isinstance(payload, list) else None
            print(f"{findings_key}: HTTP {status}" + (f", {n} records" if n is not None else "") + (f"  ({error})" if error else ""))
            if isinstance(payload, list) and payload:
                print(f"  sample record: {json.dumps(payload[0])}")
            elif status not in (0, 200) and payload:
                # Error response bodies often explain *why* -- invalid signature vs. invalid key
                # vs. missing header -- which the status code alone doesn't. Print it, it's not
                # sensitive (it's the server's own error text, not our credentials).
                print(f"  response body: {payload}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "cde_funding_rate_endpoint_authenticated_probe_findings.json"
    out_path.write_text(json.dumps(findings, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    all_statuses = [v["http_status"] for v in findings["calls"].values()]
    any_200_with_data = any(
        v["http_status"] == 200 and isinstance(v["payload"], list) and len(v["payload"]) > 0
        for v in findings["calls"].values()
    )
    still_401 = any(status in (401, 403) for status in all_statuses)
    all_unreachable = all(status == 0 for status in all_statuses)

    print(f"\nFindings: {out_path}")
    print("\n=== Verdict ===")
    if all_unreachable:
        print("Every call failed at the network level (HTTP 0) -- this didn't reach the endpoint "
              "at all, so it says nothing about credentials or symbol format. Check your network "
              "connection and that api.exchange.fairx.net is reachable, then try again.")
    elif any_200_with_data:
        print("Authenticated calls returned real records. The endpoint, symbol format, and auth "
              "scheme are all confirmed. Next step: build the real day-by-day acquisition script.")
    elif still_401:
        print("Still 401 even authenticated -- likely the key type is wrong (needs a classic "
              "Exchange-style key/secret/passphrase, not a newer CDP/Advanced-Trade key), or the "
              "key lacks permission for this specific derivatives endpoint. Worth checking exactly "
              "what kind of key was generated before trying again.")
    else:
        print("Reached the endpoint without a 401, but got no records / an unexpected response -- "
              "inspect the raw JSON in the findings file. Could mean the symbol format guess is "
              "wrong even though auth now works, or trading_session_date needs different handling.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
