# Campaign #57 — In-Thread Staff Review

**Date:** 2026-09-02

**Status:** ADVISORY REVIEW ONLY — NOT THE MANDATORY INDEPENDENT RED TEAM GATE.

This review was requested by the CEO via `/itera-staff` after the one-shot VFINX/VBMFX long-history confirmation returned `HISTORICAL_CONFIRMATION_CONDITIONAL`. This environment can inspect the repository and raw result but cannot spawn a genuinely independent subagent/context. Per `.claude/skills/itera-staff/agents/red-team.md`, this review is weaker than the required independent Red Team gate and cannot by itself mark the candidate `ALIVE`.

## Raw governed result reviewed

Primary historical confirmation:

- valid months: 476, 1987-01 through 2026-08;
- Spearman rho: -0.1524487133;
- one-sided within-five-year-block permutation p: 0.0003999600;
- pre-outcome power at the frozen central 50%-haircut effect: 85.2%;
- causal low-minus-high spread: +0.0050329468;
- trimmed rho after removing the 10 largest absolute-signal months: -0.1182484219;
- actual month-end rho more negative than each frozen -5/-10/-15-session placebo;
- every eligible leave-one-year-out full-sample rho remained negative.

Era diagnostics:

- 1980s: -0.3441 (n=36);
- 1990s: +0.02865 (n=120);
- 2000s: -0.1745 (n=120);
- 2010s: -0.2987 (n=120);
- 2020s: -0.0990 (n=80).

The sole frozen robustness failure is the slightly positive 1990s era rho.

## Quant Research review

**Verdict: PRIMARY CONFIRMATION VALID; CONDITIONAL ROBUSTNESS LABEL CORRECT.**

The primary test was adequately powered before outcomes were opened and passed strongly. The result is not dependent on the largest signal months, a single year, or a nearby generic reversal window. Signal and outcome are non-overlapping at the frozen cutoff, and the permutation null preserves broad five-year regime structure. No implementation defect was found in the runner on code review.

The 1990s decade should not be redefined, excluded, thresholded, or otherwise optimized after inspection. It remains part of the record exactly as observed.

## CIO review

**Verdict: CONTINUE RESEARCH; DO NOT CALL ALIVE.**

The long-history result materially upgrades the sandbox finding: a different equity/bond proxy pair over roughly four decades reproduces the expected full-sample monotonic sign at a smaller magnitude than the SPY/AGG discovery ceiling, consistent with the pre-registered selection-bias haircut. The 1990s are a genuine regime weakness, but the observed +0.0287 rho is economically small and qualitatively closer to “effect absent” than to a durable opposite-signed relationship.

The already-frozen VTI/BND modern replication is the correct next evidentiary question because it directly asks whether the mechanism transports into the modern ETF era without changing the rule. No new parameter search is justified.

## Red Team checklist — non-independent fallback

**Advisory verdict: CONDITIONAL PASS TO MODERN REPLICATION; NOT A FORMAL RED TEAM PASS.**

1. **Windowing / timing:** PASS. Signal ends at cutoff; outcome begins after cutoff. Primary final-3-session window was frozen before outcome inspection. Nearby placebo windows were also frozen before inspection and are weaker.
2. **Outlier dominance:** PASS. Removing the 10 largest absolute-signal months leaves rho negative (-0.1182). The primary estimator is rank-based rather than mean-sensitive.
3. **Autocorrelation / null:** PASS WITH CAVEAT. The permutation shuffles within five-year blocks, preserving broad era structure. Monthly event serial dependence is not proven absent, but the null is materially more conservative than a global IID shuffle.
4. **Multiple comparisons:** PASS. Historical confirmation has one frozen primary test. Robustness diagnostics are not treated as extra significance wins.
5. **Sign / direction:** PRIMARY PASS. Full-sample rho is expected-direction negative. One decade, the 1990s, is slightly positive and must remain explicitly recorded as a regime weakness.
6. **Power:** PASS. 85.2% power at the frozen central 50%-haircut effect before returns were opened.
7. **Universe / proxy construction:** PASS WITH SOURCE CAVEAT. VFINX/VBMFX are economically coherent long-history US equity/bond index-fund proxies. Adjusted total-return handling remains load-bearing; source hashes are recorded. Vanguard still lists VBMFX as an active Total Bond Market Index Investor share class in current distribution materials, reducing concern that the long-history series is merely a dead ticker splice.
8. **Holdout integrity:** PASS for the long-history confirmation architecture. SPY/AGG was spent discovery; VFINX/VBMFX was opened only after a timestamp-only power pass and a frozen confirmation runner. VTI/BND remains unspent as Campaign #57 return evidence.

### Interpretation of the 1990s weakness

The 1990s rho (+0.0287, n=120) is a real failure of the “every era negative” robustness diagnostic and must not be erased. However, it is near zero rather than a materially opposite effect, while four other era buckets are negative. Every leave-one-year-out aggregate result remains negative, and the full-sample effect survives extreme-month trimming. On the evidence currently available, Red Team does **not** find a specific artifact that explains the full-sample confirmation.

The 1990s weakness therefore blocks a clean `HISTORICAL_CONFIRMATION_POSITIVE` label but does not, in this advisory review, justify killing the hypothesis before the already-frozen modern replication is examined.

## Risk / Portfolio Manager

**NOT YET IN SCOPE.** Formal Risk/PM portfolio-fit review requires a genuine independent Red Team pass first. No sizing, Core v2 weight, capital, or implementation recommendation is made here.

## Chief of Staff synthesis

Campaign #57 has crossed an important evidentiary threshold but is not `ALIVE`.

- The historical primary hypothesis survived a powered, one-shot, different-proxy confirmation.
- The sole major weakness is regime inconsistency in the 1990s, where the relationship was essentially flat/slightly positive.
- The correct next empirical question is the already-frozen VTI/BND modern transportability replication, **but the fund’s standing governance still requires a genuinely independent Red Team gate before further promotion from a conditional historical result.**
- This in-thread review recommends that an independent reviewer treat the appropriate candidate verdict as **CONDITIONAL PASS TO VTI/BND REPLICATION**, not `ALIVE` and not capital-ready.

No Core v1, Core v2 composition, runtime, portfolio, paper/live, NAV, exposure, or capital behavior is authorized by this advisory review.
