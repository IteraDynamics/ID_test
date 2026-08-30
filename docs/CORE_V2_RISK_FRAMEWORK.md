# Core v2 Risk Framework — Tier 2 (Per-Pod Risk Parameters)

## Status

**ADOPTED — 2026-08-30**, after two rounds of independent review (Ops/Compliance, CIO, Red Team)
and CEO sign-off. Round 1 found real, non-overlapping problems, fixed in v2. Round 2 verification
found two convergent structural problems — reconciliation-cadence enforcement being slower than
the single-cycle risk it was meant to bound, and a regime-matching gap letting a pod dodge the
correlation-limit mechanism — each caught independently by two different seats, which is why v3
was a rewrite rather than a wording pass. This is that adopted version.

**Two items in this framework remain explicit, open CEO decisions, not resolved by adoption:**
the VRP options sleeve's actual risk-budget percentage (staff recommendation: 2%, §3) and whether
the quarterly correlation recompute cadence (§4) should be tightened against operator time cost.
Neither blocks anything today — the VRP sleeve isn't live yet, and quarterly is the working
default — but both need a real answer before they become load-bearing.

## Purpose, and how this differs from the degradation bands

`docs/ITERA_DESTINATION_CHARTER.md`'s pod degradation bands ask **"is this pod's edge still
real?"** Tier 2 asks **"how much can this pod risk, independent of whether it's currently
working?"** A pod needs both; neither replaces the other.

## What this framework can and cannot do — stated honestly after round 2

Round 2 found the same defect from two independent directions: Ops/Compliance showed the
reconciliation cadence (monthly/immediate) can only detect a breach *after* it happens; Red Team
showed the enforcement chain's detection latency can exceed the horizon of the tail event it's
meant to catch. Both are right, and no amount of process wording fixes it — **a one-person shop
with no real-time OMS cannot build after-the-fact monitoring that prevents a single acute cycle.**
Pretending otherwise would be the exact false-rigor pattern (a control that reads as more solid
than it is) this fund's Red Team process exists to catch.

Stated plainly, this framework provides two genuinely different kinds of protection, and only one
of them is fast enough for a single bad cycle:

- **Structural / ex-ante protection — the only real defense against a single acute cycle.** A
  defined-risk structure (the VRP sleeve's capped max loss by construction) or a conservative,
  pre-committed position size (crash-short's already-fixed 15%/50%) bounds the damage *before* it
  happens, with no detection required. If a pod has neither, this framework cannot protect it from
  a single bad cycle — full stop.
- **Drift / pattern protection — what reconciliation-cadence monitoring is actually good for.**
  Sustained cost-of-insurance breaches, correlation creep, or ratchet accumulation across multiple
  cycles or quarters. This is what §4's checks and the degradation bands' own triggers are built
  to catch, and they catch it at the speed reconciliation runs, not faster.

**Direct consequence: `crash_short_v6` currently has no defined-risk structure — its only
single-cycle protection is its already-decided fixed sizing, which is why verifying its real
margin commitment (below) is urgent, not a paper cleanup item.**

## 1. Moonshot-bucket-level methodology — frozen, with the regime-matching gap closed

The aggregate formula (per-regime sum of each live pod's declared worst-case loss, signed by
regime-conditional correlation) is frozen; only its numeric ceiling waits for a second live pod.

**Round 2 found the same new gap from two directions.** CIO: a pod can dodge the entire
correlation-limit mechanism by naming an idiosyncratic worst-case regime that never overlaps with
any other pod's named regime — even if both would actually co-lose in some broader, unnamed
scenario. Red Team: nothing says who decides two differently-worded regimes count as "the same
regime" for aggregation — the adjudication problem just moved, it didn't close.

**Fix — an empirical proxy instead of a judgment call, reusing infrastructure this fund already
computes:**

1. **Regime-matching protocol.** Two pods' named regimes are aggregated together only if their
   named historical anchor episodes empirically overlap — specifically, both anchor episodes fall
   within a period where SPY closed below its own 175-day SMA for at least 20 trading days (the
   same macro-bear proxy `crash_short_v6` and Core v1 already use). This is a data check against
   an existing computed series, not a person deciding two English-language descriptions match.
2. **Mandatory common-stress declaration, closing the dodge.** Every pod, regardless of its own
   self-selected worst case, must also declare its expected profit/loss *sign* (not magnitude)
   under this same SPY-175-day-SMA-confirmed-bear proxy. A pod cannot opt out of the
   correlation-limit machinery by naming a narrow, non-overlapping regime — every pod is checked
   against one common, fund-wide yardstick in addition to its own self-named worst case.

## 2. Per-pod parameter template (unchanged from v2, plus item 3's addition)

1. **Notional exposure cap**, computed from actual capital/margin commitment, not directional
   notional alone.
2. **Position-sizing rule** — one of three shapes: (a) fixed weight; (b) contracts/units per a
   defined-risk structure; (c) weight scaled by a graduated/binary signal, which must also state
   its exposure-swing (whipsaw) risk.
3. **Correlation declaration, regime-conditional and now dual:** (i) for each stress regime the
   pod names, its correlation sign against every other live pod and Core v1's sleeves, grounded in
   a named historical episode; **and (ii) its expected sign under the mandatory common
   SPY-175-day-SMA-bear proxy (§1.2), regardless of whether that is the pod's own named worst
   case.**
4. **Leverage source and margin mechanics** — actual capital commitment, funding/roll costs,
   liquidation mechanics.
5. **Git-committed at filing time.**

## 3. Filled in for the two existing pods

**`crash_short_v6`** (live, 15% Core v2 weight):
- Notional exposure: 7.5% of Core v2 notional when the gate is active (15% × coded
  `ENTRY_EXPOSURE = 0.50`).
- **Interim conservative margin assumption, adopted now rather than left open indefinitely — this
  pod is live.** Ops/Compliance's range was 15-30% of Core v2 capital tied up when the gate fires.
  **Working assumption until verified: 30%, the top of the range**, used for all Tier 2 accounting
  (including §1's aggregate formula and §4's correlation-limit checks) until the actual CDE margin
  schedule is pulled and confirmed. **Deadline: 14 days from this filing (shorter than the
  degradation bands' 30-day precedent, because this is live capital, not a paper filing).** A
  missed deadline is treated the same as a missed degradation-band backfill — itself a triggered
  breach forcing the default action in §4.
- Roll/basis and liquidation mechanics: named as open verification items (§3 of v2), unchanged —
  CDE's contracts are dated futures, not continuously-funded perpetuals; exchange auto-liquidation
  could trigger before the pod's own exit logic. No interim number is assumed for these beyond the
  30% margin working figure above, since no reasonable range has been established yet.
- Position-sizing rule: (a) fixed weight, zero perturbation.
- Correlation declaration: under "confirmed macro bear, all seven gates fired," negative
  correlation with Core v1's SPY/QQQ trend sleeves (2018, 2022). Under the mandatory common proxy
  (§1.2): also negative — this pod's own named regime and the common proxy coincide by design,
  since its gate requires SPY confirmation.

**VRP options sleeve** (not live, pending brokerage approval):
- Notional exposure cap: CEO decision. Staff recommendation: 2% risk budget.
- Position-sizing rule: (b) contracts = floor(risk_budget_dollars ÷ confirmed BPR per contract),
  provisional on the first live cycle confirming actual BPR — the $553 theoretical max loss is not
  assumed equal to buying-power reduction.
- Correlation declaration: under "equity-crash scenario" (its own named regime), positive
  correlation with Core v1's equity sleeves (2020-02-12 COVID cycle). Under the mandatory common
  proxy (§1.2): also positive — this pod's own named regime and the common proxy coincide, since
  an equity crash and a confirmed SPY bear are the same kind of event here.

**The natural-hedge finding, with a real confirmation bar this time.** `crash_short_v6` is
expected to profit under exactly the regime where the VRP options sleeve is expected to lose —
both pods' own declarations above agree on this, and now so does the mandatory common-proxy check
in §1.2. This remains a real, useful cross-read. Round 2's finding: the original fence
("a real shared-regime observation," singular) had no defined bar and could be satisfied by one
convenient data point. **Fixed: citing this finding to increase either pod's exposure cap requires
at least 2 independent live regime observations with a consistent correlation sign across both**
— not one. Until two independent observations exist, size each pod as if the other did not exist.

**Capital siloing (unchanged from v2):** unlinked accounts, no cross-margining — a confirmed
hedge reduces portfolio risk, not per-account margin requirements.

## 4. Correlation limit across pods

**Rule:** for any regime matched under §1.1's empirical protocol, if declared/measured correlation
is positive and exceeds +0.5, combined exposure under that regime may not exceed a stated ceiling
without a CEO-approved exception.

**Enforcement (unchanged mechanism, proven on the degradation bands):** a breach forces halving
exposure within 5 trading days unless overridden once with a dated written reason; a second
consecutive breach of the same regime executes with no override.

**Penalty allocation, fixed after Red Team's round-2 finding.** v2's rule halved "the most
recently added contributing pod" — a sequencing tie-breaker with no link to fault, gameable by an
operator who controls both which pod launches last and when a breach is likely. **Fixed: the
default action is applied proportionally across every pod contributing to the regime's
positively-correlated excess, each halved in proportion to its own share of that excess** — not
whichever pod happens to be newest.

**On the ratchet (honest framing after round 2):** the quarterly full-portfolio recompute bounds
how long a jointly-excessive aggregate can run undetected to one quarter — it does not eliminate
the possibility, and round 2 correctly identified this as a real residual gap, not a closed one.
Tightening the recompute cadence below quarterly is a real option but trades directly against
operator time in a one-person shop; **left as an explicit CEO choice, not decided here.**

## 5. The cross-account monitoring mechanism

No OMS, no real-time cross-venue aggregation. Reconciliation — manual or scripted — runs at each
pod's own monitoring cadence and is what §4's checks run against. **Per the honest framing above,
this is drift/pattern protection, not single-cycle protection** — a breach between reconciliation
points is caught at the next one, not prevented.

## 6. Process for adding a new pod

Before any pipeline idea (rates/duration sleeve, FX carry basket, broadened crypto trend basket)
or any future pod may hold live risk, it files both a degradation band and a Tier 2 declaration
per §2 — including both its own named-regime correlation declaration and the mandatory
common-proxy declaration (§1.2), against every pod live at that time. The full set is also
re-checked in aggregate every quarter regardless of new pods (§4).

## Still open — named, not resolved by this revision

1. **The aggregate moonshot-bucket ceiling itself** (a number) — waits for a second live pod.
2. **`crash_short_v6`'s real margin/roll/liquidation figures** — interim 30% working assumption
   adopted above; real figures due within 14 days.
3. **The VRP sleeve's real buying-power reduction** — requires a live account and a real cycle.
4. **Sub-quarterly ratchet risk** — the quarterly recompute bounds but does not eliminate a
   multi-pod correlated buildup; tightening this cadence is left as a CEO choice against operator
   time cost, not decided here.
5. **This framework provides no protection against a single acute cycle for any pod that lacks
   either a defined-risk structure or an already-fixed conservative size** — stated as a structural
   limit of a solo operator with no real-time infrastructure, not something a future revision of
   this document is expected to solve.

## Authorization boundary

This document authorizes nothing by itself. It does not change `crash_short_v6`'s coded weight,
set the VRP sleeve's risk budget (a named CEO decision), authorize any new pod, or set the
quarterly-vs-tighter recompute cadence (also a named CEO decision, §4).
