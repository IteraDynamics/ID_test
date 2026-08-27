# Core v2 Charter — DRAFT

## Status

**Draft, not frozen.** This document reconciles the Core v2 concept to the actual research state as of 2026-08-27. It authorizes no data acquisition, runtime construction, paper account, inception date, capital allocation, production behavior, or Core v1 change.

Detailed historical drafts and their decision trail remain preserved in Git. Current campaign truth is governed by `docs/ITERA_CAMPAIGN_BOARD.md` and each campaign's own document.

## Purpose

Core v2 is a separate successor strategy, not a retune or mutation of Core v1.

Core v1 remains the frozen floor with its own permanent inception, paper record, benchmark series, and governance lineage. Core v2, if eventually launched, will have its own specification, paper runtime, inception date, benchmarks, record, and capital decision.

The purpose of Core v2 is to address named architectural deficiencies that cannot be solved honestly by re-optimizing Core v1's constants on the same history.

## Relationship to Core v1

1. **Parallel, never replacing by default.** Core v1 continues untouched while Core v2 research proceeds.
2. **No inherited track record.** Core v2 begins at its own future inception; no Core v1 history is restated as Core v2 history.
3. **No parameter laundering.** Changing a Core v1 parameter and calling the result v2 is not a successor thesis.
4. **Same research standards.** Horizon feasibility, tradeability, materiality, power, pre-registration, deterministic replay, and holdout discipline apply.
5. **Any future capital transition is separate.** A later move from v1 to v2 would require its own governed decision after substantial prospective evidence.

## Why a successor is legitimate

The Core v1 parameter-sensitivity pass found no knife edge on the six constants the historical harness actually exercised: nearby perturbations produced only small Sharpe changes. The current evidence therefore does not support a tuning-led successor.

A legitimate successor must address structural deficiencies instead.

## Named structural deficiencies

### 1. Single return source

Core v1's sleeves are diversified primarily across assets, while the dominant economic source remains trend/price persistence.

Potential independent sources under research include:

- funding/carry;
- volatility risk premium;
- other future non-trend families that survive the standing research process.

### 2. Structurally long-biased opportunity set

Core v1 can reduce or exit long exposure during adverse conditions but has limited ability to earn directly from sustained declines.

`crash_short_v6` is a candidate asymmetric hedge mechanism, but current evidence is too thin to call its sizing statistically validated.

### 3. Single-name crypto concentration

Core v1's crypto exposure is centered on BTC and ETH.

**This deficiency is currently unresolved.** Campaign #53's actual frozen/statistical execution scope is BTC and ETH only. The earlier broad-CDE cross-sectional concept does not currently solve this item.

### 4. No rates / fixed-income return source

Core v1's defensive endpoint is effectively cash rather than a dedicated rates/fixed-income return sleeve.

**This deficiency is unresolved.** Recent COT work did not establish a usable rates signal and does not count as progress toward solving it.

## Candidate component status

### Core-v1-style trend component

**Status: architectural inheritance candidate, not frozen.**

A successor may retain a trend allocation because the purpose of v2 is additive diversification, not rejection of a robust existing premium. Exact v2 trend construction and weight are not set here.

### Campaign #53 — funding/carry

**Status: discovery positive / confirmation pending.**

Current reality:

- statistical scope: BTC and ETH only;
- discovery source: Deribit multi-year funding history;
- confirmation source: CDE live-forward funding accumulation;
- corrected family excludes the invalid `funding_level_24h` construction;
- all three remaining discovery hypotheses cleared BH-FDR q=0.10;
- top-2 confirmation shortlist: `funding_level_72h` and `funding_persistence_72h`;
- confirmation logger's real accumulation began 2026-08-24;
- no confirmation result exists yet.

Core v2 treatment:

- funding/carry is a **candidate return source**, not a founding admitted sleeve;
- it does not solve broad cross-sectional crypto under the current BTC/ETH scope;
- no v2 weight is assigned until confirmation clears and economic implementation is separately specified.

### Campaign #54 — crash-short hedge

**Status: provisional shadow candidate.**

Evidence:

- 2018: comparatively clean profitable crisis observation;
- 2022: profitable but plausibly contaminated by design history;
- 2020: clean regime firing but unprofitable;
- historical blend improves drawdown/Sharpe as hedge weight rises across the tested 0%-25% range, while CAGR falls;
- the tested range contains no interior optimum.

Core v2 treatment:

- 15% is retained only as a **provisional shadow-composition reference**, not a validated optimum;
- it must not be represented as permanent founding sizing;
- future prospective macro-bear behavior is the primary clean evidence still needed.

### Defined-risk equity volatility risk premium

**Status: promising / unnumbered / execution-gated.**

Current evidence suggests the premium is broad enough to survive nearby structure variation under representative modeled skew and costs, and potentially material at realistic risk budgets.

However:

- results depend materially on multi-leg execution quality;
- pessimistic crisis-level execution costs eliminate the apparent edge across the tested family;
- tail losses are positively related to the same equity-stress periods that hurt long-equity exposure;
- broker approval, verified commissions, routing, and achievable fill versus mid/NBBO remain load-bearing unknowns.

Core v2 treatment:

- not admitted;
- first require real execution-quality evidence under a pre-registered acceptance band;
- if execution is viable, charter it as a numbered campaign before any v2 inclusion or paper allocation.

## What is explicitly not part of Core v2 today

- Campaign #55 COT contrarian signal — closed clean null;
- COT gold positioning — closed clean null;
- cross-sectional crypto momentum — closed clean null;
- Jump Risk — retired because the edge is not reachable at measured runtime cadence;
- any Core v1 parameter retune;
- any unconfirmed Campaign #53 discovery candidate.

## Portfolio-level integration requirements before freeze

A future frozen Core v2 specification must answer, before a runtime exists:

1. Which components are actually admitted based on their own evidence?
2. What economic source of return does each component add?
3. What are the component correlations in normal periods and stress periods?
4. What tail risks stack rather than diversify?
5. How are weights determined without retrospective optimization against one historical sample?
6. Which components are statistically confirmed versus explicitly provisional/prospective?
7. What benchmark set will judge v2 prospectively?
8. What is the v2 paper inception rule, with no backfill or inherited record?

## Current blockers before Core v2 can freeze

1. Quantify the Core-v1 historical-harness equity de-risk semantic mismatch so historical v1-v2 comparisons use a correctly understood baseline.
2. Let Campaign #53 accumulate enough untouched CDE confirmation data and complete its governed confirmation decision.
3. Resolve whether the VRP family is execution-viable with real brokerage approval, commissions, and four-leg fill evidence.
4. Decide whether `crash_short_v6` remains a provisional shadow component, is removed, or earns stronger standing through future prospective evidence.
5. Leave the unresolved cross-sectional-crypto and rates/fixed-income deficiencies explicit rather than claiming they are solved.

## Research philosophy for Core v2

Core v2 is an **integration destination**, not a license to bundle every promising idea into one backtest.

Candidate families should earn admission independently. The final portfolio-level specification comes only after the component evidence exists, so success or failure can be attributed rather than hidden inside a giant combined architecture.

A component does not have to increase raw CAGR to improve Core v2. A lower-return component may be valuable if it materially improves drawdown, Sharpe, regime robustness, or independence of return source at a reasonable economic cost.

## Not authorized

This draft does not authorize:

- any Core v2 runtime or paper account;
- any Core v2 inception date;
- any capital allocation;
- any Core v1 change;
- treating Campaign #53 discovery as confirmation;
- treating the Campaign #54 15% reference weight as validated sizing;
- treating VRP modeled expectancy as executable expectancy without fill evidence;
- parameter optimization of Core v1 under a successor label.

## Next review

Core v2 should not be frozen until the ranked baseline actions in `docs/ITERA_RESEARCH_STATE_OF_UNION_2026-08-27.md` have materially advanced. The next charter review should use those results to decide whether enough independently supported components exist to justify a v2 specification at all.