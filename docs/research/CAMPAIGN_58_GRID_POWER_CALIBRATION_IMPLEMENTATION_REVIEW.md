# Campaign #58 Grid Power Calibration — Independent Implementation Review

## Status

Independent statistical implementation review of the post-hoc duplication concern raised in
`docs/research/CAMPAIGN_58_PHASE1_FROZEN_STATISTICAL_SPECIFICATION.md` §15, run as a genuinely
separate subagent context with no visibility into any preference for the outcome — the reviewer
was not told, and could not infer from its brief, whether Itera staff or the CEO wanted this to
land as a confirmed defect or a validated result. Per the CEO's explicit instruction, this
question was treated as potentially outcome-motivated (it was raised only after seeing a FAIL)
and was not accepted or dismissed on staff's own say-so.

**Verdict: `ORIGINAL_POWER_FAIL_VALID`.**

## What was asked

Does `scripts/run_campaign58_grid_power_analysis.py`'s approximation — residualized
feature-variant columns reuse their raw counterpart's exact real values, since true walk-forward
residualization is not yet implemented — materially distort the 45.8% grid-level power result
(§15), such that it cannot be treated as final? Seven specific sub-questions were posed; all were
required to be answered with evidence, not assumption, and the reviewer was explicitly instructed
to reject the defect hypothesis plainly if its own experiment did not support it.

## What the review found

**Q1 — are the entries really exact duplicates?** Yes, confirmed by direct code inspection of
`build_144_hypotheses`: the `raw` and `residualized_approx` variants of a given base feature
re-read the identical pooled column for both `candidate` and `target`, byte-identical values, not
merely correlated ones. One nuance the review surfaced: the two duplicate hypotheses still draw
*independent* block-bootstrap resamples per simulation step (different random draws from the same
finite population), so they are not literally re-tested on identical resampled values — this
distinction turned out to matter.

**Q2 — empirical test, not assumption.** The reviewer built a synthetic 16-hypothesis experiment,
importing this repo's own real simulator primitives (`grouped_block_bootstrap_resample`,
`inject_ic`, `benjamini_hochberg`, `build_null_reference`, `draw_independent_pair`) unmodified —
comparing a **duplicate-filler condition** (exact copies, mirroring the real script) against a
**matched-but-distinct control condition** (independently-drawn synthetic series with the same
marginal distribution and autocorrelation, but not literal copies), across 8 seeds, same central
IC (0.065), same FDR (q=0.10). Result: **paired mean power difference = 0.0000 ± 0.0009** — three
of eight seeds showed zero difference at all. A positive control confirmed the harness is not
simply insensitive to family composition generally: going from an 8-hypothesis family to a
16-hypothesis family (real size increase, not duplication) produced a real, consistent ~32%
relative power drop across all 8 seeds — exactly the family-size mechanism this fund's own power
methodology has relied on since Campaign #53. Duplication specifically, isolated from family size,
showed no effect.

**Q3 — what duplication does and doesn't distort.** Grounded in Q2: null distributions,
rejection thresholds, injected-effect power, and average family power are unaffected by
duplication as such — the suppression mechanism is family size `N=144` (correct and faithful to
the real frozen grid in both the real design and this calibration), not filler identity. BH-FDR
as coded here doesn't discount for inter-hypothesis correlation, so it treats duplicate and
distinct fillers identically toward `N`. The only place dependence could matter — variance of
false-rejection counts within a single resample — doesn't affect the *average* power over
thousands of resamples, which is what produced the 45.8% headline.

**Q4/Q5 — is a more faithful calibration identifiable without touching real data?** Yes: a
block-bootstrap-resampled (rather than byte-identical) filler is identifiable today from data
already available in the calibration, without computing any real residualized value and without
touching any frozen design constant. Q2's own result means this correction would not be expected
to move the 45.8% headline in any predictable direction, since no bias from duplication was
measured in the first place.

**Q6 — valid, invalid, or indeterminate?** **Valid, and if anything conservative.** The specific
mechanism §15 raised produced a measured effect indistinguishable from zero. The *original,
non-post-hoc* reasoning already in the script's own docstring — that reusing raw values for a
residualized stand-in is more likely to understate than overstate real residualized power, since
residualization typically narrows rather than widens autocorrelation — stands untouched and
points the same direction.

**Q7 — repair or post-hoc redesign?** The concern fails this test on two independent grounds: (1)
it is self-reportedly post-hoc — §15's own text states the duplication effect was noticed "only
after seeing this FAIL," despite the duplication itself being visible in the code before the run
was ever executed; (2) even granted full consideration, it does not hold up empirically. A
correction pursued now would not be repairing a described, direction-independent defect — there
is no demonstrated defect — it would be redesigning a calibration input after an unfavorable
result, the exact pattern this campaign's own discipline exists to prevent.

## Disposition (per the CEO's required output for this verdict)

**The 45.8% overall average power (Family R 54.9%, Family M 41.8%, Family V 40.6%) is recorded as
binding.** No rerun of the grid power calibration is warranted. The raw/residualized-duplication
concern is recorded as considered and independently rejected, not left open.

**Recommended governed disposition, put to the CEO for sign-off, not decided here:** close
Campaign #58 Phase 1's time-series track as underpowered at its frozen central IC and full
144-candidate scope — consistent with how this fund has closed other underpowered designs (the
original two-market COT design, closed at the power gate before its cross-sectional remedy).
This does not close Campaign #58 as a whole: Phase 0 (cross-sectional COT census) remains a
separate, still-open track, currently blocked on data/network access rather than closed on a
power result.

No repo file, governance document, or specification was modified by the independent review
itself — this document and the governance updates that follow it are staff's own action, taken
after and in response to the review's verdict.
