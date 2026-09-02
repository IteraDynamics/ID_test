# Campaign #57 — Independent Red Team Review

**Date:** 2026-09-02

**Status:** THE MANDATORY INDEPENDENT RED TEAM GATE, per `.claude/skills/itera-staff/agents/red-team.md` and the org
charter (`.claude/skills/itera-staff/references/org-charter.md`: *"Red Team pass/fail on a candidate | Red Team, alone
— cannot be overridden by CIO."*). This supersedes
`docs/research/CAMPAIGN_57_INTHREAD_STAFF_REVIEW_20260902.md`, which was explicitly advisory and non-independent.

**Reviewer:** Red Team seat, run as a genuinely independent subagent (separate context from CIO/Quant, separate model
instance) with the charter, both frozen scripts, the authorization/result docs, and git history — but explicitly
withheld the prior in-thread staff review until after it had formed and written its own verdict, so it could not
anchor on the existing interpretation.

## Verdict

**`CONDITIONAL_PASS_TO_VTI_BND_REPLICATION`**

Not an unconditioned pass. The conditions below (Section 6, "Binding conditions") are part of the verdict, not
optional follow-ups.

`FAIL_STOP_CAMPAIGN_57` was explicitly rejected: the reviewer found no defect in the core measurement. The primary
test was proven lookahead-clean via a canary, proven correctly sized via an empirical null-calibration simulation
(Type-I error 5.7% against nominal 5%), genuinely pre-registered (verified from git commit ordering — the runner
freeze commit `1e7942c1dec4b02ce62c49f8fab9f9cf7add2f00` predates the result-recording commit, and the authorization
doc cites that exact hash), adequately powered (the 85.2% central-haircut power figure was independently
bit-for-bit reproduced from the frozen seed and calendar alone, without access to any return data), and passed with
an effect *larger* than the pre-registered 50%-haircut target (observed rho -0.1524 vs. target -0.1243, i.e. 61.3%
of the sandbox discovery ceiling, not 50%).

An unconditioned `PASS` was also rejected: the evidentiary weight of this result, as currently recorded, is
materially overstated, and one of the two justifications Amendment 2 gave for weakening the statistical gate is
demonstrably false at the sample size it was applied to. Both must be corrected on the record — not by re-running or
re-gating anything — before VTI/BND opens.

## Material corrections to the existing record (not re-litigation of the result itself)

These do not change the primary result, the classification, or any frozen parameter. They correct claims made
*about* the result elsewhere in the governance record.

### M1 — The "confirmation" pair overlaps discovery by 57.8% of its months, and the non-overlapping remainder is not independently significant

VFINX tracks the same index SPY tracks (S&P 500); VBMFX tracks the same universe AGG tracks (Bloomberg US
Aggregate). Of the 476 VFINX/VBMFX valid months (1987-01 to 2026-08), 275 (57.8%) are the same calendar months as
the SPY/AGG sandbox discovery sample (2003-10 to 2026-08). Back-solving from the reported era rhos, VFINX/VBMFX over
that overlapping window gives rho ≈ -0.203 against SPY/AGG's -0.249 on the identical calendar — a 0.046 gap
consistent with wrapper/tracking noise, not independent information.

The genuinely new evidence is the pre-2003 extension (n=201 months, 1987-01 to 2000-12 plus stub). Under every
plausible assumption for the unreported 2000-01–2003-09 bridge segment, the implied rho for this genuinely-new
portion, tested alone, does **not** reach one-sided significance (p ranging ~0.06–0.27 depending on the bridge
assumption; only an implausibly large bridge effect of -0.50 would cross p<0.05 alone).

**Correction:** this result should be described as a **long-history consistency check with a weak, non-significant
pre-discovery extension**, not as an independent out-of-sample confirmation. It substantially rules out "the sandbox
result was a 2003–2026 artifact specific to the SPY/AGG ETF wrappers" — a real and worthwhile thing to have ruled
out — but it does not, on its own, independently establish the effect the way the existing record's language
("materially upgrades the sandbox finding," "a different equity/bond proxy pair") implies.

### M2 — Amendment 2's stated reason for replacing the dual co-primary gate with a single primary test is false at n=476

Amendment 2 §4 states the joint (dual co-primary) gate was replaced with a single primary test "solely because the
pre-outcome power study demonstrated that the redundant joint gate made meaningful confirmation impossible with
available history." Independently re-running the frozen joint-gate power machinery
(`scripts/preflight_campaign57_vti_bnd_partitions.py`) at the long-history sample size (n=476, central 50% haircut,
200 simulations) gives **75.5%** power for the dual co-primary gate — far above the 16.2%/18.0% figures that
actually killed the 50/25/25 architecture, and only 4.5 points (roughly 1.5 Monte Carlo standard errors at this
simulation count) short of the 80% floor.

The 16.2%/18.0% failure was overwhelmingly a consequence of the 58-month partition sizes in the abandoned 50/25/25
architecture, not an inherent property of the dual-gate design. Moving to the pooled 476-month sample alone would
have taken the dual gate from ~17% power to ~75.5% — nearly to the floor by itself. The single-primary-test change
was a second, independent adjustment bundled into the same amendment and credited with fixing a problem the sample
size change had already mostly fixed.

**Correction:** the sample-size fix (VFINX/VBMFX in place of the partitioned VTI/BND) was necessary and is
independently justified. The additional gate-weakening (single primary test replacing the dual co-primary
requirement) was not shown to be necessary by the cited evidence, and the record should say so. This is **not**
grounds to reopen or re-gate the already-run primary test — doing so now, after the outcome is known, would be
exactly the after-the-fact retuning this fund's governance forbids. The result stands; the stated rationale for the
architecture that produced it is corrected in place.

### M3 — Three of the five frozen robustness diagnostics could not plausibly have failed

Simulated under the campaign's own frozen alternative hypothesis (true rho = -0.1243, the central haircut target),
on the real 476-month calendar:

- leave-one-year-out all-negative: passes ~99.3% of the time;
- trimmed top-10-absolute-signal rho negative: passes ~99.3% of the time;
- causal tercile-spread sign positive: passes ~100% of the time;
- **every eligible era rho negative (the diagnostic that actually failed, on the 1990s): passes only ~51.5% of the
  time** — close to a coin flip, given the real 36/120/120/120/80 era bucket sizes;
- month-end rho more negative than all three placebos: not independently power-simulated by this review, but
  structurally more informative than the other three.

**Correction:** per this fund's own standing habit ("a check that cannot fail is not evidence"), three of the five
frozen robustness checks should not be read as meaningful confirmatory evidence — they were close to guaranteed to
pass regardless of whether the mechanism is real. The era-consistency check, which did fail (the 1990s), is the one
diagnostic in this set that was genuinely capable of catching a problem, which is exactly why its failure needs the
careful reading below rather than being waved off *or* treated as decisive.

## What the 1990s result means

Neither "harmless regime weakness" (the existing record's framing) nor "a materially unstable/nonpersistent
mechanism." The independent finding is: **a near-uninformative reading, produced in part by a diagnostic that was
not well calibrated for the era bucket sizes involved, sitting inside a five-decade sequence that has no coherent
mechanism story.**

- The era-consistency diagnostic that flagged it had only ~51.5% chance of passing even under a perfectly stable
  true effect at the campaign's own pre-registered target (see M3) — so its failure carries limited information by
  itself.
- A direct 1990s-vs-rest-of-sample test (Fisher z, 1990s rho +0.02865 n=120 vs. the n-weighted remaining 356 months
  at rho -0.2165) gives z=2.331, uncorrected two-sided p=0.0197 — but this era was selected as the worst of five,
  and Bonferroni-adjusting for that selection gives p=0.099. The 1990s' own 95% CI is [-0.151, +0.207], which
  excludes the pooled estimate of -0.1524, but only just.
- The more concerning finding is not the 1990s in isolation but the full era sequence: 1980s -0.3441, 1990s
  +0.0287, 2000s -0.1745, 2010s -0.2987, 2020s -0.0990. The campaign's stated mechanism (growth in mandate-driven
  rebalancing AUM over time — pensions, target-risk and balanced funds) predicts the effect should be weakest early
  and strongest late. The observed sequence is close to the opposite: the 1980s is the strongest era by a wide
  margin, and the 2020s is the second-weakest. No version of the stated mechanism story survives this pattern
  intact. The most honest reading is that era-to-era variation here is dominated by sampling noise around a small,
  real, but not confidently regime-stable effect.

This does not justify stopping the campaign. It also does not support recording the 1990s as "a real regime
weakness the mechanism survived," which flatters the result by implying it passed a test that was, at these bucket
sizes, close to a coin flip. The correct record is: **the era-consistency diagnostic failed on a bucket where it
had limited power to distinguish signal from noise either way; the full era pattern is inconsistent with the
campaign's own stated causal story; and neither observation is fatal to the pooled result.**

## Fatal vs. caveat — explicit

**Fatal (would kill the campaign): none found**, after deliberate adversarial effort across all eleven checklist
items (full findings below).

**Material — corrected on this record, does not require re-running anything:** M1, M2, M3 above.

**Caveats — recorded, campaign proceeds:**
- Placebo windows (-5/-10/-15 sessions before month-end) are not held to a constant signal-window length (18.7 /
  13.7 / 8.7 / 3.7 sessions respectively as offset increases) — the runner's own docstring calling them
  "otherwise-analogous" is not accurate. Two of the three placebos are themselves negative, so month-end specificity
  is a matter of degree that was never itself significance-tested.
- The cutoff close appears in both the signal denominator and the outcome numerator; sized and found implausible as
  a standalone explanation (would require ~0.85% pure pricing noise at the cutoff), and if anything historically
  biases the statistic toward zero/positive in eras with smoothed bond-fund pricing (a plausible partial, unproven,
  explanation for the weak 1990s reading).
- No unit tests exist for the Campaign #57 runner or preflight scripts, unlike Campaigns #50–53, which all shipped
  test files. This is a process regression, not a research finding.
- Economic materiality has never been estimated for this campaign, contrary to standing amendment 5 and this fund's
  own repeated practice. A rough, unverified order-of-magnitude estimate (a ~0.50% low-minus-high spread, roughly a
  third of months, 3-day equity-vs-bond relative exposure, ~12 cycles/yr on ~$100k, before costs) plausibly lands in
  the fund's familiar $400–1,500/yr range, but nobody has actually computed this.
- The single-primary-test power figure (85.2% at the 50% haircut) drops to 69.6% at a 40% haircut — a real but not
  wide margin if the true effect is smaller than pre-registered.

**Inconclusive given this environment — must be closed before VTI/BND opens, not treated as resolved:**
- No raw JSON output or source CSVs exist anywhere reachable in this session (`artifacts/*` and `data/*.csv` are
  gitignored and were never committed; Yahoo Finance, Vanguard, and SEC EDGAR are all blocked by this container's
  network proxy — confirmed via direct test, HTTP 403 on all three). The entire numeric record of this result rests
  on a hand-transcribed markdown summary of a JSON file that no longer exists anywhere this review could reach. The
  power-simulation figures were independently reproduced (they depend only on the calendar); the outcome numbers
  (rho, p, spread, era/LOYO/trim figures) were checked for internal mathematical consistency and found consistent,
  but were **not** independently re-derived from source data and cannot currently be.
- VFINX/VBMFX series continuity through 2026-08 (share-class conversions, potential splices) is asserted but
  unverified and unverifiable in this environment.
- Several JSON fields referenced by the frozen runner (`shared_sessions`, `n_low`, `n_high`, exact source date
  ranges) were never transcribed into the committed result doc and so cannot currently be checked at all.

**Resolved in the campaign's favor, not a concern:** the apparent 66-hex-character SHA-256 digests in the result doc
were checked directly and are exactly 64 hex characters each — valid, not a transcription error. VBMFX's inception
(~1986-12-11) makes 1987-01 the correct, non-suspicious first valid month (the first month with a usable prior-month
anchor), not an arbitrarily chosen favorable start date.

## What VTI/BND must show to be a valid transportability pass, not a rescue

Amendment 2 §6's frozen requirements (rho<0, causal tercile spread>0, no implementation defect, effect size/CI
reported against the long-history estimate and sandbox ceiling) stand unchanged — this review does not modify them.

However, because VTI/BND's own span (~2007-05 to 2026-08) sits entirely inside the VFINX/VBMFX sample against
near-identical underlying assets, a bare sign check is close to vacuous: at n≈232 and an assumed true rho of -0.15,
P(rho<0) ≈ 0.98 even with no real transportability. As a condition of this pass, before VTI/BND is opened:

1. **Pre-register a quantitative expectation band, not just a sign, before the run.** Based on the VFINX/VBMFX era
   rhos for the equivalent window and the measured ~0.046 wrapper-to-wrapper disagreement over the shared SPY/AGG
   vs. VFINX/VBMFX calendar, the expected pass band is **rho ∈ [-0.32, -0.10]**. A result inside that band is a real
   transportability pass. A result far outside it (e.g., near zero or positive) satisfies the letter of "rho<0" but
   should be read as a transportability **failure** — either a data/implementation defect or evidence the effect is
   far more fragile than the current record implies. This is an interpretive pre-registration by this review, not a
   change to Amendment 2's frozen statistical test.
2. Same frozen code path, same window, same causal terciles, same permutation design and seed, runner committed
   before execution — as was done for the long-history run.
3. No p-value from VTI/BND may be used to promote the classification, per Amendment 2 §6 itself — it overlaps the
   long-history sample too heavily on both calendar and economic content for a small p-value there to count as
   independent confirmation.
4. This time, commit the raw artifacts (JSON, panel CSV, source manifests, or at minimum full digests plus row
   counts and date ranges) so a future reviewer is not blocked the way this review was (see the "inconclusive"
   findings above).
5. A VTI/BND pass cannot upgrade Campaign #57 past `HISTORICAL_CONFIRMATION_CONDITIONAL` + transportability
   confirmed. A failure blocks any claim the mechanism is currently alive, per Amendment 2 §6, even if the
   long-history result stands.

## May Campaign #57 be called `ALIVE`?

**No.** This follows directly from governance, not from this review's own judgment call:

- Org charter: *"A pass here is a necessary, not sufficient, condition — Risk/PM still reviews portfolio fit
  afterward."* This Red Team pass is the first of three required gates; Risk/PM and explicit CEO approval remain
  outstanding.
- Charter §10: Red Team, then Risk/PM, then CEO approval are all required before any `ALIVE`/`VALIDATED`/Core
  v2/capital language. Two of three are not yet done.
- Charter §9 / Amendment 2 §2D: a future-forward SPY/AGG ledger is required before any capital decision, and "no
  amount of overlapping historical proxy replication substitutes for this forward record." Given M1 above, that
  forward ledger is now effectively the only genuinely unspent evidence this campaign has left.
- Standing amendment 5 / charter §8: economic materiality at ~$100k capital has never been computed for this
  campaign.

**Current status: `HISTORICAL_CONFIRMATION_CONDITIONAL`, independent Red Team review complete and cleared to modern
transportability replication subject to the binding conditions below. Not `ALIVE`. Not capital-ready. No Core v1,
Core v2 composition, runtime, portfolio, paper/live, NAV, exposure, or capital action is authorized by this
review.**

## Comparison with the prior (non-independent) in-thread review

The independent review agrees with the prior in-thread review's headline call (conditional pass toward VTI/BND, not
`ALIVE`) and credits it for correctly refusing to let the 1990s be redefined or thresholded away after inspection.
It disagrees on five specific, substantive points where the earlier review — built in the same context that produced
the candidate — missed or asserted rather than checked:

1. It never identified the 57.8% discovery/confirmation calendar overlap (M1) and its own checklist marked
   "multiple comparisons" and "holdout integrity" both PASS on this point.
2. It treated the 1990s era-consistency failure as informative on its face without checking whether the diagnostic
   itself was well-powered to detect anything at that bucket size (it was ~51.5% likely to pass regardless).
3. It did not check whether the retired dual co-primary gate would actually have been underpowered at the
   long-history sample size (M2) — it is not; power there is 75.5%, not 16–18%.
4. It described the placebo windows as "otherwise-analogous" without checking that their signal-window lengths
   differ substantially by construction.
5. It asserted, without any reachable source in this environment, that "Vanguard still lists VBMFX as an active
   Total Bond Market Index Investor share class in current distribution materials" — an unverifiable comfort claim
   doing real evidentiary work, now converted into an explicit open item (series-continuity verification) rather
   than an asserted fact.

## Binding conditions on this pass

1. This document stands as the correction to M1/M2/M3 — the primary result and classification are not re-opened or
   re-run to satisfy this.
2. VTI/BND may not be opened until: the artifact/source-continuity gaps above are closed (raw outputs and source
   manifests committed, VFINX/VBMFX series continuity verified), the missing JSON fields are transcribed into the
   committed record, and the quantitative pre-registration in "What VTI/BND must show" above is written down before
   any VTI/BND return is read.
3. Unit tests (lookahead canary, causal-label canary, null/positive-control calibration checks) should be added to
   the Campaign #57 test suite before further Campaign #57 code is trusted for a decision, matching the practice of
   Campaigns #50–53.
4. Campaign #57 remains `HISTORICAL_CONFIRMATION_CONDITIONAL`, not `ALIVE`, pending Risk/PM review, a future-forward
   SPY/AGG ledger, an economic materiality estimate, and explicit CEO approval — none of which this review performs
   or authorizes.

No Core v1, Core v2 composition/weights, runtime, portfolio, NAV, exposure, paper/live, or capital action is
authorized by this document.
