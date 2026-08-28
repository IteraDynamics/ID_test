#!/usr/bin/env python
"""Pure health / trust derivations for the Core v1 mission-control dashboard.

Extracted from ``scripts/core_v1_dashboard.py`` so the load-bearing "can I
trust the numbers on this page" logic is stdlib-only, side-effect-free, and
directly unit-testable. The dashboard module itself runs Streamlit at import
time and cannot be imported in a test; this module can.

Read-only by construction: nothing here opens a file, writes state, or
touches a network. It transforms already-parsed dicts into render decisions.

Phase 0 of ``docs/engineering/CORE_V1_DASHBOARD_REDESIGN.md``:

* items 2/3/4 — audit status must gate the NAV/PnL deck; an unavailable or
  stale audit must never read as "healthy" (:func:`derive_audit_trust`);
* item 5 — the "largest drift" figure is informational, not pass/fail
  (:data:`LARGEST_DRIFT_CAVEAT`);
* item 6 — the *full* audit failure list surfaces, not just ``failures[0]``
  (:func:`audit_failure_lines`);
* item 1 — the dashboard shows which git branch / commit / host produced the
  ``state.json`` it is rendering (:func:`runtime_identity_view`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


def _same_path(a: str | None, b: str | None) -> bool:
    """True when two path strings point at the same location, tolerating
    ``.resolve()`` vs. raw, trailing slashes, and ``..`` segments. Missing
    values never compare equal (an unknown path is not a match)."""
    if not a or not b:
        return False
    return os.path.normpath(os.path.realpath(a)) == os.path.normpath(os.path.realpath(b))

# Phase 0 item 5. "Largest drift" is the live tick's move away from each
# sleeve's last completed bar — it is expected to be nonzero on every run and
# is not a comparison the audit passes or fails. Pass/fail comes from
# bar_price_ok (stored bar price vs an independently reconstructed completed
# bar). This caveat must render in the UI, not just live in a code comment.
LARGEST_DRIFT_CAVEAT = (
    "Live tick vs. each sleeve's last completed bar — informational context, "
    "not a pass/fail check."
)


@dataclass(frozen=True)
class AuditTrust:
    """How much the NAV / P&L numbers rendered on the page can be trusted,
    derived purely from the independent price-audit status.

    ``numbers_trustworthy`` is the single bit every caller keys on: it is
    ``True`` only when an independent audit actually ran, recently, and
    passed. "No audit report" and "stale audit report" both read as
    ``False`` — not as a silent pass.
    """

    level: str  # "verified" | "unverified" | "stale" | "failing"
    numbers_trustworthy: bool
    healthy_banner_eligible: bool
    label: str  # short badge text, e.g. "PRICING UNVERIFIED"
    css: str  # one of the dashboard badge classes: ok | warn | unverified | err
    headline: str  # banner headline
    detail: str  # one-line explanation for the banner / deck flag
    deck_flag: str | None  # ribbon text on the command deck, or None when clean


def derive_audit_trust(
    *,
    audit_available: bool,
    audit_ok: bool | None,
    audit_stale: bool,
) -> AuditTrust:
    """Map the three audit-status inputs to a single trust verdict.

    * ``audit_available`` — an ``audit_report.json`` was found and parsed.
    * ``audit_ok`` — the audit's own ``ok`` flag (``None`` when unavailable).
    * ``audit_stale`` — the audit ran, but too long ago to still vouch for
      the current state.

    The ordering matters: a *failing* audit is worse than a *stale* one,
    and a stale-and-failing audit is reported as failing.
    """
    if audit_available and audit_ok is False:
        return AuditTrust(
            level="failing",
            numbers_trustworthy=False,
            healthy_banner_eligible=False,
            label="PRICING FAILED",
            css="err",
            headline="Attention Required",
            detail=(
                "Independent price/accounting audit is FAILING — every NAV "
                "and P&L figure on this page is unverified until it passes."
            ),
            deck_flag="NUMBERS UNVERIFIED — price audit is failing",
        )
    if not audit_available:
        return AuditTrust(
            level="unverified",
            numbers_trustworthy=False,
            healthy_banner_eligible=False,
            label="PRICING UNVERIFIED",
            css="unverified",
            headline="Numbers Unverified",
            detail=(
                "No independent price audit has run against this state. The "
                "NAV and P&L below are the runtime's own numbers, "
                "un-cross-checked."
            ),
            deck_flag="NUMBERS UNVERIFIED — no independent price audit has run",
        )
    if audit_stale:
        return AuditTrust(
            level="stale",
            numbers_trustworthy=False,
            healthy_banner_eligible=False,
            label="PRICING STALE",
            css="warn",
            headline="Numbers Unverified",
            detail=(
                "The last independent price audit is too old to vouch for "
                "the current state — treat the NAV and P&L below as "
                "unverified until it re-runs."
            ),
            deck_flag="NUMBERS UNVERIFIED — last price audit is stale",
        )
    return AuditTrust(
        level="verified",
        numbers_trustworthy=True,
        healthy_banner_eligible=True,
        label="PRICING VERIFIED",
        css="ok",
        headline="System Healthy",
        detail="Independent price audit passed against the current state.",
        deck_flag=None,
    )


def audit_failure_lines(audit_report: dict[str, Any] | None) -> list[str]:
    """Every failure string in the audit report, de-duplicated, order kept.

    Phase 0 item 6: the current dashboard shows only ``failures[0]`` in both
    the issues banner and the Price Audit health card, silently hiding the
    2nd..Nth failure.
    """
    if not audit_report:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in audit_report.get("failures", []) or []:
        text = str(raw).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def nav_history(events: list[dict[str, Any]], baseline: float) -> list[dict[str, Any]]:
    """Daily since-inception NAV / drawdown / return series from the raw
    per-cycle signal events. Pure and stdlib-only so it is directly testable.

    Staff review of the "Portfolio NAV" section (2026-08-28): the chart must
    show the *full* record daily-resampled, not a truncated hourly window,
    and framed as % return vs. the $100k inception baseline. Each output row:
    ``date`` (YYYY-MM-DD), ``timestamp`` (last cycle of the day), ``nav``
    (day's last), ``drawdown`` (day's worst), ``ret`` (nav/baseline - 1).
    """
    if baseline <= 0:
        return []
    rows: list[tuple[str, float, float | None]] = []
    for e in events:
        ts = e.get("timestamp")
        raw_nav = e.get("total_nav")
        if not ts or raw_nav is None:
            continue
        try:
            nav = float(raw_nav)
        except (TypeError, ValueError):
            continue
        raw_dd = e.get("drawdown_frac")
        try:
            dd = float(raw_dd) if raw_dd is not None else None
        except (TypeError, ValueError):
            dd = None
        rows.append((str(ts), nav, dd))
    if not rows:
        return []
    rows.sort(key=lambda r: r[0])

    peak: float | None = None
    days: dict[str, dict[str, Any]] = {}
    for ts, nav, dd in rows:
        peak = nav if peak is None else max(peak, nav)
        drawdown = dd if dd is not None else nav / peak - 1.0
        day = ts[:10]
        existing = days.get(day)
        if existing is None:
            days[day] = {"date": day, "timestamp": ts, "nav": nav, "drawdown": drawdown}
        else:
            existing["timestamp"] = ts  # rows are sorted, so this is the day's last
            existing["nav"] = nav
            existing["drawdown"] = min(existing["drawdown"], drawdown)

    out = [days[k] for k in sorted(days)]
    for d in out:
        d["ret"] = d["nav"] / baseline - 1.0
    return out


@dataclass(frozen=True)
class RuntimeIdentityView:
    """Which codebase produced the ``state.json`` being rendered.

    Phase 0 item 1. When ``known`` is ``False`` the runtime that wrote the
    state did not record its identity (e.g. it predates this sidecar, or a
    different deployment is writing the file) — that gap is itself the
    signal the redesign exists to surface, so it renders as a warning, not
    as blank space.
    """

    known: bool
    branch: str | None = None
    short_sha: str | None = None
    dirty: bool | None = None
    hostname: str | None = None
    state_path: str | None = None
    recorded_at: str | None = None
    entrypoint: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def commit_display(self) -> str:
        if not self.short_sha:
            return "unknown"
        return f"{self.short_sha}{'-dirty' if self.dirty else ''}"


def runtime_identity_view(
    identity: dict[str, Any] | None,
    *,
    dashboard_state_path: str,
    audit_state_path: str | None = None,
) -> RuntimeIdentityView:
    """Build the header identity strip from the runtime's identity sidecar
    (``core_v1_runtime_identity.json``, or a legacy ``state['runtime_identity']``
    block).

    ``dashboard_state_path`` is the path the dashboard *read* — cross-checked
    against the path the runtime *says* it wrote, since a mismatch means the
    dashboard is pointed at a different file than the one being described.
    ``audit_state_path`` (from ``audit_report.json``), when present, is
    checked the same way.
    """
    ident = identity or {}
    if not ident:
        return RuntimeIdentityView(
            known=False,
            state_path=dashboard_state_path,
            warnings=[
                "Runtime did not record its git branch / commit — the "
                "provenance of these numbers is unknown."
            ],
        )

    warnings: list[str] = []
    reported_path = ident.get("state_path")
    if reported_path and not _same_path(reported_path, dashboard_state_path):
        warnings.append(
            f"Dashboard is reading {dashboard_state_path}, but the runtime "
            f"reports writing {reported_path}."
        )
    if audit_state_path and reported_path and not _same_path(audit_state_path, reported_path):
        warnings.append(
            f"Price audit ran against {audit_state_path}, not the runtime's "
            f"{reported_path}."
        )
    if not ident.get("git_branch") or not ident.get("git_commit_short"):
        warnings.append("Runtime recorded a partial identity (missing branch or commit).")
    if ident.get("git_dirty"):
        warnings.append("Runtime was started from a dirty working tree.")

    return RuntimeIdentityView(
        known=True,
        branch=ident.get("git_branch"),
        short_sha=ident.get("git_commit_short"),
        dirty=bool(ident.get("git_dirty")) if ident.get("git_dirty") is not None else None,
        hostname=ident.get("hostname"),
        state_path=reported_path or dashboard_state_path,
        recorded_at=ident.get("recorded_at") or ident.get("process_started_at"),
        entrypoint=ident.get("runtime_entrypoint"),
        warnings=warnings,
    )
