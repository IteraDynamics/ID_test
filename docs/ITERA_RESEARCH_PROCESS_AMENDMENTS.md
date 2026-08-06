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
