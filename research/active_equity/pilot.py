"""Prospective evidence and decision ledger. Not a trading/P&L engine.

All commands are offline. SQLite transactions serialize append operations. Hashes
detect accidental edits; they are NOT external timestamp or anti-fraud guarantees.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import sqlite3
import subprocess
from urllib.parse import urlparse
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/research/ACTIVE_EQUITY_PILOT_20260914.md"
PROMPT = ROOT / "research/active_equity/analyst_prompt.md"
ZERO = "0" * 64
SECTORS = {
    "communication_services", "consumer_discretionary", "consumer_staples",
    "energy", "financials", "health_care", "industrials", "information_technology",
    "materials", "real_estate", "utilities",
}


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Timestamp must be an ISO-8601 string with UTC offset")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {value}") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Timezone-naive timestamps are forbidden")
    return result.astimezone(timezone.utc)


def number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite JSON number")
    return float(value)


def required_text(obj: dict, *fields: str) -> None:
    for field in fields:
        if not isinstance(obj.get(field), str) or not obj[field].strip():
            raise ValueError(f"Missing nonempty text: {field}")


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", value):
        raise ValueError("Identifiers must be 1-100 letters, digits, underscores, dots or hyphens")
    return value


def strict_json(path: Path) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    result = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=pairs)
    if not isinstance(result, dict):
        raise ValueError("Input must be a JSON object")
    canonical(result)  # Reject NaN/Infinity anywhere, including unused fields.
    return result


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def connect(root: Path) -> sqlite3.Connection:
    # mode=rw refuses to invent an empty DB for an incorrectly specified path.
    con = sqlite3.connect((root / "ledger.sqlite").resolve().as_uri() + "?mode=rw", uri=True)
    con.row_factory = sqlite3.Row
    return con


def rows(con: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in con.execute("SELECT * FROM journal ORDER BY seq")]


def entries(records: list[dict], kind: str) -> list[dict]:
    return [json.loads(row["payload"]) for row in records if json.loads(row["payload"])["kind"] == kind]


def insert(con: sqlite3.Connection, payload: dict, recorded_at: str) -> None:
    previous = con.execute("SELECT entry_hash FROM journal ORDER BY seq DESC LIMIT 1").fetchone()
    prev_hash = previous[0] if previous else ZERO
    sequence = con.execute("SELECT count(*) FROM journal").fetchone()[0] + 1
    body = canonical(payload)
    entry_hash = digest(canonical([sequence, recorded_at, prev_hash, body]).encode())
    con.execute("INSERT INTO journal VALUES (?, ?, ?, ?, ?)",
                (sequence, recorded_at, prev_hash, body, entry_hash))


def selected_events(cohort: dict) -> list[dict]:
    eligible = [e for e in cohort["events"] if (
        e["us_listed"] and e["operating_company"] and e["common_stock"]
        and 500_000_000 <= e["market_cap_usd"] <= 10_000_000_000
        and e["adv20_usd"] >= 5_000_000)]
    eligible.sort(key=lambda e: (timestamp(e["published_at"]), e["cik"], e["event_id"]))
    unique = {}
    for event in eligible:
        unique.setdefault(event["cik"], event)
    return list(unique.values())[:20]


def simple_screen(event: dict) -> bool:
    # Missing comparator inputs are never imputed or selected away.
    return event["revenue_yoy"] > 0 and event["operating_margin_yoy_change"] > 0


def validate(payload: dict, records: list[dict], now: str) -> None:
    canonical(payload)
    kind = payload.get("kind")
    clock = timestamp(now)
    if kind == "init":
        if records:
            raise ValueError("Only one initialization is allowed")
        return
    if not records:
        raise ValueError("Initialize a pilot first")
    sources = {s["source_id"]: s for s in entries(records, "source")}

    def refs(obj: dict):
        ids = obj.get("source_ids")
        if not isinstance(ids, list) or not ids or any(i not in sources for i in ids):
            raise ValueError("Every evidence record requires registered source_ids")
        return [sources[i] for i in ids]

    if kind == "source":
        identifier(payload["source_id"])
        if payload["source_id"] in sources:
            raise ValueError("Duplicate source_id; register a new version instead")
        required_text(payload, "url", "description")
        parsed = urlparse(payload["url"])
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Source URL must be public HTTPS without credentials")
        published, available = timestamp(payload["published_at"]), timestamp(payload["available_at"])
        if not published <= available <= clock:
            raise ValueError("Require published_at <= available_at <= capture time")
        if not re.fullmatch(r"[a-f0-9]{64}", payload.get("content_sha256", "")):
            raise ValueError("Source snapshot hash missing")
        if payload.get("snapshot") != f"evidence/{payload['content_sha256']}.bin":
            raise ValueError("Invalid evidence snapshot path")
    elif kind == "enrollment":
        if entries(records, "enrollment"):
            raise ValueError("Enrollment is frozen; use a new pilot to change it")
        required_text(payload, "feed_name", "coverage_statement", "universe_definition")
        refs(payload)
        if timestamp(payload["window_start"]) <= clock:
            raise ValueError("Enrollment must be recorded before its future start")
    elif kind == "cohort":
        if entries(records, "cohort"):
            raise ValueError("Cohort is locked; corrections require a new pilot")
        enrollment = entries(records, "enrollment")
        if not enrollment:
            raise ValueError("Freeze the feed and universe in an enrollment record first")
        refs(payload)
        start, end = timestamp(payload["window_start"]), timestamp(payload["window_end"])
        if start != timestamp(enrollment[0]["window_start"]):
            raise ValueError("Cannot move the predeclared cohort start")
        if not timestamp(records[0]["recorded_at"]) <= start < end <= clock:
            raise ValueError("Cohort window must start after pilot initialization and end before registration")
        if payload.get("complete_for_declared_feed") is not True:
            raise ValueError("Declare complete feed coverage or do not register a consecutive cohort")
        events = payload.get("events")
        if not isinstance(events, list) or not events:
            raise ValueError("Supply every screened event, including exclusions")
        seen = set()
        for event in events:
            identifier(event["event_id"])
            if event["event_id"] in seen:
                raise ValueError("Duplicate event_id")
            seen.add(event["event_id"])
            required_text(event, "ticker", "cik", "eligibility_explanation")
            if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", event["ticker"]):
                raise ValueError("Invalid ticker")
            if not re.fullmatch(r"[0-9]{10}", event["cik"]):
                raise ValueError("CIK must be a zero-padded ten-digit issuer identifier")
            if event["sector"] not in SECTORS:
                raise ValueError("Use the frozen sector vocabulary")
            evidence = refs(event)
            event_time = timestamp(event["published_at"])
            if not start <= event_time < end:
                raise ValueError("Event outside enrollment window")
            if not any(timestamp(s["published_at"]) == event_time for s in evidence):
                raise ValueError("Event publication must match a registered source")
            if not timestamp(event["eligibility_asof"]) <= event_time:
                raise ValueError("Eligibility must be measured no later than event publication")
            for field in ("market_cap_usd", "adv20_usd", "revenue_yoy", "operating_margin_yoy_change"):
                value = number(event[field], field)
                if field.endswith("_usd") and value < 0:
                    raise ValueError("Negative eligibility value")
            for field in ("us_listed", "operating_company", "common_stock"):
                if type(event[field]) is not bool:
                    raise ValueError(f"{field} must be a boolean")
        if len(selected_events(payload)) != 20:
            raise ValueError("Need 20 eligible distinct issuers; incomplete coverage is not a smaller cohort")
    elif kind == "decision":
        cohorts = entries(records, "cohort")
        if not cohorts:
            raise ValueError("Register the cohort before decisions")
        identifier(payload["decision_id"])
        if payload["decision_id"] in {d["decision_id"] for d in entries(records, "decision")}:
            raise ValueError("Duplicate decision_id")
        event = next((e for e in selected_events(cohorts[0]) if e["event_id"] == payload["event_id"]), None)
        if event is None:
            raise ValueError("Decision must refer to a selected cohort event")
        refs(payload)
        required_text(payload, "thesis", "valuation_case", "strongest_counterargument", "invalidation",
                      "forecast", "model_id", "model_version_status", "analyst", "confidence_reason")
        if payload.get("confidence") not in {"low", "medium", "high"}:
            raise ValueError("Confidence is qualitative, not a calibrated probability")
        if payload.get("action") not in {"buy", "watch", "reject", "hold", "sell"}:
            raise ValueError("Unknown decision action")
        if timestamp(payload["horizon_end"]) <= clock:
            raise ValueError("Forecast horizon must lie after decision registration")
        prior = [d for d in entries(records, "decision") if d["event_id"] == event["event_id"]]
        if not prior and payload["action"] not in {"buy", "watch", "reject"}:
            raise ValueError("An initial decision must be buy, watch or reject")
        if payload.get("supersedes") != (prior[-1]["decision_id"] if prior else None):
            raise ValueError("Revisions must explicitly supersede the latest decision")
        claims = payload.get("claims")
        if not isinstance(claims, list) or not claims:
            raise ValueError("Supply source-backed claims")
        for claim in claims:
            required_text(claim, "statement", "source_locator")
            claim_sources = refs(claim)
            if not set(claim["source_ids"]) <= set(payload["source_ids"]):
                raise ValueError("Claim source must be in decision source_ids")
            if claim.get("classification") not in {"fact", "inference", "unknown"}:
                raise ValueError("Claim must be fact, inference, or unknown")
            if any(timestamp(s["available_at"]) > clock for s in claim_sources):
                raise ValueError("Unavailable claim source")
    elif kind == "proposal":
        identifier(payload["proposal_id"])
        if payload["proposal_id"] in {p["proposal_id"] for p in entries(records, "proposal")}:
            raise ValueError("Duplicate proposal_id")
        decisions = {d["decision_id"]: d for d in entries(records, "decision")}
        cohorts = entries(records, "cohort")
        if not cohorts:
            raise ValueError("No cohort registered")
        events = {e["event_id"]: e for e in selected_events(cohorts[0])}
        latest = {d["event_id"]: d["decision_id"] for d in decisions.values()}
        if set(events) != set(latest):
            raise ValueError("Review all 20 companies, including rejects, before proposing a portfolio")
        if timestamp(payload["not_before"]) <= clock:
            raise ValueError("Proposed execution must be strictly after registration")
        required_text(payload, "rationale")
        weights = payload.get("targets")
        if not isinstance(weights, list):
            raise ValueError("targets must be the full proposed portfolio, not a trade delta")
        sectors, seen, total = Counter(), set(), 0.0
        for target in weights:
            decision = decisions.get(target["decision_id"])
            if not decision or decision["action"] not in {"buy", "hold"}:
                raise ValueError("Positive target requires a buy/hold decision")
            if latest[decision["event_id"]] != decision["decision_id"]:
                raise ValueError("Stale decision superseded by newer analysis")
            if timestamp(decision["horizon_end"]) <= timestamp(payload["not_before"]):
                raise ValueError("Decision horizon expires before proposed execution")
            event = events[decision["event_id"]]
            if event["cik"] in seen:
                raise ValueError("Duplicate issuer target")
            seen.add(event["cik"])
            weight = number(target["weight"], "weight")
            if not 0 < weight <= 0.10:
                raise ValueError("Each target must be positive and <=10%")
            total += weight
            sectors[event["sector"]] += weight
        cash = number(payload["cash_weight"], "cash_weight")
        if cash < 0 or abs(cash + total - 1.0) > 1e-10:
            raise ValueError("Targets plus cash must sum to one without leverage")
        if any(w > 0.25 + 1e-12 for w in sectors.values()):
            raise ValueError("Sector target exceeds 25%")
    else:
        raise ValueError(f"Unsupported record kind: {kind}")


def audit_records(root: Path, records: list[dict]) -> None:
    if not records or json.loads(records[0]["payload"]).get("kind") != "init":
        raise ValueError("Missing initialization")
    previous = ZERO
    history = []
    for sequence, row in enumerate(records, 1):
        if row["seq"] != sequence or row["prev_hash"] != previous:
            raise ValueError("Broken ledger sequence/hash chain")
        if history and timestamp(row["recorded_at"]) < timestamp(history[-1]["recorded_at"]):
            raise ValueError("Ledger clock moved backwards")
        expected = digest(canonical([sequence, row["recorded_at"], previous, row["payload"]]).encode())
        if expected != row["entry_hash"]:
            raise ValueError("Ledger payload hash mismatch")
        payload = json.loads(row["payload"])
        validate(payload, history, row["recorded_at"])
        if payload["kind"] == "source":
            path = root / payload["snapshot"]
            if path.is_symlink() or digest(path.read_bytes()) != payload["content_sha256"]:
                raise ValueError("Evidence snapshot changed")
        if payload["kind"] == "init":
            for name, sha in payload["frozen_files"].items():
                if name not in {"specification.md", "analyst_prompt.md", "pilot_code.py"}:
                    raise ValueError("Invalid frozen file path")
                if digest((root / name).read_bytes()) != sha:
                    raise ValueError("Frozen experiment file changed")
            if digest(Path(__file__).read_bytes().replace(b"\r\n", b"\n")) != payload["frozen_files"]["pilot_code.py"]:
                raise ValueError("Runner code differs from the initialized pilot; use its original commit")
        history.append(row)
        previous = row["entry_hash"]


def initialize(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=False)
    (root / "evidence").mkdir()
    frozen = {}
    for path, name in [(SPEC, "specification.md"), (PROMPT, "analyst_prompt.md"), (Path(__file__), "pilot_code.py")]:
        content = path.read_bytes().replace(b"\r\n", b"\n")
        (root / name).write_bytes(content)
        frozen[name] = digest(content)
    con = sqlite3.connect(root / "ledger.sqlite")
    try:
        con.executescript("""
            CREATE TABLE journal(seq INTEGER PRIMARY KEY, recorded_at TEXT NOT NULL,
                prev_hash TEXT NOT NULL, payload TEXT NOT NULL, entry_hash TEXT NOT NULL);
            CREATE TRIGGER no_update BEFORE UPDATE ON journal BEGIN SELECT RAISE(ABORT, 'append only'); END;
            CREATE TRIGGER no_delete BEFORE DELETE ON journal BEGIN SELECT RAISE(ABORT, 'append only'); END;
        """)
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
        insert(con, {"kind": "init", "experiment": "active_equity_pilot_v1",
                     "git_commit": result.stdout.strip() if result.returncode == 0 else "unknown",
                     "python": platform.python_version(), "frozen_files": frozen,
                     "performance_status": "NOT_RUN", "execution_enabled": False}, utc_now())
        con.commit()
    finally:
        con.close()


def append(root: Path, payload: dict, attachment: Path | None = None) -> None:
    payload = json.loads(canonical(payload))
    content = None
    if payload.get("kind") == "source":
        if attachment is None or not attachment.is_file():
            raise ValueError("Source registration requires a local --attachment snapshot")
        if attachment.stat().st_size == 0 or attachment.stat().st_size > 25_000_000:
            raise ValueError("Source snapshot must be nonempty and <=25MB")
        content = attachment.read_bytes()
        payload["content_sha256"] = digest(content)
        payload["snapshot"] = f"evidence/{digest(content)}.bin"
    elif attachment is not None:
        raise ValueError("Attachments are only valid for source registration")
    with closing(connect(root)) as con:
        con.execute("BEGIN IMMEDIATE")
        records = rows(con)
        audit_records(root, records)
        now = utc_now()  # Never accept a caller-supplied decision/recording timestamp.
        if timestamp(now) < timestamp(records[-1]["recorded_at"]):
            raise ValueError("System clock moved backwards")
        validate(payload, records, now)
        if content is not None:
            path = root / payload["snapshot"]
            if path.exists():
                if path.is_symlink() or path.read_bytes() != content:
                    raise ValueError("Existing evidence snapshot differs")
            else:
                with path.open("xb") as handle:
                    handle.write(content)
        insert(con, payload, now)
        con.commit()


def inventory(data_root: Path | None) -> dict:
    result = {"status": "NOT_REQUESTED", "files": [], "errors": [],
              "contents_read": False, "eligibility_verified": False,
              "note": "Filename/size inventory only; does not establish fundamental or point-in-time coverage."}
    if data_root is None:
        return result
    if not data_root.is_dir():
        raise ValueError(f"DataRoot is not a directory: {data_root}")
    result["status"] = "INVENTORIED"
    def on_error(error):
        result["errors"].append(str(error))
    for directory, subdirs, files in os.walk(data_root, followlinks=False, onerror=on_error):
        subdirs[:] = sorted(d for d in subdirs if not (Path(directory) / d).is_symlink() and not d.startswith("."))
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_symlink() or path.suffix.lower() not in {".csv", ".parquet", ".json", ".jsonl", ".pdf", ".html", ".txt"} or name.startswith("."):
                continue
            try:
                result["files"].append({"path": path.relative_to(data_root).as_posix(), "bytes": path.stat().st_size})
            except OSError as exc:
                on_error(exc)
    if result["errors"]:
        result["status"] = "INCOMPLETE"
    return result


def report(root: Path, data_root: Path | None = None) -> Path:
    # Export the transactionally consistent journal, not a potentially active DB.
    with closing(connect(root)) as con:
        con.execute("BEGIN")
        records = rows(con)
        audit_records(root, records)
    cohorts = entries(records, "cohort")
    decisions = entries(records, "decision")
    selected = selected_events(cohorts[0]) if cohorts else []
    latest = {d["event_id"]: d for d in decisions}
    coverage = inventory(data_root)
    summary = {"experiment": "active_equity_pilot_v1", "generated_at": utc_now(),
               "status": ("DECISION_PILOT_ONLY" if cohorts else
                          "AWAITING_COHORT" if entries(records, "enrollment") else "AWAITING_ENROLLMENT"),
               "records": len(records), "head_sha256": records[-1]["entry_hash"],
               "cohort_size": len(selected), "companies_reviewed": len(latest),
               "proposal_count": len(entries(records, "proposal")),
               "performance": None, "performance_status": "NOT_RUN",
               "execution_enabled": False, "downloads": 0, "model_calls": 0,
               "independent_timestamp_proof": False,
               "coverage_independently_verified": False,
               "blockers": ["Stage 1 has no fills, NAV, cash accrual or performance evaluator.",
                            "Cohort feed completeness requires independent review.",
                            "External anchoring of journal head is required before performance evaluation."]}
    cohort_rows = [{"event_id": e["event_id"], "ticker": e["ticker"],
                    "simple_screen_pass": simple_screen(e),
                    "latest_action": latest.get(e["event_id"], {}).get("action")}
                   for e in selected]
    export = root / "exports" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ"))
    export.mkdir(parents=True, exist_ok=False)
    write_json(export / "report.json", summary)
    write_json(export / "data_inventory.json", coverage)
    write_json(export / "cohort_comparison.json", {"rows": cohort_rows})
    with (export / "journal.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
        for row in records:
            handle.write(canonical(row) + "\n")
    bundle = export.with_suffix(".zip")
    with zipfile.ZipFile(bundle, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(export.iterdir()):
            archive.write(path, path.name)
        for name in ("specification.md", "analyst_prompt.md", "pilot_code.py"):
            archive.write(root / name, name)
        for name in sorted({s["snapshot"] for s in entries(records, "source")}):
            archive.write(root / name, name)
    print(json.dumps(summary, indent=2))
    print(f"SHARE PILOT ZIP: {bundle.resolve()}")
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "append", "report", "verify"])
    parser.add_argument("--pilot-dir", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--attachment", type=Path)
    parser.add_argument("--data-root", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "init":
            if args.data_root is not None and not args.data_root.is_dir():
                raise ValueError("DataRoot does not exist; no pilot was initialized")
            initialize(args.pilot_dir)
            report(args.pilot_dir, args.data_root)
        elif args.command == "append":
            if args.input is None:
                raise ValueError("append requires --input")
            append(args.pilot_dir, strict_json(args.input), args.attachment)
            report(args.pilot_dir, args.data_root)
        elif args.command == "report":
            report(args.pilot_dir, args.data_root)
        else:
            with closing(connect(args.pilot_dir)) as con:
                con.execute("BEGIN")
                audit_records(args.pilot_dir, rows(con))
            print("Journal and evidence verified; no performance claim.")
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as exc:
        parser.exit(2, f"Pilot stopped: {exc}\n")


if __name__ == "__main__":
    main()
