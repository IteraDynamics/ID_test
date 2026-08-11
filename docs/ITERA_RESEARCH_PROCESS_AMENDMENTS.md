# Itera Research Process Amendments — 2026-08-06

## Purpose

These standing amendments govern all campaigns chartered after 2026-08-06, beginning with
Campaign #53. They correct three structural defects identified in a review of Campaigns #50–#52:
statistical designs with near-zero power, misallocated multiplicity conservatism, and governance
overhead that consumed effort far in excess of the science it governed.

Closed campaigns are unaffected. Nothing here weakens the core discipline: pre-registration,
frozen specifications, untouched holdouts, deterministic replay, and fail-closed behavior all
remain mandatory.

## Amendment 1 — Mandatory power analysis

Every statistical specification must include a **Power** section, frozen with the rest of the
specification, containing:

1. a plausible effect-size grid for the hypothesis family, with written justification (for
   reference, realistic predictive effects in liquid markets are small — e.g. information
   coefficients on the order of 0.02–0.05);
2. a simulation-based estimate of the probability that a true effect of each plausible size
   passes every frozen gate (support gates, sign gates, multiplicity, decision rules) given the
   frozen sample;
3. the resulting power at the central plausible effect size.

**A campaign may not proceed to execution if estimated power at the central plausible effect
size is below 50%.** The remedy is redesign before any outcome is generated — more data, broader
cross-section, fewer gates, or abandonment. Running a knowingly underpowered campaign and
recording its null as evidence is prohibited: an underpowered null is not a research result.

## Amendment 2 — Multiplicity conservatism moves to confirmation

The discovery/confirmation pipeline must not be conservative twice.

- **Discovery stage:** familywise correction (Holm or equivalent) is no longer required.
  Discovery may use false-discovery-rate control (e.g. Benjamini–Hochberg at a pre-registered
  q) or pre-registered top-k ranking. Support and sanity gates remain. Discovery output is a
  shortlist, and discovery-stage results may never be described as confirmed.
- **Confirmation stage:** the untouched holdout carries the strict standard — pre-registered
  decision rules, expected signs, and multiplicity correction across the frozen shortlist only.
- **The holdout must be exercisable.** A pipeline design under which no plausible true effect
  could ever reach the holdout fails Amendment 1 by construction. The holdout exists to be
  used, under its governing GO, not to be permanently sealed by upstream over-conservatism.

Candidate families should be sized to the question: broad families (hundreds of candidates)
under FDR are preferred to narrow hand-picked families under familywise correction, which pays
the multiplicity cost without the search breadth.

## Amendment 3 — One governance document per campaign

Each campaign is governed by **a single living document**,
`docs/research/CAMPAIGN_<N>_<NAME>.md`, built from the standing template below. Sections are
appended and frozen in order (each freeze is a commit; commit hashes provide the lineage that
separate documents previously provided). Auxiliary evidence lives in `artifacts/`, not in
additional prose documents.

Standing template sections:

1. **Charter** — question, mechanism, why not already represented, falsification statement.
2. **Feasibility** — sources, coverage, support inventory.
3. **Frozen specification** — candidates, formulas, intervals, gates, decision rules,
   multiplicity, output schemas.
4. **Power** — per Amendment 1.
5. **Execution evidence** — GO records, run outputs, replay identities, safety flags.
6. **Result** — statuses and numbers, without interpretation.
7. **Closure** — interpretation, boundaries, registry updates, next-question handoff.

Judgment-bound pacing rule: a specification may not be frozen in the same session it is first
drafted; at least one review pass on a later day is required before freeze.

## Authorization boundary

These amendments modify research process only. They authorize no campaign execution, no data
acquisition, and no runtime, portfolio, or production change.

---

## Amendment 4 — Horizon feasibility must precede specification (2026-08-11)

Added after the Jump Risk Engine v0 retirement, which consumed roughly eighteen months of
research and engineering on a candidate whose edge was unreachable on this firm's
infrastructure from the outset.

### The finding that motivates it

Jump Risk's approved mapping produced +1.09pp CAGR at an effective one-bar implementation lag.
The live runtime was measured at ~1.5-1.7 effective bars across 808 cycles. Lag sensitivity
then showed 98% of the edge expires by the second bar, and turns mildly negative thereafter.
The signal was real, validated, cross-asset transferable, and independently confirmed free of
lookahead. None of that mattered: the edge decayed before the decision could be made.

The failure was not statistical and no amount of better modelling could have fixed it.

### The rule

**Every campaign charter must state, before its specification is frozen:**

1. the **expected decay horizon** of the hypothesised effect — how long after the signalling
   event the effect is expected to persist;
2. the **measured runtime cadence** applicable to the data the campaign would use, cited to a
   dated cadence audit rather than assumed;
3. an explicit **feasibility margin**: the decay horizon must exceed the measured cadence by a
   stated factor, with the factor justified.

A campaign whose decay horizon does not comfortably exceed the achievable decision lag **must
not be chartered**, regardless of how promising the underlying hypothesis is. Discovering this
after the research is complete is a preventable waste.

### Current measured cadence

From `artifacts/paper_runtime_cadence_audit` (2026-08-10, 808 cycles):

| Bar size | Median observation lag | In bar periods |
|---|---:|---:|
| 1h | 1.59h | 1.59 |
| 4h | 6.00h | 1.50 |
| 1D | 40.80h | 1.70 |

The runtime operates at approximately **1.5-1.7 bar periods** behind bar close, consistently
across timeframes. This figure must be re-measured, not assumed, whenever it is cited; the
runtime may change.

### Practical consequence

This firm's infrastructure supports **multi-day signals well and sub-daily signals badly**.
Candidate families should be selected accordingly. A hypothesis whose effect persists for days
to weeks loses little to a ~1.5-bar lag; one that expires within hours loses everything.

This is a selection criterion, not merely a caution: it rules out a class of research before
any effort is spent on it.
