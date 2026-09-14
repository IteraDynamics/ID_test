"""Synthetic mechanics only. No market observations or investment evidence."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import zipfile

import pytest

from research.active_equity import pilot as p


def stamp(day=0):
    return (datetime(2030, 1, 1, tzinfo=timezone.utc) + timedelta(days=day)).isoformat()


def journal(root):
    with closing(p.connect(root)) as con:
        return p.rows(con)


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "utc_now", lambda: stamp(0))
    root = tmp_path / "pilot"
    p.initialize(root)
    monkeypatch.setattr(p, "utc_now", lambda: stamp(1))
    document = tmp_path / "synthetic.txt"
    document.write_text("SYNTHETIC FIXTURE: no real company or investment result.")
    p.append(root, {"kind": "source", "source_id": "feed", "url": "https://example.com/calendar",
                    "description": "Synthetic calendar", "published_at": stamp(0),
                    "available_at": stamp(0)}, document)
    return root, document


def enroll(root):
    p.append(root, {"kind": "enrollment", "feed_name": "synthetic",
                    "universe_definition": "Synthetic companies only",
                    "coverage_statement": "All synthetic fixture events",
                    "source_ids": ["feed"], "window_start": stamp(2)})


def cohort():
    return {"kind": "cohort", "source_ids": ["feed"],
            "window_start": stamp(2), "window_end": stamp(4),
            "complete_for_declared_feed": True,
            "events": [dict(event_id=f"event{i}", ticker=f"TEST{i}", cik=f"{i+1:010d}",
                            sector=list(sorted(p.SECTORS))[i % len(p.SECTORS)],
                            published_at=stamp(3), eligibility_asof=stamp(2),
                            eligibility_explanation="Synthetic data", market_cap_usd=1e9,
                            adv20_usd=10e6, us_listed=True, operating_company=True,
                            common_stock=True, revenue_yoy=0.1,
                            operating_margin_yoy_change=0.01 if i % 2 else -0.01,
                            source_ids=["earnings"]) for i in range(20)]}


@pytest.fixture
def ready(ledger, monkeypatch):
    root, document = ledger
    enroll(root)
    monkeypatch.setattr(p, "utc_now", lambda: stamp(5))
    p.append(root, {"kind": "source", "source_id": "earnings", "url": "https://example.com/earnings",
                    "description": "Synthetic earnings", "published_at": stamp(3),
                    "available_at": stamp(3)}, document)
    return root


def decision(i=0):
    return dict(kind="decision", decision_id=f"d{i}", event_id=f"event{i}", action="buy",
                source_ids=["earnings"], thesis="Synthetic durability thesis",
                valuation_case="Synthetic expectations test", strongest_counterargument="Already priced",
                invalidation="Margin reversal", forecast="Margins persist", horizon_end=stamp(100),
                model_id="synthetic_test", model_version_status="not a model run", analyst="test",
                confidence="low", confidence_reason="Synthetic", supersedes=None,
                claims=[dict(statement="Synthetic reported growth", classification="fact",
                             source_ids=["earnings"], source_locator="Fixture, paragraph 1")])


@pytest.fixture
def reviewed(ready):
    p.append(ready, cohort())
    for i in range(20):
        p.append(ready, decision(i))
    return ready


def proposal():
    return dict(kind="proposal", proposal_id="p1", not_before=stamp(6),
                rationale="Synthetic risk test", cash_weight=0.8,
                targets=[dict(decision_id="d0", weight=0.1), dict(decision_id="d1", weight=0.1)])


def test_init_refuses_overwrite(ledger):
    root, _ = ledger
    before = (root / "ledger.sqlite").read_bytes()
    with pytest.raises(FileExistsError):
        p.initialize(root)
    assert (root / "ledger.sqlite").read_bytes() == before


def test_missing_pilot_does_not_create_db(tmp_path):
    with pytest.raises(sqlite3.OperationalError):
        p.connect(tmp_path)
    assert not (tmp_path / "ledger.sqlite").exists()


@pytest.mark.parametrize("bad", ["2030-01-01", "2030-01-01T00:00:00", "not a date", 1, None])
def test_invalid_timestamps(bad):
    with pytest.raises(ValueError):
        p.timestamp(bad)


def test_timezone_offsets_compare_by_instant():
    assert p.timestamp("2030-01-01T01:00:00+01:00") == p.timestamp(stamp())


@pytest.mark.parametrize("bad", [True, "0.1", None, float("nan"), float("inf")])
def test_invalid_numbers(bad):
    with pytest.raises(ValueError):
        p.number(bad, "test")


@pytest.mark.parametrize("body", ['{"x":1,"x":2}', '{"x":NaN}', '[]'])
def test_strict_json(tmp_path, body):
    file = tmp_path / "input.json"
    file.write_text(body)
    with pytest.raises(ValueError):
        p.strict_json(file)


def test_source_future_and_duplicate_rejected(ledger):
    root, document = ledger
    source = dict(kind="source", source_id="future", url="https://example.com",
                  description="Synthetic", published_at=stamp(6), available_at=stamp(6))
    before = journal(root)
    with pytest.raises(ValueError, match="capture time"):
        p.append(root, source, document)
    source.update(source_id="feed", published_at=stamp(), available_at=stamp())
    with pytest.raises(ValueError, match="Duplicate source"):
        p.append(root, source, document)
    assert journal(root) == before


def test_source_attachment_required(ledger):
    with pytest.raises(ValueError, match="attachment"):
        p.append(ledger[0], {"kind": "source"})


@pytest.mark.parametrize("url", ["file:///secret", "http://example.com", "https://user:pass@example.com"])
def test_bad_source_url(ledger, url):
    root, document = ledger
    with pytest.raises(ValueError, match="HTTPS"):
        p.append(root, dict(kind="source", source_id="new", url=url, description="fixture",
                            published_at=stamp(), available_at=stamp()), document)


def test_source_path_is_not_trusted(ledger):
    root, document = ledger
    p.append(root, dict(kind="source", source_id="safe", url="https://example.com", description="fixture",
                        published_at=stamp(), available_at=stamp(), snapshot="../../escape",
                        content_sha256="invented"), document)
    payload = json.loads(journal(root)[-1]["payload"])
    assert payload["snapshot"].startswith("evidence/")
    assert payload["content_sha256"] == p.digest(document.read_bytes())


def test_enrollment_cannot_be_backdated(ledger, monkeypatch):
    monkeypatch.setattr(p, "utc_now", lambda: stamp(2))
    with pytest.raises(ValueError, match="future start"):
        enroll(ledger[0])


def test_enrollment_cannot_be_changed(ledger):
    enroll(ledger[0])
    with pytest.raises(ValueError, match="Enrollment is frozen"):
        enroll(ledger[0])


def test_no_cohort_without_enrollment(ledger):
    with pytest.raises(ValueError, match="enrollment"):
        p.append(ledger[0], cohort())


def test_cohort_selection_is_sorted_unique_and_keeps_exclusions(ready):
    data = cohort()
    duplicate = deepcopy(data["events"][0])
    duplicate["event_id"] = "zz_duplicate"
    excluded = deepcopy(data["events"][0])
    excluded.update(event_id="excluded", cik="9999999999", market_cap_usd=100)
    data["events"] = list(reversed(data["events"])) + [duplicate, excluded]
    p.append(ready, data)
    selected = p.selected_events(data)
    assert len(selected) == 20
    assert selected[0]["event_id"] == "event0"
    assert "excluded" not in {e["event_id"] for e in selected}
    assert len(p.entries(journal(ready), "cohort")[0]["events"]) == 22
    with pytest.raises(ValueError, match="locked"):
        p.append(ready, data)


@pytest.mark.parametrize("field,value", [("market_cap_usd", None), ("adv20_usd", -1),
    ("revenue_yoy", None), ("operating_margin_yoy_change", "unknown"),
    ("us_listed", 1), ("sector", "made_up"), ("cik", "1"),
    ("eligibility_asof", stamp(4)), ("published_at", stamp(1))])
def test_bad_event_blocks_cohort(ready, field, value):
    data = cohort()
    data["events"][0][field] = value
    before = journal(ready)
    with pytest.raises(ValueError):
        p.append(ready, data)
    assert journal(ready) == before


def test_insufficient_unique_issuers_rejected(ready):
    data = cohort()
    data["events"][1]["cik"] = data["events"][0]["cik"]
    with pytest.raises(ValueError, match="20 eligible"):
        p.append(ready, data)


def test_incomplete_feed_rejected(ready):
    data = cohort()
    data["complete_for_declared_feed"] = False
    with pytest.raises(ValueError, match="complete feed"):
        p.append(ready, data)


def test_changed_enrollment_window_rejected(ready):
    data = cohort()
    data["window_start"] = stamp(3)
    with pytest.raises(ValueError, match="predeclared"):
        p.append(ready, data)


def test_no_decision_before_cohort(ready):
    with pytest.raises(ValueError, match="cohort before"):
        p.append(ready, decision())


@pytest.mark.parametrize("field,value", [("valuation_case", ""), ("model_id", ""),
    ("confidence", "99%"), ("action", "short"), ("horizon_end", stamp(5)),
    ("source_ids", ["missing"]), ("event_id", "not_selected"), ("claims", [])])
def test_bad_decision_rejected(ready, field, value):
    p.append(ready, cohort())
    data = decision()
    data[field] = value
    with pytest.raises(ValueError):
        p.append(ready, data)


def test_revisions_are_append_only(ready):
    p.append(ready, cohort())
    p.append(ready, decision())
    revised = decision()
    revised.update(decision_id="d0r1", action="sell")
    with pytest.raises(ValueError, match="supersede"):
        p.append(ready, revised)
    revised["supersedes"] = "d0"
    p.append(ready, revised)
    assert [d["action"] for d in p.entries(journal(ready), "decision")] == ["buy", "sell"]


def test_no_portfolio_until_rejects_reviewed(ready):
    p.append(ready, cohort())
    p.append(ready, decision())
    with pytest.raises(ValueError, match="all 20"):
        p.append(ready, proposal())


def test_valid_proposal_and_all_cash(reviewed):
    p.append(reviewed, proposal())
    data = proposal()
    data.update(proposal_id="cash", cash_weight=1, targets=[])
    p.append(reviewed, data)
    assert len(p.entries(journal(reviewed), "proposal")) == 2


@pytest.mark.parametrize("weight", [-0.1, 0, 0.10001, True, float("nan")])
def test_bad_position_weights(reviewed, weight):
    data = proposal()
    data["targets"][0]["weight"] = weight
    with pytest.raises(ValueError):
        p.append(reviewed, data)


def test_cash_and_execution_causality(reviewed):
    data = proposal()
    data["cash_weight"] = 0.7
    with pytest.raises(ValueError, match="sum to one"):
        p.append(reviewed, data)
    data["cash_weight"] = 0.8
    data["not_before"] = stamp(5)
    with pytest.raises(ValueError, match="strictly after"):
        p.append(reviewed, data)


def test_sector_limit(ready):
    data = cohort()
    for event in data["events"]:
        event["sector"] = "industrials"
    p.append(ready, data)
    for i in range(20):
        p.append(ready, decision(i))
    data = proposal()
    data.update(cash_weight=0.7, targets=[dict(decision_id=f"d{i}", weight=0.1) for i in range(3)])
    with pytest.raises(ValueError, match="Sector"):
        p.append(ready, data)


def test_stale_decision_cannot_be_used(reviewed):
    revised = decision()
    revised.update(decision_id="d0r1", action="reject", supersedes="d0")
    p.append(reviewed, revised)
    with pytest.raises(ValueError, match="Stale"):
        p.append(reviewed, proposal())


def test_database_updates_and_deletes_blocked(ledger):
    with closing(p.connect(ledger[0])) as con:
        with pytest.raises(sqlite3.IntegrityError, match="append only"):
            con.execute("DELETE FROM journal")
        with pytest.raises(sqlite3.IntegrityError, match="append only"):
            con.execute("UPDATE journal SET payload='{}'")


def test_evidence_tamper_detected(ledger):
    root, _ = ledger
    snapshot = p.entries(journal(root), "source")[0]["snapshot"]
    (root / snapshot).write_bytes(b"changed")
    with pytest.raises(ValueError, match="snapshot changed"):
        p.audit_records(root, journal(root))


def test_hash_canary(ledger):
    root, _ = ledger
    records = journal(root)
    records[-1]["payload"] = '{}'
    with pytest.raises(ValueError, match="hash mismatch"):
        p.audit_records(root, records)


def test_specification_tamper_detected(ledger):
    root, _ = ledger
    (root / "specification.md").write_text("changed")
    with pytest.raises(ValueError, match="Frozen"):
        p.audit_records(root, journal(root))


def test_clock_rollback_rejected(ledger, monkeypatch):
    monkeypatch.setattr(p, "utc_now", lambda: stamp())
    with pytest.raises(ValueError, match="clock"):
        enroll(ledger[0])


def test_concurrent_appends_are_serialized(ledger):
    root, document = ledger
    def add(i):
        p.append(root, dict(kind="source", source_id=f"parallel{i}", url="https://example.com",
                            description="Synthetic", published_at=stamp(), available_at=stamp()), document)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(add, range(8)))
    records = journal(root)
    assert len(records) == 10
    p.audit_records(root, records)


def test_export_is_readiness_not_fake_performance(ledger):
    root, _ = ledger
    before = journal(root)
    bundle = p.report(root)
    with zipfile.ZipFile(bundle) as z:
        report = json.loads(z.read("report.json"))
        assert report["performance"] is None
        assert report["status"] == "AWAITING_ENROLLMENT"
        assert report["execution_enabled"] is False
        assert report["model_calls"] == report["downloads"] == 0
        assert "ledger.sqlite" not in z.namelist()
        assert "journal.jsonl" in z.namelist()
    assert journal(root) == before


def test_comparison_retains_rejections(reviewed):
    revised = decision()
    revised.update(decision_id="d0r1", action="reject", supersedes="d0")
    p.append(reviewed, revised)
    with zipfile.ZipFile(p.report(reviewed)) as z:
        comparison = json.loads(z.read("cohort_comparison.json"))["rows"]
        assert len(comparison) == 20
        assert sum(row["simple_screen_pass"] for row in comparison) == 10
        assert comparison[0]["latest_action"] == "reject"


def test_inventory_does_not_read_or_copy_data(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "prices.csv").write_text("not even valid CSV")
    (data / ".secrets.json").write_text("secret")
    info = p.inventory(data)
    assert info["contents_read"] is False
    assert info["eligibility_verified"] is False
    assert info["files"] == [{"path": "prices.csv", "bytes": 18}]
    with pytest.raises(ValueError, match="directory"):
        p.inventory(tmp_path / "missing")


def test_isolation_no_runtime_or_network_imports():
    import ast
    tree = ast.parse(Path(p.__file__).read_text())
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not any(n.startswith(("runtime", "scripts", "requests", "http", "openai", "yfinance")) for n in names)
