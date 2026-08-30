# Itera Dynamics — CEO Decision Log

_Append-only. Every escalation and its resolution goes here, even quick
ones — this is what makes "brief me" informative over time._

## [date] — [one-line decision title]
- **Raised by:** [seat]
- **The ask:** [one-line choice presented to CEO]
- **CEO decision:** [what was said, verbatim if short]
- **Follow-up:** [any resulting action, and who owns it]

## 2026-08-30 — pre-registered pod degradation bands (Tier 1 addition)
- **Raised by:** Risk/PM, following a CEO gut-check on why every pod is bound by the same
  governance rules and whether the existing rule set (One Rule + standing research amendments)
  was strong enough as written.
- **The ask:** adopt a standing rule requiring every Core v2 pod to pre-register a live
  expectation and degradation band before going live, closing a gap Core v1 already had covered
  (`CORE_V1_LIVE_EXPECTATION_AND_DEGRADATION_BAND.md`) but no successor pod did.
- **Process:** Risk/PM drafted the rule; Red Team ran two independent adversarial passes (not the
  same context that drafted it). Round 1 found five real defects (no forced consequence on a
  trigger; individually-compliant pods can mask aggregate correlated risk; unenforceable
  self-graded correlation-drift triggers; silent retroactivity defaulting to grandfathering the
  two pods that most needed it; a vacuous seniority clause plus no pacing floor plus no technical
  enforcement). Round 2 verified the revision: 3 of 5 genuinely fixed, 1 correctly scoped as
  unchanged (aggregate risk was never this rule's job — the fix there was to stop the document
  implying it was covered), 1 still broken (correlation-drift), plus 3 new loopholes introduced by
  the fixes themselves (unlimited override use; self-attested funding tie-in with no independent
  ledger; no consequence for a missed backfill deadline). A third round of targeted fixes reused
  existing fund infrastructure (git-commit-before-funding as the ledger, an override cap, treating
  a missed deadline as itself a breach, named-benchmark-at-drafting for correlation triggers)
  rather than inventing new discretionary mechanisms.
- **CEO decision:** "Approved. Proceed."
- **Follow-up (done):** committed as a dated append to `docs/ITERA_DESTINATION_CHARTER.md`
  ("Refinement to the One Rule — pre-registered pod degradation bands (2026-08-30)"). The
  aggregate cross-pod risk cap remains a separate, not-yet-chartered item — explicitly named as
  open in the adopted rule itself, not implied solved by it.
  **Backfill complete, same day:** `docs/research/CORE_V2_CRASH_SHORT_DEGRADATION_BAND.md` and
  `docs/research/CORE_V2_VRP_OPTIONS_DEGRADATION_BAND.md` filed 2026-08-30, both well inside the
  2026-09-29 deadline. Real, quantified triggers grounded in each pod's own campaign record (cost
  breakpoints straight from the VRP campaign's own cost-sensitivity sweep, tail-correlation and
  win-rate thresholds, an operational-integrity trigger for each mirroring Core v1's T4) rather
  than generic placeholders.
  **Correction, same day:** the line above calling the equity-options sleeve "near live" overstates
  its status — it is not live, not chartered as a numbered campaign, and remains blocked on Gate 2
  (brokerage approval); its filing above is prospective, not a backfill. Caught while drafting its
  degradation band; recorded here rather than silently fixed.

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
