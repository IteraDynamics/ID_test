# Council — Core v2 direction, holistically

**Date:** 2026-08-28
**Question:** Itera Dynamics' operator is undecided, holistically, about what to do next regarding
Core v2 — how to prioritize the several in-flight research threads, and whether/when Core v2
should go live in paper.
**Advisors:** 5 · **Reviewers:** 3

---

## Verdict

### 🏆 Best recommendation

Charter the VRP (equity volatility risk premium / SPY-QQQ iron condor) result now, in parallel
with — not instead of — letting Campaign #53's confirmation holdout accumulate untouched. Four
of five advisors converged on this independently, and two of three peer reviewers ranked the
response that operationalized it (separating *clock-blocked* from *hours-blocked* work) as the
strongest single answer. VRP is the most economically material finding of the entire three-week
research window (an order of magnitude above every other candidate) and its remaining blocker —
brokerage options-approval — costs zero research hours to start; every day it sits unsubmitted is
pure lost time. Concretely: today, verify the CDE funding-rate holdout cron logger is actually
running (it silently broke once already) and check/submit the brokerage approval application if
that hasn't happened; this week, draft — but do not freeze — a VRP planning charter. Do not spend
further research hours on Campaign #54 or the unaddressed 4th deficiency (rates/fixed income)
this cycle; there is no idle capacity for either while #53 and VRP are both mid-flight.

**The fork:** one advisor (the Contrarian) dissented sharply — freeze all new campaign activity,
including VRP, and spend the cycle on a pre-mortem of Campaign #54's crash-hedge sizing instead.
All three reviewers flagged this response's biggest weakness: it conflates *starting an
administrative clock* (near-zero cost, asymmetric upside) with *committing research hours or
capital* (real cost) — the brokerage application doesn't compete with letting a holdout accumulate
calendar days. That makes the majority position the better default. But the dissent is not noise:
if "charter VRP" is allowed to drift from *paperwork + starting the clock* into *treating the
existing backtest as already-confirmed and sizing real risk into it*, the Contrarian's concern
becomes exactly right. The deciding condition is discipline in how "charter" is executed, not
whether to do it.

### 🔍 Biggest blind spot

The four advisors recommending "charter VRP now" under-scrutinize whether VRP's own result has
actually been through Itera's own required discovery/confirmation discipline. It hasn't. The
127-cycle options backtest was run against the *full* 12.7-year historical sample — no holdout was
reserved, unlike every campaign that reached a governed decision this session (Campaign #53's
untouched CDE holdout, Campaign #50/51's sealed 2025 holdout). Every closed-null this window
(COT equities, COT gold, cross-sectional momentum) was a result that looked strong on a first
pass and only turned out to be an artifact under adversarial scrutiny or a corrected re-run. VRP
has had extensive robustness sweeps (cost, skew, structure) but has not had an out-of-sample
confirmation stage in the sense Amendment 2 requires elsewhere. Chartering it as a *numbered
campaign with a reserved forward or held-out confirmation sample* — not as an already-validated
result ready to size into a paper account — is the difference between applying the firm's own
standard consistently and quietly relaxing it for the result the operator likes best.

### ⚠️ What everyone missed

None of the five advisors asked who or what is actually deciding Core v2's *composition* — the
weights, correlations, and interactions across its sleeves — as opposed to each sleeve's individual
evidence quality. Campaign #54 was folded into "founding composition" at 15% the moment it closed;
VRP sits outside the founding pair because it doesn't map to the four-deficiency taxonomy; funding
carry's eventual weight has never been discussed. Nobody has run the same kind of adversarial,
can-this-check-fail scrutiny on the *portfolio-level* assembly of Core v2 that individual campaigns
get — correlations between VRP and Core v1's equity trend sleeves in a crash, correlation between
crash_short and funding carry, total moonshot-bucket risk budget across all of it at once. Core v2
is accreting sleeve-by-sleeve, campaign-by-campaign, with no single governed document yet deciding
what the assembled thing is actually supposed to look like or how large it's allowed to get before
any of it goes live.

### ✅ One concrete next step

Today, the operator personally does two ~30-minute checks: (1) confirm the CDE funding-rate
holdout cron job is currently running (`crontab -l` on the droplet, check for a recent log line —
it was silently unscheduled once before and nobody caught it for three days), and (2) check the
status of the brokerage options-approval application and submit it now if it hasn't been. Both
cost research hours measured in minutes, not days, and both are pure calendar-clock accelerants
that nothing else in this plan can substitute for.

---

## The five advisors

### The Contrarian — "What could fail?"

**Position:** Do not charter, staff, or paper-launch anything new right now. Freeze new campaign
starts and spend the next research cycle on two things only: (a) let the funding-carry holdout
accumulate real calendar days untouched, and (b) run a pre-mortem on Campaign #54's hedge sleeve,
because it is the piece most likely to already be silently wrong inside "Core v2" the day it goes
live.

**Reasoning:** #54 is a live liability disguised as a closed campaign — folded into founding
composition on evidence its own adversarial review called plausibly hindsight-fit, with a
monotonic sizing sweep that never peaked; 15% is a number nobody's data actually chose. The 6-point
power margin on #53 is fragile, and the 3-day cron gap that went unnoticed is itself a canary that
monitoring has a blind spot exactly where it matters most. VRP is the trap, not the prize: it's
gated by an external brokerage approval, and it duplicates Core v1's SPY/QQQ crash exposure rather
than diversifying it.

**Sharpest insight:** Every closed-null this window was caught by finding a real bug or artifact
*after* someone believed the result — and #54 has had that same adversarial pass and *still* got
folded in. The bar for "good enough to go live" is lower than the bar the nulls were held to,
because #54 arrived first and has momentum, not because it earned it.

**Confidence:** Medium.

### The First-Principles Thinker — "What problem are we really solving?"

**Position:** Stop treating "map to one of Core v1's four named deficiencies" as the entry ticket
to Core v2. That taxonomy was derived from what Core v1 happens to lack structurally, not from
what a durable, outside-capital-worthy track record actually needs. The strongest, most material
result of the entire window (VRP) sits outside Core v2 because it doesn't check one of the four
boxes, while a thin, hindsight-contaminated crash-hedge is already "founding composition" because
it does. Redefine Core v2 as the best-evidenced, most-material, tradeable-when-cleared return
streams this operator has produced — not a forced quadrant-fill. Charter VRP now.

**Reasoning:** Campaign velocity is being mistaken for progress. The four-deficiency framing
quietly converted "does this fix a taxonomy gap" into the operative selection criterion,
displacing "is this actually strong evidence." Locking a 15%-weighted hedge into founding
composition on a sizing sweep with no visible peak is a placeholder dressed as a decision.

**Sharpest insight:** The taxonomy itself is now actively excluding the best evidence while
including the worst — that's the tell that the process has become the goal.

**Confidence:** Medium.

### The Expansionist — "What upside are we missing?"

**Position:** Charter the VRP campaign this week and treat brokerage approval as the critical-path
item to accelerate, not a passive blocker — while letting Campaign #53's confirmation holdout and
4th-deficiency scoping run unattended in parallel. VRP is 5-10x more economically material than
anything else Core v2 has touched.

**Reasoning:** Materiality dominance changes the prioritization math — $1,869-$11,212/yr on VRP
isn't incremental, it's the difference between a governance exercise and a business. The brokerage
approval is the one blocker the operator can actually compress (calendar-bound holdout
accumulation cannot be rushed; an administrative application can be escalated). VRP not fitting
the four named deficiencies is a governance technicality — Gate 4 governs retuning Core v1, not
chartering a new, unrelated sleeve.

**Sharpest insight:** The operator's attention is being allocated by which campaign happens to be
numbered and in-flight rather than by expected value — and VRP, the biggest number in the entire
record, is currently invisible to that process because it isn't chartered.

**Confidence:** Medium.

### The Outsider — "Does this make sense to someone new?"

**Position:** 22 days after the two-path commitment, the moonshot has zero runtime, zero paper
capital, and its best-supported idea is sitting in a drawer for reasons that have nothing to do
with its quality. The two "founding" campaigns getting the research hours are, on plain reading,
weak. Charter VRP now — the approval-tier wait is a queueing problem, not a research one — and
stop calling #53/#54 "founding" campaigns as if they're proven pillars.

**Reasoning:** "Two paths since 2026-08-06" implies parallel progress; the actual state is one
path frozen-and-running, the other undefined-and-idle. "Blocked at Gate 2" sounds rigorous but the
actual blocker is a brokerage form that should have been submitted the day the backtest cleared.
"Founding campaign" does a lot of unearned rhetorical work for a two-asset carry study at 56% power
and a hedge sleeve whose own review calls its best evidence likely hindsight bias.

**Sharpest insight:** The word "moonshot" is doing damage — it implies boldness and motion, but
three weeks of actual behavior has been narrow, cautious research plus one great idea shelved for
paperwork reasons.

**Confidence:** Medium.

### The Executor — "What would you actually do Monday morning?"

**Position:** Monday morning, do exactly one thing yourself: charter the VRP result as a numbered
campaign (2-3 hours — the analysis is done, this is paperwork) and open/escalate the brokerage
approval application if that isn't already the top priority. Everything else this week is a
five-minute cron/calendar check, not research hours: confirm the CDE holdout logger is actually
running, and do nothing else to Campaign #53 until it has accumulated meaningfully more data. The
4th deficiency does not start this month — no idle capacity.

**Reasoning:** Distinguish clock-blocked from hours-blocked: both funding-carry confirmation and
VRP approval progress on wall-clock time the operator doesn't control, so the only lever is
starting them earlier, not working them harder. VRP is chartering-ready today with zero additional
research needed. Don't let "current numbered campaign" status create false urgency for #53 — a
near-empty holdout cannot be rushed by attention.

**Sharpest insight:** The real Monday-morning bottleneck isn't research hours at all — it's
whether the brokerage application has actually been submitted yet, which is unstated in the
record and is itself the first thing to check.

**Confidence:** Medium.

---

## Peer review (anonymized)

| Reviewer | Strongest | Biggest blind spot | What all 5 missed |
|---|---|---|---|
| 1 | C (Executor) — cleanly separates clock-blocked from hours-blocked work, turns it into a concrete task list, and is honest about the one fact (is the application submitted?) that would flip its own call. | B (Contrarian) — conflates "don't rush VRP into live capital" with "don't even start the brokerage clock," which costs zero research hours and forecloses nothing. | Whether VRP itself has an unstated power number or will need its own live confirmation holdout once chartered — it could hit the exact same "empty holdout" wall #53 just hit, and nobody flagged that. |
| 2 | C (Executor) — same reasoning; also the only advisor to price solo-operator capacity explicitly (a real reason not to start the 4th deficiency now). | B (Contrarian) — same conflation: lumps "submit a form" in with "commit research hours," needlessly burning calendar time on the one truly free action available. | Whether Core v2's *composition* itself (which sleeves, what weights, how they interact) is being deliberately governed at all, versus accreting ad hoc campaign-by-campaign with no document owning that decision. |
| 3 | E (Expansionist) — the only response that directly resolves the tension the others merely gesture at: Gate 4's "named deficiency" requirement governs *retuning Core v1*, not chartering an unrelated new sleeve, so VRP can be chartered without touching the frozen taxonomy. | B (Contrarian) — same conflation as above, driving its costliest recommendation (sitting on the one clearly cheap, clock-sensitive move available). | Whether "charter VRP now" is even procedurally legal under the firm's own gate sequencing — tradeability is a kill-gate that precedes specification, and VRP is explicitly still pending that gate. |

**Tally:** Strongest — Executor (C): 2 votes, Expansionist (E): 1 vote. Biggest blind spot —
Contrarian (B): unanimous, 3/3.

---

*Generated by the Claude Council skill — disagreement is the signal.*
