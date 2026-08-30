# Core v2 Risk Framework — Tier 2 (Per-Pod Risk Parameters) — DRAFT v2

## Status

**Draft, revised after independent review.** Round 1 was reviewed in parallel by Ops/Compliance,
CIO, and Red Team — all three found real, non-overlapping problems, summarized in each section
below rather than glossed over. This version fixes what's fixable now; three items are named as
still open at the end, honestly, rather than papered over to look finished. Not frozen, pending
CEO sign-off.

## Purpose, and how this differs from the degradation bands

`docs/ITERA_DESTINATION_CHARTER.md`'s pod degradation bands (2026-08-30) ask **"is this pod's
edge still real?"** Tier 2 asks **"how much can this pod risk, independent of whether it's
currently working?"** A pod can be within its degradation band and still need a hard leverage cap,
because a single tail cycle can hurt the fund regardless of the long-run thesis. A pod needs both
documents; neither replaces the other.

## 1. Moonshot-bucket-level methodology — frozen now, only its numeric inputs wait

**Round 1 deferred the whole methodology, not just the number, reasoning that no second pod is
live yet to calibrate against. Red Team correctly rejected that reasoning:** the *formula* for how
pod-level risk aggregates is a policy choice independent of which pod is second or what its
numbers turn out to be. Deferring the formula itself means it would get written under time
pressure the moment a second pod is ready to fund — the same "spec frozen the same session it's
needed" failure this repo's Amendment 3 already exists to prevent, one level up.

**CIO separately found the original formula was already wrong**, not just prematurely deferred: it
assumed every pod's worst case is "a macro equity/crypto selloff," true for crash-short and VRP
options but not for a rates trend sleeve, whose defining risk is a rate-shock/inflation regime that
may or may not coincide with an equity selloff (2022 delivered both at once; that is not
guaranteed). A methodology built around one shared scenario was retrofitted to the two pods in
hand.

**Frozen methodology, fixing both problems at once:** each pod, at its own Tier 2 filing, must
name its own worst-case stress regime in its own terms (not borrowed from another pod). The
aggregate moonshot-bucket exposure under a **given** regime is the sum, across every live pod, of
that pod's own worst-case loss under that regime, signed by that pod's declared correlation in that
specific regime (see §2.3's revision below — declarations are now regime-conditional, not a single
number). This is computed for every regime any live pod has named, not one presumed universal
scenario. **Only the ceiling this computation is checked against remains deferred**, pending a
second live pod to calibrate a real number rather than guessing one — the formula itself is final
as of this filing and does not get relitigated per pod.

## 2. Per-pod parameter template (revised)

Every pod's Tier 2 filing states:

1. **Notional exposure cap**, as a percentage of Core v2's total notional, computed from the pod's
   actual capital/margin commitment — not just directional notional. For a levered or margined
   instrument, state both the notional exposure and the capital actually committed/at risk (they
   differ; see §3's revision for why this matters).
2. **Position-sizing rule** — stated as one of three shapes, since one shape does not fit every
   pod (CIO's finding): (a) **fixed weight**, no scaling; (b) **contracts/units per a defined-risk
   structure**, sized from a stated risk budget and the structure's own max loss; (c) **weight
   scaled by a graduated or binary signal** (e.g., a trend filter), for which the filing must also
   state the exposure-swing risk — how fast and how far the position can move on a signal flip,
   since for this shape *whipsaw*, not a single tail cycle, is often the dominant risk.
3. **Correlation declaration, regime-conditional.** For each stress regime the pod names (§1), the
   filing states the pod's expected or measured correlation sign against every other live pod and
   against Core v1's own sleeves **in that specific regime**, and names the specific historical
   episode the declaration is grounded in (e.g., "2022, when bonds and equities fell together" for
   a rates sleeve; "2008 and August 2024" for FX carry unwinds) — a declaration with no named
   historical anchor does not satisfy this item. A pod whose correlation sign is genuinely unstable
   across regimes must say so explicitly rather than picking one number, closing the rubber-stamp
   risk CIO flagged.
4. **Leverage source and margin mechanics** — not just "embedded vs. margin-based" but the actual
   capital commitment: initial/maintenance margin if applicable, funding or roll costs if the
   instrument carries them, and whether the venue's own liquidation mechanics could force an exit
   before the pod's own logic would (see §3).
5. **The filing is git-committed at filing time**, same discipline as the degradation bands' own
   funding-gate mechanism, so a correlation or sizing declaration cannot be revised after the fact
   without a dated, visible append.

## 3. Filled in for the two existing pods (revised)

**`crash_short_v6`** (live, 15% Core v2 weight, Campaign #54):
- Notional exposure: 7.5% of Core v2 notional (15% weight × coded `ENTRY_EXPOSURE = 0.50`) when
  the gate is active, 0% otherwise. **Capital/margin commitment is a materially different, larger
  number, not yet verified against the live account** — Ops/Compliance flagged that CDE futures
  margin is typically 10-20%+ of notional for a retail account, meaning the true capital tied up
  when the gate fires is plausibly 15-30% of Core v2 capital, not 7.5%. **This must be confirmed
  against the actual CDE margin schedule before the notional figure above is treated as the
  binding constraint** — flagged here as unverified, not silently assumed correct.
- **Roll and liquidation mechanics, previously missing entirely.** CDE's crypto contracts are
  dated futures (this fund's own prior research: `BIP-20DEC30-CDE` is "BTC PERP" in name but a
  long-dated future in mechanics), not a continuously-funded perpetual — so there is no ongoing
  funding drag while short, but there is a roll date and a basis at roll that this document does
  not yet quantify. Separately, exchange maintenance-margin auto-liquidation can trigger before
  `crash_short_v6`'s own coded exit logic would, at a retail account with no negotiated terms —
  the pod's own backtested worst case does not model this, because the backtest has no margin
  mechanics at all. Both are named as open verification items, not resolved here.
- Position-sizing rule: (a) fixed weight, zero perturbation, matching Campaign #54's frozen
  specification.
- Correlation declaration (regime-conditional): under "confirmed macro bear, all seven gates
  fired" (the only regime this pod names), expected negative correlation with Core v1's SPY/QQQ
  trend sleeves — grounded in 2018 and 2022, the pod's own two payoff episodes. Measured live via
  the degradation band's own T4 trigger.

**VRP options sleeve** (not live, pending brokerage approval):
- Notional exposure cap: still a CEO decision, not a staff one. Staff recommendation unchanged at
  2% risk budget (~4 contracts/cycle), given zero live fill-quality confirmation exists.
- **The $553/contract figure is the structure's max theoretical loss, not confirmed buying-power
  reduction** — Ops/Compliance's finding. At a real broker, BPR for a defined-risk spread is
  usually close to this if the account is approved for spread margining, but (a) approval tier is
  not yet confirmed, and (b) 4-leg entry is not atomic — a partial fill mid-construction can spike
  margin requirements before all legs are on. **This sizing formula is provisional until the first
  live cycle confirms actual BPR against the real account** — stated here as a condition of going
  live, not assumed away.
- Position-sizing rule: (b) contracts per cycle = floor(risk_budget_dollars ÷ confirmed BPR per
  contract), recalculated each cycle — BPR, not the theoretical $553, once real data exists.
- Correlation declaration (regime-conditional): under "equity-crash scenario" (the only regime
  this pod names), expected positive correlation with Core v1's equity trend sleeves — grounded in
  the 2020-02-12 COVID cycle, already flagged as a concentration risk in the campaign record.

**The crash-short / VRP "natural hedge" finding, with an explicit constraint Red Team required:**
`crash_short_v6` is expected to profit under exactly the regime where the VRP options sleeve is
expected to lose. This is a real, useful observation from reading both filings together — and it
is **not yet measured**. Per Red Team's finding, a named, plausible hedge story is psychologically
sticky enough to become the operative assumption before it's confirmed. **This finding may not be
cited to increase either pod's notional exposure cap or risk budget until both pods have live data
confirming the correlation sign in a real shared-regime observation.** Until then, size each pod
as if the other did not exist.

**Capital siloing, a real constraint not previously named (Ops/Compliance):** the two pods sit in
unlinked accounts (CDE, and a separate equity-options broker) with no cross-margining. Even a
confirmed natural hedge does not free up capital the way it would at a real prime broker — it
reduces portfolio-level *risk*, not per-account *margin requirements*. Do not size either pod
assuming capital efficiency from the other's existence.

## 4. Correlation limit across pods (revised, with an actual enforcement mechanism)

**Rule:** for any stress regime named by two or more live pods, if their declared or measured
correlation in that regime is positive and exceeds +0.5, their combined exposure under that regime
(per §1's formula) may not exceed a stated ceiling without a CEO-approved exception.

**What was missing in round 1, per Red Team, and is fixed now:** a numeric threshold with no
process behind it is not a control. This rule now carries the same mechanism already proven on the
degradation bands: a breach forces a **default action — halve the smaller pod's exposure within 5
trading days** — unless the operator files a dated, written override; **a second consecutive
breach of the same pair/regime executes the default action with no override available.** The
correlation figure feeding this check is the one git-committed at each pod's own filing time
(§2.5) — not a number recomputed informally at the moment someone wants an exception.

**Closing the one-way ratchet Red Team identified:** checking each new pod only against the
current set, forever, lets several pairwise-compliant pods jointly exceed any sane ceiling. Fix:
in addition to the per-new-pod pairwise check, **the full live-pod correlation matrix is
recomputed every quarter**, regardless of whether a new pod was added, and any regime where the
*aggregate* (not just pairwise) positively-correlated exposure exceeds the ceiling triggers the
same default action against the most recently added contributing pod, not an arbitrary one.

## 5. The cross-account monitoring mechanism, named rather than assumed (Ops/Compliance)

There is no OMS and no real-time cross-venue aggregation, and pretending otherwise would make
every number in this document paper-only. **Named mechanism:** the operator runs a reconciliation
check — manual or scripted — pulling both accounts' current exposure at each pod's own monitoring
cadence (mirroring the degradation bands' own monthly/immediate split), and that reconciliation is
what §4's checks and the quarterly recompute in §4 actually run against. This is not a real-time
control and is stated as such: **exposure caps in this document are checked at each reconciliation
point, not continuously enforced.** A breach between reconciliation points is caught at the next
one, not prevented in real time — an honest limitation for a one-person shop, not a gap to hide.

## 6. Process for adding a new pod

Before any pipeline idea (rates/duration sleeve, FX carry basket, broadened crypto trend basket)
or any future pod may hold live risk, it files both a degradation band and a Tier 2 declaration
using the revised template in §2 — including a regime-conditional correlation declaration, grounded
in a named historical episode, against every pod live at that time. New pods update the correlation
picture for the existing set; per §4's quarterly recompute, the full set is also periodically
re-checked in aggregate, not just pairwise at each new pod's launch.

## Still open — named, not resolved by this revision

1. **The aggregate moonshot-bucket ceiling itself** (a number, not the formula) — still waits for a
   second live pod, per the original reasoning, which review did not overturn.
2. **`crash_short_v6`'s real margin/roll/liquidation figures** — Ops/Compliance's finding requires
   pulling CDE's actual margin schedule, not something this document can resolve without that data.
3. **The VRP sleeve's real buying-power reduction** — requires a live account and at least one real
   cycle; cannot be confirmed on paper.

## Authorization boundary

This document authorizes nothing by itself. It does not change `crash_short_v6`'s coded weight,
set the VRP sleeve's risk budget (a named CEO decision), or authorize any new pod.
