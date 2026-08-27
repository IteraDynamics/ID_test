# Itera Research State of the Union — 2026-08-27

## Purpose

This document is a concise, current-state reconciliation of Itera Dynamics research as of 2026-08-27. It is not a new campaign charter and authorizes no runtime, order, NAV, exposure, threshold, strategy, portfolio, or production change.

It exists because the research branch accumulated many valid append-only corrections and exploratory records faster than the top-level campaign board could remain readable. The detailed historical record remains in the individual campaign and research documents. This document states the current interpretation and the ranked next-action queue.

## Strategic frame

Core v1 remains the frozen floor. Its live paper record, benchmarks, and inception are preserved. Building a successor does not require mutating Core v1: Core v2 may be developed as a separate strategy with its own charter, paper runtime, inception date, benchmarks, and track record.

The legitimate case for Core v2 is architectural, not a parameter-retuning exercise. Core v1's nearby parameter sensitivity was stable on the six constants the historical harness actually exercised; improvement therefore does not presently point toward retuning.

## Core v1 — current state

**Status: FROZEN / PAPER RECORD CONTINUES.**

Established:

- Core v1 remains the canonical floor and must not be mutated by successor research.
- Registered live benchmarks and the degradation-band precommitment remain valid prospective evaluation tools.
- Parameter sensitivity on the six exercised constants showed no knife-edge behavior: Delta Sharpe ranged approximately -0.022 to +0.039 around baseline 1.319.

Open engineering/research debt:

- The sensitivity work found a semantic mismatch between the historical backtest engine and the live paper runtime in the equity partial-de-risk branch. The strategy emits a `HOLD` intent with a non-current `desired_exposure_frac`; the historical engine treats every `HOLD` as current exposure and discards that target, while the paper runtime honors it.
- The live paper record is not invalidated by this mismatch. Historical Core-v1 backtest ceilings and any future v1-v2 historical comparisons should carry an asterisk until the difference is quantified under a governed, observation-only reconciliation.

## Campaign #52 — chronological state value

**Status: CLOSED — DEVELOPMENT_NEGATIVE.**

The campaign does not advance to validation. Economically, canonical chronology beat the static control, all three lag controls, and the permutation median on the primary comparisons; statistically, the frozen lag-family gate did not survive Holm correction across the full 20-control family.

Campaign #52 remains closed. Its validation set remains sealed.

## Campaign #53 — perpetual funding / carry

**Status: DISCOVERY POSITIVE / CONFIRMATION CLOCK-BOUND.**

Current statistical execution scope is BTC and ETH only, not the broad CDE crypto cross-section originally contemplated.

Discovery design and results:

- discovery venue/history: Deribit;
- confirmation venue: Coinbase Derivatives Exchange (CDE), accumulated live-forward because historical retail-account funding history is not obtainable;
- current corrected statistical family: `funding_level_72h`, `funding_persistence_24h`, `funding_persistence_72h`;
- `funding_level_24h` is excluded as a near-tautological construction discovered and proven by synthetic controls;
- all three corrected hypotheses cleared FDR q=0.10;
- top-2 confirmation shortlist: `funding_level_72h` (r about 0.6347) and `funding_persistence_72h` (r about 0.1922);
- discovery is not confirmation and is not a trading signal.

Power:

- original corrected-design simulation failed at about 45.4% average power;
- mechanistically justified removal of the highly overlapping 168h family and confirmation-k adjustment produced about 56.0% average power at the central assumed IC;
- 56% clears the standing minimum but remains thin rather than strong.

Clock-bound confirmation:

- CDE funding holdout accumulation actually began 2026-08-24, not 2026-08-21;
- the holdout remains untouched for a confirmation decision until enough forward data has accumulated;
- no Core v2 inclusion or runtime action is authorized from discovery alone.

Structural basis family:

- first CDE snapshot showed very small basis and liquidity concentrated in the front dated contract;
- hourly basis-ladder logging is active;
- mark-to-market tolerance and roll-timing remain intentionally unset pending at least one real roll cycle.

## Campaign #54 — crash-short hedge sleeve

**Status: CLOSED / PROVISIONAL CORE-V2 SHADOW CANDIDATE.**

Research record:

- `crash_short_v6` is a real asymmetric mechanism and can improve historical drawdown/Sharpe when blended;
- evidence is thin and partially contaminated by design history: 2018 is one comparatively clean profitable crisis; 2022 is profitable but plausibly influenced by hindsight design; 2020 is a clean regime detection that lost money;
- the 0%-25% sizing sweep was monotonic with no interior optimum: more hedge improved historical Sharpe/Calmar/drawdown while reducing CAGR throughout the tested range.

Reconciled interpretation:

- the 15% hedge weight is a reasonable provisional shadow-composition choice, not a statistically validated optimum;
- it should not be represented as an earned permanent Core-v2 allocation;
- prospective observation of future macro-bear regimes is the only clean way to materially strengthen this evidence.

## Campaign #55 — COT speculative-positioning contrarian signal

**Status: CLOSED — CLEAN NULL.**

The original two-index design was underpowered. The prescribed cross-sectional remedy was built, pre-registered, and run on the live CFTC universe. Discovery-stage aggregate signal had the wrong sign and was statistically null; effective breadth was only about 5.1 independent markets despite 21 nominal markets. The untouched holdout was correctly left unused.

This signal construction is closed. Reopening would require a materially different hypothesis, not another pass over the same design.

## Other recently tested candidate families

### Defined-risk equity volatility risk premium

**Status: PROMISING / UNNUMBERED / EXECUTION-GATED.**

This is currently the most economically interesting unconfirmed candidate family.

Evidence accumulated so far:

- real SPY/VIX history over roughly 12.7 years;
- 127 non-overlapping option-cycle approximations;
- a defined-risk iron-condor structure showed strong positive modeled expectancy under representative assumptions;
- nearby-structure sweep: 52 of 60 cells positive under moderate skew and moderate execution-cost assumptions;
- the edge survived moderate skew and realistic-cost stress but disappeared across the family under pessimistic crisis-level execution costs;
- cash-secured-put fallback was materially inferior and failed the lower-tier substitute test;
- hard loss caps make the defined-risk structure qualitatively different from undefined-risk premium selling;
- tail correlation with Core's long-equity exposure is adverse and must be modeled at portfolio level.

Binding unknown:

- execution quality, broker approval, real commissions, and achievable four-leg fills near mid.

The next valuable evidence is live/paper execution-quality measurement, not additional signal tuning.

### COT gold positioning

**Status: CLOSED — CLEAN NULL.**

A promising first result disappeared after correcting an expanding-percentile artifact with a causal rolling percentile.

### Cross-sectional crypto momentum

**Status: CLOSED — CLEAN NULL.**

The promising mean-spread result was driven by sparse-universe periods and extreme single-coin outliers. Breadth and median-aggregation corrections reduced the signal to approximately chance.

### Jump Risk

**Status: RETIRED.**

The research signal was real enough to survive structural checks, but measured paper-runtime cadence reached it too late. This finding motivated the standing horizon-feasibility rule.

## Core v2 — reconciled current state

**Status: DRAFT INTEGRATION DESTINATION / NO RUNTIME / NO CAPITAL / NO INCEPTION.**

Core v2 should remain a separate successor strategy, never a mutation of Core v1.

Current candidate components:

- Core-v1-style trend exposure: architectural inheritance candidate, not yet a final v2 specification;
- crash-short hedge: provisional shadow candidate, with 15% as a judgmental test composition rather than validated sizing;
- funding/carry: promising discovery candidate, not admitted until CDE forward confirmation clears;
- defined-risk VRP: promising unnumbered candidate, execution-gated and adversely tail-correlated with long equities;
- cross-sectional crypto: unresolved; Campaign #53's current BTC/ETH scope does not solve this deficiency;
- rates/fixed income: unresolved.

No Core-v2 paper runtime should begin until its founding composition and component evidentiary statuses are reconciled and explicitly frozen in a later charter review.

## Standing process — what to retain

Retain the strongest process reforms from the current branch:

1. ex-ante power analysis before expensive confirmatory work;
2. FDR/ranking for discovery, strict untouched-holdout confirmation;
3. horizon feasibility against measured runtime cadence;
4. tradeability and venue/account feasibility before specification;
5. economic materiality at realistic capital before deep implementation;
6. adversarial artifact checks and synthetic canaries;
7. Core v1 / successor separation;
8. prospective live benchmarks and immutable paper records.

Do not create a general 'judgment exception' that silently overrides power requirements. Rare-event families may support explicitly bounded shadow/prospective observation, but they should not be relabeled statistically validated because conventional power is unavailable.

## Ranked next-action queue

### 1. Quantify the Core-v1 historical-harness semantic mismatch

**Why first:** every historical v1-v2 comparison depends on knowing what the historical v1 baseline actually simulated.

Scope must be observation-only:

- correct or instrument a research-only reconciliation path without changing Core v1 runtime behavior;
- measure NAV/return/drawdown differences attributable solely to honoring `desired_exposure_frac` on the equity partial-de-risk `HOLD` branch;
- determine whether prior historical ceiling/benchmark claims move materially;
- preserve the live paper record untouched.

This is engineering truth-finding, not strategy retuning.

### 2. Verify the two clock-bound Campaign #53 loggers remain healthy

- CDE funding logger;
- CDE basis-ladder logger.

Do not inspect the confirmation holdout for a decision. Verify only operational continuity, timestamps, schema, and gap-free accumulation. Confirmation remains clock-bound.

### 3. Advance VRP only through execution-quality evidence

When a spread-capable brokerage/account is available:

- verify actual commission schedule and options approval;
- paper/work representative four-leg SPY orders and measure fill versus mid, NBBO, and modeled cost assumptions;
- pre-register the execution-quality acceptance band before using observed fills to decide viability;
- do not tune DTE/delta/wing parameters from those fills.

If realistic execution lands inside the modeled viable region, then charter a numbered VRP campaign before any capital or Core-v2 inclusion decision.

### 4. Refresh and later freeze the Core-v2 charter

After actions 1-3 clarify baseline comparability and component status:

- remove stale claims that Campaign #53 currently solves broad cross-sectional crypto;
- represent crash-short 15% as provisional shadow sizing unless/until prospective evidence strengthens it;
- represent funding as discovery-positive / confirmation-pending;
- represent VRP as execution-gated until real fill evidence exists;
- leave rates/fixed income and cross-sectional crypto explicitly unresolved.

### 5. Select Campaign #56 only after the above baseline work

Campaign #56 should address one unresolved architectural deficiency with a pre-feasibility screen for horizon, tradeability, materiality, and power. Do not open #56 merely to maintain campaign cadence.

## Authorization boundary

This state-of-union authorizes no runtime, threshold, order, NAV, exposure, strategy, portfolio, model-training, dashboard, paper-trading, live-trading, or capital change.

Permitted next work is limited to observation-only reconciliation, logger-health verification without holdout decision access, documentation cleanup, and separately authorized research planning under the standing process.