# Core v2 Risk Framework — Tier 2 (Per-Pod Risk Parameters) — DRAFT

## Status

**Draft, not frozen.** Per this repo's judgment-bound pacing convention (Amendment 3), this is
written today and should not be treated as final until independently reviewed by Ops/Compliance,
CIO, and Red Team, and signed off by the CEO. Authorizes nothing by itself.

## Purpose, and how this differs from the degradation bands

`docs/ITERA_DESTINATION_CHARTER.md`'s pod degradation bands (2026-08-30) ask **"is this pod's
edge still real?"** — statistical/thesis health, checked against pre-registered triggers.

Tier 2 asks a different question: **"how much can this pod risk, independent of whether it's
currently working?"** A pod can be performing exactly within its degradation band and still need
a hard leverage/notional cap, because a single tail cycle can hurt the fund regardless of whether
the long-run thesis is intact. The VRP options sleeve's own worst backtested cycle (-$455 during
the 2020-02-12 COVID vol spike) happened while the edge was, and remains, statistically real —
that is exactly the case this framework exists to bound, separately from degradation monitoring.

This document does not replace or duplicate the degradation bands. A pod needs both.

## 1. Moonshot-bucket-level framework (methodology only — no number set yet)

Per the 2026-08-30 rule's own standing caveat, individual pod compliance does not bound aggregate
moonshot-bucket risk. That gap is **not closed by this draft.** Only one Core v2 pod
(`crash_short_v6`) is actually live; the destination charter's own build-bound/clock-bound
reasoning says the aggregate number should wait for a second real pod to calibrate against
(the VRP options sleeve, once its brokerage account clears, or another pod if chartered first).

What this draft does set: **the methodology** the aggregate cap will use once a second pod is
live — computed as the maximum plausible simultaneous loss across all live pods under a shared
stress scenario (a macro equity/crypto selloff, since that is the scenario every pod examined so
far — crash-short, VRP options, and the FX-carry/rates ideas under consideration — names as its
own worst case), not a simple sum of each pod's individual worst cycle. Simple summation
overstates risk for pods with genuine offsetting correlation (see §3) and understates it for pods
that lose together.

## 2. Per-pod parameter template

Every pod's Tier 2 filing — required before it may hold live risk, same gate as the degradation
band — states:

1. **Notional exposure cap**, stated as a percentage of Core v2's total notional, computed from
   the pod's own position-sizing mechanics (not a portfolio weight alone, which can understate or
   overstate actual market exposure depending on the instrument).
2. **Position-sizing rule** — the formula converting a stated risk budget into an actual position
   size (contracts, notional, weight), so sizing isn't decided ad hoc at funding time.
3. **Correlation declaration** — the pod's stated or measured correlation, and specifically its
   *expected sign during a shared stress scenario*, against every other live Core v2 pod and
   against Core v1's own sleeves. A mechanism-based expectation is acceptable pre-launch; it must
   be replaced with measured correlation once live data exists (same discipline as the
   degradation bands' correlation triggers).
4. **Leverage source** — whether exposure comes from portfolio weight alone, embedded leverage
   (e.g., a short futures position), or margin, stated explicitly rather than left implicit.

## 3. Filled in for the two existing pods

**`crash_short_v6`** (live, 15% Core v2 weight, Campaign #54):
- Notional exposure cap: **7.5% of Core v2 notional** — the pod's own coded `ENTRY_EXPOSURE = 0.50`
  applied to its 15% portfolio weight, active only when the gate fires (0% most of the time). This
  is a *description* of the already-decided sizing, not a new number — any future change to
  `ENTRY_EXPOSURE` or the 15% weight is a Core v2 composition change requiring the existing CEO
  approval gate (per `docs/ITERA_DESTINATION_CHARTER.md`'s escalation matrix), not a Tier 2
  administrative update.
- Position-sizing rule: fixed weight, no scaling by conviction or vol — matches Campaign #54's own
  "exactly as coded, zero perturbation" discipline.
- Correlation declaration: **expected negative correlation with Core v1's SPY/QQQ trend sleeves
  during a confirmed macro bear** (that is the pod's entire purpose) — measured live via the
  degradation band's own T4 trigger.
- Leverage source: embedded (short futures position at CDE), not margin-based beyond the
  position's own notional.

**VRP options sleeve** (not live, pending brokerage approval):
- Notional exposure cap: **not yet set — this is a CEO decision, not a staff one**, since it
  determines contract count and therefore dollar risk. Gate 3's own materiality table gives the
  menu: 2% risk budget ≈ $1,869/yr (1.9% of book) at ~4 contracts/cycle ($553 max risk/contract);
  5% ≈ $5,606/yr (5.6%) at ~9 contracts; 10% ≈ $11,212/yr (11.2%) at ~18 contracts. Staff
  recommendation, not a decision: **2%**, given zero live fill-quality confirmation exists yet and
  the campaign's own pessimistic stress case (0/60 structures significant) means the realistic
  range spans from this materiality table down to zero.
- Position-sizing rule: **contracts per cycle = floor(risk_budget_dollars ÷ $553)**, recalculated
  each cycle against the actual live max-risk-per-contract at the strikes traded (not a fixed
  historical number).
- Correlation declaration: **expected positive correlation with Core v1's equity trend sleeves
  during a shared equity-crash scenario** — already flagged in the campaign record as a
  concentration risk, not a diversification benefit. This is the opposite sign from
  `crash_short_v6` (below).
- Leverage source: none beyond the defined-risk structure's own capped exposure — this is the
  entire point of the structure and the reason `T2` in its degradation band is an immediate,
  no-override trigger.

**A finding from putting these two side by side, not visible from either pod's own document
alone:** `crash_short_v6` is expected to profit during exactly the scenario (a confirmed macro
bear) where the VRP options sleeve is expected to lose. If both are live simultaneously, they are
plausibly **partial natural hedges of each other**, not simply two sources of stacked tail risk —
though this is a mechanism-based expectation, not yet measured, and should not be assumed true
until both pods have live data to check it against (the same discipline the correlation triggers
already require).

## 4. Correlation limit across pods

**Proposed rule:** no two live Core v2 pods' combined notional exposure may exceed a stated
ceiling if their measured (or, pre-launch, mechanism-expected) correlation during a shared stress
scenario is positive and exceeds +0.5, without an explicit CEO-approved exception. A negative or
near-zero expected correlation (as with the crash-short/VRP-options pair above) is not restricted
by this rule — the risk this rule targets is pods that lose together, not pods that happen to
coexist.

## 5. Process for adding a new pod

Before any of the three trade ideas under consideration (rates/duration sleeve, FX carry basket,
broadened crypto trend basket) — or any future pod — may be sized into Core v2, it must file both
a degradation band (existing rule) and a Tier 2 parameter declaration (this framework) using the
template in §2, including its correlation declaration against every pod already live at that time.
This is additive: each new pod updates the correlation picture for all existing pods' records, it
does not require re-litigating pods already sized.

## Open items for independent review, not resolved by this draft

1. Is the 7.5%/15% description of `crash_short_v6` actually complete, or does Ops/Compliance know
   of margin or venue mechanics that make the real notional exposure different from the coded
   `ENTRY_EXPOSURE` figure?
2. Does this framework's per-pod template actually fit the three pipeline ideas (rates, FX carry,
   broadened crypto), or does it implicitly assume position types (weight-based, contract-based)
   that don't generalize?
3. What is gameable, underspecified, or gives false confidence in this draft — the same adversarial
   standard Red Team already applied twice to the degradation-band rule.

## Authorization boundary

This document authorizes nothing by itself. It does not change `crash_short_v6`'s coded weight,
authorize the VRP options sleeve's risk budget (that figure is explicitly left as a CEO decision
above), or authorize any new pod. It is a proposed framework pending the review named above.
