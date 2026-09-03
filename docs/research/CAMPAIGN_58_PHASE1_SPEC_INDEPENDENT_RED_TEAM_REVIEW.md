# Campaign #58 Phase 1 Frozen Specification — Independent Red Team Review

## Status

Independent review of `docs/research/CAMPAIGN_58_PHASE1_FROZEN_STATISTICAL_SPECIFICATION.md`,
run as a genuinely separate subagent context with no visibility into the specification's own
drafting rationale, per the itera-staff skill's Red Team independence guardrail — the same
methodology used for the original Campaign #58 planning-charter review and Campaign #57's
long-history confirmation review.

**Verdict: `CONDITIONAL_PASS`, ten binding conditions.** All ten are applied to the frozen
specification in this same transition (`docs/research/CAMPAIGN_58_PHASE1_FROZEN_STATISTICAL_SPECIFICATION.md`,
corrections dated this entry) — see that document's own "Correction — independent Red Team
review" section for exactly what changed in response to each.

## What the review verified directly, not merely accepted on the specification's own claims

- Hyperparameters (spec §8) are byte-identical to the prerequisites result's own table, correctly
  adapted classifier→regressor.
- The leakage canary script was read directly and reproduces its claimed result (0.0064 clean,
  0.6923 leaky).
- The regime-state source (`research/regimes/baseline_engine.py`) was read directly and confirmed
  genuinely causal (`df.iloc[:bar_idx+1]` before any indicator computation).
- Recovery Trust's closure was independently confirmed against the campaign board and closure
  document.
- The 144-candidate grid arithmetic (16 × 3 × 3) is correct, and the R/M/V per-family FDR
  structure was checked against Campaign #48's own frozen specification text and confirmed to
  match.
- The §12c flagged-feature list (3 named features, 54 of 144 candidates) was traced directly to
  the real, committed §11 power numbers — not invented for this document.
- The standing CEO authorization's exclusion of real model-fitting was independently confirmed
  against `ops/decisions.md`'s exact text, verbatim.
- A previously unnoticed artifact was found and used as direct evidence: the smoke-test-scale
  grid power run (`artifacts/campaign58_grid_power_analysis/grid_power_analysis_20260903T152626Z.json`)
  shows 11.9% average power with `min_trials_per_hypothesis: 0` — a real, if tiny and
  uninformative, data point that the specification itself did not reference.

## Findings requiring correction (condensed; full reasoning in the review's own record)

1. **Filename defect** — §13 item 1 cited a nonexistent script filename.
2. **Grid-level power check must cover all three outcome families (R/M/V), not Family R alone**
   — the "R is the hardest, most conservative family" justification conflates whether a true
   effect exists (irrelevant to injected-IC power calibration) with how autocorrelated the
   series are (what actually drives this methodology's power). If forward volatility/magnitude
   targets are as persistent as this fund's own already-measured price-state features are, M/V
   power could be *lower* than R's, not higher — meaning an R-only result could overstate the
   real grid's power rather than lower-bound it.
3. **The §12b.1 material-margin threshold (0.02 absolute R²) is untested and roughly 5× the
   entire effect size the census is calibrated to detect** (central IC 0.065 implies R² ≈
   IC² ≈ 0.0042). No derivation existed for the 0.02 figure; it appeared nowhere in the charter
   or either CEO authorization.
4. **The permutation (§12b.3) and lift-FDR (§12b.2) null constructions did not state whether
   they replicate the full best-of-4-ML/best-of-2-baseline model-selection procedure at each
   resample**, or fix the model choice from the real run — a real, unaddressed source of
   understated null variability if left as a fixed-model comparison.
5. **The "best of 6 models" (§12a) and "best of N" (§12b) selection multiplicity has no stated
   correction beyond the between-candidate FDR** — condition 1's original literal wording
   ("every... model-type combination enumerated") suggests model type should be part of the
   charged grid; the specification instead collapses it into a per-candidate max-statistic
   without stating how that selection's own multiplicity is handled.
6. **The §12c flagged-feature list was not explicitly closed** — nothing barred a future session
   from adding a fourth "underpowered" feature to explain away an inconvenient null.
7. **The "90 clean candidates" claim (§12c) was stated unconditionally**, but its validity
   depends on the still-outstanding grid-level power check (finding 2) confirming those 90
   individually clear 50% power at the *true* 48-candidate-family FDR stringency — not the
   looser 7-candidate base-family numbers already in hand.
8. **The charter's own Risk/PM condition — a realized-correlation-to-Core-NAV check on any
   candidate before it is described as orthogonal, even at the observation-only stage — was
   absent from §12's decision rules entirely**, not deferred explicitly, just dropped.
9. **The grid-power script's resample budget needs an explicit adequacy check** — the smoke test
   produced `min_trials_per_hypothesis: 0` and degenerate 0.0/1.0 per-hypothesis power estimates,
   which would silently misinform the §12c classification if a real run were under-resampled the
   same way.
10. **§5's claim that the raw/residual doubling was "already implied by the charter's original
    design, not invented after seeing the power profile" was stated with more confidence than
    the charter's actual text supports** — the charter describes residualization as a step, not
    unambiguously a parallel raw-vs-residual comparison axis; a narrower reading (residualized
    values only) is equally defensible and was not acknowledged as an alternative.

## What was NOT required to change

The reviewer explicitly did not require re-running any script against real data in this
environment (none is available); explicitly found no evidence of the flagged-list being gamed to
date (sourced correctly, from real committed numbers); explicitly confirmed §13's own honesty
about what remains outstanding (three of its four items independently verified true, the fourth —
this review — now resolved); and explicitly found the discipline embedded in the hyperparameter
freeze, leakage canary, and regime-source restriction to be real rather than merely claimed.
