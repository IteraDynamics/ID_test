# Itera Dynamics — CEO Decision Log

_Append-only. Every escalation and its resolution goes here, even quick
ones — this is what makes "brief me" informative over time._

## [date] — [one-line decision title]
- **Raised by:** [seat]
- **The ask:** [one-line choice presented to CEO]
- **CEO decision:** [what was said, verbatim if short]
- **Follow-up:** [any resulting action, and who owns it]

## 2026-08-28 — "Portfolio NAV" dashboard section: fix now vs. bundle into Phase 2
- **Raised by:** Chief of Staff (synthesizing Performance / CIO / Risk/PM / Red Team design review)
- **The ask:** do the four honesty fixes to the NAV chart now, or hold the whole section and rebuild it as part of Phase 2 item 11 (degradation band + benchmark panel)?
- **CEO decision:** "I agree with the staff, do fixes 1-4 now."
- **Follow-up (done, branch `claude/research-assessment-feedback-4auusg`, not deployed):**
  1. equity curve reframed as % return vs. $100k inception baseline (fill anchored at 0);
  2. full since-inception daily-resampled record instead of the ~33-day hourly window;
  3. drawdown panel on a fixed −40%…+2% scale;
  4. `LIVE · PAPER` tag + inception date on the section.
  Implemented via new pure `nav_history()` in `scripts/core_v1_dashboard_health.py` (7 unit tests).
  Still deferred to Phase 2 item 11 (governed artifacts only): benchmark overlay, Sharpe/Calmar,
  −26%/−35% band as drawn reference lines. Logged separately as a candidate panel, not folded in:
  per-sleeve equity curves.

## 2026-08-28 — deploy the dashboard redesign + reconcile the prod runtime branch
- **Raised by:** Ops/Compliance (the "Needs-CEO item" in `docs/engineering/CORE_V1_DASHBOARD_REDESIGN.md`)
- **The ask:** (1) how to deploy Phase 0 to `dashboard.iteradynamics.com`; (2) the live paper
  runtime + dashboard run from `/opt/itera/app` on `gpt/core-v1-paper-runtime`, a branch nobody
  in this thread reviewed — merge everything to `main` and repoint prod (Option 1), or cherry-pick
  just the 2 commits onto the stale branch (Option 2)?
- **CEO decision:** "option 1" — after staff showed the runtime-behavior delta between the two
  branches is the +64-line identity sidecar and nothing else (frozen `allocation.py` and the
  strategies/regimes are byte-identical; the rest of the 9.9k-line delta is research modules the
  runner never imports).
- **Follow-up (done):**
  - PR #45 merged `claude/research-assessment-feedback-4auusg` → `main` (`298ab63`), CI green.
  - `/opt/itera/app` repointed `gpt/core-v1-paper-runtime` → `main`, fast-forwarded, tree clean.
  - `itera-core-v1-paper.service` restarted 19:37 UTC — one off-cadence cycle 1234 (NAV
    $108,168.09 = cycle 1233, 0 fills), resumes hourly. Sidecar `core_v1_runtime_identity.json`
    now written each cycle (`main @ 298ab63`, not dirty). `state.json` byte-shape unchanged.
  - `itera-core-v1-dashboard.service` restarted onto `main`. Live dashboard shows real provenance.
  - Preview (`itera-dash-preview.service` on :8510, `dashboard-preview.moonwire.app`) torn down.
  - The design doc's "Needs-CEO item" is now marked RESOLVED. Prod tracks the reviewed mainline.
  - Paper record integrity unaffected — parity / shadow-runtime gates prove the sidecar write is
    byte-neutral for `state.json` / `fills.jsonl` / NAV / fill count.
