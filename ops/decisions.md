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
