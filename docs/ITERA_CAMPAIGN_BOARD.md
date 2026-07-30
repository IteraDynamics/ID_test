# Itera Campaign Board

## Purpose

This file is the authoritative, version-controlled handoff for active Itera work. Read it before proposing or implementing the next step.

The board is project state and authorization record. It does not authorize production, runtime, threshold, signal, order, portfolio, NAV, exposure, model-training, dashboard, cross-asset, or strategy changes.

The long-term institutional objective is defined in `docs/ITERA_FIRM_THESIS.md`. That thesis is directional context only and does not modify active campaign authorization.

## Active campaign

**Campaign:** Campaign #48 - Simple BTC Price-State Predictive Baselines

**Classification:** Research-only predictive-baseline discovery over the frozen governed BTC hourly source

**Status:** IMPLEMENTATION GO WITH PRE-OUTCOME SOURCE-CADENCE CORRECTION - focused synthetic tests passed; governed preflight correctly failed closed before outcome generation; the source-gap contract below supersedes only the contradictory gapless-cadence language in the original specification and handoff

**Governance branch:** `agent/campaign-48-simple-btc-price-state-baselines-governance`

**Implementation branch:** `agent/campaign-48-simple-btc-price-state-baselines-implementation`

**Repository:** `IteraDynamics/ID_test`

**Governed lineage base:** Campaign #47 closure `d8f8b234ccd342369d3d134e1dd7d7b916557b0a`

**Governing specification:** `docs/research/SIMPLE_BTC_PRICE_STATE_PREDICTIVE_BASELINES.md`

**Specification freeze commit:** `e8777df3442d093fd84fb92c25d13aadc2bfe1ed`

**Implementation handoff:** `docs/research/SIMPLE_BTC_PRICE_STATE_PREDICTIVE_BASELINES_IMPLEMENTATION_HANDOFF.md`

**Implementation handoff freeze commit:** `a16c152608df481a66a2e29f7a1d7795b5490459`

**Initial implementation GO:** `99a7db937f68bb16662c4d28701f1cd52e661f36`

## Plain-English objective

Campaign #48 asks:

> Does BTC's recent price behavior contain reliable information about what happens next?

The frozen study tests eight simple recent-return, realized-volatility, and price-location predictors against future directional return, absolute return, and realized volatility at exact 24-hour, 72-hour, and 168-hour horizons.

It is a predictive-baseline discovery campaign, not a trading-strategy backtest. A supported association would remain research-only and would require a separately frozen confirmation campaign before any economic-value or Core v1 comparison.

## Frozen research contract

### Governed source

Only this source is authorized:

- path: `data/btcusd_3600s_2018-01-01_to_2025-12-31.csv`;
- SHA-256: `d7ca8ad775f899b9f65f25ff07f32dec07b62d1e5979a6c302bc0133b9090079`;
- byte count: `4,792,028`;
- data rows: `70,069`;
- timestamps: `2018-01-01 00:00:00` through `2025-12-31 00:00:00`;
- exact ordered schema: `timestamp`, `open`, `high`, `low`, `close`, `volume`;
- only `timestamp` and `close` may enter predictor or outcome calculations.

### Corrective source-cadence amendment

The first governed preflight after implementation returned `SOURCE_CADENCE_FAILURE` with `predictive_outcomes_generated:false`. Focused synthetic tests had already passed `22 passed in 6.59s`.

An observation-only timestamp inventory then established:

- source rows: `70,069`;
- continuous hourly rows implied by the endpoints: `70,105`;
- governed missing hourly timestamps: exactly `36`.

The exact missing timestamp inventory is:

1. `2018-02-01 05:00:00`;
2. `2018-02-01 06:00:00`;
3. `2018-02-01 07:00:00`;
4. `2018-05-10 04:00:00`;
5. `2018-05-30 03:00:00`;
6. `2018-06-04 03:00:00`;
7. `2018-08-10 01:00:00`;
8. `2018-08-10 02:00:00`;
9. `2018-08-10 03:00:00`;
10. `2018-08-10 04:00:00`;
11. `2018-08-10 05:00:00`;
12. `2018-08-10 06:00:00`;
13. `2018-08-10 07:00:00`;
14. `2018-08-10 08:00:00`;
15. `2018-08-10 09:00:00`;
16. `2018-08-10 10:00:00`;
17. `2018-08-10 11:00:00`;
18. `2018-08-10 12:00:00`;
19. `2018-08-10 13:00:00`;
20. `2018-08-10 14:00:00`;
21. `2018-08-10 15:00:00`;
22. `2018-12-26 02:00:00`;
23. `2019-04-11 13:00:00`;
24. `2019-06-20 15:00:00`;
25. `2019-10-31 20:00:00`;
26. `2020-01-30 17:00:00`;
27. `2020-09-04 23:00:00`;
28. `2020-10-20 20:00:00`;
29. `2023-03-04 18:00:00`;
30. `2023-03-04 19:00:00`;
31. `2023-03-04 20:00:00`;
32. `2025-10-25 16:00:00`;
33. `2025-10-25 17:00:00`;
34. `2025-10-25 18:00:00`;
35. `2025-10-25 19:00:00`;
36. `2025-10-25 20:00:00`.

This amendment supersedes only statements in the frozen specification and handoff that require the entire source to be gapless or treat any cadence break as a global preflight failure.

The corrected frozen rule is:

- timestamps must parse, be timezone-naive, unique, strictly increasing, and aligned exactly to whole hours;
- the full source gap inventory must equal the exact 36-timestamp inventory above;
- no additional or missing governed gap is permitted;
- no interpolation, filling, resampling, nearest-row matching, as-of matching, shifting, synthetic bars, or timestamp repair is permitted;
- a predictor is unavailable at an anchor unless every exact timestamp required by its trailing window exists;
- an anchor is retained only when all eight predictors are available;
- an outcome is unavailable unless every exact timestamp required by that family and horizon exists;
- unavailable predictors, anchors, and outcomes are handled visibly and deterministically under the frozen support and rankability rules.

This correction changes no predictor, outcome, horizon, anchor spacing, chronological partition rule, estimator, standardization rule, support threshold, directional-consistency rule, multiplicity family, interpretation boundary, runtime behavior, or strategy behavior.

### Predictors

Exactly eight predictors:

1. trailing 24-hour log return;
2. trailing 72-hour log return;
3. trailing 168-hour log return;
4. trailing 24-hour realized volatility;
5. trailing 168-hour realized volatility;
6. distance from trailing 168-hour close mean;
7. position within trailing 168-hour close range;
8. drawdown from trailing 168-hour close high.

### Outcomes and candidate family

At exact 24-hour, 72-hour, and 168-hour horizons:

- Family R: directional forward log return;
- Family M: absolute forward log return;
- Family V: forward realized volatility.

Candidate inventory remains exactly 8 predictors x 3 outcome families x 3 horizons = 72 candidates.

### Estimator and evaluation

Each candidate uses OLS with intercept and exactly one standardized predictor, no regime labels or fixed effects, no additional controls, HC3 covariance, two-sided normal p-value, and a 95% normal confidence interval.

Chronological evaluation uses development-only predictor standardization with population standard deviation (`ddof=0`). Required fits remain pooled, partition-2 evaluation using partition-1 development statistics, and partition-3 evaluation using partitions 1 and 2 development statistics.

A candidate requires at least 90 candidate-complete pooled anchors and 25 candidate-complete anchors in each chronological partition, finite values, finite development means, strictly positive development population standard deviations, full-rank designs, finite nonzero coefficients, finite strictly positive HC3 standard errors, and a finite pooled p-value.

Benjamini-Hochberg FDR at `q = 0.05` remains separate within three 24-test outcome families. Failed and unrankable candidates remain visible.

## Current authorization

**Decision:** GO to correct the preflight cadence implementation and focused tests to the exact governed 36-gap contract, rerun focused tests, and rerun preflight only.

Authorized now:

- modify `research/ml/validation/simple_btc_price_state_predictive_baselines.py` only to implement the corrected source-gap contract and exact-window unavailability;
- modify `tests/test_simple_btc_price_state_predictive_baselines.py` only to test the corrected source-gap contract and missing-window behavior;
- preserve the runner unless a correction is strictly required by the amended source contract;
- rerun the focused synthetic suite;
- rerun governed preflight only;
- verify preflight reports `status:PASS`, `predictive_outcomes_generated:false`, and the exact 36-gap inventory.

Not authorized:

- canonical outcome generation or result inspection before corrected preflight passes;
- changing predictors, windows, outcomes, horizons, estimators, support rules, multiplicity, or ordering;
- source substitution or source repair;
- Core v1 overlay or economic-value testing;
- Sharpe, CAGR, drawdown, turnover, sizing, timing, allocation, exposure, or portfolio optimization;
- any regime, threshold, classifier, strategy, signal, order, execution, NAV, exposure, dashboard, runtime, or model-training change.

## Authorized implementation surfaces

- `docs/ITERA_CAMPAIGN_BOARD.md` for this corrective governance transition and later closure;
- `research/ml/validation/simple_btc_price_state_predictive_baselines.py`;
- `scripts/run_simple_btc_price_state_predictive_baselines.py` only if strictly required;
- `tests/test_simple_btc_price_state_predictive_baselines.py`;
- `artifacts/simple_btc_price_state_predictive_baselines/**` only after corrected preflight passes and governed generation is separately continued under the existing implementation GO.

## Acceptance gates

1. Campaign #47 closed before Campaign #48. **Passed: `d8f8b23`.**
2. Campaign #48 design transition recorded. **Passed: `58887e0`.**
3. Specification frozen before outcomes. **Passed: `e8777df`.**
4. Implementation handoff frozen before outcomes. **Passed: `a16c152`.**
5. Initial implementation GO recorded. **Passed: `99a7db9`.**
6. Exactly three initial implementation paths created. **Passed.**
7. Focused synthetic suite passed before governed preflight. **Passed: `22 passed in 6.59s`.**
8. Initial preflight generated no predictive outcomes and failed closed on the contradictory cadence rule. **Passed: `SOURCE_CADENCE_FAILURE`; outcomes `false`.**
9. Exact governed gap inventory recorded before outcome generation. **Passed: 36 timestamps.**
10. Corrected implementation and focused tests reconcile to this amendment. **Pending.**
11. Corrected focused suite passes. **Pending.**
12. Corrected preflight passes with no outcomes generated and exact gap reconciliation. **Pending.**
13. Two governed canonical runs replay byte-identically. **Not started.**
14. Governed source bytes remain unchanged. **Must remain true.**
15. Full repository suite passes. **Not started.**
16. No runtime or strategy surface changes. **Must remain true.**

## Immediate sequence

1. Record this corrective source-cadence amendment. **Completed by this board commit.**
2. Correct the module and focused tests. **Authorized next.**
3. Rerun focused tests. **Pending.**
4. Rerun governed preflight only. **Pending.**
5. Inspect corrected preflight evidence before canonical generation. **Pending.**
6. Continue the frozen governed execution sequence only if every preceding gate passes. **Prohibited until then.**

## Campaign #47 completion record

**Campaign:** Campaign #47 - Historical Regime Persistence, Duration, Clustering, and Spacing Discovery

**Final status:** COMPLETE - canonical artifacts published; zero rankable candidates and zero supported research associations

**Working branch:** `agent/campaign-47-regime-structure-implementation`

**Publication commit:** `16692c1`

Completed evidence:

- focused suite: `21 passed`;
- governed preflight before generation: `PASS`;
- predictive outcomes generated during preflight: `false`;
- canonical Campaign #46 source ledger: `70,069` states, `2,790` runs, and `2,789` transitions;
- common 168-hour anchor grid: `403` anchors;
- chronological partitions: `135`, `134`, `134`;
- frozen candidate inventory: `72`;
- pooled OLS-HC3 fits passing estimator requirements: `48`;
- pooled fits failing closed because a one-observation `HIGH_VOL` fixed-effect level produced unit leverage and undefined HC3: `24`;
- partition-2 designs failing the frozen full-rank requirement: `72`;
- partition-3 designs failing the frozen full-rank requirement: `72`;
- rankable candidates: `0`;
- candidates entering Benjamini-Hochberg correction: `0`;
- supported research associations: `0`;
- all failed and unrankable candidates remained visible;
- two governed canonical runs completed successfully;
- all ten canonical outputs were byte-identical and LF-only;
- governed source bytes remained unchanged;
- full repository suite: `504 passed`, `75 warnings`;
- no runtime, threshold, regime, signal, strategy, order, execution, portfolio, NAV, exposure, dashboard, or model-training surface changed.

Campaign #47 conclusion:

Under the frozen development-defined fixed-effect, full-rank, HC3, chronological-evaluation, and fail-closed requirements, none of the 72 prespecified temporal regime-structure candidates was rankable. This was a negative and support-limited result and authorized no Core v1 or runtime change.

## Campaign #45 completion record

**Campaign:** Campaign #45 - Historical Regime State and Transition Discovery

**Final status:** COMPLETE - canonical artifacts published; no supported exact ordered-transition association

**Working branch:** `agent/campaign-45-historical-regime-transitions`

**Publication commit:** `5fa4b8434ed4927e69b8cc973ba0009f99215a24`

**Pull request:** PR #43

**Governed merge commit:** `42e5d7c47d90e1941e61e0e229d4fa71da07b449`

Completed evidence:

- focused suite: `24 passed`;
- governed preflight: `PASS`;
- source transitions: `2,789`;
- eligible non-`UNKNOWN` transitions: `2,788`;
- independent 168-hour-purged anchors: `242`;
- partitions: `81`, `81`, `80`;
- candidate-horizon tests: `51`;
- rankable candidates: `9`;
- insufficient binary-side support: `42`;
- supported associations: `0`;
- two governed runs completed successfully;
- all ten canonical outputs replayed byte-identically;
- governed source bytes remained unchanged;
- full repository suite: `483 passed`, `75 warnings`.

Campaign #45 conclusion:

No exact ordered BTC regime transition met the frozen multiplicity-adjusted and directional-consistency requirements for incremental 24-hour, 72-hour, or 168-hour forward-return association after controlling for the six frozen BTC price-state controls. No runtime or strategy change was authorized.

## Campaign #46 completion record

**Campaign:** Campaign #46 - Full Historical Regime State Sequence

**Final status:** COMPLETE - canonical artifacts published; `CAMPAIGN_45_SOURCE_FEASIBLE`

**Working branch:** `agent/campaign-46-full-regime-state-source`

**Canonical publication commit:** `34a6999`

Completed evidence:

- focused suite: `10 passed`;
- governed preflight: `PASS`;
- two-run replay: all eight files byte-identical;
- state rows: `70,069`;
- total transitions: `2,789`;
- eligible transitions: `2,788`;
- independent purged transitions: `242`;
- partition counts: `81`, `81`, `80`;
- predictive outcomes generated: `false`;
- full repository suite: `459 passed`, `75 warnings`.

Campaign #46 made no predictive, economic, directional, or alpha claim.

## Research-priority context

Campaign #44 ranked S-002 first, S-003 second, and S-008 and S-001 tied next. Campaign #45 completed S-002. Campaign #47 completed S-003. Campaign #48 advances S-008 as the transparent predictive hurdle for later candidates.

## Research progression boundary

Campaign #48 is a discovery campaign. Any supported association must enter a separately frozen confirmation campaign. Only candidates surviving confirmation may enter a later separately authorized incremental-value comparison against untouched Core v1.

## Registered Candidate A-001

Campaign #43 Candidate A-001 remains preliminary and is not revised, promoted, or retested by Campaign #48 unless separately authorized.

## Historical carryover

Campaign #42 validation was previously completed on branch `agent/campaign-42-event-robustness`, PR #42. Its merge state does not expand Campaign #48 authorization.
