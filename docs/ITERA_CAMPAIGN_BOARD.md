# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

The long-term institutional objective is defined in `docs/ITERA_FIRM_THESIS.md`. That thesis is directional context only and does not modify active campaign authorization.

## Active campaign

**Campaign:** Campaign #49 — Confirmation of BTC Volatility-State and Drawdown Associations

**Classification:** Research-only confirmation design following Campaign #48 discovery

**Status:** DESIGN GO — specification drafting only; no implementation, confirmation outcomes, result inspection, artifact generation, economic-value testing, Core v1 comparison, runtime work, or strategy work is authorized

**Governance branch:** `agent/campaign-49-btc-volatility-state-confirmation-governance`

**Repository:** `IteraDynamics/ID_test`

**Governed lineage base:** Campaign #48 closure `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`

## Plain-English objective

Campaign #49 asks:

> Do the volatility-state persistence and drawdown-linked future-volatility associations discovered in Campaign #48 survive a separately frozen confirmation design?

Campaign #49 is a confirmation campaign, not a second discovery sweep. It must test the Campaign #48 findings without adding new predictors, searching new transformations, changing horizons after inspection, or converting the findings into strategy logic.

## Campaign #48 findings entering confirmation

Campaign #48 completed S-008 and established a transparent simple-price-state predictive baseline.

Confirmed-for-design discovery groups:

1. trailing 24-hour realized volatility positively associated with future absolute return at 24, 72, and 168 hours;
2. trailing 24-hour realized volatility positively associated with future realized volatility at 24, 72, and 168 hours;
3. trailing 168-hour realized volatility positively associated with future absolute return at 24, 72, and 168 hours;
4. trailing 168-hour realized volatility positively associated with future realized volatility at 24, 72, and 168 hours;
5. deeper drawdown from the trailing 168-hour high associated with higher future realized volatility at 24, 72, and 168 hours.

Campaign #48 supported 15 horizon-specific associations. No directional-return candidate was supported.

## Confirmation boundary

Campaign #49 must preserve the distinction between discovery and confirmation.

The design must:

- predeclare the exact confirmation sample or temporal validation construction before outcomes are generated or inspected;
- carry forward only the supported Campaign #48 predictor-outcome-horizon associations or a formally justified grouped confirmation family;
- preserve deterministic, replay-safe, chronological, leakage-safe, observation-only, and fail-closed behavior;
- keep predictor formulas and outcome formulas unchanged unless an explicit pre-outcome governance amendment is separately frozen;
- define support, multiplicity, directional-consistency, and minimum-sample requirements before outcome generation;
- keep all failed, unavailable, and unrankable confirmation candidates visible;
- prohibit source repair, interpolation, filling, resampling, nearest-row matching, as-of matching, shifting, or synthetic bars;
- remain research-only.

## Design questions that must be resolved before specification freeze

1. Whether a genuinely untouched post-2025 BTC hourly confirmation source exists and is sufficiently mature for exact 24-, 72-, and 168-hour outcomes.
2. If no adequate untouched source exists, which separately justified temporal confirmation construction provides the strongest honest validation without rebranding Campaign #48 reuse as independent confirmation.
3. Whether the confirmatory unit is all 15 horizon-specific associations or five grouped scientific claims with prespecified within-group requirements.
4. Whether confirmation requires effect-direction replication only, multiplicity-adjusted significance, effect-size compatibility intervals, or a conjunctive rule.
5. How to prevent the strong overlap between 24-hour and 168-hour realized-volatility predictors from inflating interpretation.
6. What minimum confirmation sample is required at each horizon and whether the longest horizon creates unacceptable delay or low power.
7. What exact result would permit a later economic-value campaign and what result would close this research path.

## Current authorization

**Decision:** GO to draft the Campaign #49 governing confirmation specification only.

Authorized now:

- create and refine `docs/research/BTC_VOLATILITY_STATE_AND_DRAWDOWN_CONFIRMATION.md`;
- inspect already published Campaign #48 canonical artifacts for design inputs and exact lineage;
- inspect repository data inventories only to determine whether an untouched confirmation source exists;
- update this board for design review and later specification freeze;
- create no implementation module, runner, test file, or confirmation artifact yet.

Not authorized:

- generating, calculating, viewing, ranking, or interpreting Campaign #49 confirmation outcomes;
- re-running Campaign #48 as though it were independent confirmation;
- adding predictors, technical indicators, bins, thresholds, interactions, regime labels, or learned features;
- Sharpe, CAGR, drawdown, turnover, sizing, timing, allocation, exposure, portfolio, or Core v1 testing;
- any runtime, threshold, regime, classifier, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training change.

## Immediate sequence

1. Branch from Campaign #48 closure. **Completed.**
2. Record Campaign #49 design authorization. **Completed by this board commit.**
3. Draft the confirmation specification without outcomes. **Authorized next.**
4. Review the source and temporal confirmation options.
5. Freeze the governing specification before implementation or confirmation outcomes.
6. Freeze a separate implementation handoff.
7. Record a separate implementation GO.

## Campaign #48 completion record

**Campaign:** Campaign #48 — Simple BTC Price-State Predictive Baselines

**Final status:** COMPLETE — canonical artifacts published; 15 supported research associations under the frozen discovery design

**Implementation branch:** `agent/campaign-48-simple-btc-price-state-baselines-implementation`

**Closure commit:** `77c1ae8c70de7a16cca847aeb1a4cb2eea638007`

**Canonical artifact publication:** `fd7ee01`

Completed evidence:

- corrected focused suite: `27 passed`;
- governed preflight: `PASS` with outcomes `false`;
- exact governed missing-hour inventory: `36`;
- anchors: `403`;
- partitions: `135`, `134`, `134`;
- candidates: `72`;
- rankable: `72`;
- directionally consistent: `48`;
- supported research associations: `15`;
- multiplicity not met: `55`;
- direction inconsistent: `2`;
- two canonical runs replayed byte-identically;
- governed source bytes remained unchanged;
- full suite: `531 passed`, `75 warnings`;
- no runtime or strategy surface changed.

Campaign #48 conclusion:

Simple recent BTC volatility and drawdown information contained reproducible association with the magnitude and volatility of subsequent movement, but not direction. The findings require separately frozen confirmation before any economic-value or Core v1 comparison.

## Prior campaign carryover

Campaign #47 completed historical regime-structure discovery with zero rankable candidates and zero supported associations.

Campaign #45 completed historical regime-transition discovery with zero supported exact ordered-transition associations.

Campaign #46 completed the full historical regime-state source.

Campaign #43 Candidate A-001 remains preliminary and is not revised, promoted, or retested by Campaign #49 unless separately authorized.
