"""Synthetic feed/ledger mechanics only; network is mocked."""
from datetime import datetime, timedelta, timezone
import json
import zipfile
from urllib.error import HTTPError

import pytest

from research.active_equity import pilot as p
from research.active_equity import sec_feed as s


UNIVERSE = json.dumps({"fields": ["cik", "name", "ticker", "exchange"], "data": [
    [1, "Synthetic issuer", "TEST", "Nasdaq"], [1, "Synthetic issuer", "TEST.B", "NYSE"],
    [2, "Synthetic unlisted", "OTHER", None]]}).encode()
INDEX = b"Description\nCIK|Company Name|Form Type|Date Filed|Filename\n-----\n1|Synthetic issuer|10-Q|2030-01-04|edgar/data/1/0000000001-30-000001.txt\n"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    clock = [datetime(2030, 1, 1, 12, tzinfo=timezone.utc)]
    monkeypatch.setattr(p, "utc_now", lambda: clock[0].isoformat())
    monkeypatch.setattr(s, "get", lambda url, agent: UNIVERSE if url == s.UNIVERSE_URL else INDEX)
    root = tmp_path / "pilot"
    p.initialize(root)
    folder = tmp_path / "feed"
    folder.mkdir()
    return root, folder, clock


def test_enroll_preserves_frozen_pilot_and_future_boundary(setup):
    root, folder, clock = setup
    original = (root / "pilot_code.py").read_bytes()
    result = s.enroll(root, folder, "test")
    assert result["issuer_count"] == 1
    assert p.timestamp(result["window_start"]) > clock[0] + timedelta(hours=24)
    records = s.read_records(root)
    assert len(p.entries(records, "enrollment")) == 1
    assert not p.entries(records, "cohort")
    assert (root / "pilot_code.py").read_bytes() == original
    protocol_source = p.entries(records, "source")[-1]
    protocol = json.loads((root / protocol_source["snapshot"]).read_bytes())
    assert protocol["collector_sha256"] == p.digest(s.Path(s.__file__).read_bytes().replace(b"\r\n", b"\n"))


def test_duplicate_enrollment_refuses_network(setup, monkeypatch):
    root, folder, _ = setup
    s.enroll(root, folder, "test")
    monkeypatch.setattr(s, "get", lambda *a: pytest.fail("Unexpected network"))
    with pytest.raises(ValueError, match="already enrolled"):
        s.enroll(root, folder, "test")


def test_no_historical_candidates_before_start(setup):
    root, folder, _ = setup
    s.enroll(root, folder, "test")
    result = s.collect(root, folder, "test")
    assert result["candidate_filings"] == 0


def test_collect_retains_unknowns_and_exports_ledger(setup):
    root, folder, clock = setup
    s.enroll(root, folder, "test")
    clock[0] += timedelta(days=6)
    bundle = s.run(root, "collect", "test")
    with zipfile.ZipFile(bundle) as z:
        assert z.testzip() is None
        assert "pilot_export.zip" in z.namelist()
        assert json.loads(z.read("summary.json"))["status"] == "AWAITING_EVIDENCE_REVIEW"
        rows = json.loads(z.read("filing_candidates.json"))["rows"]
        assert rows and all(row["eligible"] is None and row["published_at"] is None for row in rows)
        assert all(len(row["listings_at_enrollment"]) == 2 for row in rows)
    assert not p.entries(s.read_records(root), "cohort")


@pytest.mark.parametrize("code", [403, 404, 429, 500])
def test_http_errors_never_claim_empty_complete_feed(setup, monkeypatch, code):
    root, folder, clock = setup
    s.enroll(root, folder, "test")
    clock[0] += timedelta(days=6)
    def fail(url, agent):
        raise HTTPError(url, code, "synthetic", {}, None)
    monkeypatch.setattr(s, "get", fail)
    result = s.collect(root, folder, "test")
    assert result["status"] == "COVERAGE_REVIEW_REQUIRED"
    assert result["coverage_complete_attested"] is False
    assert json.loads((folder / "coverage.json").read_text())["dates"][0]["http_status"] == code


def test_wrong_collector_rejected(setup, monkeypatch):
    root, folder, _ = setup
    s.enroll(root, folder, "test")
    monkeypatch.setattr(s, "__file__", str(root / "specification.md"))
    with pytest.raises(ValueError, match="Collector differs"):
        s.collect(root, folder, "test")


@pytest.mark.parametrize("body", [b"<html>Access denied</html>", INDEX + b"bad row\n", INDEX + INDEX.splitlines()[-1] + b"\n", INDEX.replace(b"edgar/data/1/", b"edgar/data/2/")])
def test_bad_index_rejected(body):
    with pytest.raises(ValueError):
        s.parse_index(body, s.universe(UNIVERSE))


def test_forms_and_frozen_membership():
    body = INDEX + b"2|Excluded|10-Q|2030-01-04|edgar/data/2/0000000002-30-000001.txt\n1|Other form|4|2030-01-04|edgar/data/1/0000000001-30-000002.txt\n"
    assert len(s.parse_index(body, s.universe(UNIVERSE))) == 1


@pytest.mark.parametrize("body", [b"{}", b"<html>blocked</html>", b'{"fields":["cik"],"data":[]}'])
def test_bad_universe_rejected(body):
    with pytest.raises((ValueError, KeyError)):
        s.universe(body)


def test_user_agent_validated_before_network():
    with pytest.raises(ValueError, match="contact email"):
        s.get(s.UNIVERSE_URL, "anonymous")


def test_missing_pilot_fails_before_network(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "get", lambda *a: pytest.fail("Unexpected network"))
    with pytest.raises(Exception):
        s.run(tmp_path / "missing", "enroll", "test")
