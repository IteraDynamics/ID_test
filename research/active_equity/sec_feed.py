"""Prospective SEC enrollment and unranked filing inbox; no stock selection or fills."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import zipfile

from research.active_equity import pilot as p

UNIVERSE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
FEED_NAME = "SEC daily master index / frozen exchange issuer universe v1"
FORMS = {"8-K", "8-K/A", "10-Q", "10-Q/A", "10-K", "10-K/A"}
POLICY = {
    "version": 1,
    "feed_name": FEED_NAME,
    "forms": sorted(FORMS),
    "universe": "All CIKs with a nonempty exchange in the captured SEC exchange mapping. No outcome or earnings screen at enrollment.",
    "coverage": "Consecutive qualifying disclosures within this frozen issuer universe and SEC daily-index feed only. Excludes later listings absent from snapshot. Not all US equities or all issuer news.",
    "event_rule": "Review every candidate filing for earnings, filed financial statements or guidance. Keep amendments and repeat filings in the review log. Resolve original public availability, duplicates and all eligibility before the first 20 distinct eligible CIKs are locked by the existing pilot rules.",
    "timing": "Daily index date is NOT publication time. Filing acceptance and earlier issuer releases require source review. Only original public events inside the registered UTC window may qualify; never substitute download time for event time.",
    "missing": "Unavailable daily indexes remain unresolved, including holidays; HTTP 404 is not an attestation of zero events. No automatic completeness or cohort registration.",
    "screen": "Keep pilot v1 market-cap, liquidity, instrument and accounting comparator rules unchanged. All unresolved values remain unknown, not zero or automatic rejection.",
}


def read_records(root: Path) -> list[dict]:
    with closing(p.connect(root)) as con:
        con.execute("BEGIN")
        records = p.rows(con)
        p.audit_records(root, records)
        return records


def get(url: str, user_agent: str) -> bytes:
    if not re.search(r"\S+@\S+\.\S+", user_agent) or "\n" in user_agent or "\r" in user_agent:
        raise ValueError("SEC User-Agent requires organization/name and a real contact email")
    if not url.startswith("https://www.sec.gov/"):
        raise ValueError("Only public SEC URLs are supported")
    time.sleep(0.25)  # Serial requests, at most four per second.
    request = Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
    with urlopen(request, timeout=60) as response:
        body = response.read(25_000_001)
    if not body or len(body) > 25_000_000:
        raise ValueError("SEC response empty or over 25MB")
    return body


def universe(body: bytes) -> dict[str, list[dict]]:
    raw = json.loads(body)
    fields = raw["fields"]
    if len(fields) != len(set(fields)) or not {"cik", "name", "ticker", "exchange"} <= set(fields):
        raise ValueError("Unexpected SEC universe schema")
    result: dict[str, list[dict]] = {}
    for values in raw["data"]:
        if len(values) != len(fields):
            raise ValueError("Malformed SEC universe row")
        row = dict(zip(fields, values))
        if not row["exchange"]:
            continue
        cik = str(row["cik"])
        if not cik.isdigit() or not 0 < int(cik) < 10**10 or not row["ticker"]:
            raise ValueError("Malformed SEC issuer identity")
        result.setdefault(cik.zfill(10), []).append(row)
    if not result:
        raise ValueError("Empty listed-issuer universe")
    return result


def save_source(root: Path, folder: Path, body: bytes, url: str, description: str) -> str:
    captured = p.utc_now()
    source_id = "sec_" + p.digest((captured + url + description).encode())[:24]
    attachment = folder / (source_id + ".bin")
    attachment.write_bytes(body)
    p.append(root, {"kind": "source", "source_id": source_id, "url": url,
                   "published_at": captured, "available_at": captured,
                   "timestamp_basis": "local snapshot publication; original upstream publication time unknown",
                   "description": description + " Snapshot timestamps describe capture, not original filing/news publication."}, attachment)
    return source_id


def enroll(root: Path, folder: Path, user_agent: str) -> dict:
    records = read_records(root)
    if p.entries(records, "enrollment"):
        raise ValueError("Pilot is already enrolled. Use Collect; enrollment is never replaced.")
    body = get(UNIVERSE_URL, user_agent)
    issuers = universe(body)
    uid = save_source(root, folder, body, UNIVERSE_URL, "SEC exchange mapping frozen for prospective universe")
    protocol = dict(POLICY, collector_sha256=p.digest(Path(__file__).read_bytes().replace(b"\r\n", b"\n")))
    pid = save_source(root, folder, p.canonical(protocol).encode(),
                      "https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data",
                      "Locally authored feed protocol; SEC URL describes upstream service, not authorship of this protocol")
    # 24-48 hours ahead so setup never silently enrolls already-observed events.
    start = (p.timestamp(p.utc_now()) + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    payload = {"kind": "enrollment", "feed_name": FEED_NAME,
               "coverage_statement": POLICY["coverage"], "universe_definition": POLICY["universe"],
               "source_ids": [uid, pid], "window_start": start.isoformat(),
               "universe_source_id": uid, "protocol_source_id": pid}
    p.append(root, payload)
    return {"status": "ENROLLED_AWAITING_FUTURE_EVENTS", "window_start": start.isoformat(),
            "suggested_first_collect_at": (start + timedelta(days=2)).isoformat(),
            "network_download_attempts": 1,
            "issuer_count": len(issuers), "cohort_registered": False, "performance": None}


def parse_index(body: bytes, issuers: dict[str, list[dict]]) -> list[dict]:
    lines = body.decode("utf-8-sig").splitlines()
    header = "CIK|Company Name|Form Type|Date Filed|Filename"
    if header not in lines:
        raise ValueError("SEC master index header missing; possible HTML/error response")
    result = []
    seen = set()
    for line in lines[lines.index(header) + 1:]:
        if not line.strip() or set(line.strip()) == {"-"}:
            continue
        fields = line.split("|")
        if len(fields) != 5:
            raise ValueError("Malformed master index row; coverage cannot be assumed")
        cik, name, form, day, filename = fields
        if not cik.isdigit() or not 0 < int(cik) < 10**10:
            raise ValueError("Invalid index CIK")
        date.fromisoformat(day)
        if not re.fullmatch(r"edgar/data/[0-9]+/[0-9-]+\.txt", filename):
            raise ValueError("Unexpected filing path")
        if int(filename.split("/")[2]) != int(cik):
            raise ValueError("Filing path and CIK disagree")
        if filename in seen:
            raise ValueError("Duplicate filing path in index")
        seen.add(filename)
        cik = cik.zfill(10)
        if cik in issuers and form in FORMS:
            result.append({"cik": cik, "company": name, "form": form, "filed_date": day,
                           "filing_url": "https://www.sec.gov/Archives/" + filename,
                           "listings_at_enrollment": issuers[cik], "review_status": "UNREVIEWED",
                           "published_at": None, "eligible": None, "simple_screen_pass": None})
    return result


def collect(root: Path, folder: Path, user_agent: str) -> dict:
    records = read_records(root)
    enrollments = p.entries(records, "enrollment")
    if len(enrollments) != 1 or enrollments[0]["feed_name"] != FEED_NAME:
        raise ValueError("Enroll this pilot with the SEC feed first")
    enrollment = enrollments[0]
    sources = {s["source_id"]: s for s in p.entries(records, "source")}
    protocol = json.loads((root / sources[enrollment["protocol_source_id"]]["snapshot"]).read_bytes())
    if protocol.get("collector_sha256") != p.digest(Path(__file__).read_bytes().replace(b"\r\n", b"\n")):
        raise ValueError("Collector differs from frozen enrollment; return to its original commit")
    issuers = universe((root / sources[enrollment["universe_source_id"]]["snapshot"]).read_bytes())
    # Include preceding date to catch NY-date/UTC boundary cases for later exact-time review.
    day = p.timestamp(enrollment["window_start"]).date() - timedelta(days=1)
    end = p.timestamp(p.utc_now()).date() - timedelta(days=2)
    if (end - day).days > 90:
        raise ValueError("Window exceeds 90 days; research review required before further collection")
    candidates, coverage = [], []
    attempts = 0
    while day <= end:
        url = f"https://www.sec.gov/Archives/edgar/daily-index/{day.year}/QTR{(day.month-1)//3+1}/master.{day:%Y%m%d}.idx"
        if day.weekday() >= 5:
            coverage.append({"date": day.isoformat(), "status": "WEEKEND_NOT_REQUESTED"})
            day += timedelta(days=1)
            continue
        try:
            attempts += 1
            body = get(url, user_agent)
            parsed = parse_index(body, issuers)
            sid = save_source(root, folder, body, url, "SEC daily index; all matching filing candidates retained")
            for row in parsed:
                row["index_source_id"] = sid
                row["index_date"] = day.isoformat()
            candidates.extend(parsed)
            coverage.append({"date": day.isoformat(), "status": "CAPTURED", "source_id": sid})
        except HTTPError as exc:
            coverage.append({"date": day.isoformat(), "status": "UNRESOLVED", "http_status": exc.code})
            if exc.code in {403, 429}:
                break  # Respect access blocks; no retries or alternate hosts.
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            coverage.append({"date": day.isoformat(), "status": "UNRESOLVED", "error": str(exc)})
            break
        day += timedelta(days=1)
    p.write_json(folder / "filing_candidates.json", {"rows": candidates})
    p.write_json(folder / "coverage.json", {"dates": coverage})
    unresolved = any(x["status"] == "UNRESOLVED" for x in coverage)
    return {"status": "COVERAGE_REVIEW_REQUIRED" if unresolved else "AWAITING_EVIDENCE_REVIEW" if candidates else "NO_CANDIDATES_YET",
            "window_start": enrollment["window_start"], "indexes_requested_through": end.isoformat(),
            "candidate_filings": len(candidates), "coverage_complete_attested": False,
            "network_download_attempts": attempts,
            "cohort_registered": False, "performance": None,
            "note": "Unranked inbox, not eligible companies. Review exact timing, duplicate disclosures, eligibility and financial evidence before cohort registration."}


def run(root: Path, mode: str, user_agent: str) -> Path:
    read_records(root)  # Fail before requests or filesystem output for an invalid pilot.
    folder = root / "feed_runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    folder.mkdir(parents=True, exist_ok=False)
    try:
        summary = enroll(root, folder, user_agent) if mode == "enroll" else collect(root, folder, user_agent)
    except (ValueError, KeyError, TypeError, OSError, URLError, sqlite3.Error) as exc:
        p.write_json(folder / "error.json", {"error": str(exc), "mode": mode})
        raise
    summary["nested_pilot_report_scope"] = "The unchanged ledger report's downloads=0 refers only to its offline exporter. This feed summary records SEC network attempts."
    p.write_json(folder / "summary.json", summary)
    ledger_zip = p.report(root)
    bundle = folder.with_suffix(".zip")
    with zipfile.ZipFile(bundle, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(ledger_zip, "pilot_export.zip")
        for path in sorted(folder.iterdir()):
            archive.write(path, path.name)
        archive.writestr("collector.py", Path(__file__).read_bytes())
    print(json.dumps(summary, indent=2))
    print(f"UPLOAD SEC FEED ZIP: {bundle.resolve()}")
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["enroll", "collect"])
    parser.add_argument("--pilot-dir", required=True, type=Path)
    parser.add_argument("--user-agent", required=True)
    args = parser.parse_args()
    try:
        run(args.pilot_dir, args.mode, args.user_agent)
    except (ValueError, KeyError, TypeError, OSError, URLError, sqlite3.Error) as exc:
        parser.exit(2, f"SEC feed stopped: {exc}\n")


if __name__ == "__main__":
    main()
