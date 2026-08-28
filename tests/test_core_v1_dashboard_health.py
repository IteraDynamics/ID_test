"""Phase 0 of the Core v1 dashboard redesign — trust/provenance gating.

Two layers:

* pure-logic canaries on ``scripts/core_v1_dashboard_health`` — each asserts
  a property *and* its negation elsewhere, so the check can actually fail;
* AppTest smoke tests that render ``scripts/core_v1_dashboard.py`` against
  fixture state/audit files and assert the redesign's load-bearing rule:
  an unavailable or stale price audit can never read as "System Healthy",
  and the NAV/PnL deck carries an explicit "unverified" flag when it can't
  be trusted (``docs/engineering/CORE_V1_DASHBOARD_REDESIGN.md`` items 2-4),
  plus the runtime-identity strip (item 1).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts.core_v1_dashboard_health import (
    LARGEST_DRIFT_CAVEAT,
    audit_failure_lines,
    derive_audit_trust,
    nav_history,
    runtime_identity_view,
)


# --------------------------------------------------------------------------- #
# pure-logic canaries
# --------------------------------------------------------------------------- #
def test_verified_audit_is_the_only_trustworthy_state():
    verified = derive_audit_trust(audit_available=True, audit_ok=True, audit_stale=False)
    assert verified.numbers_trustworthy is True
    assert verified.healthy_banner_eligible is True
    assert verified.css == "ok"
    assert verified.deck_flag is None

    # ...and every other state is explicitly NOT trustworthy (the canary:
    # if the function ever regresses to a permissive default, this fails).
    for kwargs in (
        {"audit_available": False, "audit_ok": None, "audit_stale": False},
        {"audit_available": True, "audit_ok": True, "audit_stale": True},
        {"audit_available": True, "audit_ok": False, "audit_stale": False},
        {"audit_available": True, "audit_ok": False, "audit_stale": True},
    ):
        trust = derive_audit_trust(**kwargs)
        assert trust.numbers_trustworthy is False, kwargs
        assert trust.healthy_banner_eligible is False, kwargs
        assert trust.css != "ok", kwargs
        assert trust.deck_flag, kwargs


def test_unavailable_audit_is_unverified_not_pending_pass():
    trust = derive_audit_trust(audit_available=False, audit_ok=None, audit_stale=False)
    assert trust.level == "unverified"
    assert trust.css == "unverified"
    assert "UNVERIFIED" in trust.label
    assert "no independent price audit" in trust.deck_flag.lower()


def test_stale_audit_reports_unverified_numbers():
    trust = derive_audit_trust(audit_available=True, audit_ok=True, audit_stale=True)
    assert trust.level == "stale"
    assert trust.numbers_trustworthy is False
    assert "stale" in trust.deck_flag.lower()


def test_failing_audit_outranks_stale():
    trust = derive_audit_trust(audit_available=True, audit_ok=False, audit_stale=True)
    assert trust.level == "failing"
    assert trust.css == "err"


def test_audit_failure_lines_surfaces_all_failures_deduped():
    report = {"failures": ["BTC_4H_trend: bar price mismatch", "SPY_1D_equity: stale bar", "BTC_4H_trend: bar price mismatch"]}
    assert audit_failure_lines(report) == [
        "BTC_4H_trend: bar price mismatch",
        "SPY_1D_equity: stale bar",
    ]
    # not just failures[0] — the whole point of item 6
    assert len(audit_failure_lines(report)) == 2
    assert audit_failure_lines({}) == []
    assert audit_failure_lines(None) == []


def test_largest_drift_caveat_is_informational_language():
    assert "not a pass/fail" in LARGEST_DRIFT_CAVEAT.lower()


# --- nav_history: the staff-review fixes to the "Portfolio NAV" section ---
def _hourly_events(days: int, *, start_nav: float = 100_000.0) -> list[dict]:
    base = datetime(2026, 7, 7, 1, 0, 0, tzinfo=UTC)
    out, nav = [], start_nav
    for i in range(days * 24):
        nav *= 1.0003 if i % 4 else 0.9997
        out.append(
            {
                "timestamp": (base + timedelta(hours=i)).isoformat(),
                "total_nav": nav,
                "drawdown_frac": -0.30 if i == 200 else -0.01,
            }
        )
    return out


def test_nav_history_is_daily_and_full_span():
    ev = _hourly_events(40)  # 960 hourly cycles
    hist = nav_history(ev, 100_000.0)
    assert 39 <= len(hist) <= 41  # daily, not 960 hourly points
    assert hist[0]["date"] == "2026-07-07"
    # strictly increasing dates, one row per day
    assert [h["date"] for h in hist] == sorted({h["date"] for h in hist})


def test_nav_history_ret_is_pct_vs_baseline_and_drawdown_is_worst_of_day():
    ev = [
        {"timestamp": "2026-07-07T01:00:00+00:00", "total_nav": 100_000.0, "drawdown_frac": 0.0},
        {"timestamp": "2026-07-07T05:00:00+00:00", "total_nav": 98_000.0, "drawdown_frac": -0.05},
        {"timestamp": "2026-07-07T23:00:00+00:00", "total_nav": 103_000.0, "drawdown_frac": -0.01},
    ]
    hist = nav_history(ev, 100_000.0)
    assert len(hist) == 1
    assert hist[0]["nav"] == 103_000.0  # day's last
    assert abs(hist[0]["ret"] - 0.03) < 1e-9  # +3% vs $100k baseline
    assert hist[0]["drawdown"] == -0.05  # day's worst, not last


def test_nav_history_backfills_missing_drawdown_from_running_peak():
    ev = [
        {"timestamp": "2026-07-07T01:00:00+00:00", "total_nav": 100_000.0, "drawdown_frac": None},
        {"timestamp": "2026-07-08T01:00:00+00:00", "total_nav": 110_000.0, "drawdown_frac": None},
        {"timestamp": "2026-07-09T01:00:00+00:00", "total_nav": 99_000.0, "drawdown_frac": None},
    ]
    hist = nav_history(ev, 100_000.0)
    assert abs(hist[-1]["drawdown"] - (99_000.0 / 110_000.0 - 1.0)) < 1e-9


def test_nav_history_degenerate_inputs():
    assert nav_history([], 100_000.0) == []
    assert nav_history([{"timestamp": "2026-07-07T01:00:00+00:00", "total_nav": 1.0}], 0) == []
    assert nav_history([{"timestamp": None, "total_nav": None}], 100_000.0) == []


def test_runtime_identity_unknown_when_sidecar_absent():
    view = runtime_identity_view(None, dashboard_state_path="/opt/itera/runtime/core_v1/state.json")
    assert view.known is False
    assert view.warnings
    assert view.state_path == "/opt/itera/runtime/core_v1/state.json"
    assert runtime_identity_view({}, dashboard_state_path="/x/state.json").known is False


def test_runtime_identity_reports_branch_and_flags_path_mismatch():
    view = runtime_identity_view(
        {
            "git_branch": "gpt/core-v1-paper-runtime",
            "git_commit_short": "abc123def456",
            "git_dirty": False,
            "hostname": "argus-server",
            "state_path": "/opt/itera/runtime/core_v1/state.json",
            "recorded_at": "2026-08-28T12:00:00+00:00",
        },
        dashboard_state_path="/somewhere/else/state.json",
        audit_state_path="/opt/itera/runtime/core_v1/state.json",
    )
    assert view.known is True
    assert view.branch == "gpt/core-v1-paper-runtime"
    assert view.short_sha == "abc123def456"
    assert any("reading" in w for w in view.warnings)


def test_runtime_identity_flags_dirty_tree():
    view = runtime_identity_view(
        {"git_branch": "b", "git_commit_short": "c", "git_dirty": True},
        dashboard_state_path="/x/state.json",
    )
    assert any("dirty" in w.lower() for w in view.warnings)
    assert view.commit_display.endswith("-dirty")


# --------------------------------------------------------------------------- #
# AppTest smoke tests over the real dashboard
# --------------------------------------------------------------------------- #
DASHBOARD = str(Path(__file__).resolve().parent.parent / "scripts" / "core_v1_dashboard.py")


def _healthy_state() -> dict:
    now = datetime.now(UTC).isoformat()
    sleeves = {
        "BTC_4H_trend": {"cash": 15000.0, "qty": 0.0, "cost_basis": 0.0, "avg_entry": None, "realized_pnl": 0.0, "last_price": 60000.0, "last_action": "HOLD", "last_timestamp": now},
        "ETH_1H_trend": {"cash": 10000.0, "qty": 0.0, "cost_basis": 0.0, "avg_entry": None, "realized_pnl": 0.0, "last_price": 3000.0, "last_action": "HOLD", "last_timestamp": now},
        "ETH_4H_trend": {"cash": 10000.0, "qty": 0.0, "cost_basis": 0.0, "avg_entry": None, "realized_pnl": 0.0, "last_price": 3000.0, "last_action": "HOLD", "last_timestamp": now},
        "SPY_1D_equity": {"cash": 17500.0, "qty": 0.0, "cost_basis": 0.0, "avg_entry": None, "realized_pnl": 0.0, "last_price": 500.0, "last_action": "HOLD", "last_timestamp": now},
        "QQQ_1D_equity": {"cash": 27500.0, "qty": 0.0, "cost_basis": 0.0, "avg_entry": None, "realized_pnl": 0.0, "last_price": 450.0, "last_action": "HOLD", "last_timestamp": now},
        "GLD_1D_gold": {"cash": 20000.0, "qty": 0.0, "cost_basis": 0.0, "avg_entry": None, "realized_pnl": 0.0, "last_price": 200.0, "last_action": "HOLD", "last_timestamp": now},
    }
    return {
        "version": "core_v1_paper_runtime_v2",
        "scenario": "selected_core_v1",
        "cycle": 42,
        "capital": 100000.0,
        "last_cycle_at": now,
        "last_total_nav": 100000.0,
        "high_water_nav": 100000.0,
        "drawdown_frac": 0.0,
        "sleeves": sleeves,
        "sleeve_navs": {k: v["cash"] for k, v in sleeves.items()},
        "sleeve_telemetry": {
            k: {"qty": 0.0, "cost_basis": 0.0, "position_value": 0.0, "avg_entry": 0.0, "unrealized_pnl": 0.0, "unrealized_return": 0.0}
            for k in sleeves
        },
        "total_cash": 100000.0,
        "total_position_value": 0.0,
        "total_cost_basis": 0.0,
        "unrealized_pnl": 0.0,
        "open_position_count": 0,
        "realized_pnl": 0.0,
        "realized_fees": 0.0,
        "realized_slippage": 0.0,
    }


def _audit_report(*, ok: bool, age: timedelta, state_path: str = "/opt/itera/runtime/core_v1/state.json") -> dict:
    return {
        "timestamp": (datetime.now(UTC) - age).isoformat(),
        "state_path": state_path,
        "ok": ok,
        "failures": [] if ok else ["BTC_4H_trend: stored bar price disagrees with re-fetched bar", "SPY_1D_equity: newer completed bar expected by now"],
        "rows": [
            {"sleeve": "BTC_4H_trend", "asset": "BTC", "live_drift_pct": 0.012, "bar_price_ok": ok, "bar_completed": True, "position_value_ok": True, "unrealized_ok": True, "avg_entry_ok": True},
        ],
    }


@pytest.fixture
def dash_env(tmp_path, monkeypatch):
    paths = {
        "CORE_V1_STATE_PATH": tmp_path / "state.json",
        "CORE_V1_SIGNALS_LOG": tmp_path / "signals.jsonl",
        "CORE_V1_FILLS_LOG": tmp_path / "fills.jsonl",
        "CORE_V1_MARKET_DATA_LOG": tmp_path / "market_data.jsonl",
        "CORE_V1_AUDIT_REPORT_PATH": tmp_path / "audit_report.json",
        "CORE_V1_RUNTIME_IDENTITY_PATH": tmp_path / "core_v1_runtime_identity.json",
    }
    for k, v in paths.items():
        monkeypatch.setenv(k, str(v))
    return paths


def _render(dash_env):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(DASHBOARD, default_timeout=90)
    at.run()
    assert not at.exception, list(at.exception)
    # Drop the injected <style> block — it names every CSS class as literal
    # text and would match any class-name substring assertion.
    return "\n".join(m.value for m in at.markdown if "<style>" not in m.value)


def _render_blocks(dash_env):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(DASHBOARD, default_timeout=90)
    at.run()
    assert not at.exception, list(at.exception)
    return [m.value for m in at.markdown if "<style>" not in m.value]


def _first_index(blocks, needle):
    return next(i for i, b in enumerate(blocks) if needle in b)


def test_healthy_state_without_audit_never_renders_system_healthy(dash_env):
    dash_env["CORE_V1_STATE_PATH"].write_text(json.dumps(_healthy_state()))
    # no audit_report.json written
    html = _render(dash_env)
    assert "healthy-banner" not in html
    assert "System Healthy" not in html
    assert "UNVERIFIED" in html
    assert "deck-flag" in html


def test_stale_audit_flags_the_command_deck_and_blocks_green_banner(dash_env):
    dash_env["CORE_V1_STATE_PATH"].write_text(json.dumps(_healthy_state()))
    dash_env["CORE_V1_AUDIT_REPORT_PATH"].write_text(json.dumps(_audit_report(ok=True, age=timedelta(days=3))))
    html = _render(dash_env)
    assert "healthy-banner" not in html
    assert "deck-flag" in html
    assert "stale" in html.lower()


def test_failing_audit_surfaces_every_failure(dash_env):
    dash_env["CORE_V1_STATE_PATH"].write_text(json.dumps(_healthy_state()))
    dash_env["CORE_V1_AUDIT_REPORT_PATH"].write_text(json.dumps(_audit_report(ok=False, age=timedelta(minutes=30))))
    html = _render(dash_env)
    assert "attention-banner" in html
    assert "stored bar price disagrees" in html
    assert "newer completed bar expected" in html  # the 2nd failure, not just failures[0]


def test_fresh_passing_audit_renders_green_and_no_deck_flag(dash_env):
    dash_env["CORE_V1_STATE_PATH"].write_text(json.dumps(_healthy_state()))
    dash_env["CORE_V1_AUDIT_REPORT_PATH"].write_text(json.dumps(_audit_report(ok=True, age=timedelta(minutes=20))))
    html = _render(dash_env)
    assert "healthy-banner" in html
    assert "System Healthy" in html
    assert "deck-flag" not in html
    assert "informational context, not a pass/fail check" in html  # item 5 caveat
    # audit passes but the runtime identity sidecar is absent -> the green
    # banner must not imply full confidence
    assert "provenance unverified" in html.lower()


def test_missing_runtime_identity_renders_unknown_provenance_strip(dash_env):
    dash_env["CORE_V1_STATE_PATH"].write_text(json.dumps(_healthy_state()))
    dash_env["CORE_V1_AUDIT_REPORT_PATH"].write_text(json.dumps(_audit_report(ok=True, age=timedelta(minutes=20))))
    html = _render(dash_env)
    assert "identity-strip unknown" in html
    assert "Provenance" in html


def test_runtime_identity_strip_shows_branch_and_commit(dash_env):
    dash_env["CORE_V1_STATE_PATH"].write_text(json.dumps(_healthy_state()))
    dash_env["CORE_V1_RUNTIME_IDENTITY_PATH"].write_text(
        json.dumps(
            {
                "git_branch": "gpt/core-v1-paper-runtime",
                "git_commit_short": "abc123def456",
                "git_dirty": False,
                "hostname": "argus-server",
                "state_path": str(dash_env["CORE_V1_STATE_PATH"]),
                "recorded_at": datetime.now(UTC).isoformat(),
            }
        )
    )
    dash_env["CORE_V1_AUDIT_REPORT_PATH"].write_text(json.dumps(_audit_report(ok=True, age=timedelta(minutes=20))))
    html = _render(dash_env)
    assert "gpt/core-v1-paper-runtime" in html
    assert "abc123def456" in html
    assert "argus-server" in html


def test_compact_health_bar_above_deck_full_grid_below_chart(dash_env):
    """Option B layout: a compact health bar sits directly above the NAV/PnL
    command deck; the full System Health grid moves below the NAV chart."""
    dash_env["CORE_V1_STATE_PATH"].write_text(json.dumps(_healthy_state()))
    dash_env["CORE_V1_AUDIT_REPORT_PATH"].write_text(json.dumps(_audit_report(ok=True, age=timedelta(minutes=20))))
    blocks = _render_blocks(dash_env)

    bar = _first_index(blocks, '"health-bar"')
    deck = _first_index(blocks, "command-deck")
    grid = _first_index(blocks, "health-grid")
    chart = _first_index(blocks, "Equity curve as % return")
    assert bar < deck < chart < grid
    # the bar carries the trust-relevant checks, not the operational trivia
    assert "Runtime Identity" in blocks[bar] and "Price Audit" in blocks[bar]
    assert "Cost & Fees" not in blocks[bar] and "Scheduler" not in blocks[bar]


def test_clean_known_identity_shows_no_loud_strip(dash_env):
    state = _healthy_state()
    dash_env["CORE_V1_STATE_PATH"].write_text(json.dumps(state))
    dash_env["CORE_V1_RUNTIME_IDENTITY_PATH"].write_text(
        json.dumps(
            {
                "git_branch": "main",
                "git_commit_short": "deadbeef0001",
                "git_dirty": False,
                "hostname": "argus-server",
                "state_path": str(dash_env["CORE_V1_STATE_PATH"]),
                "recorded_at": datetime.now(UTC).isoformat(),
            }
        )
    )
    dash_env["CORE_V1_AUDIT_REPORT_PATH"].write_text(
        json.dumps(_audit_report(ok=True, age=timedelta(minutes=20), state_path=str(dash_env["CORE_V1_STATE_PATH"])))
    )
    html = _render(dash_env)
    assert "identity-strip unknown" not in html
    assert "main @ deadbeef0001" in html  # shown in the bar chip + grid tile instead
    assert "Provenance Verified" in html and "provenance unverified" not in html.lower()


def test_nav_section_renders_full_record_with_live_tag(dash_env):
    state = _healthy_state()
    state["started_at"] = "2026-07-07T01:07:23+00:00"
    dash_env["CORE_V1_STATE_PATH"].write_text(json.dumps(state))
    dash_env["CORE_V1_AUDIT_REPORT_PATH"].write_text(json.dumps(_audit_report(ok=True, age=timedelta(minutes=20))))
    lines = [json.dumps(e) for e in _hourly_events(45)]
    dash_env["CORE_V1_SIGNALS_LOG"].write_text("\n".join(lines) + "\n")
    html = _render(dash_env)
    assert "live-pill" in html
    assert "Jul 7, 2026" in html
    assert "% return vs. $100k inception" in html
    assert "No NAV history yet." not in html
    # drawdown caption: current + worst + the pre-registered planning band as text
    assert "planning band" in html and "-26% / -35%" in html
    assert "Drawdown from high-water" in html


def test_dashboard_writes_nothing(dash_env):
    """Read-only guarantee: rendering must not create or mutate any of the
    files the dashboard reads."""
    dash_env["CORE_V1_STATE_PATH"].write_text(json.dumps(_healthy_state()))
    dash_env["CORE_V1_AUDIT_REPORT_PATH"].write_text(json.dumps(_audit_report(ok=True, age=timedelta(minutes=20))))
    before = {k: (v.read_bytes() if v.exists() else None) for k, v in dash_env.items()}
    _render(dash_env)
    after = {k: (v.read_bytes() if v.exists() else None) for k, v in dash_env.items()}
    assert before == after
