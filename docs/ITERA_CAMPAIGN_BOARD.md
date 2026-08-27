# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The detailed chronological correction history remains preserved in Git and in each campaign's governing document. This board states **current truth and current authorization only**.

No production or portfolio behavior is authorized unless explicitly stated.

## Current operating branch

**Branch:** `agent/research-baseline-reconciliation-20260827`

**Parent research branch:** `claude/research-assessment-feedback-4auusg`

**Repository:** `IteraDynamics/ID_test`

**Current research state:** `docs/ITERA_RESEARCH_STATE_OF_UNION_2026-08-27.md`

## Strategic boundary

- **Core v1 is the frozen floor.** Its paper record, inception, registered benchmarks, parameters, weights, and runtime behavior remain untouched.
- **Core v2 is a separate successor concept.** It may be researched in parallel with its own charter, paper runtime, inception date, and record. It is not a retune or mutation of Core v1.
- No campaign, successor, overlay, or research result authorizes changing Core v1 unless a later explicit governed decision says so.

## Core v1

**Status:** FROZEN — live/paper record continues.

Key current findings:

- nearby parameter sensitivity on the six constants actually exercised by the historical harness showed no knife-edge behavior;
- the sensitivity work exposed a historical-harness semantic mismatch in the equity partial-de-risk branch: the historical engine discards a non-current `desired_exposure_frac` carried on a `HOLD`, while the live paper runtime honors it;
- the live paper record is not invalidated;
- historical backtest ceilings and future historical v1-v2 comparisons carry an unresolved asterisk until the mismatch is quantified observation-only.

Reference: `docs/research/CORE_V1_PARAMETER_SENSITIVITY_RESULT.md`.

## Campaign #52 — Core v1 Chronological State Value

**Status:** CLOSED — DEVELOPMENT_NEGATIVE.

The governed 2020-2022 development test completed successfully and does not advance to validation.

Current interpretation:

- canonical chronology beat the static control on all three primary endpoints;
- canonical beat all three lag controls economically;
- canonical beat the permutation median on all three primary endpoints;
- no lag comparison survived the frozen Holm-adjusted 20-control family;
- validation remains sealed.

Reference closure: `bc818fffe33ca5c899140416e1f0dd9588537114`.

## Campaign #53 — Perpetual Funding and Basis Carry

**Status:** DISCOVERY POSITIVE / CONFIRMATION CLOCK-BOUND.

Governing document: `docs/research/CAMPAIGN_53_FUNDING_CARRY_PLANNING_CHARTER.md`.

Current statistical scope:

- assets: BTC and ETH only;
- discovery history: Deribit;
- confirmation: CDE live-forward funding accumulation;
- corrected hypotheses: `funding_level_72h`, `funding_persistence_24h`, `funding_persistence_72h`;
- excluded: `funding_level_24h` because its 24h window/horizon/rebalance construction is near-tautological and was proven invalid with synthetic controls;
- corrected discovery: all three remaining hypotheses cleared BH-FDR q=0.10;
- top-2 confirmation shortlist: `funding_level_72h` and `funding_persistence_72h`;
- discovery is not confirmation and is not a trading signal.

Power state:

- original design failed at about 45.4% average power;
- mechanistically justified design correction produced about 56.0% average power at the central assumed IC;
- 56% clears the standing floor but remains a thin margin.

Confirmation clock:

- CDE funding logger's first real snapshot: 2026-08-24T14:56Z;
- confirmation holdout must remain untouched for a decision until enough forward sample exists;
- do not backfill or substitute another confirmation source.

Structural basis thread:

- first snapshot showed small basis and concentrated front-contract liquidity;
- hourly CDE basis-ladder logger is accumulating forward observations;
- mark-to-market tolerance and roll timing remain unset pending real roll-cycle evidence.

## Campaign #54 — Macro-Confirmed Crash-Short Hedge Sleeve

**Status:** CLOSED — PROVISIONAL CORE-V2 SHADOW CANDIDATE.

Governing document: `docs/research/CAMPAIGN_54_CRASH_SHORT_PLANNING_CHARTER.md`.

Current interpretation:

- the mechanism is plausible and historically improves risk shape when blended;
- evidentiary base is thin: one comparatively clean profitable crisis (2018), one plausibly hindsight-contaminated profitable crisis (2022), one clean fired-but-unprofitable crisis (2020);
- sizing sweep from 0%-25% had no interior optimum: more hedge monotonically improved Sharpe/Calmar/drawdown while reducing CAGR;
- the recorded 15% hedge weight is a **provisional shadow composition choice**, not a statistically validated or permanent optimum;
- only future prospective macro-bear observations can materially strengthen the evidence.

No Core v1 change, Core v2 runtime, paper account, or capital allocation is authorized by Campaign #54.

## Campaign #55 — COT Speculative Positioning Contrarian Signal

**Status:** CLOSED — CLEAN NULL.

Governing document: `docs/research/CAMPAIGN_55_COT_INDEX_POSITIONING_CONTRARIAN_CHARTER.md`.

The initial two-market design was underpowered. The prescribed cross-sectional redesign was built and pre-registered. Discovery on 21 markets produced the wrong aggregate sign and no significant primary effect; effective breadth was only about 5.1 independent markets. The 14-market holdout remains untouched.

This signal construction is closed. Reopening requires a materially different hypothesis.

## Other candidate-family status

### Defined-risk equity volatility risk premium

**Status:** PROMISING / UNNUMBERED / EXECUTION-GATED.

Current evidence suggests a defined-risk SPY options-premium family may be economically material under representative modeled skew and execution costs, with broad nearby-structure robustness. The entire family fails under pessimistic crisis-level execution costs, making real execution quality the binding unknown.

Required next evidence is brokerage approval, verified commissions, and measured four-leg fill quality versus mid/NBBO under a pre-registered acceptance band. Do not tune DTE/delta/wing parameters from those fill observations.

### COT gold positioning

**Status:** CLOSED — CLEAN NULL after correcting expanding-percentile bias.**

### Cross-sectional crypto momentum

**Status:** CLOSED — CLEAN NULL after breadth and outlier-robustness corrections.**

### Jump Risk

**Status:** RETIRED — effect not reachable at measured runtime cadence.**

## Core v2

**Status:** DRAFT INTEGRATION DESTINATION — NO RUNTIME / NO CAPITAL / NO INCEPTION.

Current reconciled component status:

- trend architecture: inheritance candidate, not yet final v2 specification;
- crash-short: provisional shadow candidate; 15% is not treated as validated sizing;
- funding/carry: discovery-positive, confirmation-pending;
- defined-risk VRP: promising but execution-gated and adversely tail-correlated with long equities;
- broad cross-sectional crypto: unresolved — Campaign #53's current BTC/ETH scope does not solve it;
- rates/fixed income: unresolved.

The existing draft `docs/CORE_V2_CHARTER.md` should be refreshed before freeze to match these current states.

## Standing research process

Retain:

1. pre-registration and frozen specifications;
2. untouched holdouts;
3. deterministic, replay-safe, fail-closed implementation;
4. ex-ante power analysis before expensive confirmatory work;
5. FDR/ranking for discovery and stricter confirmation;
6. measured horizon feasibility against actual runtime cadence;
7. tradeability / venue / account feasibility before specification;
8. economic materiality at realistic capital before deep build-out;
9. adversarial artifact checks and synthetic canaries;
10. immutable Core-v1 and successor track records.

Rare-event families may be observed prospectively under explicitly bounded claims, but inability to obtain conventional power is not by itself permission to relabel them statistically validated.

## Ranked next-action queue

### Priority 1 — Core-v1 historical-harness reconciliation

Quantify the equity partial-de-risk semantic mismatch observation-only.

Authorized scope:

- instrument or correct a research-only reconciliation path;
- measure the NAV/return/drawdown difference attributable solely to honoring the strategy's non-current `desired_exposure_frac` on `HOLD`;
- determine whether prior historical Core-v1 ceilings materially move;
- leave Core-v1 runtime and paper record unchanged.

No threshold, weight, order, NAV semantics, runtime, or strategy changes are authorized.

### Priority 2 — Clock-bound logger health

Verify operational continuity only for:

- CDE funding logger;
- CDE basis-ladder logger.

Do not inspect or analyze the funding confirmation holdout for a campaign decision. Operational checks may confirm process health, timestamps, schema, and gaps only.

### Priority 3 — VRP execution-quality evidence

When a spread-capable brokerage/account is available:

- verify actual options approval and commission schedule;
- pre-register acceptable fill-quality bands;
- measure representative four-leg SPY spread fills versus mid/NBBO;
- do not change structure parameters from the observed fills.

If execution lies inside the modeled viable region, charter a numbered VRP campaign before any paper or capital action.

### Priority 4 — Core-v2 charter reconciliation

Refresh the draft only after baseline reconciliation and current component statuses are reflected accurately. Do not start a Core-v2 paper runtime before a later explicit freeze/authorization.

### Priority 5 — Campaign #56 selection

Do not open Campaign #56 merely for cadence. Select it only after the above baseline work and only if it addresses a named unresolved architectural deficiency with horizon, tradeability, materiality, and power feasibility screened first.

## Current authorization

Authorized now:

- observation-only Core-v1 historical-harness reconciliation;
- operational health verification of the two clock-bound CDE loggers without decision-level holdout analysis;
- documentation reconciliation;
- planning work consistent with the standing research process.

Still prohibited:

- opening Campaign #52 validation targets or outcomes;
- using Campaign #53 CDE holdout for a confirmation decision before its governed sample requirement is satisfied;
- treating Campaign #53 discovery as confirmed;
- changing Core v1 behavior, parameters, sources, weights, thresholds, costs, folds, orders, execution, NAV, exposure, runtime, dashboard, or training;
- starting a Core-v2 runtime or assigning capital;
- paper/live economic action from any unconfirmed candidate;
- opening Campaign #56 before a separate charter decision.

## Passive campaign

Campaign #49 remains in passive prospective accumulation under method lock `9203b6f20983b8c168182e6bc58135f4f7d5913c`.